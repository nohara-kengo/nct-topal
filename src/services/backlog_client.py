"""Backlog APIとの通信を行うクライアントモジュール。"""

import logging

import requests

from src.services import ssm_client

logger = logging.getLogger(__name__)


def _get_auth_params(project_key: str) -> tuple[str, str]:
    """SSMからBacklog接続情報を取得する。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        (space_url, api_key) のタプル
    """
    space_url = ssm_client.get_backlog_space_url(project_key)
    api_key = ssm_client.get_backlog_api_key(project_key)
    return space_url, api_key


def get_project(project_key: str) -> dict:
    """プロジェクト情報を取得する。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        プロジェクト情報
    """
    space_url, api_key = _get_auth_params(project_key)
    resp = requests.get(
        f"{space_url}/api/v2/projects/{project_key}",
        params={"apiKey": api_key},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_project_users(project_key: str) -> list[dict]:
    """プロジェクトのメンバー一覧を取得する。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        ユーザー情報のリスト（id, userId, name, mailAddress等）
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/users"
    resp = requests.get(url, params={"apiKey": api_key}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_statuses(project_key: str) -> list[dict]:
    """プロジェクトのステータス一覧を取得する。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        ステータス情報のリスト
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/statuses"
    resp = requests.get(url, params={"apiKey": api_key}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def add_status(project_key: str, name: str, color: str) -> dict:
    """プロジェクトにカスタムステータスを追加する。

    Args:
        project_key: Backlogプロジェクトキー
        name: ステータス名
        color: 色コード（例: "#3b9dbd"）

    Returns:
        作成されたステータス情報
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/statuses"
    resp = requests.post(
        url,
        params={"apiKey": api_key},
        data={"name": name, "color": color},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_categories(project_key: str) -> list[dict]:
    """プロジェクトのカテゴリ一覧を取得する。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        カテゴリ情報のリスト
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/categories"
    resp = requests.get(url, params={"apiKey": api_key}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def add_category(project_key: str, name: str) -> dict:
    """プロジェクトにカテゴリを追加する。

    Args:
        project_key: Backlogプロジェクトキー
        name: カテゴリ名

    Returns:
        作成されたカテゴリ情報
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/categories"
    resp = requests.post(
        url,
        params={"apiKey": api_key},
        data={"name": name},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_issue_types(project_key: str) -> list[dict]:
    """プロジェクトの種別一覧を取得する。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        種別情報のリスト
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/issueTypes"
    resp = requests.get(url, params={"apiKey": api_key}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def add_issue_type(project_key: str, name: str, color: str) -> dict:
    """プロジェクトに種別を追加する。

    Args:
        project_key: Backlogプロジェクトキー
        name: 種別名
        color: 色コード（例: "#7ea800"）

    Returns:
        作成された種別情報
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/issueTypes"
    resp = requests.post(
        url,
        params={"apiKey": api_key},
        data={"name": name, "color": color},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def update_issue_type(project_key: str, issue_type_id: int, **fields) -> dict:
    """種別を更新する。

    Args:
        project_key: Backlogプロジェクトキー
        issue_type_id: 種別ID
        **fields: 更新するフィールド（templateSummary, templateDescriptionなど）

    Returns:
        更新された種別情報
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/projects/{project_key}/issueTypes/{issue_type_id}"
    resp = requests.patch(url, params={"apiKey": api_key}, data=fields, timeout=10)
    resp.raise_for_status()
    return resp.json()


def update_issue(issue_key: str, project_key: str, **fields) -> dict:
    """課題を更新する。

    Args:
        issue_key: 課題キー（例: NOHARATEST-1）
        project_key: Backlogプロジェクトキー
        **fields: 更新するフィールド（statusId, priorityId, dueDateなど）

    Returns:
        更新された課題情報
    """
    space_url, api_key = _get_auth_params(project_key)
    url = f"{space_url}/api/v2/issues/{issue_key}"
    resp = requests.patch(url, params={"apiKey": api_key}, data=fields, timeout=10)
    resp.raise_for_status()
    return resp.json()


def create_issue(
    project_key: str,
    summary: str,
    issue_type_id: int,
    priority_id: int = 3,
    status_id: int | None = None,
    category_ids: list[int] | None = None,
    description: str = "",
    start_date: str | None = None,
    due_date: str | None = None,
    estimated_hours: float | None = None,
    assignee_id: int | None = None,
) -> dict:
    """Backlogに課題を作成する。

    作成後にステータスを変更する（Backlog APIは作成時にstatus指定不可のため）。

    Args:
        project_key: Backlogプロジェクトキー
        summary: 課題の件名
        issue_type_id: 種別ID
        priority_id: 優先度ID（2=高, 3=中, 4=低）
        status_id: ステータスID（指定時は作成後に変更）
        category_ids: カテゴリIDリスト
        description: 課題の詳細
        start_date: 開始日（YYYY-MM-DD形式）
        due_date: 期限（YYYY-MM-DD形式）
        estimated_hours: 予定時間（時間）
        assignee_id: 担当者のユーザーID

    Returns:
        作成された課題情報
    """
    project = get_project(project_key)

    space_url, api_key = _get_auth_params(project_key)
    data = {
        "projectId": project["id"],
        "summary": summary,
        "issueTypeId": issue_type_id,
        "priorityId": priority_id,
    }
    if category_ids:
        for i, cid in enumerate(category_ids):
            data[f"categoryId[{i}]"] = cid
    if description:
        data["description"] = description
    if start_date:
        data["startDate"] = start_date
    if due_date:
        data["dueDate"] = due_date
    if estimated_hours is not None:
        data["estimatedHours"] = estimated_hours
    if assignee_id is not None:
        data["assigneeId"] = assignee_id

    url = f"{space_url}/api/v2/issues"
    resp = requests.post(url, params={"apiKey": api_key}, data=data, timeout=10)
    resp.raise_for_status()
    issue = resp.json()

    if status_id:
        issue = update_issue(issue["issueKey"], project_key, statusId=status_id)

    return issue
