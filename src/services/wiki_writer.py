"""Backlog Wikiへの日次レポート書き込みを行うモジュール。"""

import logging

import requests

from src.services import backlog_client

logger = logging.getLogger(__name__)


def fetch_prev_wikis(project_key: str, prev_date_path: str) -> dict[str, str]:
    """前日のWikiページ群のコンテンツを取得する。

    Args:
        project_key: Backlogプロジェクトキー
        prev_date_path: 前日の日付パス（YYYY-MM-DD形式）

    Returns:
        {ページ名: content} のマップ。前日Wikiが無ければ空dict
    """
    # 日次レポート/YYYY-MM-DD/全体, 日次レポート/YYYY-MM-DD/担当者名
    prefix = f"日次レポート/{prev_date_path}"
    existing = backlog_client.get_wikis(project_key)

    result = {}
    for wiki in existing:
        if wiki["name"].startswith(prefix):
            # 個別Wikiの内容を取得
            try:
                content = _fetch_wiki_content(wiki["id"], project_key)
                result[wiki["name"]] = content
            except Exception:
                logger.warning("前日Wiki取得に失敗: %s", wiki["name"])
    return result


def _fetch_wiki_content(wiki_id: int, project_key: str) -> str:
    """Wiki IDからコンテンツを取得する。"""
    space_url, api_key = backlog_client._get_auth_params(project_key)
    resp = backlog_client._request_with_retry(
        "GET", f"{space_url}/api/v2/wikis/{wiki_id}",
        params={"apiKey": api_key}, timeout=10,
    )
    return resp.json().get("content", "")


def write_daily_report(project_key: str, date_str: str, pages: list[dict]) -> list[dict]:
    """レポートページ群をBacklog Wikiに作成/更新する。

    既存のWikiページがあれば更新し、なければ新規作成する。

    Args:
        project_key: Backlogプロジェクトキー
        date_str: レポート日付（YYYY/MM/DD形式、ログ用）
        pages: [{"name": str, "content": str}, ...] のリスト

    Returns:
        作成/更新されたWiki情報のリスト
    """
    existing_wikis = backlog_client.get_wikis(project_key)
    wiki_by_name = {w["name"]: w for w in existing_wikis}

    results = []
    for page in pages:
        name = page["name"]
        content = page["content"]

        existing = wiki_by_name.get(name)
        if existing:
            logger.info("Wiki更新: %s (id=%s)", name, existing["id"])
            result = backlog_client.update_wiki(existing["id"], name, content, project_key)
        else:
            logger.info("Wiki作成: %s", name)
            result = backlog_client.create_wiki(project_key, name, content)

        results.append(result)

    return results
