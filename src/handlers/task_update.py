"""Teamsメンションからタスクを編集するハンドラー。"""

import json
import logging

from src.services import backlog_client, backlog_setup

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
    if not project_key or not task_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "project_key と taskId は必須です"}, ensure_ascii=False),
        }

    # カテゴリ・ステータスを確保（まだ無ければ作成）
    backlog_setup.ensure_preset(project_key)

    estimated_hours = body.get("estimated_hours")
    schedule = backlog_setup.calc_schedule(estimated_hours)

    fields = {
        "startDate": schedule.start_date,
        "dueDate": schedule.due_date,
        "estimatedHours": schedule.estimated_hours,
    }
    priority = body.get("priority")
    if priority:
        fields["priorityId"] = PRIORITY_MAP.get(priority, 3)

    issue = backlog_client.update_issue(task_id, project_key, **fields)

    logger.info("課題を更新しました: %s", issue["issueKey"])

    return {
        "statusCode": 200,
        "body": json.dumps({
            "id": issue["issueKey"],
            "title": issue["summary"],
            "status": issue["status"]["name"],
        }, ensure_ascii=False),
    }
