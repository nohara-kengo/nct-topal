import json
from unittest.mock import patch, MagicMock

from src.services.intent_classifier import classify


def _mock_claude_response(text: str):
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.text = text
    mock_response.content = [mock_block]
    return mock_response


MOCK_SSM = {
    "src.services.intent_classifier.ssm_client.get_anthropic_api_key": "test-key",
    "src.services.intent_classifier.ssm_client.get_claude_model": "claude-sonnet-4-20250514",
}


def _ssm_patches():
    patches = []
    for target, return_value in MOCK_SSM.items():
        p = patch(target, return_value=return_value)
        patches.append(p)
    return patches


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_create(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "action": "create",
            "project_key": "NOHARATEST",
            "task_id": None,
            "title": "新機能の追加",
            "priority": "高",
            "due_date": "2026-04-01",
        }))

        result = classify("[NOHARATEST] この件、課題にしておいて")

        assert result["action"] == "create"
        assert result["project_key"] == "NOHARATEST"
        assert result["task_id"] is None
        assert result["title"] == "新機能の追加"
        assert result["priority"] == "高"
        assert result["due_date"] == "2026-04-01"
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_update(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "action": "update",
            "project_key": "NOHARATEST",
            "task_id": "NOHARATEST-123",
            "title": "優先度変更",
            "priority": "高",
            "due_date": None,
        }))

        result = classify("NOHARATEST-123の優先度上げて")

        assert result["action"] == "update"
        assert result["project_key"] == "NOHARATEST"
        assert result["task_id"] == "NOHARATEST-123"
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_no_project_key(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "action": "create",
            "project_key": None,
            "task_id": None,
            "title": "何かのタスク",
            "priority": "中",
            "due_date": None,
        }))

        result = classify("この件、課題にして")

        assert result["action"] == "create"
        assert result["project_key"] is None
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_with_code_fence(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        response_text = '```json\n{"action": "create", "project_key": "NOHARATEST", "task_id": null, "title": "テスト", "priority": "中", "due_date": null}\n```'
        mock_client.messages.create.return_value = _mock_claude_response(response_text)

        result = classify("[NOHARATEST] テストタスク作って")

        assert result["action"] == "create"
        assert result["title"] == "テスト"
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_invalid_action_raises(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "action": "delete",
            "project_key": None,
            "task_id": None,
            "title": "削除",
            "priority": "中",
            "due_date": None,
        }))

        try:
            classify("これ削除して")
            assert False, "ValueErrorが発生すべき"
        except ValueError:
            pass
    finally:
        patch.stopall()
