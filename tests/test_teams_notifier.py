from unittest.mock import patch, MagicMock

import pytest
import requests

from src.services.teams_notifier import notify


MOCK_WEBHOOK_URL = "https://example.webhook.office.com/webhookb2/test"


@patch("src.services.teams_notifier.ssm_client.get_teams_incoming_webhook_url", return_value=MOCK_WEBHOOK_URL)
@patch("src.services.teams_notifier.requests.post")
def test_notify_success(mock_post, mock_ssm):
    """正常送信時にAdaptive Card形式でPOSTされる。"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    notify("タスクを作成しました: NOHARATEST-1")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.args[0] == MOCK_WEBHOOK_URL

    payload = call_kwargs.kwargs["json"]
    assert payload["type"] == "message"
    card = payload["attachments"][0]["content"]
    assert card["type"] == "AdaptiveCard"
    assert card["body"][0]["text"] == "タスクを作成しました: NOHARATEST-1"


@patch("src.services.teams_notifier.ssm_client.get_teams_incoming_webhook_url", return_value=MOCK_WEBHOOK_URL)
@patch("src.services.teams_notifier.requests.post")
def test_notify_http_error_raises(mock_post, mock_ssm):
    """HTTPエラー時にRequestExceptionが送出される。"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    mock_post.return_value = mock_resp

    with pytest.raises(requests.HTTPError):
        notify("テストメッセージ")


@patch("src.services.teams_notifier.ssm_client.get_teams_incoming_webhook_url", return_value=MOCK_WEBHOOK_URL)
@patch("src.services.teams_notifier.requests.post", side_effect=requests.ConnectionError("接続失敗"))
def test_notify_connection_error_raises(mock_post, mock_ssm):
    """接続エラー時にRequestExceptionが送出される。"""
    with pytest.raises(requests.ConnectionError):
        notify("テストメッセージ")


@patch("src.services.teams_notifier.ssm_client.get_teams_incoming_webhook_url", return_value=MOCK_WEBHOOK_URL)
@patch("src.services.teams_notifier.requests.post")
def test_notify_message_in_payload(mock_post, mock_ssm):
    """日本語メッセージがそのままペイロードに含まれる。"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    msg = "✅ 野原 太郎さんのリクエストでタスクを作成しました: NOHARATEST-99 ログイン機能を実装する。"
    notify(msg)

    payload = mock_post.call_args.kwargs["json"]
    assert payload["attachments"][0]["content"]["body"][0]["text"] == msg
