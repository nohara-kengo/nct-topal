import base64
import hashlib
import hmac

from src.services.hmac_validator import validate


SECRET = base64.b64encode(b"test-secret-key").decode("utf-8")


def _make_hmac(body: str, secret: str = SECRET) -> str:
    secret_bytes = base64.b64decode(secret)
    digest = hmac.new(secret_bytes, body.encode("utf-8"), hashlib.sha256).digest()
    return "HMAC " + base64.b64encode(digest).decode("utf-8")


def test_valid_signature():
    body = '{"text": "hello"}'
    auth = _make_hmac(body)
    assert validate(body, auth, secret=SECRET) is True


def test_invalid_signature():
    body = '{"text": "hello"}'
    assert validate(body, "HMAC invalid-hmac", secret=SECRET) is False


def test_tampered_body():
    body = '{"text": "hello"}'
    auth = _make_hmac(body)
    assert validate('{"text": "tampered"}', auth, secret=SECRET) is False


def test_empty_body():
    assert validate("", "HMAC abc", secret=SECRET) is False


def test_empty_authorization():
    assert validate('{"text": "hello"}', "", secret=SECRET) is False


def test_empty_secret():
    body = '{"text": "hello"}'
    auth = _make_hmac(body)
    assert validate(body, auth, secret="") is False
