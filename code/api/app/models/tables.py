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
    # False for tables whose rows are created elsewhere (a dedicated route or a
    # pipeline) — the generic POST is skipped so routes don't collide.
    create: bool = True


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
    # --- Profile (financial settings + personal context) ---
    Entity(
        "profile",
        {"full_name": str, "preferred_name": str, "birthdate": date, "birthplace": str, "location": str,
         "nationality": str, "headline": str, "bio": str, "target_role": str, "target_salary": float,
         "current_income": float, "remittance_pct": float, "monthly_essential_expenses": float,
         "goal_title": str, "goal_target_date": date, "life_expectancy_years": float},
        order_by="updated_at DESC",
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
    # --- Net worth: assets (holdings) & snapshots ---
    # Liabilities are the existing `debts`; assets − debts = net worth. Snapshots are
    # a per-day time series written by the /api/networth/snapshot route (create=False).
    Entity(
        "assets",
        {"name": str, "kind": str, "institution": str, "value": float, "currency": str,
         "as_of": date, "active": bool, "notes": str},
        order_by="value DESC",
    ),
    Entity(
        "net_worth_snapshots",
        {"snapshot_date": date, "total_assets": float, "total_liabilities": float,
         "net_worth": float, "currency": str},
        order_by="snapshot_date DESC",
        create=False,  # written by the snapshot route, not the generic POST
    ),
    # --- Bank accounts & transactions ---
    Entity(
        "bank_accounts",
        {"institution": str, "status": str, "active": bool, "balance": float},
        order_by="institution ASC",
    ),
    Entity(
        "bank_transactions",
        {"account_id": UUID, "transaction_id": str, "date": date, "amount": float,
         "merchant": str, "category": str, "status": str},
        order_by="date DESC",
    ),
    # --- Documents ---
    Entity(
        "documents",
        {"filename": str, "mime_type": str, "size_bytes": int, "status": str},
        order_by="created_at DESC",
        create=False,  # created via the multipart upload route (POST /api/documents)
    ),
    Entity(
        "document_extractions",
        {"document_id": UUID, "kind": str, "summary": str, "status": str},
        order_by="created_at DESC",
        create=False,  # created by the analysis pipeline only
    ),
    # --- Human-in-the-loop proposals ---
    # The assistant queues real-world EXTERNAL actions (move money, send an email,
    # pay a bill) here instead of executing them; the user reviews and approves.
    Entity(
        "proposals",
        {"title": str, "detail": str, "category": str, "status": str},
        order_by="created_at DESC",
        create=False,  # created by the assistant's propose_action tool
    ),
]
