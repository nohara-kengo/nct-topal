"""Slack Signing Secretによるリクエスト検証モジュール。"""

import hashlib
import hmac
import logging
import time

from src.services import ssm_client

logger = logging.getLogger(__name__)


def validate_request(headers: dict, body: str) -> bool:
    """Slackリクエストの署名を検証する。

    Args:
        headers: HTTPヘッダー辞書
        body: リクエストボディ（生文字列）

    Returns:
        署名が有効ならTrue
    """
    timestamp = headers.get("X-Slack-Request-Timestamp") or headers.get(
        "x-slack-request-timestamp", ""
    )
    signature = headers.get("X-Slack-Signature") or headers.get(
        "x-slack-signature", ""
    )

    if not timestamp or not signature:
        logger.warning("Slackリクエストヘッダーが不足")
        return False

    # リプレイ攻撃対策: 5分以上古いリクエストを拒否
    try:
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("タイムスタンプが期限切れ: %s", timestamp)
            return False
    except ValueError:
        logger.warning("不正なタイムスタンプ: %s", timestamp)
        return False

    signing_secret = ssm_client.get_slack_signing_secret()
    base_string = f"v0:{timestamp}:{body}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(), base_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        logger.warning("Slack署名検証に失敗")
        return False

    return True
