from unittest.mock import patch, MagicMock

import pytest
import requests

from src.services.teams_notifier import notify


MOCK_APP_ID = "test-app-id"
MOCK_APP_PASSWORD = "test-app-password"
MOCK_SERVICE_URL = "https://smba.trafficmanager.net/jp"
MOCK_CONVERSATION = {"id": "19:abc123@thread.tacv2"}
MOCK_TOKEN_RESPONSE = {"access_token": "test-bot-token", "expires_in": 3600}


@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_id", return_value=MOCK_APP_ID)
@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_password", return_value=MOCK_APP_PASSWORD)
@patch("src.services.teams_notifier.requests.post")
def test_notify_success(mock_post, mock_password, mock_app_id):
    # トークン取得 → メッセージ送信の2回のPOSTが呼ばれる
    token_resp = MagicMock()
    token_resp.json.return_value = MOCK_TOKEN_RESPONSE
    token_resp.raise_for_status = MagicMock()

    message_resp = MagicMock()
    message_resp.raise_for_status = MagicMock()

    mock_post.side_effect = [token_resp, message_resp]

    # キャッシュをリセット
    from src.services import teams_notifier
    teams_notifier._token_cache = {"token": None, "expires_at": 0}

    notify("タスクを作成しました: NOHARATEST-1", MOCK_SERVICE_URL, MOCK_CONVERSATION)

    assert mock_post.call_count == 2

    # 2回目の呼び出し（メッセージ送信）を確認
    msg_call = mock_post.call_args_list[1]
    assert MOCK_SERVICE_URL in msg_call.args[0]
    assert MOCK_CONVERSATION["id"] in msg_call.args[0]

    payload = msg_call.kwargs["json"]
    assert payload["type"] == "message"
    card = payload["attachments"][0]["content"]
    assert card["type"] == "AdaptiveCard"
    assert card["body"][0]["text"] == "タスクを作成しました: NOHARATEST-1"

    # Authorizationヘッダーにトークンが含まれる
    assert msg_call.kwargs["headers"]["Authorization"] == "Bearer test-bot-token"


@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_id", return_value=MOCK_APP_ID)
@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_password", return_value=MOCK_APP_PASSWORD)
@patch("src.services.teams_notifier.requests.post")
def test_notify_http_error_raises(mock_post, mock_password, mock_app_id):
    token_resp = MagicMock()
    token_resp.json.return_value = MOCK_TOKEN_RESPONSE
    token_resp.raise_for_status = MagicMock()

    message_resp = MagicMock()
    message_resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

    mock_post.side_effect = [token_resp, message_resp]

    from src.services import teams_notifier
    teams_notifier._token_cache = {"token": None, "expires_at": 0}

    with pytest.raises(requests.HTTPError):
        notify("テストメッセージ", MOCK_SERVICE_URL, MOCK_CONVERSATION)


@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_id", return_value=MOCK_APP_ID)
@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_password", return_value=MOCK_APP_PASSWORD)
@patch("src.services.teams_notifier.requests.post")
def test_notify_connection_error_raises(mock_post, mock_password, mock_app_id):
    token_resp = MagicMock()
    token_resp.json.return_value = MOCK_TOKEN_RESPONSE
    token_resp.raise_for_status = MagicMock()

    mock_post.side_effect = [token_resp, requests.ConnectionError("接続失敗")]

    from src.services import teams_notifier
    teams_notifier._token_cache = {"token": None, "expires_at": 0}

    with pytest.raises(requests.ConnectionError):
        notify("テストメッセージ", MOCK_SERVICE_URL, MOCK_CONVERSATION)


@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_id", return_value=MOCK_APP_ID)
@patch("src.services.teams_notifier.ssm_client.get_microsoft_app_password", return_value=MOCK_APP_PASSWORD)
@patch("src.services.teams_notifier.requests.post")
def test_notify_uses_cached_token(mock_post, mock_password, mock_app_id):
    """トークンキャッシュが有効な場合、トークン取得をスキップする。"""
    import time
    from src.services import teams_notifier
    teams_notifier._token_cache = {"token": "cached-token", "expires_at": time.time() + 3600}

    message_resp = MagicMock()
    message_resp.raise_for_status = MagicMock()
    mock_post.return_value = message_resp

    notify("テスト", MOCK_SERVICE_URL, MOCK_CONVERSATION)

    # トークン取得のPOSTはスキップされ、メッセージ送信の1回のみ
    assert mock_post.call_count == 1
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer cached-token"
