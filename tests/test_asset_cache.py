"""Dashboard pages must never serve a stale JS bundle after an upgrade.

The dashboard has no build step, so `base.js` and friends keep the same URL forever.
Without help, a browser's heuristic caching can pair a new API with last release's
JS. Two things prevent that, and both are asserted here: the page itself is
`no-store`, and every asset URL inside it carries a fingerprint that changes when
any asset changes.
"""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PAGES = ("/", "/tracker", "/assistant", "/accounts", "/login")


@pytest.fixture
def client():
    return TestClient(create_app())


def _versions(html: str) -> list[str]:
    return re.findall(r'/static/assets/[\w.\-]+\?v=([0-9a-f]+)"', html)


@pytest.mark.parametrize("path", PAGES)
def test_pages_are_never_cached(client, path):
    assert client.get(path).headers["cache-control"] == "no-store"


@pytest.mark.parametrize("path", PAGES)
def test_asset_urls_are_fingerprinted(client, path):
    html = client.get(path).text
    assert "/static/assets/" in html, "page should reference dashboard assets"
    versions = _versions(html)
    assert versions, f"no fingerprinted asset URLs in {path}"
    # One build, one fingerprint — a page must not mix versions.
    assert len(set(versions)) == 1
    # And nothing may slip through unstamped.
    assert not re.search(r'/static/assets/[\w.\-]+"', html)


def test_assets_are_revalidated_not_blindly_cached(client):
    res = client.get("/static/assets/base.js")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-cache"
    assert res.headers.get("etag"), "revalidation needs an ETag to be cheap"


def test_fingerprint_changes_when_an_asset_changes(client, tmp_path):
    """The whole point: edit an asset, get a new URL."""
    from app.core.config import get_settings
    from app.routers import dashboard

    before = _versions(client.get("/").text)[0]
    asset = get_settings().dashboard_dir / "assets" / "base.js"
    original = asset.read_bytes()
    try:
        asset.write_bytes(original + b"\n// touched\n")
        dashboard._asset_version.cache_clear()
        after = _versions(client.get("/").text)[0]
    finally:
        asset.write_bytes(original)
        dashboard._asset_version.cache_clear()
    assert after != before
