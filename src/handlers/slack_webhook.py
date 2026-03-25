"""Slack Event APIからのメッセージを受信してSQSにメッセージを投入するハンドラー。"""

import base64
import json
import logging
import os

import boto3

from src.services import slack_auth, slack_message_parser, slack_response
from src.services.log_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

_SQS_QUEUE_URL = os.environ.get("TASK_QUEUE_URL")


def _get_sqs_client():
    kwargs = {"region_name": os.environ.get("AWS_REGION", "ap-northeast-1")}
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("sqs", **kwargs)


def _json_response(body: dict, status_code: int = 200) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event, context):
    """Slack Event API受信エンドポイント。

    API: POST /webhook/slack

    署名を検証し、app_mentionイベントをSQSキューに投入して即時応答する。
    TASK_QUEUE_URLが未設定の場合は同期処理にフォールバックする。

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        API Gateway形式のレスポンス
    """
    headers = event.get("headers", {})
    raw_body = event.get("body", "")

    # API GatewayがBase64エンコードしている場合の対応
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    # 署名検証
    if not slack_auth.validate_request(headers, raw_body):
        logger.warning("Slack署名検証に失敗")
        return _json_response({"error": "認証に失敗しました。"}, 401)

    # ペイロード解析
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        logger.warning("不正なリクエストボディ")
        return _json_response({"error": "リクエストの形式が不正です。"}, 400)

    # Slack URL検証チャレンジ
    if payload.get("type") == "url_verification":
        return _json_response({"challenge": payload.get("challenge", "")})

    # app_mentionイベント以外は無視
    event_data = payload.get("event", {})
    if event_data.get("type") != "app_mention":
        return _json_response({"ok": True})

    # botメッセージはループ防止で無視
    if event_data.get("bot_id"):
        return _json_response({"ok": True})

    # テキスト抽出
    message = slack_message_parser.extract_text(payload)
    if not message:
        return _json_response({"ok": True})

    channel = event_data.get("channel", "")
    thread_ts = event_data.get("thread_ts") or event_data.get("ts", "")
    sender_user = event_data.get("user", "不明")

    # SQSが設定されていれば非同期処理
    if _SQS_QUEUE_URL:
        return _enqueue_and_respond(message, sender_user, channel, thread_ts)

    # フォールバック: 同期処理（開発・テスト用）
    return _process_sync(message, channel, thread_ts, context)


def _enqueue_and_respond(message: str, sender_name: str, channel: str, thread_ts: str) -> dict:
    """SQSにメッセージを投入して即時応答する。"""
    sqs = _get_sqs_client()

    sqs_message = {
        "message": message,
        "sender_name": sender_name,
        "platform": "slack",
        "channel": channel,
        "thread_ts": thread_ts,
    }

    try:
        sqs.send_message(
            QueueUrl=_SQS_QUEUE_URL,
            MessageBody=json.dumps(sqs_message, ensure_ascii=False),
        )
        logger.info("SQSにメッセージを投入: sender=%s, channel=%s", sender_name, channel)
    except Exception:
        logger.exception("SQSへの送信に失敗")
        return _json_response({"error": "処理の受付に失敗しました。"}, 500)

    return _json_response({"ok": True})


def _process_sync(message: str, channel: str, thread_ts: str, context) -> dict:
    """同期処理フォールバック（開発・テスト用、TASK_QUEUE_URL未設定時）。"""
    # 遅延importで循環参照を回避
    from src.services import backlog_client, intent_classifier, issue_generator, ssm_client
    from src.handlers import task_create, task_update

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
        slack_response.post_message(channel, "メッセージの解析に失敗しました。", thread_ts)
        return _json_response({"ok": True})

    project_key = intent["project_key"]
    if not project_key:
        slack_response.post_message(
            channel, "プロジェクトキーを指定してください。例: [NOHARATEST] タスクの内容", thread_ts
        )
        return _json_response({"ok": True})

    try:
        ssm_client.get_backlog_api_key(project_key)
    except Exception:
        slack_response.post_message(channel, f"プロジェクト {project_key} は登録されていません。", thread_ts)
        return _json_response({"ok": True})

    if intent["action"] == "create":
        try:
            generated = issue_generator.generate(message, intent)
        except Exception:
            logger.exception("課題情報の生成に失敗")
            slack_response.post_message(channel, "課題情報の生成に失敗しました。", thread_ts)
            return _json_response({"ok": True})

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
            slack_response.post_message(
                channel,
                f"タスクの作成に失敗しました: {result_body.get('error', '不明なエラー')}",
                thread_ts,
            )
        else:
            slack_response.post_message(
                channel,
                f"タスクを作成しました: {result_body.get('title', '')}",
                thread_ts,
            )
        return _json_response({"ok": True})

    elif intent["action"] == "update":
        if not intent["task_id"]:
            slack_response.post_message(channel, "更新対象の課題キーが特定できませんでした。", thread_ts)
            return _json_response({"ok": True})

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
            slack_response.post_message(
                channel,
                f"タスクの更新に失敗しました: {result_body.get('error', '不明なエラー')}",
                thread_ts,
            )
        else:
            slack_response.post_message(
                channel,
                f"タスク {result_body.get('id', '')} を更新しました。",
                thread_ts,
            )
        return _json_response({"ok": True})

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
            slack_response.post_message(channel, "レポートの生成に失敗しました。", thread_ts)
            return _json_response({"ok": True})

        total = report["summary"]["total"]
        slack_response.post_message(
            channel,
            f"日次レポートを作成しました。\n対象課題: {total}件\nWikiページ: 日次レポート/{today}",
            thread_ts,
        )
        return _json_response({"ok": True})

    slack_response.post_message(channel, "不明なアクションです。", thread_ts)
    return _json_response({"ok": True})
