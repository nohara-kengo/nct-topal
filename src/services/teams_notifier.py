"""Bot Frameworkプロアクティブメッセージで結果を通知するモジュール。"""

import logging
import time

import requests

from src.services import ssm_client

logger = logging.getLogger(__name__)

# アクセストークンキャッシュ（Lambdaウォームスタート活用）
_token_cache = {"token": None, "expires_at": 0}

_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"


def _get_bot_token() -> str:
    """Azure ADからBot Frameworkアクセストークンを取得する。"""
    now = time.time()
    # 有効期限の5分前までキャッシュを使う
    if _token_cache["token"] and now < _token_cache["expires_at"] - 300:
        return _token_cache["token"]

    app_id = ssm_client.get_microsoft_app_id()
    app_password = ssm_client.get_microsoft_app_password()

    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": app_password,
            "scope": "https://api.botframework.com/.default",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)

    return data["access_token"]


def notify(message: str, service_url: str, conversation: dict) -> None:
    """Bot Frameworkプロアクティブメッセージで結果を通知する。

    Args:
        message: 送信するテキストメッセージ
        service_url: Teams serviceUrl（元メッセージから引き継ぎ）
        conversation: 元メッセージのconversationオブジェクト
    """
    token = _get_bot_token()
    conversation_id = conversation.get("id", "")

    url = f"{service_url.rstrip('/')}/v3/conversations/{conversation_id}/activities"

    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [{
                    "type": "TextBlock",
                    "text": message,
                    "wrap": True,
                }],
            },
        }],
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Teams通知を送信しました: conversation=%s", conversation_id)
    except requests.RequestException:
        logger.exception("Teams通知の送信に失敗")
        raise
