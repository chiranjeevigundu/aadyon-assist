"""Postgres connection pool and query helpers.

Multi-user isolation is enforced by Postgres Row-Level Security (RLS). Each
request identifies its user (see routers/auth.get_current_user), which stores the
id in the `current_user` ContextVar. Every `query()` opens a transaction, sets the
`app.current_user_id` GUC on it, and the RLS policies filter every row by it. The
GUC is transaction-local and the transaction always ends per call, so it never
bleeds across pooled connections. `query_unscoped()` skips the GUC for the auth
table (users) and global tables (model_routes).

Uses `ThreadedConnectionPool`, not `SimpleConnectionPool`: FastAPI runs sync `def`
route handlers (e.g. routers/crud.py) on a worker threadpool, so concurrent
requests call getconn()/putconn() from multiple threads. SimpleConnectionPool
has no locking and is documented as unsafe across threads — under concurrent
load it can hand the same connection to two threads at once, letting one
request's query interleave with another's mid-transaction and leak rows across
the RLS boundary. ThreadedConnectionPool wraps the same calls in a lock.
"""
import contextvars
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from app.core.config import get_settings

# Pydantic-validated payloads (see routers/crud.py) carry real uuid.UUID values;
# psycopg2 can't adapt those unless the UUID adapter is registered. Process-wide,
# once, at import time — otherwise every UUID param raises "can't adapt type 'UUID'".
psycopg2.extras.register_uuid()

_pool: ThreadedConnectionPool | None = None

# The current request's user id (str UUID) or None. Set by the auth dependency
# (async, so it propagates into sync endpoints' threadpool context) and by the
# background jobs before they touch per-user data.
current_user: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_user_id", default=None
)


def set_current_user(uid) -> None:
    """Bind the current user for subsequent queries in this context."""
    current_user.set(str(uid) if uid is not None else None)


def current_user_id() -> str | None:
    return current_user.get()


def pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=s.db_host,
            port=s.db_port,
            dbname=s.db_name,
            user=s.db_user,
            password=s.db_password,
        )
    return _pool


@contextmanager
def cursor(commit: bool = False, scoped: bool = True):
    conn = pool().getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if scoped:
                # Transaction-local (is_local=true): applies to this transaction
                # only and is cleared when it ends below. An unset user -> '' ->
                # RLS sees NULL -> zero rows (fail-closed).
                uid = current_user.get()
                cur.execute(
                    "SELECT set_config('app.current_user_id', %s, true)",
                    (str(uid) if uid else "",),
                )
            yield cur
            # Always end the transaction so the local GUC can't survive on the
            # pooled connection: commit to persist writes, rollback for reads.
            if commit:
                conn.commit()
            else:
                conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool().putconn(conn)


def query(sql: str, params: tuple = (), commit: bool = False):
    """User-scoped query — RLS restricts every row to the current user."""
    with cursor(commit=commit, scoped=True) as cur:
        cur.execute(sql, params)
        if cur.description:
            return cur.fetchall()
        return []


def query_unscoped(sql: str, params: tuple = (), commit: bool = False):
    """Query WITHOUT setting the user GUC. Only for non-RLS tables: `users`
    (auth) and global config like `model_routes`. Never use for per-user data."""
    with cursor(commit=commit, scoped=False) as cur:
        cur.execute(sql, params)
        if cur.description:
            return cur.fetchall()
        return []


def active_user_ids() -> list[str]:
    """All active users — for background jobs to iterate and scope per user."""
    rows = query_unscoped("SELECT id FROM users WHERE is_active ORDER BY created_at")
    return [str(r["id"]) for r in rows]
