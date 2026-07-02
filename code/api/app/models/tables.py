"""Declarative registry of CRUD-managed tables and their writable columns.

`id`, `created_at` and `updated_at` are managed by the database and are never
writable through the API.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    table: str
    columns: list[str]
    order_by: str = "updated_at DESC"


ENTITIES: list[Entity] = [
    Entity(
        "deadlines",
        ["title", "category", "due_date", "status", "priority", "blocked_on", "notes"],
        order_by="due_date ASC",
    ),
    Entity(
        "debts",
        ["name", "kind", "balance", "apr", "min_payment", "credit_limit",
         "due_date", "installment_amount", "term_months", "installments_paid",
         "priority_rank", "notes"],
        order_by="priority_rank NULLS LAST",
    ),
    Entity(
        "bills",
        ["name", "amount", "frequency", "due_day", "autopay", "category", "active", "notes"],
        order_by="due_day NULLS LAST",
    ),
    Entity(
        "subscriptions",
        ["name", "amount", "billing_cycle", "renews_on", "category", "active", "notes"],
        order_by="renews_on NULLS LAST",
    ),
    Entity(
        "shifts",
        ["employer", "role", "shift_date", "start_time", "end_time", "hours",
         "hourly_rate", "est_pay", "status", "notes"],
        order_by="shift_date DESC",
    ),
    # --- Digital Me layer ---
    Entity(
        "profile",
        ["full_name", "preferred_name", "birthdate", "birthplace", "location",
         "nationality", "headline", "bio", "visa_type", "visa_status",
         "work_auth_until", "target_role", "target_salary", "current_income",
         "remittance_pct", "monthly_essential_expenses", "goal_title",
         "goal_target_date", "life_expectancy_years"],
        order_by="updated_at DESC",
    ),
    Entity(
        "applications",
        ["company", "role", "status", "salary_min", "salary_max", "location",
         "work_type", "source", "url", "applied_date", "notes"],
        order_by="updated_at DESC",
    ),
    Entity(
        "milestones",
        ["title", "category", "milestone_date", "achieved", "progress_pct", "notes"],
        order_by="milestone_date ASC",
    ),
    # --- Work & income ---
    Entity(
        "jobs",
        ["employer", "role", "kind", "status", "hourly_rate", "annual_salary",
         "remittance_pct", "start_date", "end_date", "notes"],
        order_by="status ASC, employer ASC",
    ),
    Entity(
        "work_schedule",
        ["job_id", "day_of_week", "start_time", "end_time", "hours", "active", "notes"],
        order_by="day_of_week ASC",
    ),
    # --- Email accounts (registry; live connect added later) ---
    Entity(
        "email_accounts",
        ["email", "provider", "purpose", "auth_type", "imap_host", "imap_port",
         "status", "active", "notes"],
        order_by="provider ASC, email ASC",
    ),
    # --- Calendar accounts ---
    Entity(
        "calendar_accounts",
        ["email", "provider", "status", "active", "notes"],
        order_by="email ASC",
    ),
    # --- Agentic org layer ---
    Entity(
        "teams",
        ["name", "dimension", "mission", "active"],
        order_by="name ASC",
    ),
    Entity(
        "agents",
        ["name", "title", "agent_type", "team_id", "reports_to", "model_tier",
         "model_id", "system_prompt", "autonomy", "active"],
        order_by="agent_type ASC, name ASC",
    ),
    Entity(
        "tasks",
        ["title", "description", "kind", "team_id", "agent_id", "parent_id",
         "status", "priority", "requires_approval", "result", "error",
         "model_used", "created_by"],
        order_by="created_at DESC",
    ),
    Entity(
        "model_routes",
        ["tier", "provider", "model_id", "temperature", "active", "notes"],
        order_by="tier ASC",
    ),
    Entity(
        "agent_runs",
        ["task_id", "agent_id", "step", "provider", "model", "role",
         "tool_name", "content", "tokens"],
        order_by="created_at DESC",
    ),
]
