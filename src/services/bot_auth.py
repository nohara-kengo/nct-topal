"""Bot Framework JWT トークンを検証するモジュール。"""

import logging
import time

import jwt
import requests

from src.services import ssm_client

logger = logging.getLogger(__name__)

# Microsoft Bot Framework OpenID Connect メタデータURL
_OPENID_METADATA_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"
_VALID_ISSUERS = [
    "https://api.botframework.com",
    "https://sts.windows.net/d6d49420-f39b-4df7-a1dc-d59a935871db/",
    "https://login.microsoftonline.com/d6d49420-f39b-4df7-a1dc-d59a935871db/v2.0",
    "https://sts.windows.net/f8cdef31-a31e-4b4a-93e4-5f571e91255a/",
    "https://login.microsoftonline.com/f8cdef31-a31e-4b4a-93e4-5f571e91255a/v2.0",
]

# JWKSクライアントのキャッシュ（Lambdaウォームスタート活用）
_jwks_client = None
_jwks_cache_time = 0
_JWKS_CACHE_TTL = 86400  # 24時間


def _get_jwks_client() -> jwt.PyJWKClient:
    """OpenID Connect メタデータからJWKSクライアントを取得する。"""
    global _jwks_client, _jwks_cache_time
    now = time.time()
    if _jwks_client and (now - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_client

    resp = requests.get(_OPENID_METADATA_URL, timeout=10)
    resp.raise_for_status()
    jwks_uri = resp.json()["jwks_uri"]

    _jwks_client = jwt.PyJWKClient(jwks_uri)
    _jwks_cache_time = now
    return _jwks_client


def validate_token(authorization: str) -> bool:
    """Bot Framework のJWTトークンを検証する。

    Args:
        authorization: Authorizationヘッダー値（"Bearer <token>"形式）

    Returns:
        トークンが有効ならTrue
    """
    if not authorization:
        return False

    if not authorization.startswith("Bearer "):
        return False

    token = authorization[7:]

    try:
        app_id = ssm_client.get_microsoft_app_id()
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=app_id,
            issuer=_VALID_ISSUERS,
            options={"require": ["exp", "iss", "aud"]},
        )
        return True
    except jwt.ExpiredSignatureError:
        logger.warning("JWTトークンの有効期限切れ")
        return False
    except jwt.InvalidAudienceError:
        logger.warning("JWTトークンのaudience不一致")
        return False
    except jwt.InvalidIssuerError:
        logger.warning("JWTトークンのissuer不正")
        return False
    except Exception:
        logger.exception("JWTトークン検証に失敗")
        return False
