from __future__ import annotations

import datetime as dt
import pathlib
from typing import Any, Dict

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import JWTError, jwt
from jose.constants import Algorithms

from .config import get_settings

_settings = get_settings()

_PRIVATE_KEY: bytes | None = None
_PUBLIC_KEY: bytes | None = None


def _load_key(path: pathlib.Path | None) -> bytes | None:
    if not path:
        return None
    if not path.exists():
        raise FileNotFoundError(f"JWT key not found at {path}")
    return path.read_bytes()


def _ensure_keys() -> tuple[bytes, bytes]:
    global _PRIVATE_KEY, _PUBLIC_KEY  # noqa: PLW0603

    if _PRIVATE_KEY and _PUBLIC_KEY:
        return _PRIVATE_KEY, _PUBLIC_KEY

    private = _load_key(_settings.jwt_private_key_path)
    public = _load_key(_settings.jwt_public_key_path)

    if private and not public:
        priv_key = serialization.load_pem_private_key(private, password=None)
        public = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    elif public and not private:
        raise RuntimeError("JWT public key provided without private key. Configure both or neither.")

    if not private:
        priv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = priv_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public = priv_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    _PRIVATE_KEY = private
    _PUBLIC_KEY = public
    return _PRIVATE_KEY, _PUBLIC_KEY


def encode_jwt(subject: str, claims: Dict[str, Any] | None = None, expires_delta: dt.timedelta | None = None) -> str:
    private_key, _ = _ensure_keys()
    now = dt.datetime.utcnow()
    payload: Dict[str, Any] = {
        "sub": subject,
        "iss": _settings.jwt_issuer,
        "aud": _settings.jwt_audience,
        "iat": now,
    }
    if expires_delta is None:
        expires_delta = dt.timedelta(seconds=_settings.access_token_ttl_seconds)
    payload["exp"] = now + expires_delta
    if claims:
        payload.update(claims)

    token = jwt.encode(payload, private_key, algorithm=Algorithms.RS256)
    return token


def decode_jwt(token: str) -> Dict[str, Any]:
    _, public_key = _ensure_keys()
    try:
        return jwt.decode(
            token,
            public_key,
            algorithms=[Algorithms.RS256],
            audience=_settings.jwt_audience,
            issuer=_settings.jwt_issuer,
        )
    except JWTError as exc:
        raise PermissionError("Invalid token") from exc


def get_public_key_pem() -> bytes:
    _, public_key = _ensure_keys()
    return public_key
