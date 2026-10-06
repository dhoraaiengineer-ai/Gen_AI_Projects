import pytest

from app.core.ratelimit import SlidingWindowLimiter
from tests.conftest import AppHarness, make_token


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_then_blocks_with_retry_after() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60, clock=clock)

    assert limiter.hit("u").remaining == 1
    assert limiter.hit("u").remaining == 0
    clock.now += 15
    blocked = limiter.hit("u")
    assert not blocked.allowed
    assert blocked.retry_after == 45


def test_window_slides_and_users_are_independent() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.hit("a").allowed
    assert limiter.hit("b").allowed  # another user has their own budget
    assert not limiter.hit("a").allowed
    clock.now += 60
    assert limiter.hit("a").allowed


def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError):
        SlidingWindowLimiter(limit=0)


QUERY = {"question": "Capital?"}


def test_query_is_limited_per_user_with_headers(harness: AppHarness) -> None:
    harness.settings.rate_limit_query_per_minute = 2
    with harness.client("a", "b", "c", role="user") as c:
        c.post("/api/v1/ingest", json={"documents": [{"text": "Paris is the capital of France."}]})
        first = c.post("/api/v1/query", json=QUERY)
        c.post("/api/v1/query", json=QUERY)
        blocked = c.post("/api/v1/query", json=QUERY)
        other_user = c.post(
            "/api/v1/query", json=QUERY, headers={"Authorization": f"Bearer {make_token(sub='someone-else')}"}
        )

    assert first.headers["X-RateLimit-Limit"] == "2"
    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"]
    assert blocked.json()["detail"].startswith("Too many requests: limit is 2 per minute")
    assert other_user.status_code == 200


def test_unauthenticated_calls_are_rejected_before_counting(harness: AppHarness) -> None:
    harness.settings.rate_limit_query_per_minute = 1
    with harness.client(role=None) as c:
        assert [c.post("/api/v1/query", json=QUERY).status_code for _ in range(3)] == [401, 401, 401]


def test_rate_limiting_can_be_disabled(harness: AppHarness) -> None:
    harness.settings.rate_limit_enabled = False
    harness.settings.rate_limit_eval_per_minute = 1
    with harness.client() as c:
        codes = [c.post("/api/v1/eval", json={"judge": False}).status_code for _ in range(3)]
    assert codes == [200, 200, 200]


def test_eval_is_limited(harness: AppHarness) -> None:
    harness.settings.rate_limit_eval_per_minute = 1
    with harness.client() as c:
        codes = [c.post("/api/v1/eval", json={"judge": False}).status_code for _ in range(2)]
    assert codes == [200, 429]
