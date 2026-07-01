"""Centralized application settings.

Reads from environment variables, with the DB password sourced from a Docker
secret file when present (falling back to POSTGRES_PASSWORD for local runs).
"""
import os
from functools import lru_cache
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.db_host = os.getenv("DB_HOST", "db")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("POSTGRES_DB", "aadyon_assist")
        self.db_user = os.getenv("POSTGRES_USER", "aadyon")
        self.db_password_file = os.getenv("DB_PASSWORD_FILE", "/run/secrets/db_password")
        # app/core/config.py -> app -> api -> code ; dashboard sits beside `code/api`
        # in the repo (code/dashboard) and beside `/srv/api` in the image (/srv/dashboard).
        self.dashboard_dir = Path(__file__).resolve().parents[3] / "dashboard"
        # Worker / briefing settings.
        self.artifacts_dir = Path(os.getenv("ARTIFACTS_DIR", "/srv/artifacts"))
        self.briefing_hour = int(os.getenv("BRIEFING_HOUR", "7"))
        self.tz = os.getenv("TZ", "UTC")

        # --- Agentic layer: model routing (OpenRouter cloud + local Ollama) ---
        self.openrouter_base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.openrouter_key_file = os.getenv(
            "OPENROUTER_API_KEY_FILE", "/run/secrets/openrouter_api_key"
        )
        # Local models via Ollama. From a container, the host is host.docker.internal.
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        # Push notifications via self-hosted ntfy (briefing -> phone). Empty topic = off.
        self.ntfy_internal_url = os.getenv("NTFY_INTERNAL_URL", "http://ntfy")
        self.ntfy_topic = os.getenv("NTFY_TOPIC", "").strip()

        # Email ingest: Fernet key to encrypt stored app-passwords. Empty = email
        # connect disabled. Generate with: python -c "from cryptography.fernet import
        # Fernet; print(Fernet.generate_key().decode())"
        self.email_key_file = os.getenv("EMAIL_ENC_KEY_FILE", "/run/secrets/email_key")
        self.email_lookback_days = int(os.getenv("EMAIL_LOOKBACK_DAYS", "14"))
        self.email_max_messages = int(os.getenv("EMAIL_MAX_MESSAGES", "40"))
        # Microsoft Graph (Outlook/365) OAuth — device-code flow (public client).
        self.ms_client_id = os.getenv("MS_CLIENT_ID", "").strip()
        self.ms_tenant = os.getenv("MS_TENANT", "common").strip()  # common | organizations | <tenant-id>
        # Gmail OAuth (added in the Gmail pass).
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

        # --- Auth (multi-user): JWT bearer tokens for the mobile app / API ---
        # Secret file (Docker secret) takes precedence over the env var, mirroring
        # db_password / email_enc_key. Empty secret => auth cannot mint/verify tokens.
        self.jwt_secret_file = os.getenv("JWT_SECRET_FILE", "/run/secrets/jwt_secret")
        self.jwt_alg = os.getenv("JWT_ALG", "HS256")
        # 30 days by default — mobile clients stay logged in between sessions.
        self.jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 30)))

        # The background agency worker that drains the task queue.
        self.agency_worker_enabled = os.getenv("AGENCY_WORKER_ENABLED", "true").lower() == "true"
        self.agent_max_steps = int(os.getenv("AGENT_MAX_STEPS", "6"))
        # Fallback tier -> (provider, model) if the model_routes table has no row.
        self.default_routes = {
            "reasoning": ("openrouter", "openrouter/auto"),
            "cheap": ("openrouter", "openai/gpt-4o-mini"),
            "local": ("ollama", "llama3.1"),
        }

    @property
    def db_password(self) -> str:
        """Docker secret takes precedence over the env var."""
        if os.path.exists(self.db_password_file):
            with open(self.db_password_file) as f:
                return f.read().strip()
        return os.getenv("POSTGRES_PASSWORD", "postgres")

    @property
    def openrouter_api_key(self) -> str:
        """Secret file takes precedence over the env var; empty string if unset."""
        if os.path.exists(self.openrouter_key_file):
            with open(self.openrouter_key_file) as f:
                return f.read().strip()
        return os.getenv("OPENROUTER_API_KEY", "").strip()

    @property
    def email_enc_key(self) -> str:
        """Fernet key for encrypting email app-passwords (secret file or env)."""
        if os.path.exists(self.email_key_file):
            with open(self.email_key_file) as f:
                return f.read().strip()
        return os.getenv("EMAIL_ENC_KEY", "").strip()

    @property
    def jwt_secret(self) -> str:
        """Signing secret for auth tokens (Docker secret file or env)."""
        if os.path.exists(self.jwt_secret_file):
            with open(self.jwt_secret_file) as f:
                return f.read().strip()
        return os.getenv("JWT_SECRET", "").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
