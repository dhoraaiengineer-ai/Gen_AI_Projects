"""Shared fixtures. Tests never read .env and never touch the network."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.config import Settings
from app.container import build_container
from app.main import create_app
from tests.fakes import FakeChatModel, FakeEmbedder, FakeOcr, FakeProbe, StaticKeyResolver

SUPABASE_URL = "https://example-test.supabase.co"
ISSUER = f"{SUPABASE_URL}/auth/v1"


def make_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "app_env": "test",
        "supabase_url": SUPABASE_URL,
        "supabase_publishable_key": "sb_publishable_test",
        "emergency_number": "112",
        "crisis_line_name": "Test Crisis Line",
        "crisis_line_number": "0000-TEST",
        "poison_line_number": "0001-TEST",
        "log_level": "WARNING",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture(scope="session")
def ec_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def token_factory(ec_key: ec.EllipticCurvePrivateKey) -> Callable[..., str]:
    def make(
        role: str | None = "user",
        *,
        sub: str = "user-123",
        exp_in: int = 3600,
        aud: str = "authenticated",
        top_level_role: str = "authenticated",
        key: Any = None,
        alg: str = "ES256",
        **extra: Any,
    ) -> str:
        claims = {
            "sub": sub,
            "email": "synthetic.user@example.test",
            "aud": aud,
            "iss": ISSUER,
            "exp": int(time.time()) + exp_in,
            "role": top_level_role,
            "app_metadata": {"role": role} if role else {},
            **extra,
        }
        return jwt.encode(claims, key if key is not None else ec_key, algorithm=alg)

    return make


@pytest.fixture
def client_factory(ec_key: ec.EllipticCurvePrivateKey) -> Callable[..., tuple[TestClient, FakeChatModel]]:
    def make(
        model: FakeChatModel | None = None,
        probe: FakeProbe | None = None,
        embedder: FakeEmbedder | None = None,
        ocr: FakeOcr | None = None,
        **settings: Any,
    ):
        fake = model or FakeChatModel()
        container = build_container(
            make_settings(**settings),
            model=fake,
            classifier=fake,
            embedder=embedder or FakeEmbedder(),
            ocr=ocr or FakeOcr(),
            key_resolver=StaticKeyResolver(ec_key.public_key()),
            db_probe=probe,
        )
        return TestClient(create_app(container), raise_server_exceptions=False), fake

    return make


@pytest.fixture
def auth_header(token_factory: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_factory()}"}
