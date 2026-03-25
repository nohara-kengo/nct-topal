import hashlib
import hmac
import json
import time
from unittest.mock import patch, MagicMock

from src.handlers.slack_webhook import handler

SIGNING_SECRET = "test-signing-secret"


def _make_event(text: str, valid_signature: bool = True, event_type: str = "app_mention") -> dict:
    payload = {
        "type": "event_callback",
        "event": {
            "type": event_type,
            "text": f"<@UBOTID> {text}",
            "user": "U_USER",
            "channel": "C_CHANNEL",
            "ts": "1234567890.123456",
        },
    }
    body = json.dumps(payload, ensure_ascii=False)
    timestamp = str(int(time.time()))

    if valid_signature:
        base = f"v0:{timestamp}:{body}"
        sig = "v0=" + hmac.new(SIGNING_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest()
    else:
        sig = "v0=invalid"

    return {
        "body": body,
        "headers": {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": sig,
        },
    }


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
@patch("src.handlers.slack_webhook.slack_response.post_message")
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
@patch("src.services.issue_generator.generate")
@patch("src.handlers.task_create.handler")
def test_webhook_create(mock_task_create, mock_generate, mock_classify, mock_ssm, mock_post, mock_auth):
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
    mock_post.assert_called_once()
    msg = mock_post.call_args[0][1]
    assert "作成しました" in msg


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
@patch("src.handlers.slack_webhook.slack_response.post_message")
@patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-key")
@patch("src.services.intent_classifier.classify")
@patch("src.handlers.task_update.handler")
def test_webhook_update(mock_task_update, mock_classify, mock_ssm, mock_post, mock_auth):
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
    mock_post.assert_called_once()
    msg = mock_post.call_args[0][1]
    assert "更新しました" in msg


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=False)
def test_webhook_invalid_signature(mock_auth):
    event = _make_event("テスト", valid_signature=False)
    response = handler(event, None)
    assert response["statusCode"] == 401


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
def test_url_verification(mock_auth):
    payload = {"type": "url_verification", "challenge": "test-challenge-token"}
    body = json.dumps(payload)
    timestamp = str(int(time.time()))

    event = {
        "body": body,
        "headers": {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": "v0=dummy",
        },
    }
    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = json.loads(response["body"])
    assert resp_body["challenge"] == "test-challenge-token"


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
def test_webhook_bot_message_ignored(mock_auth):
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "<@UBOTID> テスト",
            "user": "U_USER",
            "bot_id": "B_BOT",
            "channel": "C_CHANNEL",
            "ts": "1234567890.123456",
        },
    }
    body = json.dumps(payload)
    event = {
        "body": body,
        "headers": {
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=dummy",
        },
    }
    response = handler(event, None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]).get("ok") is True


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
def test_webhook_empty_message(mock_auth):
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "<@UBOTID>",
            "user": "U_USER",
            "channel": "C_CHANNEL",
            "ts": "1234567890.123456",
        },
    }
    body = json.dumps(payload)
    event = {
        "body": body,
        "headers": {
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=dummy",
        },
    }
    response = handler(event, None)
    assert response["statusCode"] == 200


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
@patch("src.handlers.slack_webhook.slack_response.post_message")
@patch("src.services.intent_classifier.classify")
def test_webhook_no_project_key(mock_classify, mock_post, mock_auth):
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

    event = _make_event("この件、課題にして")
    response = handler(event, None)

    assert response["statusCode"] == 200
    mock_post.assert_called_once()
    msg = mock_post.call_args[0][1]
    assert "プロジェクトキーを指定" in msg


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
@patch("src.handlers.slack_webhook._get_sqs_client")
def test_webhook_sqs_enqueue(mock_sqs_client, mock_auth):
    mock_sqs = MagicMock()
    mock_sqs_client.return_value = mock_sqs

    event = _make_event("[NOHARATEST] タスク作成して")

    with patch("src.handlers.slack_webhook._SQS_QUEUE_URL", "https://sqs.example.com/queue"):
        response = handler(event, None)

    assert response["statusCode"] == 200
    mock_sqs.send_message.assert_called_once()
    sent_body = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert sent_body["platform"] == "slack"
    assert sent_body["channel"] == "C_CHANNEL"
    assert "NOHARATEST" in sent_body["message"]
