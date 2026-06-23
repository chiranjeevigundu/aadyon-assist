"""Import smoke tests.

Importing every module (and building the app) catches the class of bug that the
email-module split risked: a broken import path takes the whole API down at
startup. These run without a database — psycopg2's pool is lazy, so importing
never opens a connection.
"""
import importlib

import pytest

MODULES = [
    "app.main",
    "app.core.config",
    "app.db.session",
    "app.models.tables",
    "app.routers.system",
    "app.routers.crud",
    "app.routers.agency",
    "app.routers.email",
    "app.routers.dashboard",
    "app.services.common",
    "app.services.dimensions",
    "app.services.digital_me",
    "app.services.summary",
    "app.services.schema",
    "app.services.routing",
    "app.services.llm",
    "app.services.tools",
    "app.services.agency",
    "app.services.crypto",
    "app.services.notify",
    "app.services.ms_graph",
    "app.services.email_extract",
    "app.services.email_store",
    "app.services.email_imap",
    "app.services.email_graph",
    "app.services.email_ingest",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    assert importlib.import_module(name) is not None


def test_app_factory_builds():
    from app.main import create_app

    app = create_app()
    assert app.title == "Aadyon Assist"


def test_email_ingest_public_surface():
    # The router and briefing import these names off email_ingest; keep them.
    from app.services import email_ingest

    for fn in ("sync_account", "sync_all", "approve_extraction", "test_login"):
        assert callable(getattr(email_ingest, fn))
