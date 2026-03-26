from unittest.mock import patch, MagicMock

from src.services.slack_user_resolver import resolve_display_name, _user_cache


def _mock_response(ok=True, user=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"ok": ok, "user": user or {}}
    return resp


@patch("src.services.slack_user_resolver.ssm_client.get_slack_bot_token", return_value="xoxb-dummy")
@patch("src.services.slack_user_resolver.requests.get")
def test_resolve_display_name(mock_get, mock_token):
    _user_cache.clear()
    mock_get.return_value = _mock_response(user={
        "real_name": "野原 太郎",
        "profile": {"display_name": "nohara"},
        "name": "nohara.taro",
    })

    result = resolve_display_name("U123ABC")
    assert result == "nohara"
    mock_get.assert_called_once()


@patch("src.services.slack_user_resolver.ssm_client.get_slack_bot_token", return_value="xoxb-dummy")
@patch("src.services.slack_user_resolver.requests.get")
def test_resolve_fallback_to_real_name(mock_get, mock_token):
    _user_cache.clear()
    mock_get.return_value = _mock_response(user={
        "real_name": "野原 太郎",
        "profile": {"display_name": ""},
        "name": "nohara.taro",
    })

    result = resolve_display_name("U456DEF")
    assert result == "野原 太郎"


@patch("src.services.slack_user_resolver.ssm_client.get_slack_bot_token", return_value="xoxb-dummy")
@patch("src.services.slack_user_resolver.requests.get")
def test_resolve_api_error_returns_user_id(mock_get, mock_token):
    _user_cache.clear()
    mock_get.return_value = _mock_response(ok=False)

    result = resolve_display_name("U789GHI")
    assert result == "U789GHI"


@patch("src.services.slack_user_resolver.ssm_client.get_slack_bot_token", return_value="xoxb-dummy")
@patch("src.services.slack_user_resolver.requests.get")
def test_resolve_cached(mock_get, mock_token):
    _user_cache.clear()
    _user_cache["U_CACHED"] = "キャッシュ済み"

    result = resolve_display_name("U_CACHED")
    assert result == "キャッシュ済み"
    mock_get.assert_not_called()


def test_resolve_empty_user_id():
    assert resolve_display_name("") == "不明"
    assert resolve_display_name(None) == "不明"
