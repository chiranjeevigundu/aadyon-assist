"""RLS scoping mechanism: cursor() sets app.current_user_id for scoped queries
and leaves it unset for query_unscoped. Verified against a fake connection, so it
needs no real Postgres (the RLS enforcement itself is a DB-level integration test)."""
from app.db import session


class FakeCursor:
    def __init__(self, calls):
        self.calls = calls
        self.description = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=()):
        self.calls.append((sql, params))

    def fetchall(self):
        return []


class FakeConn:
    def __init__(self, calls):
        self.calls = calls
        self.committed = False
        self.rolledback = False

    def cursor(self, **kwargs):
        return FakeCursor(self.calls)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolledback = True


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def getconn(self):
        return self.conn

    def putconn(self, conn):
        pass


def _wire(monkeypatch):
    calls: list = []
    conn = FakeConn(calls)
    monkeypatch.setattr(session, "pool", lambda: FakePool(conn))
    return calls, conn


def test_scoped_query_sets_user_guc(monkeypatch):
    calls, _ = _wire(monkeypatch)
    session.set_current_user("u-7")
    session.query("SELECT 1")
    setcfg = [c for c in calls if "set_config('app.current_user_id'" in c[0]]
    assert setcfg and setcfg[0][1] == ("u-7",)


def test_unset_user_is_fail_closed(monkeypatch):
    calls, _ = _wire(monkeypatch)
    session.set_current_user(None)
    session.query("SELECT 1")
    setcfg = [c for c in calls if "set_config('app.current_user_id'" in c[0]]
    # GUC still set, but to '' -> RLS sees NULL -> zero rows (never another user's).
    assert setcfg and setcfg[0][1] == ("",)


def test_unscoped_query_does_not_set_guc(monkeypatch):
    calls, _ = _wire(monkeypatch)
    session.set_current_user("u-7")
    session.query_unscoped("SELECT 1")
    assert not [c for c in calls if "set_config" in c[0]]


def test_reads_rollback_writes_commit(monkeypatch):
    calls, conn = _wire(monkeypatch)
    session.set_current_user("u-1")
    session.query("SELECT 1")            # read
    assert conn.rolledback and not conn.committed

    calls2, conn2 = _wire(monkeypatch)
    session.query("UPDATE t SET x=1", commit=True)
    assert conn2.committed
