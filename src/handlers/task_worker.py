"""SQSキューからメッセージを受け取り、タスクの作成・更新を行うワーカーハンドラー。"""

import json
import logging

from src.services import backlog_client, intent_classifier, issue_generator, ssm_client, teams_notifier
from src.services.log_config import setup_logging
from src.handlers import task_create, task_update

setup_logging()
logger = logging.getLogger(__name__)


def handler(event, context):
    """SQSイベントソースから呼び出されるワーカー。

    API: SQS → Lambda（イベントソースマッピング）

    teams_webhookが即時応答後、SQSに投入したメッセージを処理する。
    処理結果はBot Frameworkプロアクティブメッセージで通知する。

    Args:
        event: SQSイベント（Records配列）
        context: Lambda コンテキスト

    Returns:
        処理結果のサマリー
    """
    results = []

    for record in event.get("Records", []):
        try:
            result = _process_record(record, context)
            results.append(result)
        except Exception:
            logger.exception("レコード処理に失敗: messageId=%s", record.get("messageId"))
            # DLQに移動させるため例外を再送出
            raise

    return {"processed": len(results)}


def _notify(message: str, notify_ctx: dict) -> None:
    """通知のラッパー。通知先情報がない場合はログのみ。"""
    service_url = notify_ctx.get("service_url")
    conversation = notify_ctx.get("conversation")
    if service_url and conversation:
        teams_notifier.notify(message, service_url, conversation)
    else:
        logger.warning("通知先情報がないため通知をスキップ: %s", message)


def _process_record(record: dict, context) -> dict:
    """1件のSQSメッセージを処理する。"""
    body = json.loads(record["body"])
    message = body["message"]
    project_key = body.get("project_key")
    sender_name = body.get("sender_name", "不明")
    notify_ctx = {
        "service_url": body.get("service_url"),
        "conversation": body.get("conversation"),
    }

    logger.info("タスク処理開始: project=%s, sender=%s", project_key, sender_name)

    # メッセージからproject_keyを事前抽出してメンバー一覧を取得
    pre_project_key = project_key or intent_classifier.extract_project_key(message)
    members = None
    if pre_project_key:
        try:
            ssm_client.get_backlog_api_key(pre_project_key)
            members = backlog_client.get_project_users(pre_project_key)
        except Exception:
            logger.info("メンバー一覧の事前取得をスキップ: %s", pre_project_key)

    # Claude APIで意図判定（メンバー一覧があれば担当者IDも解決）
    intent = intent_classifier.classify(message, members=members)

    # intent_classifierがproject_keyを返さなかった場合、SQSメッセージのproject_keyを使う
    if not intent.get("project_key") and project_key:
        intent["project_key"] = project_key

    resolved_project_key = intent["project_key"]
    if not resolved_project_key:
        _notify(f"⚠ {sender_name}さんのメッセージからプロジェクトキーを特定できませんでした。\n例: [NOHARATEST] タスクの内容", notify_ctx)
        return {"status": "error", "reason": "no_project_key"}

    # SSMからプロジェクト設定を取得（存在チェック）
    try:
        ssm_client.get_backlog_api_key(resolved_project_key)
    except Exception:
        _notify(f"⚠ プロジェクト {resolved_project_key} は登録されていません。", notify_ctx)
        return {"status": "error", "reason": "unknown_project"}

    if intent["action"] == "create":
        return _handle_create(message, intent, resolved_project_key, sender_name, context, notify_ctx)
    elif intent["action"] == "update":
        return _handle_update(intent, resolved_project_key, sender_name, context, notify_ctx)

    _notify(f"⚠ 不明なアクションです: {intent['action']}", notify_ctx)
    return {"status": "error", "reason": "unknown_action"}


def _handle_create(message: str, intent: dict, project_key: str, sender_name: str, context, notify_ctx: dict) -> dict:
    """新規タスク作成処理。"""
    generated = issue_generator.generate(message, intent)

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
        error_msg = result_body.get("error", "不明なエラー")
        logger.error("タスク作成に失敗: %s", error_msg)
        _notify(f"⚠ {sender_name}さんのリクエストでタスク作成に失敗しました: {error_msg}", notify_ctx)
        return {"status": "error", "reason": error_msg}

    title = result_body.get("title", "")
    issue_key = result_body.get("id", "")
    _notify(f"✅ {sender_name}さんのリクエストでタスクを作成しました: {issue_key} {title}", notify_ctx)
    return {"status": "created", "issue_key": issue_key}


def _handle_update(intent: dict, project_key: str, sender_name: str, context, notify_ctx: dict) -> dict:
    """既存タスク更新処理。"""
    if not intent.get("task_id"):
        _notify(f"⚠ {sender_name}さんのリクエストで更新対象の課題キーが特定できませんでした。", notify_ctx)
        return {"status": "error", "reason": "no_task_id"}

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
        error_msg = result_body.get("error", "不明なエラー")
        logger.error("タスク更新に失敗: %s", error_msg)
        _notify(f"⚠ {sender_name}さんのリクエストでタスク更新に失敗しました: {error_msg}", notify_ctx)
        return {"status": "error", "reason": error_msg}

    issue_key = result_body.get("id", "")
    _notify(f"✅ {sender_name}さんのリクエストでタスク {issue_key} を更新しました。", notify_ctx)
    return {"status": "updated", "issue_key": issue_key}
