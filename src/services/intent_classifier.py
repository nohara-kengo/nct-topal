"""Claude APIを使ってユーザーメッセージの意図を判定するモジュール。"""

import json
import logging
import time
from datetime import date

import anthropic

from src.services import ssm_client

logger = logging.getLogger(__name__)

# Claude APIリトライ設定
_MAX_RETRIES = 2
_RETRY_DELAY_SEC = 1.0


SYSTEM_PROMPT = """あなたはタスク管理アシスタントです。
ユーザーのメッセージを分析し、以下のJSON形式で意図を判定してください。

必ず以下のJSONのみを返してください（説明文は不要）:
{
  "action": "create" または "update",
  "project_key": "プロジェクトキー（例: NOHARATEST）。メッセージに含まれていない場合はnull",
  "task_id": "課題キー（例: NOHARATEST-123）。不明な場合はnull",
  "title": "要約されたタスク名",
  "priority": "高" または "中" または "低"。判断できない場合は "中",
  "estimated_hours": 予定時間（数値、時間単位）。判断できない場合はnull,
  "assignee": "担当者名。メッセージから判断できない場合はnull"
}

判定ルール:
- メッセージ内の [XXX] や「XXXプロジェクト」をproject_keyとして抽出する
- 既存の課題キー（例: NOHARATEST-123）が含まれていれば "update"。課題キーのハイフン前がproject_keyになる
- 新しいタスクの作成を依頼していれば "create"
- 曖昧な場合は "create" をデフォルトとする
- titleは簡潔に要約する（20文字以内目安）
- estimated_hoursは「2時間」「半日(4h)」「1日(8.5h)」「2日(17h)」等から判断する
- assigneeは「○○さんに」「○○担当で」等から担当者名を抽出する
"""


def _call_with_retry(client, model: str, system: str, message: str) -> str:
    """Claude APIをリトライ付きで呼び出す。

    Args:
        client: anthropic.Anthropicクライアント
        model: モデル名
        system: システムプロンプト
        message: ユーザーメッセージ

    Returns:
        レスポンステキスト
    """
    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=256,
                system=system,
                messages=[{"role": "user", "content": message}],
            )
            return response.content[0].text.strip()
        except (anthropic.RateLimitError, anthropic.APIStatusError) as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_SEC * (2 ** attempt)
                logger.warning("Claude API呼び出し失敗（リトライ %d/%d, %.1f秒後）: %s",
                               attempt + 1, _MAX_RETRIES, delay, e)
                time.sleep(delay)
            else:
                logger.error("Claude APIリトライ上限到達: %s", e)
    raise last_error


def classify(message: str) -> dict:
    """メッセージの意図をClaude APIで判定する。

    Args:
        message: 前処理済みのユーザーメッセージ

    Returns:
        意図判定結果のdict（action, project_key, task_id, title, priority, due_date）

    Raises:
        ValueError: Claude APIのレスポンスが不正なJSON形式の場合
    """
    api_key = ssm_client.get_anthropic_api_key()
    model = ssm_client.get_claude_model()

    client = anthropic.Anthropic(api_key=api_key)

    today = date.today().isoformat()

    raw = _call_with_retry(client, model, SYSTEM_PROMPT + f"\n\n今日の日付: {today}", message)

    # JSONブロックがコードフェンスで囲まれている場合に対応
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)

    # 必須フィールドの検証
    if result.get("action") not in ("create", "update"):
        raise ValueError(f"不正なaction値: {result.get('action')}")

    # action と title は常に必須。priority はデフォルト"中"にフォールバック
    # project_key, estimated_hours, assignee はnull許容（後段で補完・チェック）
    if not result.get("title"):
        raise ValueError("必須フィールドが不足しています: ['title']")

    return {
        "action": result["action"],
        "project_key": result.get("project_key"),
        "task_id": result.get("task_id"),
        "title": result["title"],
        "priority": result.get("priority") or "中",
        "estimated_hours": result.get("estimated_hours"),
        "assignee": result.get("assignee"),
    }
