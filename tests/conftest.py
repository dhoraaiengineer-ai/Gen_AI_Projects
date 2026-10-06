"""Shared fixtures. Everything here is offline: fake LLM, fake embeddings, in-memory vector store."""

import time
from collections.abc import Iterator, Sequence
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.vectorstores import InMemoryVectorStore

from app.config import Settings
from app.container import Container, build_container_from
from app.core.auth import TokenVerifier
from app.main import create_app
from app.rag.retriever import Retriever


class FakeChatModel(GenericFakeChatModel):
    """Scripted chat model that also accepts bind_tools() and records every prompt it sees."""

    seen: list[list[BaseMessage]] = []

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FakeChatModel":
        return self

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> BaseMessage:
        self.seen.append(list(input))
        return super().invoke(input, config, **kwargs)


def fake_llm(*responses: AIMessage | str) -> FakeChatModel:
    messages = [r if isinstance(r, AIMessage) else AIMessage(r) for r in responses]
    return FakeChatModel(messages=iter(messages), seen=[])


class ScoredInMemoryVectorStore(InMemoryVectorStore):
    """InMemoryVectorStore returns cosine similarity in [-1, 1]; rescale it to a [0, 1] relevance score
    (PGVector, used in production, ships its own relevance function)."""

    def _select_relevance_score_fn(self):  # type: ignore[override]
        return lambda similarity: (similarity + 1) / 2


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: tests must never pick up real keys or URLs from .env.
    return Settings(
        _env_file=None,
        chunk_size=200,
        chunk_overlap=20,
        top_k=3,
        agent_max_iterations=3,
        supabase_url=TEST_SUPABASE_URL,
        supabase_publishable_key="sb_publishable_test",
    )


@pytest.fixture
def vector_store() -> InMemoryVectorStore:
    return ScoredInMemoryVectorStore(DeterministicFakeEmbedding(size=64))


@pytest.fixture
def retriever(vector_store: InMemoryVectorStore, settings: Settings) -> Retriever:
    return Retriever(vector_store, settings.chunk_size, settings.chunk_overlap, settings.top_k)


TEST_SUPABASE_URL = "https://test-project.supabase.co"
_SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())  # stands in for Supabase's ES256 key


def make_token(
    role: str | None = None,
    *,
    sub: str = "user-123",
    email: str = "dev@example.com",
    expires_in: int = 3600,
    audience: str = "authenticated",
    issuer: str = f"{TEST_SUPABASE_URL}/auth/v1",
    key: Any = _SIGNING_KEY,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + expires_in,
        "role": "authenticated",  # Supabase's Postgres role claim; must not be mistaken for ours
        "app_metadata": {"app_role": role} if role else {},
    }
    return jwt.encode(claims, key, algorithm="ES256")


def auth_headers(role: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(role)}"}


def make_test_verifier() -> TokenVerifier:
    return TokenVerifier(
        lambda _token: _SIGNING_KEY.public_key(), issuer=f"{TEST_SUPABASE_URL}/auth/v1", audience="authenticated"
    )


class AppHarness:
    """Builds a TestClient around a container whose LLM responses, readiness and auth the test controls."""

    def __init__(self, settings: Settings, vector_store: InMemoryVectorStore):
        self.settings = settings
        self.vector_store = vector_store
        self.llm = fake_llm()
        self.db_ready = True
        self.auth_enabled = True
        self.fallback_llm: FakeChatModel | None = None
        self.agent_fallback_llm: FakeChatModel | None = None

    def client(self, *responses: AIMessage | str, role: str | None = "admin") -> TestClient:
        """role="admin"/"user" sends a valid token by default; role=None sends no Authorization header."""
        self.llm = fake_llm(*responses)

        def factory(settings: Settings) -> Container:
            return build_container_from(
                settings,
                self.vector_store,
                self.llm,
                readiness_checks={"database": lambda: self.db_ready},
                verifier=make_test_verifier() if self.auth_enabled else None,
                fallback_llm=self.fallback_llm,
                agent_fallback_llm=self.agent_fallback_llm,
            )

        headers = auth_headers(role if role != "user" else None) if role else {}
        return TestClient(create_app(self.settings, container_factory=factory), headers=headers)


@pytest.fixture
def harness(settings: Settings, vector_store: InMemoryVectorStore) -> Iterator[AppHarness]:
    yield AppHarness(settings, vector_store)
