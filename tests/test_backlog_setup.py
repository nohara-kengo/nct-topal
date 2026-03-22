from datetime import date, datetime
from unittest.mock import patch

from src.services.backlog_setup import ensure_preset, calc_schedule, _round_half, _remaining_work_hours


def test_ensure_preset_all_exist():
    """カテゴリ・ステータスが既に存在する場合はそのまま返す。"""
    mock_categories = [{"id": 200, "name": "AI生成"}, {"id": 201, "name": "その他"}]
    mock_statuses = [{"id": 1, "name": "未対応"}, {"id": 10, "name": "AI下書き"}]

    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_categories.return_value = mock_categories
        mock_client.get_statuses.return_value = mock_statuses

        preset = ensure_preset("TEST")

    assert preset.category_ai_generated_id == 200
    assert preset.status_ai_draft_id == 10
    mock_client.add_category.assert_not_called()
    mock_client.add_status.assert_not_called()


def test_ensure_preset_create_both():
    """カテゴリ・ステータスが未作成の場合は新規作成する。"""
    with patch("src.services.backlog_setup.backlog_client") as mock_client:
        mock_client.get_categories.return_value = []
        mock_client.get_statuses.return_value = [{"id": 1, "name": "未対応"}]
        mock_client.add_category.return_value = {"id": 300, "name": "AI生成"}
        mock_client.add_status.return_value = {"id": 30, "name": "AI下書き"}

        preset = ensure_preset("TEST")

    assert preset.category_ai_generated_id == 300
    assert preset.status_ai_draft_id == 30
    mock_client.add_category.assert_called_once_with("TEST", "AI生成")
    mock_client.add_status.assert_called_once_with("TEST", "AI下書き", "#3b9dbd")


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
