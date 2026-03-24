from unittest.mock import patch

from src.services.assignee_resolver import resolve_assignee_id


MOCK_USERS = [
    {"id": 10, "userId": "nohara", "name": "野原 太郎"},
    {"id": 20, "userId": "sato", "name": "佐藤 花子"},
    {"id": 30, "userId": "tanaka", "name": "田中 一郎"},
]


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
def test_exact_match_name(mock_users):
    assert resolve_assignee_id("TEST", "野原 太郎") == 10


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
def test_exact_match_user_id(mock_users):
    assert resolve_assignee_id("TEST", "nohara") == 10


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
def test_partial_match_surname(mock_users):
    assert resolve_assignee_id("TEST", "野原") == 10


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
def test_partial_match_given_name(mock_users):
    assert resolve_assignee_id("TEST", "花子") == 20


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
def test_no_match(mock_users):
    assert resolve_assignee_id("TEST", "山田") is None


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
def test_none_assignee(mock_users):
    assert resolve_assignee_id("TEST", None) is None
    mock_users.assert_not_called()


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=MOCK_USERS)
def test_fullwidth_space_normalization(mock_users):
    """全角スペースを含む名前でも検索できる。"""
    assert resolve_assignee_id("TEST", "野原\u3000太郎") == 10


@patch("src.services.assignee_resolver.backlog_client.get_project_users", return_value=[
    {"id": 10, "userId": "tanaka_i", "name": "田中 一郎"},
    {"id": 20, "userId": "tanaka_j", "name": "田中 次郎"},
])
def test_multiple_partial_matches_returns_first(mock_users):
    """複数部分一致の場合は先頭を返す。"""
    assert resolve_assignee_id("TEST", "田中") == 10
