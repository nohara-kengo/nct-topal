"""Backlogプロジェクトに必要なカテゴリ・ステータスを確保する共通コンポーネント。"""

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from src.services import backlog_client

logger = logging.getLogger(__name__)

# ToPalが使うカテゴリ・ステータスの定義
CATEGORY_AI_GENERATED = "AI生成"
STATUS_AI_DRAFT = "AI下書き"
STATUS_AI_DRAFT_COLOR = "#3b9dbd"
DEFAULT_ESTIMATED_HOURS = 8.0
WORK_START = time(9, 0)
WORK_END = time(17, 30)
HOURS_PER_DAY = 8.5


@dataclass
class BacklogPreset:
    """ToPalが使うBacklogのカテゴリ・ステータスIDをまとめた値オブジェクト。"""
    category_ai_generated_id: int
    status_ai_draft_id: int


def ensure_preset(project_key: str) -> BacklogPreset:
    """「AI生成」カテゴリと「AI下書き」ステータスが存在することを保証する。

    なければ作成し、IDをまとめて返す。
    task_create / task_update の両方から呼び出す共通処理。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        BacklogPreset（カテゴリID・ステータスID）
    """
    category_id = _ensure_category(project_key)
    status_id = _ensure_status(project_key)
    return BacklogPreset(
        category_ai_generated_id=category_id,
        status_ai_draft_id=status_id,
    )


@dataclass
class Schedule:
    """開始日・終了日・予定時間をまとめた値オブジェクト。"""
    start_date: str
    due_date: str
    estimated_hours: float


def _round_half(hours: float) -> float:
    """0.5h単位に丸める（切り上げ）。"""
    return math.ceil(hours * 2) / 2


def _remaining_work_hours(now: datetime) -> float:
    """現在時刻から本日の残り作業時間を算出する（0.5h単位切り捨て）。

    Args:
        now: 現在日時

    Returns:
        本日の残り作業時間。土日や業務時間外は0.0
    """
    if now.weekday() >= 5:
        return 0.0
    current_time = now.time()
    if current_time < WORK_START:
        return HOURS_PER_DAY
    if current_time >= WORK_END:
        return 0.0
    end_dt = datetime.combine(now.date(), WORK_END)
    remaining = (end_dt - now).total_seconds() / 3600
    # 0.5h単位で切り捨て（残り時間は多く見積もらない）
    return math.floor(remaining * 2) / 2


def _next_business_day(d: date) -> date:
    """次の営業日を返す。dが営業日ならそのまま返す。"""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _add_business_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def calc_schedule(estimated_hours: float | None = None, now: datetime | None = None) -> Schedule:
    """現在時刻と予定時間から開始日・終了日を算出する。

    現在時刻の残り作業時間を考慮し、予定時間が本日中に収まるか判定する。
    収まらない場合は翌営業日以降に繰り越す。

    Args:
        estimated_hours: 予定時間（時間）。Noneの場合はデフォルト8.0h
        now: 現在日時。Noneの場合はdatetime.now()

    Returns:
        Schedule（start_date, due_date, estimated_hours）
    """
    if now is None:
        now = datetime.now()
    if estimated_hours is None:
        estimated_hours = DEFAULT_ESTIMATED_HOURS
    estimated_hours = _round_half(estimated_hours)

    start_date = now.date()
    remaining_today = _remaining_work_hours(now)

    if remaining_today > 0 and estimated_hours <= remaining_today:
        due_date = start_date
    elif remaining_today > 0:
        # 今日の残り時間では足りない → 翌営業日以降に繰り越し
        hours_left = estimated_hours - remaining_today
        work_days_needed = math.ceil(hours_left / HOURS_PER_DAY)
        due_date = _add_business_days(start_date, work_days_needed)
    else:
        # 業務時間外・土日 → 翌営業日を基準に丸ごと起算
        base = _next_business_day(start_date + timedelta(days=1))
        work_days_needed = math.ceil(estimated_hours / HOURS_PER_DAY)
        due_date = _add_business_days(base, work_days_needed - 1)

    return Schedule(
        start_date=start_date.isoformat(),
        due_date=due_date.isoformat(),
        estimated_hours=estimated_hours,
    )


def _ensure_category(project_key: str) -> int:
    categories = backlog_client.get_categories(project_key)
    existing = {c["name"]: c["id"] for c in categories}

    if CATEGORY_AI_GENERATED in existing:
        logger.info("カテゴリ '%s' は既に存在 (id=%s)", CATEGORY_AI_GENERATED, existing[CATEGORY_AI_GENERATED])
        return existing[CATEGORY_AI_GENERATED]

    logger.info("カテゴリ '%s' を作成します", CATEGORY_AI_GENERATED)
    created = backlog_client.add_category(project_key, CATEGORY_AI_GENERATED)
    logger.info("カテゴリ '%s' を作成しました (id=%s)", CATEGORY_AI_GENERATED, created["id"])
    return created["id"]


def _ensure_status(project_key: str) -> int:
    statuses = backlog_client.get_statuses(project_key)
    existing = {s["name"]: s["id"] for s in statuses}

    if STATUS_AI_DRAFT in existing:
        logger.info("ステータス '%s' は既に存在 (id=%s)", STATUS_AI_DRAFT, existing[STATUS_AI_DRAFT])
        return existing[STATUS_AI_DRAFT]

    logger.info("ステータス '%s' を作成します (color=%s)", STATUS_AI_DRAFT, STATUS_AI_DRAFT_COLOR)
    created = backlog_client.add_status(project_key, STATUS_AI_DRAFT, STATUS_AI_DRAFT_COLOR)
    logger.info("ステータス '%s' を作成しました (id=%s)", STATUS_AI_DRAFT, created["id"])
    return created["id"]
