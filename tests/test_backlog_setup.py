from datetime import date, datetime
from unittest.mock import patch

from src.services.backlog_setup import (
    ensure_preset, ensure_issue_types, ensure_issue_type_templates,
    ensure_statuses, calc_schedule, load_issue_type_templates,
    _round_half, _remaining_work_hours, ISSUE_TYPES, STATUSES,
    MAX_STATUSES, StatusLimitExceeded,
)


def test_ensure_preset_all_exist():
    """カテゴリ・ステータスが既に存在する場合はそのまま返す。"""
    mock_categories = [{"id": 200, "name": "AI生成"}]
    all_statuses = [{"id": 1, "name": "未対応"}, {"id": 10, "name": "AI下書き"}]
    for i, (name, _) in enumerate(STATUSES):
        if name != "AI下書き":
            all_statuses.append({"id": 100 + i, "name": name})

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_categories.return_value = mock_categories
        mock_client.get_statuses.return_value = all_statuses

        preset = ensure_preset("TEST")

    assert preset.category_ai_generated_id == 200
    assert preset.status_ai_draft_id == 10
    mock_client.add_category.assert_not_called()
    mock_client.add_status.assert_not_called()


def test_ensure_preset_create_missing():
    """カテゴリ・ステータスが未作成の場合は新規作成する。"""
    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_categories.return_value = []
        mock_client.get_statuses.return_value = [{"id": 1, "name": "未対応"}]
        mock_client.add_category.return_value = {"id": 300, "name": "AI生成"}
        mock_client.add_status.side_effect = lambda pk, name, color: {"id": 900, "name": name}

        preset = ensure_preset("TEST")

    assert preset.category_ai_generated_id == 300
    assert preset.status_ai_draft_id == 900
    mock_client.add_category.assert_called_once_with("TEST", "AI生成")


# --- 種別確保 ---

def test_ensure_issue_types_all_exist():
    """種別がすべて存在する場合は作成しない。"""
    existing = [{"id": i, "name": name} for i, (name, _) in enumerate(ISSUE_TYPES)]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_issue_types.return_value = existing
        result = ensure_issue_types("TEST")

    assert len(result) == len(ISSUE_TYPES)
    mock_client.add_issue_type.assert_not_called()


def test_ensure_issue_types_create_missing():
    """不足している種別のみ作成する。"""
    existing = [{"id": 1, "name": "タスク"}, {"id": 2, "name": "バグ"}]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_issue_types.return_value = existing
        mock_client.add_issue_type.side_effect = lambda pk, name, color: {"id": 999, "name": name}
        result = ensure_issue_types("TEST")

    assert result["タスク"] == 1
    assert result["バグ"] == 2
    assert result["課題"] == 999
    created_names = [call.args[1] for call in mock_client.add_issue_type.call_args_list]
    assert "タスク" not in created_names
    assert "バグ" not in created_names
    assert "課題" in created_names


# --- ステータス確保 ---

def test_ensure_statuses_all_exist():
    """ステータスがすべて存在する場合は作成しない。"""
    existing = [{"id": 1, "name": "未対応"}, {"id": 2, "name": "処理中"}]
    existing += [{"id": i + 10, "name": name} for i, (name, _) in enumerate(STATUSES)]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_statuses.return_value = existing
        result = ensure_statuses("TEST")

    assert result["AI下書き"] == 10
    assert result["未対応"] == 1
    mock_client.add_status.assert_not_called()


def test_ensure_statuses_create_missing():
    """不足しているステータスのみ作成する。"""
    existing = [{"id": 1, "name": "未対応"}, {"id": 10, "name": "AI下書き"}]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_statuses.return_value = existing
        mock_client.add_status.side_effect = lambda pk, name, color: {"id": 999, "name": name}
        result = ensure_statuses("TEST")

    assert result["未対応"] == 1
    assert result["AI下書き"] == 10
    assert result["遅延-処理中"] == 999
    created_names = [call.args[1] for call in mock_client.add_status.call_args_list]
    assert "AI下書き" not in created_names
    assert "遅延-処理中" in created_names
    assert "レビュー: 済" in created_names


def test_ensure_statuses_limit_exceeded():
    """上限を超える場合はStatusLimitExceededを送出する。"""
    # 既に12個あって、追加が必要なステータスがある場合
    existing = [{"id": i, "name": f"status_{i}"} for i in range(MAX_STATUSES)]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_statuses.return_value = existing
        try:
            ensure_statuses("TEST")
            assert False, "StatusLimitExceeded should have been raised"
        except StatusLimitExceeded as e:
            assert "上限" in str(e)
        mock_client.add_status.assert_not_called()


# --- テンプレート確保 ---

def test_load_issue_type_templates():
    """JSONファイルからテンプレートを読み込める。"""
    templates = load_issue_type_templates()
    assert "タスク" in templates
    assert "summary" in templates["タスク"]
    assert "description" in templates["タスク"]
    assert "目的" in templates["タスク"]["description"]
    assert "完了条件" in templates["タスク"]["description"]


def test_ensure_templates_set_when_empty():
    """テンプレート未設定の種別にテンプレートを設定する。"""
    current = [{"id": 1, "name": "タスク", "templateSummary": None, "templateDescription": None}]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_issue_types.return_value = current
        result = ensure_issue_type_templates("TEST")

    assert result["タスク"] == "updated"
    mock_client.update_issue_type.assert_called_once()
    call_args = mock_client.update_issue_type.call_args
    assert call_args.args == ("TEST", 1)
    assert "〜する。" in call_args.kwargs["templateSummary"]


def test_ensure_templates_overwrite_existing():
    """テンプレート設定済みでもJSON定義で上書きする。"""
    current = [{"id": 1, "name": "タスク", "templateSummary": "古いテンプレ", "templateDescription": "古い説明"}]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_issue_types.return_value = current
        result = ensure_issue_type_templates("TEST")

    assert result["タスク"] == "updated"
    mock_client.update_issue_type.assert_called_once()


def test_ensure_templates_skip_unknown_type():
    """JSONに定義がない種別はスキップする。"""
    current = [{"id": 99, "name": "未知の種別", "templateSummary": None, "templateDescription": None}]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_issue_types.return_value = current
        result = ensure_issue_type_templates("TEST")

    assert result["未知の種別"] == "skipped"
    mock_client.update_issue_type.assert_not_called()


# --- 0.5h丸め ---

def test_round_half_exact():
    assert _round_half(4.0) == 4.0

def test_round_half_ceil():
    """0.5h未満の端数は切り上げ。"""
    assert _round_half(4.1) == 4.5
    assert _round_half(4.3) == 4.5

def test_round_half_at_boundary():
    assert _round_half(4.5) == 4.5

def test_round_half_over():
    assert _round_half(4.6) == 5.0


# --- 残り作業時間 ---

def test_remaining_morning():
    """9:00始業前 → 1日分(8.5h)。"""
    now = datetime(2026, 3, 23, 8, 0)  # 月曜8:00
    assert _remaining_work_hours(now) == 8.5

def test_remaining_midday():
    """14:00 → 残り3.5h(17:30-14:00)。"""
    now = datetime(2026, 3, 23, 14, 0)  # 月曜14:00
    assert _remaining_work_hours(now) == 3.5

def test_remaining_after_hours():
    """17:30以降 → 0h。"""
    now = datetime(2026, 3, 23, 18, 0)  # 月曜18:00
    assert _remaining_work_hours(now) == 0.0

def test_remaining_weekend():
    """土曜 → 0h。"""
    now = datetime(2026, 3, 28, 10, 0)  # 土曜10:00
    assert _remaining_work_hours(now) == 0.0

def test_remaining_rounds_down():
    """端数は0.5h切り捨て（例: 残り2h20m → 2.0h）。"""
    now = datetime(2026, 3, 23, 15, 10)  # 残り2h20m
    assert _remaining_work_hours(now) == 2.0


# --- スケジュール算出 ---

def test_calc_schedule_fits_today():
    """残り時間内に収まる → 当日終了。"""
    # 月曜10:00、残り7.5h、予定4h → 当日
    now = datetime(2026, 3, 23, 10, 0)
    s = calc_schedule(estimated_hours=4.0, now=now)
    assert s.start_date == "2026-03-23"
    assert s.due_date == "2026-03-23"
    assert s.estimated_hours == 4.0


def test_calc_schedule_spills_to_tomorrow():
    """残り時間を超える → 翌営業日。"""
    # 月曜14:00、残り3.5h、予定8h → 超過4.5h → 翌日(火)
    now = datetime(2026, 3, 23, 14, 0)
    s = calc_schedule(estimated_hours=8.0, now=now)
    assert s.start_date == "2026-03-23"
    assert s.due_date == "2026-03-24"


def test_calc_schedule_after_hours():
    """業務時間外 → 翌営業日から起算。"""
    # 月曜18:00、残り0h、予定8h → 翌日(火)に8h → 火曜中に終わる
    now = datetime(2026, 3, 23, 18, 0)
    s = calc_schedule(estimated_hours=8.0, now=now)
    assert s.start_date == "2026-03-23"
    assert s.due_date == "2026-03-24"


def test_calc_schedule_friday_spill_to_monday():
    """金曜午後に溢れ → 翌週月曜。"""
    # 金曜16:00、残り1.5h、予定4h → 超過2.5h → 翌営業日(月)
    now = datetime(2026, 3, 27, 16, 0)
    s = calc_schedule(estimated_hours=4.0, now=now)
    assert s.start_date == "2026-03-27"
    assert s.due_date == "2026-03-30"


def test_calc_schedule_saturday():
    """土曜 → 翌週月曜から起算。"""
    # 土曜、予定8.5h → 月曜1日分 → 月曜終了
    now = datetime(2026, 3, 28, 10, 0)
    s = calc_schedule(estimated_hours=8.5, now=now)
    assert s.start_date == "2026-03-28"
    assert s.due_date == "2026-03-30"


def test_calc_schedule_multi_day():
    """複数日にまたがる場合。"""
    # 月曜9:00、残り8.5h、予定20h → 超過11.5h → ceil(11.5/8.5)=2日 → 水曜
    now = datetime(2026, 3, 23, 9, 0)
    s = calc_schedule(estimated_hours=20.0, now=now)
    assert s.start_date == "2026-03-23"
    assert s.due_date == "2026-03-25"


def test_calc_schedule_default_hours():
    """estimated_hours=None → デフォルト8.0h。"""
    now = datetime(2026, 3, 23, 9, 0)
    s = calc_schedule(None, now=now)
    assert s.estimated_hours == 8.0


def test_calc_schedule_rounds_to_half():
    """端数は0.5h単位に丸められる。"""
    now = datetime(2026, 3, 23, 9, 0)
    s = calc_schedule(estimated_hours=3.3, now=now)
    assert s.estimated_hours == 3.5


def test_calc_schedule_exact_remaining():
    """残り時間とぴったり同じ → 当日終了。"""
    # 月曜9:00、残り8.5h、予定8.5h → 当日
    now = datetime(2026, 3, 23, 9, 0)
    s = calc_schedule(estimated_hours=8.5, now=now)
    assert s.start_date == "2026-03-23"
    assert s.due_date == "2026-03-23"
