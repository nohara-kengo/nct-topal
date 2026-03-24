"""Teamsから実際に届くペイロードを想定したE2E検証テスト。

Claude APIの意図判定・課題生成は実際に呼び出す（ANTHROPIC_API_KEYが必要）。
JWT認証はモックし、Claude APIの判定結果が正しいかを検証する。
Backlog APIはモックする。
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from src.handlers.teams_webhook import handler


# Claude APIのモデル（E2Eテストではコスト抑制のためHaikuも可）
TEST_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


def _build_bot_event(teams_payload: dict) -> dict:
    """Bot Frameworkペイロードをイベント形式に変換する。"""
    body = json.dumps(teams_payload, ensure_ascii=False)
    return {
        "body": body,
        "headers": {
            "Authorization": "Bearer test-jwt-token",
            "Content-Type": "application/json",
        },
    }


# --- Bot Frameworkが送るActivityペイロード例 ---

# ケース1: 新規タスク作成（シンプル）
PAYLOAD_CREATE_SIMPLE = {
    "type": "message",
    "id": "1234567890",
    "timestamp": "2026-03-22T10:00:00.000Z",
    "localTimestamp": "2026-03-22T19:00:00.000+09:00",
    "serviceUrl": "https://smba.trafficmanager.net/jp/",
    "channelId": "msteams",
    "from": {
        "id": "29:user-aad-id-here",
        "name": "野原 太郎",
        "aadObjectId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    },
    "conversation": {
        "conversationType": "channel",
        "id": "19:channel-id@thread.tacv2",
        "tenantId": "tenant-id-here",
    },
    "channelData": {
        "teamsChannelId": "19:channel-id@thread.tacv2",
        "teamsTeamId": "19:team-id@thread.tacv2",
        "channel": {"id": "19:channel-id@thread.tacv2"},
        "team": {"id": "19:team-id@thread.tacv2"},
        "tenant": {"id": "tenant-id-here"},
    },
    "text": "<at>ToPal</at> [NOHARATEST] 画面のログインボタンが押せないバグがあるので課題にしてください\u3000優先度は高で野原担当、2時間くらい",
}

# ケース2: 既存タスク更新（課題キーあり）
PAYLOAD_UPDATE_WITH_KEY = {
    "type": "message",
    "id": "1234567891",
    "timestamp": "2026-03-22T10:05:00.000Z",
    "localTimestamp": "2026-03-22T19:05:00.000+09:00",
    "serviceUrl": "https://smba.trafficmanager.net/jp/",
    "channelId": "msteams",
    "from": {
        "id": "29:user-aad-id-here",
        "name": "野原 太郎",
        "aadObjectId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    },
    "conversation": {
        "conversationType": "channel",
        "id": "19:channel-id@thread.tacv2",
        "tenantId": "tenant-id-here",
    },
    "channelData": {
        "teamsChannelId": "19:channel-id@thread.tacv2",
        "teamsTeamId": "19:team-id@thread.tacv2",
        "channel": {"id": "19:channel-id@thread.tacv2"},
        "team": {"id": "19:team-id@thread.tacv2"},
        "tenant": {"id": "tenant-id-here"},
    },
    "text": "<at>ToPal</at> NOHARATEST-3のLocalStack疎通テスト用タスクの優先度を高に変更して、野原担当で1時間",
}

# ケース3: 新規タスク作成（期限指定あり）
PAYLOAD_CREATE_WITH_DUE = {
    "type": "message",
    "id": "1234567892",
    "timestamp": "2026-03-22T10:10:00.000Z",
    "localTimestamp": "2026-03-22T19:10:00.000+09:00",
    "serviceUrl": "https://smba.trafficmanager.net/jp/",
    "channelId": "msteams",
    "from": {
        "id": "29:another-user-id",
        "name": "佐藤 花子",
        "aadObjectId": "ffffffff-gggg-hhhh-iiii-jjjjjjjjjjjj",
    },
    "conversation": {
        "conversationType": "channel",
        "id": "19:channel-id@thread.tacv2",
        "tenantId": "tenant-id-here",
    },
    "channelData": {
        "teamsChannelId": "19:channel-id@thread.tacv2",
        "teamsTeamId": "19:team-id@thread.tacv2",
        "channel": {"id": "19:channel-id@thread.tacv2"},
        "team": {"id": "19:team-id@thread.tacv2"},
        "tenant": {"id": "tenant-id-here"},
    },
    "text": "<at>ToPal</at> [NOHARATEST] APIのレスポンスが遅い件を調査タスクとして起票して。野原担当で半日くらい、優先度中",
}

# ケース4: HTMLタグ付きメンション（リッチテキスト）
PAYLOAD_RICH_TEXT = {
    "type": "message",
    "id": "1234567893",
    "timestamp": "2026-03-22T10:15:00.000Z",
    "localTimestamp": "2026-03-22T19:15:00.000+09:00",
    "serviceUrl": "https://smba.trafficmanager.net/jp/",
    "channelId": "msteams",
    "from": {
        "id": "29:user-aad-id-here",
        "name": "野原 太郎",
        "aadObjectId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    },
    "conversation": {
        "conversationType": "channel",
        "id": "19:channel-id@thread.tacv2",
        "tenantId": "tenant-id-here",
    },
    "channelData": {
        "teamsChannelId": "19:channel-id@thread.tacv2",
        "teamsTeamId": "19:team-id@thread.tacv2",
        "channel": {"id": "19:channel-id@thread.tacv2"},
        "team": {"id": "19:team-id@thread.tacv2"},
        "tenant": {"id": "tenant-id-here"},
    },
    "text": '<div><div><span itemscope="" itemtype="http://schema.skype.com/Mention" itemid="0"><at>ToPal</at></span> [NOHARATEST] お客様から問い合わせがあった件、タスクにしておいて。優先度低で野原担当、1時間</div></div>',
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


def _run_webhook(payload: dict) -> dict:
    """ペイロードでhandlerを呼び出す。JWT認証・SSM・Backlogをモック、Claude APIのみ実呼び出し。"""
    event = _build_bot_event(payload)
    patches = (
        [patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)]
        + _ssm_patches()
        + _backlog_patches()
    )
    for p in patches:
        p.start()
    try:
        response = handler(event, None)
    finally:
        patch.stopall()
    return response


def _parse_response(response: dict) -> dict:
    return json.loads(response["body"])


requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY が未設定（Claude API実呼び出しテスト）",
)


@requires_api_key
def test_e2e_create_simple():
    response = _run_webhook(PAYLOAD_CREATE_SIMPLE)
    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert "作成しました" in body["text"]


@requires_api_key
def test_e2e_update_with_key():
    response = _run_webhook(PAYLOAD_UPDATE_WITH_KEY)
    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert "NOHARATEST-3" in body["text"]
    assert "更新しました" in body["text"]


@requires_api_key
def test_e2e_create_with_due_date():
    response = _run_webhook(PAYLOAD_CREATE_WITH_DUE)
    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert "作成しました" in body["text"]


@requires_api_key
def test_e2e_rich_text_mention():
    response = _run_webhook(PAYLOAD_RICH_TEXT)
    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert "作成しました" in body["text"]


def test_e2e_invalid_jwt():
    """JWTが不正な場合は401。"""
    payload = PAYLOAD_CREATE_SIMPLE
    body = json.dumps(payload, ensure_ascii=False)
    event = {
        "body": body,
        "headers": {"Authorization": "Bearer invalid-token"},
    }
    response = handler(event, None)
    assert response["statusCode"] == 401


@patch("src.handlers.teams_webhook.bot_auth.validate_token", return_value=True)
def test_e2e_empty_mention(mock_auth):
    """メンションだけで本文がない場合。"""
    payload = {
        "type": "message",
        "id": "9999",
        "text": "<at>ToPal</at>",
        "from": {"id": "29:user", "name": "テストユーザー"},
        "serviceUrl": "https://smba.trafficmanager.net/jp/",
        "conversation": {"id": "19:test@thread.tacv2"},
    }
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "Bearer dummy"}}
    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = _parse_response(response)
    assert "空です" in resp_body["text"]
