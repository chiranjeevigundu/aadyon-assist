"""Declarative registry of CRUD-managed tables and their writable columns.

`id`, `created_at` and `updated_at` are managed by the database and are never
writable through the API.
"""
from dataclasses import dataclass
from datetime import date, time
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Entity:
    table: str
    columns: dict[str, Any]
    order_by: str = "updated_at DESC"


ENTITIES: list[Entity] = [
    Entity(
        "deadlines",
        {"title": str, "category": str, "due_date": date, "status": str, "priority": int, "blocked_on": str, "notes": str},
        order_by="due_date ASC",
    ),
    Entity(
        "debts",
        {"name": str, "kind": str, "balance": float, "apr": float, "min_payment": float, "credit_limit": float,
         "due_date": date, "installment_amount": float, "term_months": int, "installments_paid": int,
         "priority_rank": int, "notes": str},
        order_by="priority_rank NULLS LAST",
    ),
    Entity(
        "bills",
        {"name": str, "amount": float, "frequency": str, "due_day": int, "autopay": bool, "category": str, "active": bool, "notes": str},
        order_by="due_day NULLS LAST",
    ),
    Entity(
        "subscriptions",
        {"name": str, "amount": float, "billing_cycle": str, "renews_on": date, "category": str, "active": bool, "notes": str},
        order_by="renews_on NULLS LAST",
    ),
    Entity(
        "shifts",
        {"employer": str, "role": str, "shift_date": date, "start_time": time, "end_time": time, "hours": float,
         "hourly_rate": float, "est_pay": float, "status": str, "notes": str},
        order_by="shift_date DESC",
    ),
    # --- Digital Me layer ---
    Entity(
        "profile",
        {"full_name": str, "preferred_name": str, "birthdate": date, "birthplace": str, "location": str,
         "nationality": str, "headline": str, "bio": str, "visa_type": str, "visa_status": str,
         "work_auth_until": date, "target_role": str, "target_salary": float, "current_income": float,
         "remittance_pct": float, "monthly_essential_expenses": float, "goal_title": str,
         "goal_target_date": date, "life_expectancy_years": float},
        order_by="updated_at DESC",
    ),
    Entity(
        "applications",
        {"company": str, "role": str, "status": str, "salary_min": float, "salary_max": float, "location": str,
         "work_type": str, "source": str, "url": str, "applied_date": date, "notes": str},
        order_by="updated_at DESC",
    ),
    Entity(
        "milestones",
        {"title": str, "category": str, "milestone_date": date, "achieved": bool, "progress_pct": float, "notes": str},
        order_by="milestone_date ASC",
    ),
    # --- Work & income ---
    Entity(
        "jobs",
        {"employer": str, "role": str, "kind": str, "status": str, "hourly_rate": float, "annual_salary": float,
         "remittance_pct": float, "start_date": date, "end_date": date, "notes": str},
        order_by="status ASC, employer ASC",
    ),
    Entity(
        "work_schedule",
        {"job_id": UUID, "day_of_week": int, "start_time": time, "end_time": time, "hours": float, "active": bool, "notes": str},
        order_by="day_of_week ASC",
    ),
    # --- Email accounts (registry; live connect added later) ---
    Entity(
        "email_accounts",
        {"email": str, "provider": str, "purpose": str, "auth_type": str, "imap_host": str, "imap_port": int,
         "status": str, "active": bool, "notes": str},
        order_by="provider ASC, email ASC",
    ),
    # --- Calendar accounts ---
    Entity(
        "calendar_accounts",
        {"email": str, "provider": str, "status": str, "active": bool, "notes": str},
        order_by="email ASC",
    ),
    # --- Drive accounts & files ---
    Entity(
        "drive_accounts",
        {"email": str, "provider": str, "status": str, "active": bool, "notes": str},
        order_by="email ASC",
    ),
    Entity(
        "drive_files",
        {"account_id": UUID, "file_id": str, "file_name": str, "mime_type": str,
         "web_view_link": str, "size_bytes": int, "status": str},
        order_by="updated_at DESC",
    ),
    # --- Agentic org layer ---
    Entity(
        "teams",
        {"name": str, "dimension": str, "mission": str, "active": bool},
        order_by="name ASC",
    ),
    Entity(
        "agents",
        {"name": str, "title": str, "agent_type": str, "team_id": UUID, "reports_to": UUID, "model_tier": str,
         "model_id": str, "system_prompt": str, "autonomy": str, "active": bool},
        order_by="agent_type ASC, name ASC",
    ),
    Entity(
        "tasks",
        {"title": str, "description": str, "kind": str, "team_id": UUID, "agent_id": UUID, "parent_id": UUID,
         "status": str, "priority": int, "requires_approval": bool, "result": str, "error": str,
         "model_used": str, "created_by": str},
        order_by="created_at DESC",
    ),
    Entity(
        "model_routes",
        {"tier": str, "provider": str, "model_id": str, "temperature": float, "active": bool, "notes": str},
        order_by="tier ASC",
    ),
    Entity(
        "agent_runs",
        {"task_id": UUID, "agent_id": UUID, "step": int, "provider": str, "model": str, "role": str,
         "tool_name": str, "content": str, "tokens": int},
        order_by="created_at DESC",
    ),
]
