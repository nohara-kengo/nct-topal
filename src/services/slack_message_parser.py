"""Slackメッセージからメンションを除去し前処理を行うモジュール。"""

import re


def strip_mentions(text: str) -> str:
    """メッセージからSlackメンション（<@UXXXXX>）を除去する。

    Args:
        text: Slackメッセージ本文

    Returns:
        メンション除去後のクリーンなテキスト
    """
    cleaned = re.sub(r"<@[A-Z0-9]+>", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_text(payload: dict) -> str:
    """Slack Event APIペイロードからユーザーメッセージテキストを抽出する。

    Args:
        payload: Slack Event APIのペイロード全体

    Returns:
        前処理済みのメッセージテキスト
    """
    text = payload.get("event", {}).get("text", "")
    return strip_mentions(text)
