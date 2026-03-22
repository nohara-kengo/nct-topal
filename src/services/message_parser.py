"""Teamsメッセージからメンションタグを除去し前処理を行うモジュール。"""

import re


def strip_mentions(text: str) -> str:
    """メッセージからメンションタグ（<at>...</at>）を除去する。

    Args:
        text: Teamsメッセージ本文（HTML含む）

    Returns:
        メンションタグ除去後のクリーンなテキスト
    """
    # <at>ToPal</at> 等のメンションタグを除去
    cleaned = re.sub(r"<at>.*?</at>", "", text)
    # 残ったHTMLタグを除去
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # 前後の空白・連続空白を整理
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_text(teams_payload: dict) -> str:
    """Teamsペイロードからユーザーメッセージテキストを抽出する。

    Args:
        teams_payload: Teams Outgoing Webhookのリクエストボディ

    Returns:
        前処理済みのメッセージテキスト
    """
    raw_text = teams_payload.get("text", "")
    return strip_mentions(raw_text)
