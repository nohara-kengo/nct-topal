"""担当者名からBacklogユーザーIDを解決するモジュール。"""

import logging

import requests

from src.services import backlog_client

logger = logging.getLogger(__name__)


def resolve_assignee_id(project_key: str, assignee_name: str | None) -> int | None:
    """担当者名からBacklogユーザーIDを解決する。

    完全一致 → 部分一致（姓 or 名） → 未発見 の順に検索する。

    Args:
        project_key: Backlogプロジェクトキー
        assignee_name: 担当者名（例: "野原", "野原 太郎", "nohara"）

    Returns:
        BacklogユーザーID。見つからない場合はNone
    """
    if not assignee_name:
        return None

    try:
        users = backlog_client.get_project_users(project_key)
    except requests.RequestException:
        logger.warning("プロジェクトメンバーの取得に失敗: %s", project_key)
        return None

    # 検索文字列の正規化（全角スペース→半角、前後空白除去）
    query = assignee_name.replace("\u3000", " ").strip()

    # 1. 完全一致（name または userId）
    for user in users:
        if query in (user.get("name", ""), user.get("userId", "")):
            return user["id"]

    # 2. 部分一致（nameに含まれるか）
    matches = []
    for user in users:
        name = user.get("name", "")
        user_id = user.get("userId", "")
        if query in name or query in user_id:
            matches.append(user)

    if len(matches) == 1:
        logger.info("担当者 '%s' を部分一致で解決: %s", query, matches[0]["name"])
        return matches[0]["id"]

    if len(matches) > 1:
        names = [m.get("name", "") for m in matches]
        logger.warning("担当者 '%s' が複数一致: %s（先頭を使用）", query, names)
        return matches[0]["id"]

    logger.warning("担当者 '%s' が見つかりません", query)
    return None
