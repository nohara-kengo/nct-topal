"""Teams Incoming Webhookで結果を通知するモジュール。"""

import json
import logging

import requests

from src.services import ssm_client

logger = logging.getLogger(__name__)


def notify(message: str) -> None:
    """Teams Incoming Webhookにメッセージを送信する。

    Args:
        message: 送信するテキストメッセージ
    """
    webhook_url = ssm_client.get_teams_incoming_webhook_url()

    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "contentUrl": None,
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
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("Teams通知を送信しました")
    except requests.RequestException:
        logger.exception("Teams通知の送信に失敗")
        raise
