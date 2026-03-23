"""Claude APIを使って課題の種別・題名・説明・予定時間を生成するモジュール。"""

import json
import logging

import anthropic

from src.services import ssm_client
from src.services.backlog_setup import load_issue_type_templates

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたはプロジェクト管理の専門家です。
ユーザーのメッセージと意図判定結果をもとに、Backlogの課題を作成するための情報を生成してください。

必ず以下のJSONのみを返してください（説明文は不要）:
{
  "issue_type": "種別名",
  "title": "課題の題名",
  "description": "課題の説明",
  "estimated_hours": 数値
}

## 種別の選定ルール
- 以下の「種別一覧とテンプレート」から、メッセージの内容に最も適した種別を1つ選んでください
- 迷った場合は「タスク」を選んでください

## 題名のルール
- 必ず「〜する。」のように動詞で完結する形で書いてください
- 例: 「ログイン機能を実装する。」「APIのレスポンス速度を改善する。」
- 題名だけで何の課題か瞬時に把握できるようにしてください
- 30文字以内を目安にしてください

## 説明のルール
- 選択した種別のテンプレートの構造に従って記載してください
- テンプレート内のHTMLコメント（<!-- -->）は削除し、実際の内容に置き換えてください
- 「# 目的」「# 概要」「# 詳細」「# 完了条件」をすべて埋めてください
- ユーザーのメッセージから読み取れる情報を最大限活用してください
- メッセージから読み取れない情報は「※ 要確認」と記載してください
- 完了条件は具体的かつ検証可能な形で書いてください
- 末尾の「---」以降の注意書きもテンプレートどおりに含めてください

## 予定時間のルール
- タスクの複雑さ・規模から作業時間の概算を算出してください
- 0.5時間単位で記載してください（例: 0.5, 1.0, 2.0, 4.0, 8.5）
- 1日 = 8.5時間として換算してください
- 判断の目安:
  - 簡単な修正・設定変更: 0.5〜2.0h
  - 小規模な機能追加・調査: 2.0〜4.0h
  - 中規模な機能実装: 4.0〜8.5h
  - 大規模な機能実装・設計含む: 8.5〜17.0h
  - 複数機能にまたがる大規模対応: 17.0h以上
"""


def generate(message: str, intent: dict) -> dict:
    """ユーザーメッセージと意図判定結果から課題情報を生成する。

    Args:
        message: ユーザーの元メッセージ
        intent: intent_classifierの判定結果

    Returns:
        {"issue_type": str, "title": str, "description": str, "estimated_hours": float}

    Raises:
        ValueError: Claude APIのレスポンスが不正な場合
    """
    api_key = ssm_client.get_anthropic_api_key()
    model = ssm_client.get_claude_model()

    templates = load_issue_type_templates()
    templates_text = _format_templates(templates)

    user_prompt = f"""\
## ユーザーのメッセージ
{message}

## 意図判定結果
- アクション: {intent["action"]}
- 優先度: {intent["priority"]}
- 担当者: {intent["assignee"]}

## 種別一覧とテンプレート
{templates_text}"""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)

    # バリデーション
    missing = [f for f in ("issue_type", "title", "description", "estimated_hours") if not result.get(f)]
    if missing:
        raise ValueError(f"必須フィールドが不足しています: {missing}")

    if result["issue_type"] not in templates:
        logger.warning("不明な種別 '%s' が返されました。'タスク'にフォールバック", result["issue_type"])
        result["issue_type"] = "タスク"

    return {
        "issue_type": result["issue_type"],
        "title": result["title"],
        "description": result["description"],
        "estimated_hours": float(result["estimated_hours"]),
    }


def _format_templates(templates: dict) -> str:
    parts = []
    for name, tmpl in templates.items():
        desc_preview = tmpl["description"][:200]
        parts.append(f"### {name}\n- 題名例: {tmpl['summary']}\n- 説明テンプレート:\n```\n{tmpl['description']}\n```")
    return "\n\n".join(parts)
