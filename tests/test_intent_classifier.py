import json
from unittest.mock import patch, MagicMock

from src.services.intent_classifier import classify, extract_project_key


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
            "estimated_hours": 4.0,
            "assignee": "田中",
        }))

        result = classify("[NOHARATEST] この件、課題にしておいて")

        assert result["action"] == "create"
        assert result["project_key"] == "NOHARATEST"
        assert result["task_id"] is None
        assert result["title"] == "新機能の追加"
        assert result["priority"] == "高"
        assert result["estimated_hours"] == 4.0
        assert result["assignee"] == "田中"
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
            "estimated_hours": 2.0,
            "assignee": "田中",
        }))

        result = classify("NOHARATEST-123の優先度上げて")

        assert result["action"] == "update"
        assert result["project_key"] == "NOHARATEST"
        assert result["task_id"] == "NOHARATEST-123"
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_no_project_key(mock_anthropic_cls):
    """project_keyがnullでもValueErrorにはならない（webhook handler側でチェック）。"""
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
            "estimated_hours": None,
            "assignee": None,
        }))

        result = classify("この件、課題にして")
        assert result["project_key"] is None
        assert result["estimated_hours"] is None
        assert result["assignee"] is None
        assert result["priority"] == "中"
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_no_title_raises(mock_anthropic_cls):
    """titleがnullの場合はValueError。"""
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "action": "create",
            "project_key": "NOHARATEST",
            "task_id": None,
            "title": "",
            "priority": "中",
            "estimated_hours": 4.0,
            "assignee": "田中",
        }))

        try:
            classify("よくわからないメッセージ")
            assert False, "ValueErrorが発生すべき"
        except ValueError as e:
            assert "title" in str(e)
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_with_code_fence(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        response_text = '```json\n{"action": "create", "project_key": "NOHARATEST", "task_id": null, "title": "テスト", "priority": "中", "estimated_hours": 8.0, "assignee": "田中"}\n```'
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
            "project_key": "NOHARATEST",
            "task_id": None,
            "title": "削除",
            "priority": "中",
            "estimated_hours": 4.0,
            "assignee": "田中",
        }))

        try:
            classify("これ削除して")
            assert False, "ValueErrorが発生すべき"
        except ValueError:
            pass
    finally:
        patch.stopall()


# --- extract_project_key ---

def test_extract_project_key_bracket():
    assert extract_project_key("[NOHARATEST] タスク作って") == "NOHARATEST"


def test_extract_project_key_issue_key():
    assert extract_project_key("NOHARATEST-123の優先度上げて") == "NOHARATEST"


def test_extract_project_key_none():
    assert extract_project_key("この件、課題にして") is None


# --- classify with members ---

MOCK_MEMBERS = [
    {"id": 100, "name": "田中 一郎", "userId": "tanaka.ichiro"},
    {"id": 200, "name": "野原 太郎", "userId": "nohara.taro"},
]


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_with_members_resolves_assignee_id(mock_anthropic_cls):
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
            "priority": "中",
            "estimated_hours": 4.0,
            "assignee": "田中 一郎",
            "assignee_id": 100,
        }))

        result = classify("[NOHARATEST] たなかさんに割り当てて", members=MOCK_MEMBERS)

        assert result["assignee_id"] == 100
        assert result["assignee"] == "田中 一郎"
        # メンバー一覧がプロンプトに含まれることを確認
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "tanaka.ichiro" in call_kwargs["system"]
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_report(mock_anthropic_cls):
    for p in _ssm_patches():
        p.start()
    try:
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_claude_response(json.dumps({
            "action": "report",
            "project_key": "NOHARATEST",
            "task_id": None,
            "title": None,
            "priority": None,
            "estimated_hours": None,
            "assignee": None,
        }))

        result = classify("[NOHARATEST] レポート出して")

        assert result["action"] == "report"
        assert result["project_key"] == "NOHARATEST"
        assert result["title"] is None
    finally:
        patch.stopall()


@patch("src.services.intent_classifier.anthropic.Anthropic")
def test_classify_without_members_no_assignee_id(mock_anthropic_cls):
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
            "priority": "中",
            "estimated_hours": 4.0,
            "assignee": "田中",
            "assignee_id": None,
        }))

        result = classify("[NOHARATEST] 田中さんに割り当てて")

        assert result["assignee_id"] is None
        assert result["assignee"] == "田中"
        # メンバー一覧がプロンプトに含まれないことを確認
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "tanaka.ichiro" not in call_kwargs["system"]
    finally:
        patch.stopall()
