from unittest.mock import patch

from src.services import report_generator
from src.services.report_generator import parse_wiki_table, parse_wiki_content, get_prev_business_date_path


MOCK_ISSUES = [
    {
        "issueKey": "NOHARATEST-1",
        "summary": "ログイン修正",
        "status": {"id": 1, "name": "処理中"},
        "assignee": {"id": 100, "name": "野原太郎"},
        "priority": {"id": 2, "name": "高"},
    },
    {
        "issueKey": "NOHARATEST-2",
        "summary": "API追加",
        "status": {"id": 2, "name": "未対応"},
        "assignee": {"id": 200, "name": "田中一郎"},
        "priority": {"id": 3, "name": "中"},
    },
    {
        "issueKey": "NOHARATEST-3",
        "summary": "テスト追加",
        "status": {"id": 1, "name": "処理中"},
        "assignee": {"id": 100, "name": "野原太郎"},
        "priority": {"id": 4, "name": "低"},
    },
    {
        "issueKey": "NOHARATEST-4",
        "summary": "未割当タスク",
        "status": {"id": 2, "name": "未対応"},
        "assignee": None,
        "priority": {"id": 3, "name": "中"},
    },
]

MOCK_USERS = [
    {"id": 100, "name": "野原太郎", "userId": "nohara.taro"},
    {"id": 200, "name": "田中一郎", "userId": "tanaka.ichiro"},
]


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_generate_daily_report(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25")

    assert result["summary"]["total"] == 4
    assert result["summary"]["by_status"]["処理中"] == 2
    assert result["summary"]["by_status"]["未対応"] == 2

    # 全体ページ + 担当者2名（未割当はページなし）
    assert len(result["pages"]) == 3

    overall = result["pages"][0]
    assert overall["name"] == "日次レポート/2026-03-25/全体"
    assert "# 日次レポート（全体） 2026-03-25" in overall["content"]
    assert "NOHARATEST-1" in overall["content"]
    assert "NOHARATEST-4" in overall["content"]

    # 担当者別ページ（ソート順）
    assert result["pages"][1]["name"] == "日次レポート/2026-03-25/田中一郎"
    assert result["pages"][2]["name"] == "日次レポート/2026-03-25/野原太郎"


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_overall_page_has_assignee_summary(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25")
    content = result["pages"][0]["content"]
    assert "## 担当者別" in content
    assert "野原太郎" in content
    assert "田中一郎" in content


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_overall_page_has_summary_table(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25")
    content = result["pages"][0]["content"]
    assert "## サマリー" in content
    assert "| 処理中 | 2 |" in content


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_assignee_page_content(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25")
    nohara_page = result["pages"][2]
    assert "野原太郎" in nohara_page["name"]
    assert "NOHARATEST-1" in nohara_page["content"]
    assert "NOHARATEST-3" in nohara_page["content"]
    assert "NOHARATEST-2" not in nohara_page["content"]


MOCK_ISSUES_WITH_SCHEDULE = MOCK_ISSUES + [
    {
        "issueKey": "NOHARATEST-99",
        "summary": "定例ミーティング",
        "status": {"id": 1, "name": "処理中"},
        "issueType": {"id": 999, "name": "スケジュール"},
        "assignee": {"id": 100, "name": "野原太郎"},
        "priority": {"id": 3, "name": "中"},
    },
]


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES_WITH_SCHEDULE)
def test_schedule_issue_type_excluded(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25")
    assert result["summary"]["total"] == 4
    all_content = "\n".join(p["content"] for p in result["pages"])
    assert "NOHARATEST-99" not in all_content


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=[])
@patch("src.services.report_generator.backlog_client.get_issues", return_value=[])
def test_generate_empty_issues(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25")
    assert result["summary"]["total"] == 0
    assert len(result["pages"]) == 1


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_date_format_with_hyphen(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026-03-25")
    assert result["pages"][0]["name"] == "日次レポート/2026-03-25/全体"


# --- parse_wiki_table ---

SAMPLE_WIKI = """# 野原太郎 - 日次レポート 2026-03-24

## サマリー
| ステータス | 件数 |
|-----------|------|
| 未対応 | 1 |
| 処理中 | 1 |

## 課題一覧
| 課題キー | タイトル | ステータス | 担当者 | 優先度 |
|---------|---------|-----------|--------|--------|
| NOHARATEST-1 | ログイン修正 | 未対応 | 野原太郎 | 高 |
| NOHARATEST-3 | テスト追加 | 処理中 | 野原太郎 | 低 |
"""


def test_parse_wiki_table():
    issues = parse_wiki_table(SAMPLE_WIKI)
    assert len(issues) == 2
    assert issues[0]["key"] == "NOHARATEST-1"
    assert issues[0]["status"] == "未対応"
    assert issues[1]["key"] == "NOHARATEST-3"


def test_parse_wiki_table_empty():
    issues = parse_wiki_table("# 空のページ\nテキストだけ")
    assert len(issues) == 0


def test_parse_wiki_content():
    data = parse_wiki_content(SAMPLE_WIKI)
    assert len(data["issues"]) == 2
    assert data["by_status"]["未対応"] == 1
    assert data["by_status"]["処理中"] == 1
    assert data["completed"] == 0


def test_parse_wiki_content_with_completed():
    wiki = SAMPLE_WIKI + "\n| **完了済み** | **3** |\n\n完了済み: 3件\n"
    data = parse_wiki_content(wiki)
    assert data["completed"] == 3


# --- get_prev_business_date_path ---

def test_prev_business_date_weekday():
    assert get_prev_business_date_path("2026/03/25") == "2026-03-24"


def test_prev_business_date_monday():
    assert get_prev_business_date_path("2026/03/23") == "2026-03-20"


def test_prev_business_date_tuesday():
    assert get_prev_business_date_path("2026/03/24") == "2026-03-23"


def test_prev_business_date_saturday():
    assert get_prev_business_date_path("2026/03/21") == "2026-03-20"


def test_prev_business_date_sunday():
    assert get_prev_business_date_path("2026/03/22") == "2026-03-20"


def test_prev_business_date_month_boundary():
    assert get_prev_business_date_path("2026/03/02") == "2026-02-27"


def test_prev_business_date_year_boundary():
    assert get_prev_business_date_path("2026/01/05") == "2026-01-02"


# --- 前日比つきレポート生成 ---

PREV_WIKI_OVERALL = """# 日次レポート（全体） 2026-03-24

## サマリー
| ステータス | 件数 |
|-----------|------|
| 未対応 | 3 |
| 処理中 | 1 |
| **完了済み** | **1** |

完了済み: 1件

## 課題一覧
| 課題キー | タイトル | ステータス | 担当者 | 優先度 |
|---------|---------|-----------|--------|--------|
| NOHARATEST-1 | ログイン修正 | 未対応 | 野原太郎 | 高 |
| NOHARATEST-2 | API追加 | 未対応 | 田中一郎 | 中 |
| NOHARATEST-3 | テスト追加 | 処理中 | 野原太郎 | 低 |
| NOHARATEST-5 | 削除された課題 | 未対応 | 野原太郎 | 中 |
"""

PREV_WIKI_NOHARA = """# 野原太郎 - 日次レポート 2026-03-24

## サマリー
| ステータス | 件数 |
|-----------|------|
| 未対応 | 2 |
| **完了済み** | **0** |

完了済み: 0件

## 課題一覧
| 課題キー | タイトル | ステータス | 担当者 | 優先度 |
|---------|---------|-----------|--------|--------|
| NOHARATEST-1 | ログイン修正 | 未対応 | 野原太郎 | 高 |
| NOHARATEST-5 | 削除された課題 | 未対応 | 野原太郎 | 中 |
"""


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_overall_page_with_prev_data(mock_issues, mock_users):
    prev_wikis = {
        "日次レポート/2026-03-24/全体": PREV_WIKI_OVERALL,
        "日次レポート/2026-03-24/野原太郎": PREV_WIKI_NOHARA,
    }
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25", prev_wikis)
    overall = result["pages"][0]
    assert "## 前日比" in overall["content"]
    assert "ステータス別増減" in overall["content"]


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_assignee_page_with_prev_data(mock_issues, mock_users):
    prev_wikis = {
        "日次レポート/2026-03-24/野原太郎": PREV_WIKI_NOHARA,
    }
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25", prev_wikis)

    nohara_page = result["pages"][2]
    content = nohara_page["content"]

    assert "## 前日比" in content
    assert "未完了課題数" in content
    assert "新規追加" in content
    assert "今日完了" in content
    assert "ステータス変更" in content

    # 前日比なし担当者（田中）は前日比セクションなし
    tanaka_page = result["pages"][1]
    assert "## 前日比" not in tanaka_page["content"]


@patch("src.services.report_generator.backlog_client.get_project_users", return_value=MOCK_USERS)
@patch("src.services.report_generator.backlog_client.get_issues", return_value=MOCK_ISSUES)
def test_no_prev_wikis_no_diff_section(mock_issues, mock_users):
    result = report_generator.generate_daily_report("NOHARATEST", "2026/03/25", prev_wikis=None)
    for page in result["pages"]:
        assert "## 前日比" not in page["content"]
