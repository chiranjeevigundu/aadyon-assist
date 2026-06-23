"""Worker: writes the daily briefing markdown to the artifacts dir.

Runs once on start (so today's file always exists), then wakes each day at the
configured hour. Lives in its own container (see docker-compose `briefing`).
"""
import time
from datetime import date, datetime

from app.core.config import get_settings
from app.services.briefing import build_briefing
from app.services.notify import push_briefing


def _write_today() -> str:
    s = get_settings()
    s.artifacts_dir.mkdir(parents=True, exist_ok=True)
    md = build_briefing()
    path = s.artifacts_dir / f"briefing-{date.today():%Y-%m-%d}.md"
    path.write_text(md, encoding="utf-8")
    # Stable pointer to the latest one.
    (s.artifacts_dir / "briefing-latest.md").write_text(md, encoding="utf-8")
    # Push to the phone (no-op if NTFY_TOPIC is unset).
    push_briefing(md)
    return str(path)


def main() -> None:
    s = get_settings()
    last_written = None
    print(f"[briefing] worker up; target hour={s.briefing_hour}", flush=True)
    while True:
        now = datetime.now()
        if last_written is None or (now.hour == s.briefing_hour and last_written != now.date()):
            scheduled_run = now.hour == s.briefing_hour
            # On the scheduled morning run (not on container start), pull email first
            # so the briefing reflects anything new — then write + push.
            if scheduled_run:
                try:
                    from app.services.email_ingest import sync_all
                    print(f"[briefing] email sync: {sync_all()}", flush=True)
                except Exception as e:  # noqa: BLE001
                    print(f"[briefing] email sync error: {e}", flush=True)
            try:
                p = _write_today()
                last_written = now.date()
                print(f"[briefing] wrote {p}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[briefing] error: {e}", flush=True)
        time.sleep(300)


if __name__ == "__main__":
    main()
