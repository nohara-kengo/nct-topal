"""Teams Outgoing WebhookのHMAC-SHA256署名を検証するモジュール。"""

import base64
import hashlib
import hmac
import logging

from src.services import ssm_client

logger = logging.getLogger(__name__)


def get_secret():
    """SSMからWebhookシークレットを取得する。

    Returns:
        Webhookシークレット文字列
    """
    try:
        return ssm_client.get_teams_webhook_secret()
    except Exception:
        logger.warning("Teams Webhookシークレットの取得に失敗")
        return ""


def validate(body: str, authorization: str, secret: str = None) -> bool:
    """リクエストのHMAC-SHA256署名を検証する。

    Teams Outgoing Webhookは、リクエストボディのHMAC-SHA256ダイジェストを
    Base64エンコードしてAuthorizationヘッダーに付与する。

    Args:
        body: リクエストボディ（生文字列）
        authorization: AuthorizationヘッダーのHMAC値（"HMAC <base64>"形式）
        secret: Webhookシークレット。Noneの場合はSSMから取得

    Returns:
        署名が有効ならTrue
    """
    if not authorization or not body:
        return False

    if secret is None:
        secret = get_secret()

    if not secret:
        return False

    # Authorizationヘッダーから"HMAC "プレフィックスを除去
    provided_hmac = authorization.replace("HMAC ", "")

    # シークレットはBase64エンコードされた状態で提供される
    secret_bytes = base64.b64decode(secret)
    body_bytes = body.encode("utf-8")

    expected_hmac = base64.b64encode(
        hmac.new(secret_bytes, body_bytes, hashlib.sha256).digest()
    ).decode("utf-8")

    return hmac.compare_digest(expected_hmac, provided_hmac)
