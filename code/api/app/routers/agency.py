from fastapi import APIRouter, HTTPException
from uuid import UUID

from app.db.session import query
from app.services import agency

router = APIRouter(prefix="/api/agency", tags=["agency"])


@router.get("/org")
def org():
    return agency.org_tree()


@router.get("/health")
def health():
    return agency.llm_health()


@router.post("/ask")
def ask(payload: dict):
    goal = (payload or {}).get("goal", "").strip()
    if not goal:
        raise HTTPException(400, "Provide a 'goal'.")
    task = agency.ask_ceo(goal, (payload or {}).get("title"))
    return {"task": task, "note": "queued for the CEO; runs via the worker or POST /run"}


@router.get("/tasks")
def tasks(status: str | None = None):
    sql = (
        "SELECT t.*, te.name AS team_name, a.name AS agent_name "
        "FROM tasks t LEFT JOIN teams te ON te.id = t.team_id "
        "LEFT JOIN agents a ON a.id = t.agent_id "
    )
    params: tuple = ()
    if status:
        sql += "WHERE t.status = %s "
        params = (status,)
    sql += "ORDER BY t.created_at DESC LIMIT 200"
    return query(sql, params)


@router.get("/runs")
def runs(task_id: UUID):
    return query(
        "SELECT ar.*, a.name AS agent_name FROM agent_runs ar "
        "LEFT JOIN agents a ON a.id = ar.agent_id "
        "WHERE ar.task_id = %s ORDER BY ar.step ASC, ar.created_at ASC",
        (str(task_id),),
    )


@router.post("/tasks/{task_id}/run")
def run(task_id: UUID):
    return agency.run_task(str(task_id))


@router.post("/tasks/{task_id}/approve")
def approve(task_id: UUID):
    agency.set_status(str(task_id), "approved")
    return {"status": "approved", "note": "Approved — execute the action yourself (human-in-the-loop)."}


@router.post("/tasks/{task_id}/reject")
def reject(task_id: UUID):
    agency.set_status(str(task_id), "cancelled")
    return {"status": "cancelled"}
