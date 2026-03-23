"""Backlogプロジェクトに必要なカテゴリ・ステータスを確保する共通コンポーネント。"""

import json
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from src.services import backlog_client

logger = logging.getLogger(__name__)


class StatusLimitExceeded(Exception):
    """Backlogのステータス上限に達した場合に送出される例外。"""

# ToPalが使うカテゴリ・ステータスの定義
CATEGORY_AI_GENERATED = "AI生成"
DEFAULT_ESTIMATED_HOURS = 8.0
WORK_START = time(9, 0)
WORK_END = time(17, 30)
HOURS_PER_DAY = 8.5

# プロジェクトに必要な種別の定義（名前, 色）
# Backlog種別カラーパレット(10色):
#   #7ea800(緑) #990000(暗赤) #ff9200(橙) #2779ca(青)
#   #e30000(赤) #934981(紫) #814fbc(薄紫) #007e9a(水色)
#   #ff3265(ピンク) #666665(灰)
ISSUE_TYPES = [
    ("タスク", "#7ea800"),
    ("課題", "#ff9200"),
    ("親タスク", "#2779ca"),
    ("子タスク", "#007e9a"),
    ("親課題", "#934981"),
    ("子課題", "#814fbc"),
    ("QA", "#ff3265"),
    ("要求/要望", "#e30000"),
    ("バグ", "#990000"),
    ("親スケジュール", "#666665"),
    ("スケジュール", "#666665"),
    ("情報共有", "#007e9a"),
    ("その他", "#7ea800"),
]

# 種別テンプレートは外部JSONファイルから読み込む
# Claudeへのプロンプト入力としても利用可能
_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "templates" / "issue_type_templates.json"


def load_issue_type_templates() -> dict[str, dict[str, str]]:
    """種別テンプレートをJSONファイルから読み込む。

    Returns:
        {"タスク": {"summary": "...", "description": "..."}, ...}
    """
    with open(_TEMPLATES_PATH, encoding="utf-8") as f:
        return json.load(f)

# プロジェクトに必要なステータスの定義（名前, 色）
# 既存の「未対応」「処理中」「処理済み」「完了」はBacklogデフォルトなので定義不要
STATUSES = [
    ("AI下書き", "#3b9dbd"),
    ("遅延-処理中", "#ea2c00"),
    ("処理待", "#eda62a"),
    ("レビュー: 待", "#868cb7"),
    ("レビュー: 済", "#4caf93"),
]

# Backlogのステータス上限（デフォルト4 + カスタム8 = 12）
MAX_STATUSES = 12


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
    status_map = ensure_statuses(project_key)
    return BacklogPreset(
        category_ai_generated_id=category_id,
        status_ai_draft_id=status_map["AI下書き"],
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


def ensure_issue_types(project_key: str) -> dict[str, int]:
    """プロジェクトに必要な種別がすべて存在することを保証する。

    なければ作成し、種別名→IDのマッピングを返す。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        {"タスク": id, "課題": id, ...} の辞書
    """
    current = backlog_client.get_issue_types(project_key)
    existing = {t["name"]: t["id"] for t in current}

    result = {}
    for name, color in ISSUE_TYPES:
        if name in existing:
            logger.info("種別 '%s' は既に存在 (id=%s)", name, existing[name])
            result[name] = existing[name]
        else:
            logger.info("種別 '%s' を作成します (color=%s)", name, color)
            created = backlog_client.add_issue_type(project_key, name, color)
            result[name] = created["id"]
            logger.info("種別 '%s' を作成しました (id=%s)", name, result[name])

    return result


def ensure_issue_type_templates(project_key: str) -> dict[str, str]:
    """種別のテンプレートをJSONファイル定義で上書き設定する。

    JSONファイルの定義を正として常に設定する。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        {"タスク": "updated", "未知の種別": "skipped", ...} の辞書
    """
    templates = load_issue_type_templates()
    current = backlog_client.get_issue_types(project_key)
    result = {}

    for t in current:
        name = t["name"]
        if name not in templates:
            result[name] = "skipped"
            continue

        tmpl = templates[name]
        logger.info("種別 '%s' にテンプレートを設定します", name)
        backlog_client.update_issue_type(
            project_key,
            t["id"],
            templateSummary=tmpl["summary"],
            templateDescription=tmpl["description"],
        )
        result[name] = "updated"
        logger.info("種別 '%s' のテンプレートを設定しました", name)

    return result


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


def ensure_statuses(project_key: str) -> dict[str, int]:
    """プロジェクトに必要なカスタムステータスがすべて存在することを保証する。

    なければ作成し、ステータス名→IDのマッピングを返す。
    既存のデフォルトステータス（未対応・処理中・処理済み・完了）も含む。
    上限（12個）に達している場合は追加せずエラー情報を返す。

    Args:
        project_key: Backlogプロジェクトキー

    Returns:
        {"未対応": id, "処理中": id, ..., "AI下書き": id, ...} の辞書

    Raises:
        StatusLimitExceeded: ステータス上限に達して追加できない場合
    """
    current = backlog_client.get_statuses(project_key)
    existing = {s["name"]: s["id"] for s in current}

    missing = [(name, color) for name, color in STATUSES if name not in existing]
    if missing and len(current) + len(missing) > MAX_STATUSES:
        names = [name for name, _ in missing]
        raise StatusLimitExceeded(
            f"ステータス上限({MAX_STATUSES})を超えるため追加できません。"
            f" 現在{len(current)}個、追加予定{len(missing)}個: {names}"
        )

    result = dict(existing)
    for name, color in STATUSES:
        if name in existing:
            logger.info("ステータス '%s' は既に存在 (id=%s)", name, existing[name])
        else:
            logger.info("ステータス '%s' を作成します (color=%s)", name, color)
            created = backlog_client.add_status(project_key, name, color)
            result[name] = created["id"]
            logger.info("ステータス '%s' を作成しました (id=%s)", name, result[name])

    return result
