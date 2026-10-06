"""Serves the single-page chat UI at `/`. Static assets are mounted at /static in main.py."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

router = APIRouter(include_in_schema=False)


def security_headers(supabase_url: str | None) -> dict[str, str]:
    # The page loads only same-origin CSS/JS and talks only to this API and Supabase Auth.
    # (Applied to the UI page only: Swagger at /docs loads its assets from a CDN.)
    connect = "'self'" + (f" {supabase_url.rstrip('/')}" if supabase_url else "")
    return {
        "Content-Security-Policy": (
            f"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            f"connect-src {connect}; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        ),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }


@router.get("/")
def index(request: Request) -> FileResponse:
    settings = request.app.state.settings
    return FileResponse(STATIC_DIR / "index.html", headers=security_headers(settings.supabase_url))
