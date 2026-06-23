"""Postgres connection pool and query helpers."""
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

from app.core.config import get_settings

_pool: SimpleConnectionPool | None = None


def pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = SimpleConnectionPool(
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
def cursor(commit: bool = False):
    conn = pool().getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool().putconn(conn)


def query(sql: str, params: tuple = (), commit: bool = False):
    with cursor(commit=commit) as cur:
        cur.execute(sql, params)
        if cur.description:
            return cur.fetchall()
        return []
