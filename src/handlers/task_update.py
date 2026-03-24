"""Teamsメンションからタスクを編集するハンドラー。"""

import json
import logging

import requests

from src.services import backlog_client, backlog_setup
from src.services.assignee_resolver import resolve_assignee_id

logger = logging.getLogger(__name__)

PRIORITY_MAP = {"高": 2, "中": 3, "低": 4}


def handler(event, context):
    """タスク編集エンドポイント。

    API: PUT /tasks/{taskId}

    Args:
        event: API Gateway イベント
        context: Lambda コンテキスト

    Returns:
        statusCode 200 と更新されたタスク情報を返す
    """
    task_id = event.get("pathParameters", {}).get("taskId", "")
    body = json.loads(event.get("body") or "{}")

    project_key = body.get("project_key", "")
    missing = [f for f in ("project_key", "priority", "estimated_hours", "assignee")
               if not body.get(f)]
    if missing:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"必須パラメータが不足しています: {missing}"}, ensure_ascii=False),
        }

    # カテゴリ・ステータスを確保（まだ無ければ作成）
    try:
        backlog_setup.ensure_preset(project_key)
    except Exception:
        logger.exception("プロジェクト初期設定に失敗: %s", project_key)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "プロジェクト初期設定に失敗しました"}, ensure_ascii=False),
        }

    estimated_hours = body.get("estimated_hours")
    schedule = backlog_setup.calc_schedule(estimated_hours)
    assignee = body.get("assignee")
    assignee_id = resolve_assignee_id(project_key, assignee)

    fields = {
        "startDate": schedule.start_date,
        "dueDate": schedule.due_date,
        "estimatedHours": schedule.estimated_hours,
    }
    priority = body.get("priority")
    if priority:
        fields["priorityId"] = PRIORITY_MAP.get(priority, 3)
    if assignee_id is not None:
        fields["assigneeId"] = assignee_id

    try:
        issue = backlog_client.update_issue(task_id, project_key, **fields)
    except requests.RequestException:
        logger.exception("Backlog課題の更新に失敗: %s", task_id)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Backlog課題 {task_id} の更新に失敗しました"}, ensure_ascii=False),
        }

    logger.info("課題を更新しました: %s", issue["issueKey"])

    return {
        "statusCode": 200,
        "body": json.dumps({
            "id": issue["issueKey"],
            "title": issue["summary"],
            "status": issue["status"]["name"],
        }, ensure_ascii=False),
    }
