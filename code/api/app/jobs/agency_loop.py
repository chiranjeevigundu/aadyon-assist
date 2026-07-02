"""Worker: drains the agentic task queue.

Polls for the next 'queued' task and runs it through the agent engine. The CEO's
delegations create more queued tasks, which this loop then picks up — so a single
"ask the CEO" fans out across the org automatically. Bounded by per-task step
limits. Lives in its own container (see docker-compose `agency`).

Deliberately NOT APScheduler: this is a queue consumer, not a schedule. It drains
back-to-back with zero inter-task latency and only sleeps when idle; an interval
trigger would add up to 5s between every task (see briefing_loop for the cron case).
"""
import time

from app.core.config import get_settings
from app.db.session import active_user_ids, set_current_user
from app.services import agency


def main() -> None:
    s = get_settings()
    if not s.agency_worker_enabled:
        print("[agency] worker disabled (AGENCY_WORKER_ENABLED=false)", flush=True)
        return
    print("[agency] worker up; polling each user's task queue", flush=True)
    while True:
        ran = False
        try:
            # Drain each user's queue in turn; RLS scopes next_queued/run_task per user.
            for uid in active_user_ids():
                set_current_user(uid)
                task_id = agency.next_queued()
                if task_id:
                    print(f"[agency] user={uid[:8]} running task {task_id}", flush=True)
                    out = agency.run_task(task_id)
                    print(f"[agency] -> {out}", flush=True)
                    ran = True
        except Exception as e:  # noqa: BLE001 — never let the loop die
            print(f"[agency] error: {e}", flush=True)
        if not ran:
            time.sleep(5)  # idle only when no user had queued work


if __name__ == "__main__":
    main()
