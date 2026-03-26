import json
from unittest.mock import patch

from src.handlers.teams_webhook import handler


def _make_event(text: str, valid_jwt: bool = True) -> dict:
    payload = {
        "text": f"<at>ToPal</at> {text}",
        "from": {"name": "テストユーザー"},
        "serviceUrl": "https://smba.trafficmanager.net/jp",
        "conversation": {"id": "19:test@thread.tacv2"},
    }
    body = json.dumps(payload, ensure_ascii=False)

    auth = "Bearer valid-jwt-token" if valid_jwt else "Bearer invalid"

    return {
        "body": body,
        "headers": {"Authorization": auth},
    }


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
@patch("src.services.issue_generator.generate")
@patch("src.handlers.task_create.handler")
def test_webhook_create(mock_task_create, mock_generate, mock_classify, mock_ssm, mock_auth):
    mock_classify.return_value = {
        "action": "create",
        "project_key": "NOHARATEST",
        "task_id": None,
        "title": "新しいタスク",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
        "assignee_id": None,
    }
    mock_generate.return_value = {
        "issue_type": "タスク",
        "title": "新しいタスクを実装する。",
        "description": "# 目的\nテスト",
        "estimated_hours": 4.0,
    }
    mock_task_create.return_value = {
        "statusCode": 201,
        "body": json.dumps({"id": "NOHARATEST-1", "title": "新しいタスクを実装する。", "status": "AI下書き"}),
    }

    event = _make_event("[NOHARATEST] この件、課題にして")
    response = handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "作成しました" in body["text"]


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
@patch("src.handlers.task_update.handler")
def test_webhook_update(mock_task_update, mock_classify, mock_ssm, mock_auth):
    mock_classify.return_value = {
        "action": "update",
        "project_key": "NOHARATEST",
        "task_id": "NOHARATEST-123",
        "title": "優先度変更",
        "priority": "高",
        "estimated_hours": 4.0,
        "assignee": "田中",
        "assignee_id": None,
    }
    mock_task_update.return_value = {
        "statusCode": 200,
        "body": json.dumps({"id": "NOHARATEST-123", "title": "優先度変更", "status": "処理中"}),
    }

    event = _make_event("NOHARATEST-123の優先度上げて")
    response = handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "NOHARATEST-123" in body["text"]
    assert "更新しました" in body["text"]


def test_webhook_invalid_jwt():
    event = _make_event("テスト", valid_jwt=False)
    response = handler(event, None)

    assert response["statusCode"] == 401


def test_webhook_empty_body():
    event = {"body": "", "headers": {"Authorization": "Bearer some-token"}}
    response = handler(event, None)

    assert response["statusCode"] == 401


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
def test_webhook_empty_message(mock_auth):
    payload = {
        "text": "<at>ToPal</at>  ",
        "serviceUrl": "https://smba.trafficmanager.net/jp",
        "conversation": {"id": "19:test@thread.tacv2"},
    }
    body = json.dumps(payload)
    event = {"body": body, "headers": {"Authorization": "Bearer dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "空です" in body["text"]


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
@patch("src.services.intent_classifier.classify")
def test_webhook_no_project_key(mock_classify, mock_auth):
    mock_classify.return_value = {
        "action": "create",
        "project_key": None,
        "task_id": None,
        "title": "何か",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
        "assignee_id": None,
    }

    payload = {
        "text": "<at>ToPal</at> この件、課題にして",
        "serviceUrl": "https://smba.trafficmanager.net/jp",
        "conversation": {"id": "19:test@thread.tacv2"},
    }
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "Bearer dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = json.loads(response["body"])
    assert "紐づくプロジェクトがありません" in resp_body["text"]


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.ssm_client.get_channel_project_key", return_value="NOHARATEST")
@patch("src.services.intent_classifier.classify")
@patch("src.services.issue_generator.generate")
@patch("src.handlers.task_create.handler")
def test_webhook_channel_mapping_fallback(mock_task_create, mock_generate, mock_classify, mock_channel_map, mock_ssm, mock_auth):
    """チャネルマッピングでproject_keyを解決するケース。"""
    mock_classify.return_value = {
        "action": "create",
        "project_key": None,
        "task_id": None,
        "title": "新しいタスク",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
        "assignee_id": None,
    }
    mock_generate.return_value = {
        "issue_type": "タスク",
        "title": "新しいタスクを実装する。",
        "description": "# 目的\nテスト",
        "estimated_hours": 4.0,
    }
    mock_task_create.return_value = {
        "statusCode": 201,
        "body": json.dumps({"id": "NOHARATEST-1", "title": "新しいタスクを実装する。", "status": "AI下書き"}),
    }

    event = _make_event("この件、課題にして")
    response = handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "作成しました" in body["text"]
    mock_channel_map.assert_called_once_with("19:test@thread.tacv2")


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", side_effect=Exception("not found"))
@patch("src.services.intent_classifier.classify")
def test_webhook_unknown_project(mock_classify, mock_ssm, mock_auth):
    mock_classify.return_value = {
        "action": "create",
        "project_key": "UNKNOWN",
        "task_id": None,
        "title": "何か",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
        "assignee_id": None,
    }

    payload = {
        "text": "<at>ToPal</at> [UNKNOWN] タスク作って",
        "serviceUrl": "https://smba.trafficmanager.net/jp",
        "conversation": {"id": "19:test@thread.tacv2"},
    }
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "Bearer dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = json.loads(response["body"])
    assert "登録されていません" in resp_body["text"]


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
def test_webhook_update_without_task_id(mock_classify, mock_ssm, mock_auth):
    mock_classify.return_value = {
        "action": "update",
        "project_key": "NOHARATEST",
        "task_id": None,
        "title": "何か",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
        "assignee_id": None,
    }

    payload = {
        "text": "<at>ToPal</at> [NOHARATEST] さっきの課題を更新して",
        "serviceUrl": "https://smba.trafficmanager.net/jp",
        "conversation": {"id": "19:test@thread.tacv2"},
    }
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "Bearer dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = json.loads(response["body"])
    assert "特定できません" in resp_body["text"]
