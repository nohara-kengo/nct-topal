import hashlib
import hmac
import time
from unittest.mock import patch

from src.services.slack_auth import validate_request


def _make_signature(secret: str, timestamp: str, body: str) -> str:
    base = f"v0:{timestamp}:{body}"
    return "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()


SIGNING_SECRET = "test-signing-secret"


@patch("src.services.slack_auth.ssm_client.get_slack_signing_secret", return_value=SIGNING_SECRET)
def test_valid_signature(mock_ssm):
    timestamp = str(int(time.time()))
    body = '{"type":"event_callback"}'
    signature = _make_signature(SIGNING_SECRET, timestamp, body)

    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
    }
    assert validate_request(headers, body) is True


@patch("src.services.slack_auth.ssm_client.get_slack_signing_secret", return_value=SIGNING_SECRET)
def test_invalid_signature(mock_ssm):
    timestamp = str(int(time.time()))
    body = '{"type":"event_callback"}'

    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": "v0=invalid",
    }
    assert validate_request(headers, body) is False


@patch("src.services.slack_auth.ssm_client.get_slack_signing_secret", return_value=SIGNING_SECRET)
def test_expired_timestamp(mock_ssm):
    timestamp = str(int(time.time()) - 600)
    body = '{"type":"event_callback"}'
    signature = _make_signature(SIGNING_SECRET, timestamp, body)

    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
    }
    assert validate_request(headers, body) is False


def test_missing_headers():
    assert validate_request({}, "body") is False
    assert validate_request({"X-Slack-Request-Timestamp": "123"}, "body") is False
    assert validate_request({"X-Slack-Signature": "v0=abc"}, "body") is False
