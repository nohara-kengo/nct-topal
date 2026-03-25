"""Slack Web APIで結果メッセージを送信するモジュール。"""

import logging

import requests

from src.services import ssm_client

logger = logging.getLogger(__name__)

_SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


def post_message(channel: str, text: str, thread_ts: str | None = None) -> None:
    """Slack Web API chat.postMessageで結果を送信する。

    Args:
        channel: チャンネルID
        text: 送信テキスト
        thread_ts: スレッドのタイムスタンプ（スレッド返信する場合）
    """
    token = ssm_client.get_slack_bot_token()

    payload = {
        "channel": channel,
        "text": text,
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts

    try:
        resp = requests.post(
            _SLACK_POST_MESSAGE_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=10,
        )
        resp.raise_for_status()

        data = resp.json()
        if not data.get("ok"):
            logger.error("Slack API エラー: %s", data.get("error", "unknown"))
            raise RuntimeError(f"Slack API error: {data.get('error')}")

        logger.info("Slack通知を送信しました: channel=%s", channel)
    except requests.RequestException:
        logger.exception("Slack通知の送信に失敗")
        raise
