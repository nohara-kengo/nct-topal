"""Teamsメンションからタスクを新規作成するハンドラー。"""

import json
import logging

from src.services import backlog_client, backlog_setup

logger = logging.getLogger(__name__)

PRIORITY_MAP = {"高": 2, "中": 3, "低": 4}


def _resolve_assignee_id(project_key: str, assignee_name: str | None) -> int | None:
    if not assignee_name:
        return None
    users = backlog_client.get_project_users(project_key)
    for user in users:
        if assignee_name in (user.get("name", ""), user.get("userId", "")):
            return user["id"]
    logger.warning("担当者 '%s' が見つかりません", assignee_name)
    return None


def handler(event, context):
    """タスク新規作成エンドポイント。

    API: POST /tasks

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        statusCode 201 と作成されたタスク情報を返す
    """
    body = json.loads(event.get("body") or "{}")

    project_key = body.get("project_key", "")
    title = body.get("title", "")
    description = body.get("description", "")
    issue_type_name = body.get("issue_type", "")
    priority = body.get("priority", "中")
    estimated_hours = body.get("estimated_hours")
    assignee = body.get("assignee")

    missing = [f for f in ("project_key", "title", "description", "issue_type", "priority", "estimated_hours", "assignee")
               if not body.get(f)]
    if missing:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"必須パラメータが不足しています: {missing}"}, ensure_ascii=False),
        }

    preset = backlog_setup.ensure_preset(project_key)
    schedule = backlog_setup.calc_schedule(estimated_hours)
    assignee_id = _resolve_assignee_id(project_key, assignee)

    issue_types = backlog_client.get_issue_types(project_key)
    if not issue_types:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "種別が取得できませんでした"}, ensure_ascii=False),
        }

    # 種別名からIDを解決（見つからなければ先頭の種別をフォールバック）
    type_map = {t["name"]: t["id"] for t in issue_types}
    issue_type_id = type_map.get(issue_type_name, issue_types[0]["id"])

    issue = backlog_client.create_issue(
        project_key=project_key,
        summary=title,
        description=description,
        issue_type_id=issue_type_id,
        priority_id=PRIORITY_MAP.get(priority, 3),
        status_id=preset.status_ai_draft_id,
        category_ids=[preset.category_ai_generated_id],
        start_date=schedule.start_date,
        due_date=schedule.due_date,
        estimated_hours=schedule.estimated_hours,
        assignee_id=assignee_id,
    )

    logger.info("課題を作成しました: %s", issue["issueKey"])

    return {
        "statusCode": 201,
        "body": json.dumps({
            "id": issue["issueKey"],
            "title": issue["summary"],
            "status": issue["status"]["name"],
        }, ensure_ascii=False),
    }
