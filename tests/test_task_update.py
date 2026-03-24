import json
from unittest.mock import patch

from src.handlers.task_update import handler
from src.services.backlog_setup import BacklogPreset, Schedule


MOCK_PRESET = BacklogPreset(category_ai_generated_id=200, status_ai_draft_id=10)
MOCK_SCHEDULE = Schedule(start_date="2026-03-23", due_date="2026-03-23", estimated_hours=8.0)
MOCK_USERS = [{"id": 501, "userId": "tanaka", "name": "田中太郎"}]
MOCK_ISSUE = {
    "issueKey": "PROJ-123",
    "summary": "更新タスク",
    "status": {"id": 2, "name": "処理中"},
}


@patch("src.handlers.task_update.backlog_setup.ensure_preset", return_value=MOCK_PRESET)
@patch("src.handlers.task_update.backlog_setup.calc_schedule", return_value=MOCK_SCHEDULE)
@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.handlers.task_update.backlog_client.update_issue", return_value=MOCK_ISSUE)
def test_task_update(mock_update, mock_users, mock_schedule, mock_preset):
    event = {
        "pathParameters": {"taskId": "PROJ-123"},
        "body": json.dumps({
            "project_key": "NOHARATEST",
            "priority": "高",
            "estimated_hours": 8,
            "assignee": "田中太郎",
        }),
    }
    response = handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["id"] == "PROJ-123"
    assert body["title"] == "更新タスク"
    mock_update.assert_called_once_with(
        "PROJ-123", "NOHARATEST",
        startDate="2026-03-23",
        dueDate="2026-03-23",
        estimatedHours=8.0,
        priorityId=2,
        assigneeId=501,
        **{"notifiedUserId[]": 501},
    )


def test_task_update_missing_params():
    """必須パラメータが不足している場合はエラー。"""
    event = {
        "pathParameters": {"taskId": "PROJ-123"},
        "body": json.dumps({"project_key": "NOHARATEST"}),
    }
    response = handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "必須" in body["error"]
    assert "priority" in body["error"]
    assert "estimated_hours" in body["error"]
    assert "assignee" in body["error"]
