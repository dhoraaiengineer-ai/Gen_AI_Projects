from tests.conftest import AppHarness


def test_index_serves_ui_with_security_headers(harness: AppHarness) -> None:
    with harness.client() as c:
        r = c.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "RAG Assistant" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]


def test_static_assets_served(harness: AppHarness) -> None:
    with harness.client() as c:
        js = c.get("/static/app.js")
        css = c.get("/static/styles.css")
    assert js.status_code == 200 and "/api/v1/query" in js.text
    assert css.status_code == 200


def test_ui_not_in_openapi_schema(harness: AppHarness) -> None:
    with harness.client() as c:
        paths = c.get("/openapi.json").json()["paths"]
    assert "/" not in paths
