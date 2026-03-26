"""Bot Framework からのメッセージを受信してSQSにメッセージを投入するハンドラー。

JWTトークンを検証し、メッセージ解析のみ行い、
重い処理（Claude API + Backlog API）はtask_workerに委譲する。
"""

import json
import logging
import os

import boto3

from src.services import bot_auth, message_parser, teams_response
from src.services.log_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

# SQSキューURL（環境変数から取得、未設定時は同期処理にフォールバック）
_SQS_QUEUE_URL = os.environ.get("TASK_QUEUE_URL")


def _get_sqs_client():
    kwargs = {"region_name": os.environ.get("AWS_REGION", "ap-northeast-1")}
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("sqs", **kwargs)


def handler(event, context):
    """Bot Framework メッセージ受信エンドポイント。

    API: POST /webhook/teams

    JWTトークンを検証し、メッセージをSQSキューに投入して即時応答する。
    TASK_QUEUE_URLが未設定の場合は従来の同期処理にフォールバックする。

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        Bot Framework Activity形式のレスポンス
    """
    # JWT トークン検証
    body = event.get("body", "")
    headers = event.get("headers", {})
    authorization = headers.get("Authorization") or headers.get("authorization", "")

    if not bot_auth.validate_token(authorization):
        logger.warning("JWTトークン検証に失敗")
        return teams_response.error("認証に失敗しました。", status_code=401)

    # ペイロード解析
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        logger.warning("不正なリクエストボディ")
        return teams_response.error("リクエストの形式が不正です。")

    # メンションタグ除去・テキスト抽出
    message = message_parser.extract_text(payload)
    if not message:
        return teams_response.error("メッセージが空です。")

    sender_name = payload.get("from", {}).get("name", "不明")
    service_url = payload.get("serviceUrl", "")
    conversation = payload.get("conversation", {})

    # SQSが設定されていれば非同期処理
    if _SQS_QUEUE_URL:
        return _enqueue_and_respond(message, sender_name, service_url, conversation)

    # フォールバック: 同期処理（開発・テスト用）
    return _process_sync(message, event, context, service_url, conversation)


def _enqueue_and_respond(message: str, sender_name: str, service_url: str, conversation: dict) -> dict:
    """SQSにメッセージを投入して即時応答する。"""
    sqs = _get_sqs_client()

    sqs_message = {
        "message": message,
        "sender_name": sender_name,
        "service_url": service_url,
        "conversation": conversation,
    }

    try:
        sqs.send_message(
            QueueUrl=_SQS_QUEUE_URL,
            MessageBody=json.dumps(sqs_message, ensure_ascii=False),
        )
        logger.info("SQSにメッセージを投入: sender=%s", sender_name)
    except Exception:
        logger.exception("SQSへの送信に失敗")
        return teams_response.error("処理の受付に失敗しました。")

    return teams_response.accepted()


def _process_sync(message: str, event: dict, context, service_url: str, conversation: dict) -> dict:
    """同期処理フォールバック（開発・テスト用、TASK_QUEUE_URL未設定時）。"""
    # 遅延importで循環参照を回避
    from src.services import backlog_client, intent_classifier, issue_generator, ssm_client
    from src.handlers import task_create, task_update

    # メッセージからproject_keyを事前抽出してメンバー一覧を取得
    pre_project_key = intent_classifier.extract_project_key(message)
    members = None
    if pre_project_key:
        try:
            ssm_client.get_backlog_api_key(pre_project_key)
            members = backlog_client.get_project_users(pre_project_key)
        except Exception:
            logger.info("メンバー一覧の事前取得をスキップ: %s", pre_project_key)

    try:
        intent = intent_classifier.classify(message, members=members)
    except Exception:
        logger.exception("意図判定に失敗")
        return teams_response.error("メッセージの解析に失敗しました。")

    project_key = intent["project_key"]

    # チャネルマッピングでフォールバック
    if not project_key:
        conversation_id = (conversation or {}).get("id")
        if conversation_id:
            project_key = ssm_client.get_channel_project_key(conversation_id)
            if project_key:
                intent["project_key"] = project_key

    if not project_key:
        return teams_response.error("プロジェクトキーを指定してください。例: [NOHARATEST] タスクの内容")

    try:
        ssm_client.get_backlog_api_key(project_key)
    except Exception:
        return teams_response.error(f"プロジェクト {project_key} は登録されていません。")

    if intent["action"] == "create":
        try:
            generated = issue_generator.generate(message, intent)
        except Exception:
            logger.exception("課題情報の生成に失敗")
            return teams_response.error("課題情報の生成に失敗しました。")

        create_body = {
            "title": generated["title"],
            "description": generated["description"],
            "issue_type": generated["issue_type"],
            "priority": intent["priority"],
            "estimated_hours": generated["estimated_hours"],
            "assignee": intent["assignee"],
            "project_key": project_key,
        }
        if intent.get("assignee_id"):
            create_body["assignee_id"] = intent["assignee_id"]
        create_event = {"body": json.dumps(create_body, ensure_ascii=False)}
        result = task_create.handler(create_event, context)
        result_body = json.loads(result["body"])

        if result["statusCode"] >= 400:
            logger.error("タスク作成に失敗: %s", result_body.get("error", ""))
            return teams_response.error(f"タスクの作成に失敗しました: {result_body.get('error', '不明なエラー')}")

        return teams_response.success(
            f"タスクを作成しました: {result_body.get('title', '')}"
        )

    elif intent["action"] == "update":
        if not intent["task_id"]:
            return teams_response.error("更新対象の課題キーが特定できませんでした。")

        update_body = {
            "title": intent["title"],
            "priority": intent["priority"],
            "estimated_hours": intent.get("estimated_hours"),
            "assignee": intent.get("assignee"),
            "project_key": project_key,
        }
        if intent.get("assignee_id"):
            update_body["assignee_id"] = intent["assignee_id"]
        update_event = {
            "pathParameters": {"taskId": intent["task_id"]},
            "body": json.dumps(update_body, ensure_ascii=False),
        }
        result = task_update.handler(update_event, context)
        result_body = json.loads(result["body"])

        if result["statusCode"] >= 400:
            logger.error("タスク更新に失敗: %s", result_body.get("error", ""))
            return teams_response.error(f"タスクの更新に失敗しました: {result_body.get('error', '不明なエラー')}")

        return teams_response.success(
            f"タスク {result_body.get('id', '')} を更新しました。"
        )

    elif intent["action"] == "report":
        from datetime import date
        from src.services import report_generator, wiki_writer

        today = date.today().strftime("%Y/%m/%d")
        prev_date_path = report_generator.get_prev_business_date_path(today)
        prev_wikis = {}
        try:
            prev_wikis = wiki_writer.fetch_prev_wikis(project_key, prev_date_path)
        except Exception:
            logger.warning("前日Wiki取得に失敗、前日比なしで続行")

        try:
            report = report_generator.generate_daily_report(project_key, today, prev_wikis)
            wiki_writer.write_daily_report(project_key, today, report["pages"])
        except Exception:
            logger.exception("レポート生成に失敗")
            return teams_response.error("レポートの生成に失敗しました。")

        total = report["summary"]["total"]
        return teams_response.success(
            f"日次レポートを作成しました。\n対象課題: {total}件\nWikiページ: 日次レポート/{today}"
        )

    return teams_response.error("不明なアクションです。")
