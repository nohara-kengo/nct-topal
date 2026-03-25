from unittest.mock import patch, MagicMock

from src.services import backlog_client


MOCK_AUTH = ("https://test.backlog.com", "test-api-key")
MOCK_PROJECT = {"id": 1, "projectKey": "NOHARATEST"}


def _patch_auth():
    return patch.object(backlog_client, "_get_auth_params", return_value=MOCK_AUTH)


def _patch_project():
    return patch.object(backlog_client, "get_project", return_value=MOCK_PROJECT)


@patch.object(backlog_client, "_request_with_retry")
def test_get_issues(_mock_request, ):
    _mock_request.return_value.json.return_value = [
        {"issueKey": "NOHARATEST-1", "summary": "テスト課題"},
    ]
    with _patch_auth(), _patch_project():
        result = backlog_client.get_issues("NOHARATEST")
    assert len(result) == 1
    assert result[0]["issueKey"] == "NOHARATEST-1"
    call_kwargs = _mock_request.call_args
    assert call_kwargs[0][0] == "GET"
    assert "issues" in call_kwargs[0][1]


@patch.object(backlog_client, "_request_with_retry")
def test_get_issues_with_filters(_mock_request):
    _mock_request.return_value.json.return_value = []
    with _patch_auth(), _patch_project():
        backlog_client.get_issues("NOHARATEST", **{"statusId[]": 1})
    call_kwargs = _mock_request.call_args
    assert call_kwargs[1]["params"]["statusId[]"] == 1


@patch.object(backlog_client, "_request_with_retry")
def test_get_wikis(_mock_request):
    _mock_request.return_value.json.return_value = [
        {"id": 10, "name": "日次レポート/2026/03/25"},
    ]
    with _patch_auth(), _patch_project():
        result = backlog_client.get_wikis("NOHARATEST")
    assert len(result) == 1
    assert result[0]["name"] == "日次レポート/2026/03/25"


@patch.object(backlog_client, "_request_with_retry")
def test_create_wiki(_mock_request):
    _mock_request.return_value.json.return_value = {
        "id": 20, "name": "日次レポート/2026/03/25", "content": "# テスト",
    }
    with _patch_auth(), _patch_project():
        result = backlog_client.create_wiki("NOHARATEST", "日次レポート/2026/03/25", "# テスト")
    assert result["id"] == 20
    call_kwargs = _mock_request.call_args
    assert call_kwargs[0][0] == "POST"
    assert call_kwargs[1]["data"]["name"] == "日次レポート/2026/03/25"


@patch.object(backlog_client, "_request_with_retry")
def test_update_wiki(_mock_request):
    _mock_request.return_value.json.return_value = {
        "id": 20, "name": "日次レポート/2026/03/25", "content": "# 更新済",
    }
    with _patch_auth():
        result = backlog_client.update_wiki(20, "日次レポート/2026/03/25", "# 更新済", "NOHARATEST")
    assert result["content"] == "# 更新済"
    call_kwargs = _mock_request.call_args
    assert call_kwargs[0][0] == "PATCH"
    assert "/wikis/20" in call_kwargs[0][1]
