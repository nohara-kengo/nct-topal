"""Slackから実際に届くペイロードを想定したE2E検証テスト。

Claude APIの意図判定・課題生成は実際に呼び出す（ANTHROPIC_API_KEYが必要）。
Slack署名検証はモックし、Claude APIの判定結果が正しいかを検証する。
Backlog APIはモックする。
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from src.handlers.slack_webhook import handler


TEST_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def _build_slack_event(slack_payload: dict) -> dict:
    """Slack Event APIペイロードをイベント形式に変換する。"""
    body = json.dumps(slack_payload, ensure_ascii=False)
    return {
        "body": body,
        "headers": {
            "X-Slack-Request-Timestamp": "1234567890",
            "X-Slack-Signature": "v0=dummy",
        },
    }


# --- Slack Event APIペイロード例 ---

PAYLOAD_CREATE_SIMPLE = {
    "type": "event_callback",
    "team_id": "T_TEAM",
    "api_app_id": "A_APP",
    "event": {
        "type": "app_mention",
        "user": "U_NOHARA",
        "text": "<@UBOTID> [NOHARATEST] 画面のログインボタンが押せないバグがあるので課題にしてください　優先度は高で野原担当、2時間くらい",
        "channel": "C_GENERAL",
        "ts": "1234567890.123456",
    },
}

PAYLOAD_UPDATE_WITH_KEY = {
    "type": "event_callback",
    "team_id": "T_TEAM",
    "api_app_id": "A_APP",
    "event": {
        "type": "app_mention",
        "user": "U_NOHARA",
        "text": "<@UBOTID> NOHARATEST-3のLocalStack疎通テスト用タスクの優先度を高に変更して、野原担当で1時間",
        "channel": "C_GENERAL",
        "ts": "1234567891.123456",
    },
}

PAYLOAD_CREATE_WITH_DUE = {
    "type": "event_callback",
    "team_id": "T_TEAM",
    "api_app_id": "A_APP",
    "event": {
        "type": "app_mention",
        "user": "U_SATO",
        "text": "<@UBOTID> [NOHARATEST] APIのレスポンスが遅い件を調査タスクとして起票して。野原担当で半日くらい、優先度中",
        "channel": "C_GENERAL",
        "ts": "1234567892.123456",
    },
}


# --- Backlog APIモック ---

def _mock_backlog_create_issue(**kwargs):
    return {
        "issueKey": "NOHARATEST-99",
        "summary": kwargs.get("summary", "テストタスク"),
        "status": {"name": "AI下書き"},
    }


def _mock_backlog_update_issue(issue_key, project_key, **kwargs):
    return {
        "issueKey": issue_key,
        "summary": "更新されたタスク",
        "status": {"name": "処理中"},
    }


MOCK_PRESET = MagicMock()
MOCK_PRESET.category_ai_generated_id = 1
MOCK_PRESET.status_ai_draft_id = 100

MOCK_ISSUE_TYPES = [
    {"id": 1, "name": "タスク"},
    {"id": 2, "name": "課題"},
    {"id": 3, "name": "バグ"},
    {"id": 4, "name": "要求/要望"},
    {"id": 5, "name": "QA"},
]

MOCK_PROJECT_USERS = [
    {"id": 10, "userId": "nohara", "name": "野原 太郎"},
    {"id": 20, "userId": "sato", "name": "佐藤 花子"},
]


def _backlog_patches():
    return [
        patch("src.services.backlog_setup.ensure_preset", return_value=MOCK_PRESET),
        patch("src.services.backlog_setup.calc_schedule", return_value=MagicMock(
            start_date="2026-03-24", due_date="2026-03-24", estimated_hours=2.0,
        )),
        patch("src.services.backlog_client.get_issue_types", return_value=MOCK_ISSUE_TYPES),
        patch("src.services.backlog_client.get_project_users", return_value=MOCK_PROJECT_USERS),
        patch("src.services.backlog_client.create_issue", side_effect=_mock_backlog_create_issue),
        patch("src.services.backlog_client.update_issue", side_effect=_mock_backlog_update_issue),
    ]


def _ssm_patches():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return [
        patch("src.services.ssm_client.get_anthropic_api_key", return_value=api_key),
        patch("src.services.ssm_client.get_claude_model", return_value=TEST_MODEL),
        patch("src.services.ssm_client.get_backlog_api_key", return_value="dummy-backlog-key"),
        patch("src.services.ssm_client.get_backlog_space_url", return_value="https://example.backlog.com"),
    ]


def _run_webhook(payload: dict) -> tuple[dict, MagicMock]:
    """ペイロードでhandlerを呼び出す。署名検証・SSM・Backlogをモック、Claude APIのみ実呼び出し。"""
    event = _build_slack_event(payload)
    mock_post = MagicMock()
    patches = (
        [
            patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True),
            patch("src.handlers.slack_webhook.slack_response.post_message", mock_post),
        ]
        + _ssm_patches()
        + _backlog_patches()
    )
    for p in patches:
        p.start()
    try:
        response = handler(event, None)
    finally:
        patch.stopall()
    return response, mock_post


requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY が未設定（Claude API実呼び出しテスト）",
)


@requires_api_key
def test_e2e_create_simple():
    response, mock_post = _run_webhook(PAYLOAD_CREATE_SIMPLE)
    assert response["statusCode"] == 200
    mock_post.assert_called_once()
    msg = mock_post.call_args[0][1]
    assert "作成しました" in msg


@requires_api_key
def test_e2e_update_with_key():
    response, mock_post = _run_webhook(PAYLOAD_UPDATE_WITH_KEY)
    assert response["statusCode"] == 200
    mock_post.assert_called_once()
    msg = mock_post.call_args[0][1]
    assert "NOHARATEST-3" in msg
    assert "更新しました" in msg


@requires_api_key
def test_e2e_create_with_due_date():
    response, mock_post = _run_webhook(PAYLOAD_CREATE_WITH_DUE)
    assert response["statusCode"] == 200
    mock_post.assert_called_once()
    msg = mock_post.call_args[0][1]
    assert "作成しました" in msg


def test_e2e_invalid_signature():
    """署名が不正な場合は401。"""
    event = _build_slack_event(PAYLOAD_CREATE_SIMPLE)
    response = handler(event, None)
    assert response["statusCode"] == 401


@patch("src.handlers.slack_webhook.slack_auth.validate_request", return_value=True)
def test_e2e_empty_mention(mock_auth):
    """メンションだけで本文がない場合。"""
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "text": "<@UBOTID>",
            "user": "U_USER",
            "channel": "C_CHANNEL",
            "ts": "1234567890.123456",
        },
    }
    event = _build_slack_event(payload)
    # bodyを直接設定（_build_slack_eventが二重エンコードしないよう）
    event["body"] = json.dumps(payload, ensure_ascii=False)
    response = handler(event, None)
    assert response["statusCode"] == 200
