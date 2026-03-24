"""Teams Outgoing Webhookを受信してタスク起票・更新を行うハンドラー。"""

import json
import logging

from src.services import hmac_validator, message_parser, intent_classifier, issue_generator, teams_response, ssm_client
from src.handlers import task_create, task_update

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Teams Outgoing Webhookエンドポイント。

    API: POST /webhook/teams

    HMAC署名を検証し、メッセージの意図とプロジェクトキーをClaude APIで判定した後、
    SSMからプロジェクト設定を取得してタスクの新規作成または更新に振り分ける。

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        Teams形式のレスポンス（type: message）
    """
    # HMAC署名検証
    body = event.get("body", "")
    headers = event.get("headers", {})
    authorization = headers.get("Authorization") or headers.get("authorization", "")

    if not hmac_validator.validate(body, authorization):
        logger.warning("HMAC署名検証に失敗")
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

    # Claude APIで意図判定（プロジェクトキーも抽出）
    try:
        intent = intent_classifier.classify(message)
    except Exception:
        logger.exception("意図判定に失敗")
        return teams_response.error("メッセージの解析に失敗しました。")

    project_key = intent["project_key"]
    if not project_key:
        return teams_response.error("プロジェクトキーを指定してください。例: [NOHARATEST] タスクの内容")

    # SSMからプロジェクト設定を取得（存在しなければ未登録）
    try:
        ssm_client.get_backlog_api_key(project_key)
    except Exception:
        return teams_response.error(f"プロジェクト {project_key} は登録されていません。")

    # 振り分け
    if intent["action"] == "create":
        # 2回目のClaude呼び出し: 種別・題名・説明・予定時間を生成
        try:
            generated = issue_generator.generate(message, intent)
        except Exception:
            logger.exception("課題情報の生成に失敗")
            return teams_response.error("課題情報の生成に失敗しました。")

        create_event = {
            "body": json.dumps({
                "title": generated["title"],
                "description": generated["description"],
                "issue_type": generated["issue_type"],
                "priority": intent["priority"],
                "estimated_hours": generated["estimated_hours"],
                "assignee": intent["assignee"],
                "project_key": project_key,
            }, ensure_ascii=False),
        }
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

        update_event = {
            "pathParameters": {"taskId": intent["task_id"]},
            "body": json.dumps({
                "title": intent["title"],
                "priority": intent["priority"],
                "estimated_hours": intent.get("estimated_hours"),
                "assignee": intent.get("assignee"),
                "project_key": project_key,
            }, ensure_ascii=False),
        }
        result = task_update.handler(update_event, context)
        result_body = json.loads(result["body"])

        if result["statusCode"] >= 400:
            logger.error("タスク更新に失敗: %s", result_body.get("error", ""))
            return teams_response.error(f"タスクの更新に失敗しました: {result_body.get('error', '不明なエラー')}")

        return teams_response.success(
            f"タスク {result_body.get('id', '')} を更新しました。"
        )

    return teams_response.error("不明なアクションです。")
