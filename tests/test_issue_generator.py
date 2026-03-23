import json
from unittest.mock import patch, MagicMock

from src.services.issue_generator import generate


def _mock_claude_response(text: str):
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.text = text
    mock_response.content = [mock_block]
    return mock_response


MOCK_SSM = {
    "src.services.issue_generator.ssm_client.get_anthropic_api_key": "test-key",
    "src.services.issue_generator.ssm_client.get_claude_model": "claude-sonnet-4-20250514",
}

MOCK_INTENT = {
    "action": "create",
    "project_key": "NOHARATEST",
    "task_id": None,
    "title": "ログイン機能",
    "priority": "高",
    "estimated_hours": 8.0,
    "assignee": "田中",
}


def _ssm_patches():
    return [patch(target, return_value=val) for target, val in MOCK_SSM.items()]


@patch("src.services.issue_generator.anthropic.Anthropic")
def test_generate_task(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "issue_type": "タスク",
            "title": "ログイン機能を実装する。",
            "description": "# 目的\nユーザー認証が必要\n\n# 概要\nログイン機能を実装\n\n# 詳細\nID/PWで認証\n\n# 完了条件\nログインできること",
            "estimated_hours": 8.5,
        }))

        result = generate("[NOHARATEST] ログイン機能作って", MOCK_INTENT)

        assert result["issue_type"] == "タスク"
        assert "実装する。" in result["title"]
        assert "# 目的" in result["description"]
        assert result["estimated_hours"] == 8.5
    finally:
        patch.stopall()


@patch("src.services.issue_generator.anthropic.Anthropic")
def test_generate_bug(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "issue_type": "バグ",
            "title": "ログイン画面のエラー表示を修正する。",
            "description": "# 目的\nバグ修正\n\n# 概要\nエラーが出る\n\n# 詳細\n## 再現手順\n1. ログイン\n\n## 期待動作\nログインできる\n\n## 実際の動作\nエラー\n\n## 影響範囲\n全ユーザー\n\n# 完了条件\nエラーが出ないこと",
            "estimated_hours": 2.0,
        }))

        result = generate("ログイン画面でエラーが出る", MOCK_INTENT)

        assert result["issue_type"] == "バグ"
        assert result["estimated_hours"] == 2.0
    finally:
        patch.stopall()


@patch("src.services.issue_generator.anthropic.Anthropic")
def test_generate_unknown_type_fallback(mock_anthropic_cls):
    """不明な種別が返された場合はタスクにフォールバック。"""
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "issue_type": "存在しない種別",
            "title": "何かをする。",
            "description": "# 目的\nテスト",
            "estimated_hours": 4.0,
        }))

        result = generate("何かして", MOCK_INTENT)

        assert result["issue_type"] == "タスク"
    finally:
        patch.stopall()


@patch("src.services.issue_generator.anthropic.Anthropic")
def test_generate_missing_field_raises(mock_anthropic_cls):
    """必須フィールドが欠けた場合はValueError。"""
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "issue_type": "タスク",
            "title": "",
            "description": "",
            "estimated_hours": None,
        }))

        try:
            generate("テスト", MOCK_INTENT)
            assert False, "ValueErrorが発生すべき"
        except ValueError as e:
            assert "必須フィールドが不足" in str(e)
    finally:
        patch.stopall()
