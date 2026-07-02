"""Shared test helpers.

The app's two side-effect seams are the DB (`query`) and the network (`requests`
/ the LLM `chat`). Unit tests mock those so they run without Postgres or any
external service. CI installs the deps; this is all pure-Python orchestration.
"""
import importlib


def patch_query(monkeypatch, module_path, handler):
    """Replace `query` in a service module with a fake.

    `handler` may be:
      - a list  -> returned in call order (each call pops the next; [] when empty)
      - callable(sql, params, commit) -> returns rows for that call
    Returns the fake (its `.calls` list records every (sql, params, commit)).
    """
    mod = importlib.import_module(module_path)
    calls = []

    if isinstance(handler, list):
        seq = list(handler)

        def _q(sql, params=(), commit=False):
            calls.append((sql, params, commit))
            return seq.pop(0) if seq else []
    else:
        def _q(sql, params=(), commit=False):
            calls.append((sql, params, commit))
            return handler(sql, params, commit)

    _q.calls = calls
    monkeypatch.setattr(mod, "query", _q)
    return _q
