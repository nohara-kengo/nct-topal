import os

import pytest

from unittest.mock import patch

from src.services.ssm_client import (
    get_backlog_api_key,
    get_backlog_space_url,
    get_channel_project_key,
    get_slack_signing_secret,
    get_slack_bot_token,
    clear_cache,
)


requires_localstack = pytest.mark.skipif(
    not os.environ.get("AWS_ENDPOINT_URL"),
    reason="AWS_ENDPOINT_URL が未設定（LocalStackテスト）",
)


@requires_localstack
def test_get_backlog_api_key():
    clear_cache()
    key = get_backlog_api_key("NOHARATEST")
    assert key == "r5jVhoYIvU9yPIyt5rppwU6MwiXxCfI30Wl7JOvkeddEEhacwkX6m1JXYnP9zTiP"


@requires_localstack
def test_get_backlog_space_url():
    clear_cache()
    url = get_backlog_space_url("NOHARATEST")
    assert url == "https://comthink06.backlog.com"


@requires_localstack
def test_get_backlog_api_key_cached():
    clear_cache()
    key1 = get_backlog_api_key("NOHARATEST")
    key2 = get_backlog_api_key("NOHARATEST")
    assert key1 == key2


@requires_localstack
def test_get_backlog_api_key_not_found():
    clear_cache()
    with pytest.raises(Exception):
        get_backlog_api_key("NONEXISTENT")


@patch("src.services.ssm_client._get_parameter", return_value="test-signing-secret")
def test_get_slack_signing_secret(mock_param):
    result = get_slack_signing_secret()
    assert result == "test-signing-secret"
    args = mock_param.call_args[0][0]
    assert args.endswith("/slack_signing_secret")


@patch("src.services.ssm_client._get_parameter", return_value="xoxb-test-token")
def test_get_slack_bot_token(mock_param):
    result = get_slack_bot_token()
    assert result == "xoxb-test-token"
    args = mock_param.call_args[0][0]
    assert args.endswith("/slack_bot_token")


@patch("src.services.ssm_client._get_parameter", return_value="NOHARATEST")
def test_get_channel_project_key_found(mock_param):
    result = get_channel_project_key("C0AP3RM59B3")
    assert result == "NOHARATEST"
    args = mock_param.call_args[0][0]
    assert args.endswith("/channel_mappings/C0AP3RM59B3")


@patch("src.services.ssm_client._get_parameter", side_effect=Exception("ParameterNotFound"))
def test_get_channel_project_key_not_found(mock_param):
    result = get_channel_project_key("C_UNKNOWN")
    assert result is None
