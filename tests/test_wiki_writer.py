from unittest.mock import patch, MagicMock

from src.services import wiki_writer


EXISTING_WIKIS = [
    {"id": 10, "name": "日次レポート/全体/2026/03/25"},
    {"id": 11, "name": "日次レポート/全体/2026/03/24"},
    {"id": 12, "name": "日次レポート/担当者別/2026/03/24/野原太郎"},
]


@patch("src.services.wiki_writer.backlog_client.update_wiki")
@patch("src.services.wiki_writer.backlog_client.create_wiki")
@patch("src.services.wiki_writer.backlog_client.get_wikis", return_value=EXISTING_WIKIS)
def test_update_existing_wiki(mock_get, mock_create, mock_update):
    mock_update.return_value = {"id": 10, "name": "日次レポート/全体/2026/03/25"}
    pages = [{"name": "日次レポート/全体/2026/03/25", "content": "# 更新"}]

    results = wiki_writer.write_daily_report("NOHARATEST", "2026/03/25", pages)

    assert len(results) == 1
    mock_update.assert_called_once_with(10, "日次レポート/全体/2026/03/25", "# 更新", "NOHARATEST")
    mock_create.assert_not_called()


@patch("src.services.wiki_writer.backlog_client.update_wiki")
@patch("src.services.wiki_writer.backlog_client.create_wiki")
@patch("src.services.wiki_writer.backlog_client.get_wikis", return_value=EXISTING_WIKIS)
def test_create_new_wiki(mock_get, mock_create, mock_update):
    mock_create.return_value = {"id": 30, "name": "日次レポート/全体/2026/03/26"}
    pages = [{"name": "日次レポート/全体/2026/03/26", "content": "# 新規"}]

    results = wiki_writer.write_daily_report("NOHARATEST", "2026/03/26", pages)

    assert len(results) == 1
    mock_create.assert_called_once_with("NOHARATEST", "日次レポート/全体/2026/03/26", "# 新規")
    mock_update.assert_not_called()


@patch("src.services.wiki_writer.backlog_client.update_wiki")
@patch("src.services.wiki_writer.backlog_client.create_wiki")
@patch("src.services.wiki_writer.backlog_client.get_wikis", return_value=EXISTING_WIKIS)
def test_mixed_create_and_update(mock_get, mock_create, mock_update):
    mock_update.return_value = {"id": 10, "name": "日次レポート/全体/2026/03/25"}
    mock_create.return_value = {"id": 30, "name": "日次レポート/担当者別/2026/03/25/野原太郎"}
    pages = [
        {"name": "日次レポート/全体/2026/03/25", "content": "# 全体"},
        {"name": "日次レポート/担当者別/2026/03/25/野原太郎", "content": "# 野原"},
    ]

    results = wiki_writer.write_daily_report("NOHARATEST", "2026/03/25", pages)

    assert len(results) == 2
    mock_update.assert_called_once()
    mock_create.assert_called_once()


@patch("src.services.wiki_writer.backlog_client.update_wiki")
@patch("src.services.wiki_writer.backlog_client.create_wiki")
@patch("src.services.wiki_writer.backlog_client.get_wikis", return_value=[])
def test_empty_existing_wikis(mock_get, mock_create, mock_update):
    mock_create.return_value = {"id": 40, "name": "日次レポート/全体/2026/03/25"}
    pages = [{"name": "日次レポート/全体/2026/03/25", "content": "# テスト"}]

    results = wiki_writer.write_daily_report("NOHARATEST", "2026/03/25", pages)

    assert len(results) == 1
    mock_create.assert_called_once()
    mock_update.assert_not_called()


# --- fetch_prev_wikis ---

@patch("src.services.wiki_writer._fetch_wiki_content")
@patch("src.services.wiki_writer.backlog_client.get_wikis", return_value=EXISTING_WIKIS)
def test_fetch_prev_wikis(mock_get_wikis, mock_fetch):
    mock_fetch.side_effect = lambda wid, pk: f"content-{wid}"

    result = wiki_writer.fetch_prev_wikis("NOHARATEST", "2026/03/24")

    assert len(result) == 2
    assert "日次レポート/全体/2026/03/24" in result
    assert "日次レポート/担当者別/2026/03/24/野原太郎" in result
    assert result["日次レポート/全体/2026/03/24"] == "content-11"
    assert result["日次レポート/担当者別/2026/03/24/野原太郎"] == "content-12"


@patch("src.services.wiki_writer._fetch_wiki_content")
@patch("src.services.wiki_writer.backlog_client.get_wikis", return_value=EXISTING_WIKIS)
def test_fetch_prev_wikis_no_match(mock_get_wikis, mock_fetch):
    result = wiki_writer.fetch_prev_wikis("NOHARATEST", "2026/03/20")
    assert result == {}
    mock_fetch.assert_not_called()
