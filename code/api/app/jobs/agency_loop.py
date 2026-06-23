"""Worker: drains the agentic task queue.

Polls for the next 'queued' task and runs it through the agent engine. The CEO's
delegations create more queued tasks, which this loop then picks up — so a single
"ask the CEO" fans out across the org automatically. Bounded by per-task step
limits. Lives in its own container (see docker-compose `agency`).
"""
import time

from app.core.config import get_settings
from app.services import agency


def main() -> None:
    s = get_settings()
    if not s.agency_worker_enabled:
        print("[agency] worker disabled (AGENCY_WORKER_ENABLED=false)", flush=True)
        return
    print("[agency] worker up; polling the task queue", flush=True)
    while True:
        try:
            task_id = agency.next_queued()
            if task_id:
                print(f"[agency] running task {task_id}", flush=True)
                out = agency.run_task(task_id)
                print(f"[agency] -> {out}", flush=True)
                continue  # immediately check for the next (delegated) task
        except Exception as e:  # noqa: BLE001 — never let the loop die
            print(f"[agency] error: {e}", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
