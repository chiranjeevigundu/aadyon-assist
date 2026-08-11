"""Structural guards on the dashboard's plain-JS layout.

There is no bundler and no module system here, so every page's scripts share one
global scope. That makes two mistakes easy and expensive, and both have happened:

- Page-specific work in `base.js`. It is loaded by every page, so a data fetch
  there runs everywhere — on `/login` it 401s, and on `/tracker` it raced the real
  loader for the `#app` element.
- Native `confirm()`/`alert()` in the product UI, which looks nothing like the rest
  of the app and is suppressed outright in some embedded browsers.

These are cheap to assert and impossible to catch in a Python-only unit test
otherwise.
"""
import re

import pytest

from app.core.config import get_settings

ASSETS = get_settings().dashboard_dir / "assets"

# data.js backs /data, the DEV_MODE-only raw table console — not the product UI.
PRODUCT_SCRIPTS = sorted(p for p in ASSETS.glob("*.js") if p.name != "data.js")


def test_there_are_product_scripts_to_check():
    """Guard the guard: a bad glob would make every test below vacuously pass."""
    assert len(PRODUCT_SCRIPTS) >= 5


def test_base_js_fetches_no_page_specific_data():
    """base.js is shared by every page; only shared endpoints belong in it."""
    base = (ASSETS / "base.js").read_text(encoding="utf-8")
    endpoints = set(re.findall(r'fetchApi\(\s*"(/api/[\w/-]+)', base))
    # /api/app-config drives the nav, which every page renders.
    assert endpoints <= {"/api/app-config"}, (
        f"base.js fetches page-specific data: {sorted(endpoints - {'/api/app-config'})}"
    )


def test_base_js_registers_no_page_bootstrap():
    """A DOMContentLoaded handler in base.js runs on every page, including /login."""
    base = (ASSETS / "base.js").read_text(encoding="utf-8")
    handlers = re.findall(r'addEventListener\(\s*"DOMContentLoaded"\s*,\s*(\w+)', base)
    assert handlers == ["renderNav"], f"unexpected bootstrap in base.js: {handlers}"


@pytest.mark.parametrize("path", PRODUCT_SCRIPTS, ids=lambda p: p.name)
def test_product_ui_uses_the_app_dialog_not_the_browser_one(path):
    src = path.read_text(encoding="utf-8")
    stray = re.findall(r"(?<![.\w])(confirm|alert)\s*\(", src)
    assert not stray, f"{path.name} uses native {stray[0]}() — use confirmAction()"
