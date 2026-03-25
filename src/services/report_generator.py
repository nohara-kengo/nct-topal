"""Backlog課題データを集計し日次レポートのMarkdownを生成するモジュール。"""

import logging
import re
from collections import Counter
from datetime import date, timedelta

from src.services import backlog_client

logger = logging.getLogger(__name__)

# Wikiページパスのプレフィックス
_PREFIX = "日次レポート"
_OVERALL_SUFFIX = "全体"


def generate_daily_report(project_key: str, date_str: str, prev_wikis: dict[str, str] | None = None) -> dict:
    """日次レポートデータを生成する。

    Backlogから課題一覧を取得し、全体レポートと担当者別レポートの
    Wikiページ用コンテンツを生成する。前日Wikiが渡された場合は前日比を算出する。

    Args:
        project_key: Backlogプロジェクトキー
        date_str: レポート日付（YYYY/MM/DD形式）
        prev_wikis: 前日Wikiの {ページ名: content} マップ（任意）

    Returns:
        {"summary": {"total": int, "completed": int, "by_status": dict}, "pages": [...]}
    """
    all_issues = backlog_client.get_issues(project_key)
    backlog_client.get_project_users(project_key)

    # 「スケジュール」種別を除外
    non_schedule = [
        i for i in all_issues
        if "スケジュール" not in i.get("issueType", {}).get("name", "")
    ]

    # 完了と未完了に分離
    issues = [i for i in non_schedule if i.get("status", {}).get("name", "") != "完了"]
    completed_issues = [i for i in non_schedule if i.get("status", {}).get("name", "") == "完了"]

    # ステータス別集計（未完了のみ）
    status_counter = Counter(
        issue.get("status", {}).get("name", "不明") for issue in issues
    )

    date_label = date_str.replace("/", "-")

    if prev_wikis is None:
        prev_wikis = {}

    # --- 担当者ごとの集計 ---
    assignee_issues = {}
    assignee_completed = {}
    for issue in issues:
        assignee = issue.get("assignee")
        name = assignee.get("name", "未割当") if assignee else "未割当"
        assignee_issues.setdefault(name, []).append(issue)
    for issue in completed_issues:
        assignee = issue.get("assignee")
        name = assignee.get("name", "未割当") if assignee else "未割当"
        assignee_completed.setdefault(name, []).append(issue)

    all_assignees = sorted(set(list(assignee_issues.keys()) + list(assignee_completed.keys())) - {"未割当"})

    # --- 全体ページ ---
    prev_overall_key = _find_overall_wiki_key(prev_wikis)
    prev_overall_data = parse_wiki_content(prev_wikis[prev_overall_key]) if prev_overall_key else None

    overall_name = f"{_PREFIX}/{date_label}/{_OVERALL_SUFFIX}"
    overall_content = _build_overall_page(
        date_label, issues, completed_issues, status_counter,
        assignee_issues, assignee_completed, all_assignees, prev_overall_data,
    )
    pages = [{"name": overall_name, "content": overall_content}]

    # --- 担当者別ページ ---
    for assignee_name in all_assignees:
        page_name = f"{_PREFIX}/{date_label}/{assignee_name}"
        a_issues = assignee_issues.get(assignee_name, [])
        a_completed = assignee_completed.get(assignee_name, [])

        prev_key = _find_assignee_wiki_key(prev_wikis, assignee_name)
        prev_data = parse_wiki_content(prev_wikis[prev_key]) if prev_key else None

        page_content = _build_assignee_page(assignee_name, date_label, a_issues, a_completed, prev_data)
        pages.append({"name": page_name, "content": page_content})

    summary = {
        "total": len(issues),
        "completed": len(completed_issues),
        "by_status": dict(status_counter),
    }

    return {"summary": summary, "pages": pages}


def _find_assignee_wiki_key(prev_wikis: dict[str, str], assignee_name: str) -> str | None:
    for key in prev_wikis:
        if key.endswith(f"/{assignee_name}"):
            return key
    return None


def _find_overall_wiki_key(prev_wikis: dict[str, str]) -> str | None:
    for key in prev_wikis:
        if key.endswith(f"/{_OVERALL_SUFFIX}"):
            return key
    return None


def get_prev_business_date_path(date_str: str) -> str:
    """日付文字列から前営業日（土日スキップ）のパスを返す。

    月曜なら金曜、それ以外は前日を返す。

    Args:
        date_str: YYYY/MM/DD形式

    Returns:
        前営業日のYYYY/MM/DD文字列
    """
    parts = date_str.replace("-", "/").split("/")
    d = date(int(parts[0]), int(parts[1]), int(parts[2]))
    if d.weekday() == 0:
        prev = d - timedelta(days=3)
    elif d.weekday() == 6:
        prev = d - timedelta(days=2)
    elif d.weekday() == 5:
        prev = d - timedelta(days=1)
    else:
        prev = d - timedelta(days=1)
    return prev.strftime("%Y-%m-%d")


# --- Wikiパーサー ---

def parse_wiki_table(content: str) -> list[dict]:
    """Wiki Markdownから課題一覧テーブルをパースする。

    Args:
        content: WikiページのMarkdown文字列

    Returns:
        課題dictのリスト
    """
    issues = []
    in_table = False

    for line in content.split("\n"):
        line = line.strip()
        if "課題キー" in line and "ステータス" in line:
            in_table = True
            continue
        if in_table and re.match(r"^\|[-|\s]+\|$", line):
            continue
        if in_table and line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 5:
                issues.append({
                    "key": cells[0],
                    "title": cells[1],
                    "status": cells[2],
                    "assignee": cells[3],
                    "priority": cells[4],
                })
        elif in_table and not line.startswith("|"):
            in_table = False

    return issues


def _parse_completed_count(content: str) -> int:
    match = re.search(r"完了済み:\s*(\d+)件", content)
    return int(match.group(1)) if match else 0


def parse_wiki_content(content: str) -> dict:
    """Wiki Markdownから課題一覧と完了件数をパースする。

    Args:
        content: WikiページのMarkdown文字列

    Returns:
        {"issues": [...], "by_status": {...}, "completed": int}
    """
    issues = parse_wiki_table(content)
    by_status = dict(Counter(i["status"] for i in issues))
    completed = _parse_completed_count(content)
    return {"issues": issues, "by_status": by_status, "completed": completed}


# --- ページ生成 ---

def _build_overall_page(
    date_path: str,
    issues: list[dict],
    completed_issues: list[dict],
    status_counter: Counter,
    assignee_issues: dict[str, list],
    assignee_completed: dict[str, list],
    all_assignees: list[str],
    prev_data: dict | None = None,
) -> str:
    lines = [f"# 日次レポート（全体） {date_path}", ""]

    lines.append(_build_summary_section(status_counter, len(completed_issues)))
    lines.append("")

    if prev_data is not None:
        lines.append(_build_diff_section(issues, len(completed_issues), status_counter, prev_data))
        lines.append("")

    # 担当者別サマリー
    lines.append(_build_assignee_summary(assignee_issues, assignee_completed, all_assignees))
    lines.append("")

    lines.append(_build_issues_table(issues))
    return "\n".join(lines)


def _build_assignee_summary(
    assignee_issues: dict[str, list],
    assignee_completed: dict[str, list],
    all_assignees: list[str],
) -> str:
    lines = [
        "## 担当者別",
        "| 担当者 | 未完了 | 完了済み |",
        "|--------|--------|---------|",
    ]
    # 未割当も含める
    for name in list(all_assignees) + ["未割当"]:
        open_count = len(assignee_issues.get(name, []))
        done_count = len(assignee_completed.get(name, []))
        if open_count == 0 and done_count == 0:
            continue
        lines.append(f"| {name} | {open_count} | {done_count} |")
    return "\n".join(lines)


def _build_summary_section(status_counter: Counter, completed_count: int) -> str:
    lines = [
        "## サマリー",
        "| ステータス | 件数 |",
        "|-----------|------|",
    ]
    for status, count in sorted(status_counter.items()):
        lines.append(f"| {status} | {count} |")
    lines.append(f"| **完了済み** | **{completed_count}** |")
    lines.append("")
    lines.append(f"完了済み: {completed_count}件")
    return "\n".join(lines)


def _build_issues_table(issues: list[dict]) -> str:
    lines = [
        "## 課題一覧",
        "| 課題キー | タイトル | ステータス | 担当者 | 優先度 |",
        "|---------|---------|-----------|--------|--------|",
    ]
    for issue in issues:
        key = issue.get("issueKey", "")
        summary = issue.get("summary", "")
        status = issue.get("status", {}).get("name", "")
        assignee = issue.get("assignee")
        assignee_name = assignee.get("name", "") if assignee else ""
        priority = issue.get("priority", {}).get("name", "")
        lines.append(f"| {key} | {summary} | {status} | {assignee_name} | {priority} |")
    return "\n".join(lines)


def _build_assignee_page(
    assignee_name: str,
    date_path: str,
    issues: list[dict],
    completed_issues: list[dict],
    prev_data: dict | None,
) -> str:
    """担当者別レポートページのMarkdownを生成する。"""
    status_counter = Counter(
        issue.get("status", {}).get("name", "不明") for issue in issues
    )

    lines = [f"# {assignee_name} - 日次レポート {date_path}", ""]
    lines.append(_build_summary_section(status_counter, len(completed_issues)))
    lines.append("")

    if prev_data is not None:
        lines.append(_build_diff_section(issues, len(completed_issues), status_counter, prev_data))
        lines.append("")

    lines.append(_build_issues_table(issues))
    return "\n".join(lines)


def _build_diff_section(
    issues: list[dict],
    completed_count: int,
    status_counter: Counter,
    prev_data: dict,
) -> str:
    """前日比セクションを生成する。"""
    prev_status = prev_data["by_status"]
    prev_keys = {i["key"] for i in prev_data["issues"]}
    curr_keys = {i.get("issueKey", "") for i in issues}
    prev_completed = prev_data.get("completed", 0)

    # ステータスが変わった課題
    prev_by_key = {i["key"]: i["status"] for i in prev_data["issues"]}
    progressed_count = 0
    for issue in issues:
        key = issue.get("issueKey", "")
        curr_status = issue.get("status", {}).get("name", "")
        old_status = prev_by_key.get(key)
        if old_status and old_status != curr_status:
            progressed_count += 1

    new_count = len(curr_keys - prev_keys)
    newly_completed = len(prev_keys - curr_keys)
    total_prev = len(prev_data["issues"])
    total_curr = len(issues)
    diff_total = total_curr - total_prev
    diff_completed = completed_count - prev_completed

    lines = [
        "## 前日比",
        "| 指標 | 値 |",
        "|------|-----|",
        f"| 未完了課題数 | {total_curr}件（前日比 {_fmt_diff(diff_total)}） |",
        f"| 完了済み | {completed_count}件（前日比 {_fmt_diff(diff_completed)}） |",
        f"| 新規追加 | {new_count}件 |",
        f"| 今日完了 | {newly_completed}件 |",
        f"| ステータス変更 | {progressed_count}件 |",
    ]

    # ステータス別の前日比
    all_statuses = sorted(set(list(status_counter.keys()) + list(prev_status.keys())))
    lines.append("")
    lines.append("### ステータス別増減")
    lines.append("| ステータス | 前日 | 今日 | 増減 |")
    lines.append("|-----------|------|------|------|")
    for s in all_statuses:
        prev_c = prev_status.get(s, 0)
        curr_c = status_counter.get(s, 0)
        lines.append(f"| {s} | {prev_c} | {curr_c} | {_fmt_diff(curr_c - prev_c)} |")

    return "\n".join(lines)


def _fmt_diff(n: int) -> str:
    if n > 0:
        return f"+{n}"
    return str(n)
