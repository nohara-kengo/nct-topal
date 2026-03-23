"""Claude APIを使ってユーザーメッセージの意図を判定するモジュール。"""

import json
from datetime import date

import anthropic

from src.services import ssm_client


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

    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=SYSTEM_PROMPT + f"\n\n今日の日付: {today}",
        messages=[{"role": "user", "content": message}],
    )

    raw = response.content[0].text.strip()

    # JSONブロックがコードフェンスで囲まれている場合に対応
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)

    # 必須フィールドの検証（task_id以外は必須）
    if result.get("action") not in ("create", "update"):
        raise ValueError(f"不正なaction値: {result.get('action')}")

    missing = []
    for field in ("project_key", "title", "priority", "estimated_hours", "assignee"):
        if not result.get(field):
            missing.append(field)
    if missing:
        raise ValueError(f"必須フィールドが不足しています: {missing}")

    return {
        "action": result["action"],
        "project_key": result["project_key"],
        "task_id": result.get("task_id"),
        "title": result["title"],
        "priority": result["priority"],
        "estimated_hours": result["estimated_hours"],
        "assignee": result["assignee"],
    }
