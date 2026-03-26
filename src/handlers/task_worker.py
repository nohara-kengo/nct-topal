"""SQSキューからメッセージを受け取り、タスクの作成・更新を行うワーカーハンドラー。"""

import json
import logging

from src.services import backlog_client, intent_classifier, issue_generator, report_generator, ssm_client, teams_notifier, wiki_writer
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
            # エラーを通知して正常消化（リトライで重複通知しない）
            try:
                body = json.loads(record.get("body", "{}"))
                sender_name = body.get("sender_name", "不明")
                notify_ctx = {
                    "platform": body.get("platform", "teams"),
                    "service_url": body.get("service_url"),
                    "conversation": body.get("conversation"),
                    "channel": body.get("channel"),
                    "thread_ts": body.get("thread_ts"),
                }
                _notify(f"⚠ {sender_name}さんのリクエスト処理中にエラーが発生しました。", notify_ctx)
            except Exception:
                logger.exception("エラー通知にも失敗")
            results.append({"status": "error"})

    return {"processed": len(results)}


def _notify(message: str, notify_ctx: dict) -> None:
    """通知のラッパー。platformに応じて通知先を切り替える。"""
    platform = notify_ctx.get("platform", "teams")

    if platform == "slack":
        from src.services import slack_response

        channel = notify_ctx.get("channel")
        if channel:
            slack_response.post_message(channel, message, notify_ctx.get("thread_ts"))
        else:
            logger.warning("Slack通知先情報がないため通知をスキップ: %s", message)
    else:
        service_url = notify_ctx.get("service_url")
        conversation = notify_ctx.get("conversation")
        if service_url and conversation:
            teams_notifier.notify(message, service_url, conversation)
        else:
            logger.warning("Teams通知先情報がないため通知をスキップ: %s", message)


def _process_record(record: dict, context) -> dict:
    """1件のSQSメッセージを処理する。"""
    body = json.loads(record["body"])

    # スケジュール実行（report_schedulerからの直接投入）
    if body.get("scheduled_action") == "report":
        return _handle_scheduled_report(body)

    message = body["message"]
    project_key = body.get("project_key")
    sender_name = body.get("sender_name", "不明")
    platform = body.get("platform", "teams")

    # Slackの場合、sender_nameはユーザーIDなので表示名に解決する
    if platform == "slack" and sender_name.startswith("U"):
        from src.services import slack_user_resolver
        sender_name = slack_user_resolver.resolve_display_name(sender_name)

    notify_ctx = {
        "platform": body.get("platform", "teams"),
        "service_url": body.get("service_url"),
        "conversation": body.get("conversation"),
        "channel": body.get("channel"),
        "thread_ts": body.get("thread_ts"),
    }

    logger.info("タスク処理開始: project=%s, sender=%s", project_key, sender_name)

    # 処理中メッセージを送信
    _notify(f"⏳ {sender_name}さんのリクエストを処理中です…", notify_ctx)

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
    elif intent["action"] == "report":
        return _handle_report(intent, resolved_project_key, sender_name, context, notify_ctx)

    _notify(f"⚠ 不明なアクションです: {intent['action']}", notify_ctx)
    return {"status": "error", "reason": "unknown_action"}


def _handle_create(message: str, intent: dict, project_key: str, sender_name: str, context, notify_ctx: dict) -> dict:
    """新規タスク作成処理。"""
    generated = issue_generator.generate(message, intent)

    # 担当者が未指定の場合、送信者をフォールバックで割り当て
    assignee = intent["assignee"] or sender_name

    create_body = {
        "title": generated["title"],
        "description": generated["description"],
        "issue_type": generated["issue_type"],
        "priority": intent["priority"],
        "estimated_hours": generated["estimated_hours"],
        "assignee": assignee,
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
    space_url = ssm_client.get_backlog_space_url(project_key)
    issue_url = f"{space_url}/view/{issue_key}"
    _notify(
        f"✅ タスクを作成しました\n\n"
        f"課題: <{issue_url}|{issue_key}> {title}\n"
        f"依頼者: {sender_name}\n\n"
        f"処理を完了しました。",
        notify_ctx,
    )
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
    title = result_body.get("title", "")
    space_url = ssm_client.get_backlog_space_url(project_key)
    issue_url = f"{space_url}/view/{issue_key}"
    _notify(
        f"✅ タスクを更新しました\n\n"
        f"課題: <{issue_url}|{issue_key}> {title}\n"
        f"依頼者: {sender_name}\n\n"
        f"処理を完了しました。",
        notify_ctx,
    )
    return {"status": "updated", "issue_key": issue_key}


def _handle_report(intent: dict, project_key: str, sender_name: str, context, notify_ctx: dict) -> dict:
    """日次レポート生成処理。"""
    from datetime import date

    today = date.today().strftime("%Y/%m/%d")

    # 前日Wikiから比較データを取得
    prev_date_path = report_generator.get_prev_business_date_path(today)
    prev_wikis = {}
    try:
        prev_wikis = wiki_writer.fetch_prev_wikis(project_key, prev_date_path)
    except Exception:
        logger.warning("前日Wiki取得に失敗、前日比なしで続行")

    try:
        report = report_generator.generate_daily_report(project_key, today, prev_wikis)
    except Exception:
        logger.exception("レポート生成に失敗")
        _notify(f"⚠ {sender_name}さんのリクエストでレポート生成に失敗しました。", notify_ctx)
        return {"status": "error", "reason": "report_generation_failed"}

    try:
        results = wiki_writer.write_daily_report(project_key, today, report["pages"])
    except Exception:
        logger.exception("Wiki書き込みに失敗")
        _notify(f"⚠ {sender_name}さんのリクエストでWiki書き込みに失敗しました。", notify_ctx)
        return {"status": "error", "reason": "wiki_write_failed"}

    total = report["summary"]["total"]
    page_count = len(results)
    _notify(
        f"✅ {sender_name}さんのリクエストで日次レポートを作成しました。\n"
        f"対象課題: {total}件 / 作成ページ: {page_count}件\n"
        f"Wikiページ: 日次レポート/{today}\n"
        f"処理を完了しました。",
        notify_ctx,
    )
    return {"status": "report_created", "total_issues": total, "pages": page_count}


def _handle_scheduled_report(body: dict) -> dict:
    """スケジュール実行による日次レポート生成。intent分類をスキップして直接実行する。"""
    from datetime import date

    project_key = body["project_key"]
    today = date.today().strftime("%Y/%m/%d")

    logger.info("スケジュールレポート開始: project=%s, date=%s", project_key, today)

    try:
        ssm_client.get_backlog_api_key(project_key)
    except Exception:
        logger.error("プロジェクト %s のAPIキー取得に失敗", project_key)
        return {"status": "error", "reason": "auth_failed", "project_key": project_key}

    prev_date_path = report_generator.get_prev_business_date_path(today)
    prev_wikis = {}
    try:
        prev_wikis = wiki_writer.fetch_prev_wikis(project_key, prev_date_path)
    except Exception:
        logger.warning("前日Wiki取得に失敗、前日比なしで続行: %s", project_key)

    try:
        report = report_generator.generate_daily_report(project_key, today, prev_wikis)
    except Exception:
        logger.exception("スケジュールレポート生成に失敗: %s", project_key)
        raise

    try:
        wiki_writer.write_daily_report(project_key, today, report["pages"])
    except Exception:
        logger.exception("スケジュールレポートWiki書き込みに失敗: %s", project_key)
        raise

    total = report["summary"]["total"]
    page_count = len(report["pages"])
    logger.info("スケジュールレポート完了: project=%s, issues=%d, pages=%d", project_key, total, page_count)
    return {"status": "report_created", "project_key": project_key, "total_issues": total, "pages": page_count}
