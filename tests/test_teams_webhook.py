import base64
import hashlib
import hmac
import json
from unittest.mock import patch

from src.handlers.teams_webhook import handler


SECRET = base64.b64encode(b"test-secret-key").decode("utf-8")


def _make_event(text: str, valid_hmac: bool = True) -> dict:
    payload = {"text": f"<at>ToPal</at> {text}"}
    body = json.dumps(payload, ensure_ascii=False)

    if valid_hmac:
        secret_bytes = base64.b64decode(SECRET)
        digest = hmac.new(secret_bytes, body.encode("utf-8"), hashlib.sha256).digest()
        auth = "HMAC " + base64.b64encode(digest).decode("utf-8")
    else:
        auth = "HMAC invalid"

    return {
        "body": body,
        "headers": {"Authorization": auth},
    }


@patch("src.handlers.teams_webhook.hmac_validator.validate", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
@patch("src.services.issue_generator.generate")
@patch("src.handlers.task_create.handler")
def test_webhook_create(mock_task_create, mock_generate, mock_classify, mock_ssm, mock_hmac):
    mock_classify.return_value = {
        "action": "create",
        "project_key": "NOHARATEST",
        "task_id": None,
        "title": "新しいタスク",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
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


@patch("src.handlers.teams_webhook.hmac_validator.validate", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
@patch("src.handlers.task_update.handler")
def test_webhook_update(mock_task_update, mock_classify, mock_ssm, mock_hmac):
    mock_classify.return_value = {
        "action": "update",
        "project_key": "NOHARATEST",
        "task_id": "NOHARATEST-123",
        "title": "優先度変更",
        "priority": "高",
        "estimated_hours": 4.0,
        "assignee": "田中",
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


def test_webhook_invalid_hmac():
    event = _make_event("テスト", valid_hmac=False)
    with patch("src.services.hmac_validator.get_secret", return_value=SECRET):
        response = handler(event, None)

    assert response["statusCode"] == 401


def test_webhook_empty_body():
    event = {"body": "", "headers": {"Authorization": "HMAC abc"}}
    with patch("src.services.hmac_validator.get_secret", return_value=SECRET):
        response = handler(event, None)

    assert response["statusCode"] == 401


@patch("src.handlers.teams_webhook.hmac_validator.validate", return_value=True)
def test_webhook_empty_message(mock_hmac):
    payload = {"text": "<at>ToPal</at>  "}
    body = json.dumps(payload)
    event = {"body": body, "headers": {"Authorization": "HMAC dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "空です" in body["text"]


@patch("src.handlers.teams_webhook.hmac_validator.validate", return_value=True)
@patch("src.services.intent_classifier.classify")
def test_webhook_no_project_key(mock_classify, mock_hmac):
    mock_classify.return_value = {
        "action": "create",
        "project_key": None,
        "task_id": None,
        "title": "何か",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
    }

    payload = {"text": "<at>ToPal</at> この件、課題にして"}
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "HMAC dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = json.loads(response["body"])
    assert "プロジェクトキーを指定" in resp_body["text"]


@patch("src.handlers.teams_webhook.hmac_validator.validate", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", side_effect=Exception("not found"))
@patch("src.services.intent_classifier.classify")
def test_webhook_unknown_project(mock_classify, mock_ssm, mock_hmac):
    mock_classify.return_value = {
        "action": "create",
        "project_key": "UNKNOWN",
        "task_id": None,
        "title": "何か",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
    }

    payload = {"text": "<at>ToPal</at> [UNKNOWN] タスク作って"}
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "HMAC dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = json.loads(response["body"])
    assert "登録されていません" in resp_body["text"]


@patch("src.handlers.teams_webhook.hmac_validator.validate", return_value=True)
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
def test_webhook_update_without_task_id(mock_classify, mock_ssm, mock_hmac):
    mock_classify.return_value = {
        "action": "update",
        "project_key": "NOHARATEST",
        "task_id": None,
        "title": "何か",
        "priority": "中",
        "estimated_hours": 4.0,
        "assignee": "田中",
    }

    payload = {"text": "<at>ToPal</at> [NOHARATEST] さっきの課題を更新して"}
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "HMAC dummy"}}

    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = json.loads(response["body"])
    assert "特定できません" in resp_body["text"]
