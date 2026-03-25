from unittest.mock import patch, MagicMock

from src.services.slack_response import post_message


@patch("src.services.slack_response.ssm_client.get_slack_bot_token", return_value="xoxb-test")
@patch("src.services.slack_response.requests.post")
def test_post_message(mock_post, mock_token):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp

    post_message("C123", "テスト通知")

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["channel"] == "C123"
    assert call_kwargs.kwargs["json"]["text"] == "テスト通知"
    assert "thread_ts" not in call_kwargs.kwargs["json"]


@patch("src.services.slack_response.ssm_client.get_slack_bot_token", return_value="xoxb-test")
@patch("src.services.slack_response.requests.post")
def test_post_message_with_thread(mock_post, mock_token):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp

    post_message("C123", "スレッド返信", thread_ts="1234567890.123456")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["thread_ts"] == "1234567890.123456"


@patch("src.services.slack_response.ssm_client.get_slack_bot_token", return_value="xoxb-test")
@patch("src.services.slack_response.requests.post")
def test_post_message_api_error(mock_post, mock_token):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "error": "channel_not_found"}
    mock_post.return_value = mock_resp

    try:
        post_message("C_INVALID", "テスト")
        assert False, "RuntimeError が発生すべき"
    except RuntimeError as e:
        assert "channel_not_found" in str(e)
