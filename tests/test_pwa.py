"""The dashboard installs to a phone's home screen as a PWA.

This shipped half-wired: `manifest.webmanifest` and its icons existed from the
initial release, but no page ever linked the manifest, so "Add to Home Screen"
gave a Safari screenshot instead of the app. Nothing failed loudly — it just
quietly wasn't a PWA. These tests are the loud failure.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# /data is the DEV_MODE-only console but still ships the same head; including it
# keeps the pages consistent.
PAGES = ("/", "/tracker", "/assistant", "/accounts", "/login")


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_manifest_is_served_from_the_root(client):
    """A manifest may only claim a scope at or below its own URL."""
    res = client.get("/manifest.webmanifest")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/manifest+json")


def test_manifest_declares_an_installable_app(client):
    m = json.loads(client.get("/manifest.webmanifest").text)
    assert m["display"] == "standalone", "without this it opens in a browser tab"
    assert m["start_url"].startswith("/")
    assert m["scope"] == "/", "scope must cover every page, not just the start URL"
    assert m["name"] and m["short_name"]


def test_every_manifest_icon_actually_resolves(client):
    """A 404 icon silently downgrades the install prompt."""
    m = json.loads(client.get("/manifest.webmanifest").text)
    assert m["icons"], "an installable PWA needs at least one icon"
    for icon in m["icons"]:
        assert client.get(icon["src"]).status_code == 200, icon["src"]
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes, f"missing a required size: {sizes}"
    assert any("maskable" in i.get("purpose", "") for i in m["icons"])


@pytest.mark.parametrize("path", PAGES)
def test_pages_link_the_manifest(client, path):
    html = client.get(path).text
    assert 'rel="manifest"' in html, f"{path} does not link the manifest"
    assert "/manifest.webmanifest" in html


@pytest.mark.parametrize("path", PAGES)
def test_pages_carry_the_ios_home_screen_tags(client, path):
    """iOS reads these, not the manifest, when added to the Home Screen."""
    html = client.get(path).text
    assert 'rel="apple-touch-icon"' in html, f"{path}: iOS would use a screenshot"
    assert 'name="apple-mobile-web-app-capable" content="yes"' in html
    assert 'name="theme-color"' in html


def test_the_apple_touch_icon_resolves(client):
    assert client.get("/static/assets/icon-180.png").status_code == 200
