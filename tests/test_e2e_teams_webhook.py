"""Teamsから実際に届くペイロードを想定したE2E検証テスト。

Claude APIの意図判定は実際に呼び出す（ANTHROPIC_API_KEYが必要）。
HMAC署名検証はテスト用シークレットで自前生成する。
"""

import base64
import hashlib
import hmac
import json
import os
from unittest.mock import patch

import pytest

from src.handlers.teams_webhook import handler


# テスト用シークレット（本番ではTeams管理画面で発行される値）
TEST_SECRET = base64.b64encode(b"e2e-test-secret-key-2026").decode("utf-8")


def _sign_and_build_event(teams_payload: dict) -> dict:
    """Teamsペイロードに署名してAPI Gatewayイベント形式に変換する。"""
    body = json.dumps(teams_payload, ensure_ascii=False)
    secret_bytes = base64.b64decode(TEST_SECRET)
    digest = hmac.new(secret_bytes, body.encode("utf-8"), hashlib.sha256).digest()
    auth = "HMAC " + base64.b64encode(digest).decode("utf-8")

    return {
        "body": body,
        "headers": {
            "Authorization": auth,
            "Content-Type": "application/json",
        },
    }


# --- Teams Outgoing Webhookが実際に送るペイロード例 ---

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
    "text": "<at>ToPal</at> 画面のログインボタンが押せないバグがあるので課題にしてください\u3000優先度は高でお願いします",
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
    "text": "<at>ToPal</at> PROJ-456の優先度を高に変更して、期限は来週金曜にしてください",
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
    "text": "<at>ToPal</at> APIのレスポンスが遅い件を調査タスクとして起票して。期限は4月10日で",
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
    "text": "<div><div><span itemscope=\"\" itemtype=\"http://schema.skype.com/Mention\" itemid=\"0\"><at>ToPal</at></span> お客様から問い合わせがあった件、タスクにしておいて。優先度低でOK</div></div>",
}


# --- 検証ヘルパー ---

def _run_webhook(payload: dict) -> dict:
    """ペイロードに署名してhandlerを呼び出し、レスポンスを返す。"""
    event = _sign_and_build_event(payload)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TEAMS_WEBHOOK_SECRET", TEST_SECRET)
        response = handler(event, None)
    return response


def _parse_response(response: dict) -> dict:
    """レスポンスのbodyをパースする。"""
    return json.loads(response["body"])


# --- テスト本体 ---
# ANTHROPIC_API_KEYが設定されていない場合はスキップ
requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY が未設定（Claude API実呼び出しテスト）",
)


@requires_api_key
def test_e2e_create_simple():
    """シンプルな新規タスク作成リクエスト。"""
    response = _run_webhook(PAYLOAD_CREATE_SIMPLE)

    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert body["type"] == "message"
    assert "作成しました" in body["text"]
    print(f"\n[CREATE_SIMPLE] レスポンス: {body['text']}")


@requires_api_key
def test_e2e_update_with_key():
    """課題キー指定の更新リクエスト。"""
    response = _run_webhook(PAYLOAD_UPDATE_WITH_KEY)

    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert body["type"] == "message"
    assert "PROJ-456" in body["text"]
    assert "更新しました" in body["text"]
    print(f"\n[UPDATE_WITH_KEY] レスポンス: {body['text']}")


@requires_api_key
def test_e2e_create_with_due_date():
    """期限指定ありの新規タスク作成リクエスト。"""
    response = _run_webhook(PAYLOAD_CREATE_WITH_DUE)

    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert body["type"] == "message"
    assert "作成しました" in body["text"]
    print(f"\n[CREATE_WITH_DUE] レスポンス: {body['text']}")


@requires_api_key
def test_e2e_rich_text_mention():
    """HTMLリッチテキスト形式のメンション。"""
    response = _run_webhook(PAYLOAD_RICH_TEXT)

    assert response["statusCode"] == 200
    body = _parse_response(response)
    assert body["type"] == "message"
    assert "作成しました" in body["text"]
    print(f"\n[RICH_TEXT] レスポンス: {body['text']}")


@patch("src.services.hmac_validator.get_secret", return_value=TEST_SECRET)
def test_e2e_invalid_hmac(mock_secret):
    """HMAC署名が不正な場合は401。"""
    payload = PAYLOAD_CREATE_SIMPLE
    body = json.dumps(payload, ensure_ascii=False)
    event = {
        "body": body,
        "headers": {"Authorization": "HMAC definitely-wrong-signature"},
    }
    response = handler(event, None)

    assert response["statusCode"] == 401
    print("\n[INVALID_HMAC] 正しく401を返却")


@patch("src.handlers.teams_webhook.hmac_validator.validate", return_value=True)
def test_e2e_empty_mention(mock_hmac):
    """メンションだけで本文がない場合。"""
    payload = {
        "type": "message",
        "id": "9999",
        "text": "<at>ToPal</at>",
        "from": {"id": "29:user", "name": "テストユーザー"},
        "channelData": {"teamsChannelId": "19:test@thread.tacv2"},
    }
    body = json.dumps(payload, ensure_ascii=False)
    event = {"body": body, "headers": {"Authorization": "HMAC dummy"}}
    response = handler(event, None)

    assert response["statusCode"] == 200
    resp_body = _parse_response(response)
    assert "空です" in resp_body["text"]
    print("\n[EMPTY_MENTION] 正しくエラーメッセージを返却")
