import os

import pytest

from src.services.ssm_client import get_backlog_api_key, get_backlog_space_url, clear_cache


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
