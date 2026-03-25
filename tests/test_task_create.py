import json
from unittest.mock import patch

from src.handlers.task_create import handler
from src.services.backlog_setup import BacklogPreset, Schedule


MOCK_PRESET = BacklogPreset(category_ai_generated_id=200, status_ai_draft_id=10)
MOCK_SCHEDULE = Schedule(start_date="2026-03-23", due_date="2026-03-23", estimated_hours=8.0)
MOCK_ISSUE_TYPES = [{"id": 100, "name": "タスク"}]
MOCK_USERS = [{"id": 501, "userId": "tanaka", "name": "田中太郎"}]
MOCK_ISSUE = {
    "issueKey": "NOHARATEST-1",
    "summary": "テストタスク",
    "status": {"id": 10, "name": "AI下書き"},
}


@patch("src.handlers.task_create.backlog_setup.ensure_preset", return_value=MOCK_PRESET)
@patch("src.handlers.task_create.backlog_setup.calc_schedule", return_value=MOCK_SCHEDULE)
@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.handlers.task_create.backlog_client.get_issue_types", return_value=MOCK_ISSUE_TYPES)
@patch("src.handlers.task_create.backlog_client.create_issue", return_value=MOCK_ISSUE)
def test_task_create(mock_create, mock_types, mock_users, mock_schedule, mock_preset):
    event = {"body": json.dumps({
        "title": "テストタスク",
        "project_key": "NOHARATEST",
        "description": "テスト概要",
        "issue_type": "タスク",
        "priority": "中",
        "estimated_hours": 8,
        "assignee": "田中太郎",
    })}
    response = handler(event, None)
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["title"] == "テストタスク"
    assert body["status"] == "AI下書き"
    assert body["id"] == "NOHARATEST-1"
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["category_ids"] == [200]
    assert call_kwargs["status_id"] == 10
    assert call_kwargs["start_date"] == "2026-03-23"
    assert call_kwargs["due_date"] == "2026-03-23"
    assert call_kwargs["estimated_hours"] == 8.0
    assert call_kwargs["assignee_id"] == 501
    assert call_kwargs["description"] == "テスト概要"


@patch("src.handlers.task_create.backlog_setup.ensure_preset", return_value=MOCK_PRESET)
@patch("src.handlers.task_create.backlog_setup.calc_schedule")
@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=[])
@patch("src.handlers.task_create.backlog_client.get_issue_types", return_value=MOCK_ISSUE_TYPES)
@patch("src.handlers.task_create.backlog_client.create_issue", return_value=MOCK_ISSUE)
def test_task_create_custom_hours(mock_create, mock_types, mock_users, mock_schedule, mock_preset):
    """estimated_hoursを指定した場合、calc_scheduleに渡される。"""
    mock_schedule.return_value = Schedule(
        start_date="2026-03-23", due_date="2026-03-24", estimated_hours=16.0,
    )
    event = {"body": json.dumps({
        "title": "大きめタスク", "project_key": "NOHARATEST", "estimated_hours": 16,
        "description": "テスト", "issue_type": "タスク", "priority": "中", "assignee": "田中太郎",
    })}
    response = handler(event, None)
    assert response["statusCode"] == 201
    mock_schedule.assert_called_once_with(16)


def test_task_create_empty_body():
    event = {"body": "{}"}
    response = handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "必須" in body["error"]


def test_task_create_missing_partial():
    """一部パラメータが欠けている場合もエラー。"""
    event = {"body": json.dumps({"project_key": "NOHARATEST", "title": "テスト"})}
    response = handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "description" in body["error"]
    assert "issue_type" in body["error"]
    assert "estimated_hours" in body["error"]
    # assigneeは任意パラメータ
