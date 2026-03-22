"""Teamsメンションからタスクを新規作成するハンドラー。"""

import json
import logging

from src.services import backlog_client, backlog_setup

logger = logging.getLogger(__name__)

PRIORITY_MAP = {"高": 2, "中": 3, "低": 4}


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
    priority = body.get("priority", "中")
    estimated_hours = body.get("estimated_hours")

    if not project_key or not title:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "project_key と title は必須です"}, ensure_ascii=False),
        }

    preset = backlog_setup.ensure_preset(project_key)
    schedule = backlog_setup.calc_schedule(estimated_hours)

    issue_types = backlog_client.get_issue_types(project_key)
    if not issue_types:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "種別が取得できませんでした"}, ensure_ascii=False),
        }

    issue = backlog_client.create_issue(
        project_key=project_key,
        summary=title,
        issue_type_id=issue_types[0]["id"],
        priority_id=PRIORITY_MAP.get(priority, 3),
        status_id=preset.status_ai_draft_id,
        category_ids=[preset.category_ai_generated_id],
        start_date=schedule.start_date,
        due_date=schedule.due_date,
        estimated_hours=schedule.estimated_hours,
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
