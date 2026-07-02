"""Worker: writes the daily briefing markdown to the artifacts dir.

Runs once on container start (so today's file always exists), then APScheduler
fires the daily job at BRIEFING_HOUR in the configured TZ. The scheduled run
also syncs email first, so the briefing reflects anything new; the start-up run
does not (matching long-standing behavior). Lives in its own container
(see docker-compose `briefing`).
"""
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.db.session import active_user_ids, set_current_user
from app.services.briefing import build_briefing
from app.services.notify import push_briefing


def _write_today() -> str:
    """Write a briefing per active user (RLS-scoped). Files are suffixed with a
    short user id; the global briefing-latest.md points at the first user's for
    backward-compat. (Per-user push topics are a Phase-5 item.)"""
    s = get_settings()
    s.artifacts_dir.mkdir(parents=True, exist_ok=True)
    today = f"{date.today():%Y-%m-%d}"
    written = []
    for i, uid in enumerate(active_user_ids()):
        set_current_user(uid)
        md = build_briefing()
        short = uid[:8]
        (s.artifacts_dir / f"briefing-{today}-{short}.md").write_text(md, encoding="utf-8")
        (s.artifacts_dir / f"briefing-latest-{short}.md").write_text(md, encoding="utf-8")
        if i == 0:
            (s.artifacts_dir / "briefing-latest.md").write_text(md, encoding="utf-8")
        push_briefing(uid, md)  # no-op if NTFY_TOPIC unset
        written.append(short)
    return f"{len(written)} briefing(s): {', '.join(written) or 'none'}"


def _daily_run() -> None:
    """The scheduled morning job: sync mail, then write + push briefings."""
    try:
        from app.services.email_ingest import sync_all
        print(f"[briefing] email sync: {sync_all()}", flush=True)
    except Exception as e:  # noqa: BLE001 — a bad mailbox must not kill the briefing
        print(f"[briefing] email sync error: {e}", flush=True)
    try:
        from app.services.calendar_ingest import sync_all as cal_sync_all
        print(f"[briefing] calendar sync: {cal_sync_all()}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[briefing] calendar sync error: {e}", flush=True)
    try:
        print(f"[briefing] wrote {_write_today()}", flush=True)
    except Exception as e:  # noqa: BLE001 — never let the worker die
        print(f"[briefing] error: {e}", flush=True)

    try:
        from app.services.proactive import evaluate_rules
        print(f"[briefing] proactive alerts: {evaluate_rules()}", flush=True)
    except Exception as e:
        print(f"[briefing] proactive alerts error: {e}", flush=True)


    try:
        from app.jobs.backup_sync import sync_backups
        sync_backups()
    except Exception as e:
        print(f"[briefing] backup sync error: {e}", flush=True)

def main() -> None:
    s = get_settings()
    # On start: write today's briefing immediately (no email sync — matches the
    # historical container-start behavior), so the file always exists.
    try:
        print(f"[briefing] start-up write: {_write_today()}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[briefing] start-up error: {e}", flush=True)

    scheduler = BlockingScheduler(timezone=s.tz)
    scheduler.add_job(
        _daily_run,
        CronTrigger(hour=s.briefing_hour, minute=0),
        id="daily-briefing",
        coalesce=True,             # a missed window fires once, not N times
        misfire_grace_time=3600,   # restart within the hour still counts
    )
    print(f"[briefing] worker up; daily at {s.briefing_hour:02d}:00 {s.tz}", flush=True)
    scheduler.start()


if __name__ == "__main__":
    main()
