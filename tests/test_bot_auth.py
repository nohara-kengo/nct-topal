import time
from unittest.mock import patch, MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from src.services.bot_auth import validate_token


@pytest.fixture
def rsa_key_pair():
    """テスト用RSA鍵ペアを生成する。"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key


@pytest.fixture
def mock_jwks(rsa_key_pair):
    """JWKSクライアントをモックして、テスト用公開鍵を返す。"""
    public_key = rsa_key_pair.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("src.services.bot_auth._get_jwks_client", return_value=mock_client):
        yield


def _make_token(private_key, app_id="test-app-id", issuer="https://api.botframework.com", exp_offset=3600):
    """テスト用JWTトークンを生成する。"""
    payload = {
        "iss": issuer,
        "aud": app_id,
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
        "nbf": int(time.time()),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


@patch("src.services.bot_auth.ssm_client.get_microsoft_app_id", return_value="test-app-id")
def test_valid_token(mock_ssm, rsa_key_pair, mock_jwks):
    token = _make_token(rsa_key_pair)
    assert validate_token(f"Bearer {token}") is True


@patch("src.services.bot_auth.ssm_client.get_microsoft_app_id", return_value="test-app-id")
def test_expired_token(mock_ssm, rsa_key_pair, mock_jwks):
    token = _make_token(rsa_key_pair, exp_offset=-3600)
    assert validate_token(f"Bearer {token}") is False


@patch("src.services.bot_auth.ssm_client.get_microsoft_app_id", return_value="test-app-id")
def test_wrong_audience(mock_ssm, rsa_key_pair, mock_jwks):
    token = _make_token(rsa_key_pair, app_id="wrong-app-id")
    assert validate_token(f"Bearer {token}") is False


@patch("src.services.bot_auth.ssm_client.get_microsoft_app_id", return_value="test-app-id")
def test_wrong_issuer(mock_ssm, rsa_key_pair, mock_jwks):
    token = _make_token(rsa_key_pair, issuer="https://evil.example.com")
    assert validate_token(f"Bearer {token}") is False


def test_empty_authorization():
    assert validate_token("") is False


def test_no_bearer_prefix():
    assert validate_token("HMAC some-value") is False


@patch("src.services.bot_auth.ssm_client.get_microsoft_app_id", return_value="test-app-id")
def test_invalid_token_string(mock_ssm, mock_jwks):
    assert validate_token("Bearer not-a-valid-jwt") is False
