import json
from unittest.mock import patch

from src.handlers.project_setup import handler
from src.services.backlog_setup import ISSUE_TYPES, STATUSES, StatusLimitExceeded


MOCK_ISSUE_TYPE_MAP = {name: i + 1 for i, (name, _) in enumerate(ISSUE_TYPES)}
MOCK_TEMPLATE_MAP = {name: "updated" for name, _ in ISSUE_TYPES}
MOCK_STATUS_MAP = {"未対応": 1, "処理中": 2, "処理済み": 3, "完了": 4}
MOCK_STATUS_MAP.update({name: i + 10 for i, (name, _) in enumerate(STATUSES)})


@patch("src.handlers.project_setup.backlog_setup.ensure_issue_types", return_value=MOCK_ISSUE_TYPE_MAP)
@patch("src.handlers.project_setup.backlog_setup.ensure_issue_type_templates", return_value=MOCK_TEMPLATE_MAP)
@patch("src.handlers.project_setup.backlog_setup.ensure_statuses", return_value=MOCK_STATUS_MAP)
@patch("src.handlers.project_setup.backlog_setup._ensure_category", return_value=200)
def test_project_setup(mock_cat, mock_statuses, mock_templates, mock_types):
    event = {"pathParameters": {"projectKey": "NOHARATEST"}}
    response = handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["project_key"] == "NOHARATEST"
    assert body["issue_types"]["タスク"] == 1
    assert body["issue_types"]["バグ"] == 9
    assert body["templates"]["タスク"] == "updated"
    assert body["statuses"]["AI下書き"] == 10
    assert body["statuses"]["未対応"] == 1
    assert body["category_ai_generated_id"] == 200


@patch("src.handlers.project_setup.backlog_setup.ensure_issue_types", return_value=MOCK_ISSUE_TYPE_MAP)
@patch("src.handlers.project_setup.backlog_setup.ensure_issue_type_templates", return_value=MOCK_TEMPLATE_MAP)
@patch("src.handlers.project_setup.backlog_setup.ensure_statuses", return_value=MOCK_STATUS_MAP)
@patch("src.handlers.project_setup.backlog_setup._ensure_category", return_value=200)
def test_project_setup_from_body(mock_cat, mock_statuses, mock_templates, mock_types):
    """pathParametersが無い場合、bodyからproject_keyを取得。"""
    event = {"body": json.dumps({"project_key": "NOHARATEST"})}
    response = handler(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["project_key"] == "NOHARATEST"


def test_project_setup_missing_key():
    event = {"body": "{}"}
    response = handler(event, None)
    assert response["statusCode"] == 400


@patch("src.handlers.project_setup.backlog_setup.ensure_issue_types", return_value=MOCK_ISSUE_TYPE_MAP)
@patch("src.handlers.project_setup.backlog_setup.ensure_issue_type_templates", return_value=MOCK_TEMPLATE_MAP)
@patch("src.handlers.project_setup.backlog_setup.ensure_statuses", side_effect=StatusLimitExceeded("上限超過"))
def test_project_setup_status_limit(mock_statuses, mock_templates, mock_types):
    """ステータス上限超過時は409を返す。"""
    event = {"pathParameters": {"projectKey": "NOHARATEST"}}
    response = handler(event, None)
    assert response["statusCode"] == 409
    body = json.loads(response["body"])
    assert "上限" in body["error"]
