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
        # DB_USER (api/briefing/agency) is the restricted, non-superuser role RLS
        # actually applies to; POSTGRES_USER (migrate) is the DDL-privileged
        # bootstrap superuser, which always bypasses RLS -- see
        # 202607032100_restricted_app_role.sql.
        self.db_user = os.getenv("DB_USER") or os.getenv("POSTGRES_USER", "aadyon")
        self.db_password_file = os.getenv("DB_PASSWORD_FILE", "/run/secrets/db_password")
        # app/core/config.py -> app -> api -> code ; dashboard sits beside `code/api`
        # in the repo (code/dashboard) and beside `/srv/api` in the image (/srv/dashboard).
        self.dashboard_dir = Path(__file__).resolve().parents[3] / "dashboard"
        # Worker / briefing settings.
        self.artifacts_dir = Path(os.getenv("ARTIFACTS_DIR", "/srv/artifacts"))
        self.briefing_hour = int(os.getenv("BRIEFING_HOUR", "7"))
        # Proactive alerts: look-ahead window in days for deadline/bill pushes.
        self.alert_days = int(os.getenv("ALERT_DAYS", "3"))
        self.tz = os.getenv("TZ", "UTC")

        # --- Document/file storage backend ---
        # "local" (default): persist under artifacts_dir/uploads — works on a single
        # host (the Mac Mini). "s3": S3-compatible object storage (set the creds below)
        # — the cloud-scale / multi-instance option. "mock": no real I/O, for tests/CI.
        # Explicit so a real deployment never silently discards uploads.
        self.storage_backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()
        # --- Cloud Storage (S3-compatible) ---
        # This layer is deliberately vendor-neutral: the SAME code talks to real AWS
        # S3, a local emulator (Floci / LocalStack / MinIO), or any S3-compatible
        # store. You migrate between them by changing config only — never code:
        #   * Real AWS  : leave S3_ENDPOINT_URL empty, set S3_REGION + real creds.
        #   * Emulator  : set S3_ENDPOINT_URL (e.g. http://host.docker.internal:4566).
        # See docs/cloud-storage.md for copy-paste profiles.
        self.s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", "").strip()
        self.s3_bucket = os.getenv("S3_BUCKET_NAME", "aadyon-assist").strip()
        self.s3_access_key_file = os.getenv("S3_ACCESS_KEY_FILE", "/run/secrets/s3_access_key")
        self.s3_secret_key_file = os.getenv("S3_SECRET_KEY_FILE", "/run/secrets/s3_secret_key")
        # Region for SigV4 signing + bucket location. AWS needs the bucket's real
        # region; emulators accept anything (us-east-1 is the convention). Honors the
        # standard AWS_REGION / AWS_DEFAULT_REGION so ambient AWS config Just Works.
        self.s3_region = (
            os.getenv("S3_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        ).strip()
        # Addressing style. Real AWS uses virtual-host (bucket.s3.amazonaws.com);
        # emulators generally need path-style (endpoint/bucket/key). "auto" (default)
        # picks path-style whenever a custom endpoint is set, virtual-host otherwise —
        # so both worlds work with no extra config. Force with true/false.
        _paths = os.getenv("S3_FORCE_PATH_STYLE", "auto").strip().lower()
        if _paths in ("1", "true", "yes", "on"):
            self.s3_force_path_style = True
        elif _paths in ("0", "false", "no", "off"):
            self.s3_force_path_style = False
        else:  # "auto" / anything else
            self.s3_force_path_style = bool(self.s3_endpoint_url)
        # Create the bucket on startup if it doesn't exist (idempotent). Convenient
        # for emulator onboarding; set false on real AWS if the app's IAM role
        # shouldn't hold CreateBucket (pre-provision the bucket via IaC instead).
        self.s3_auto_create_bucket = (
            os.getenv("S3_AUTO_CREATE_BUCKET", "true").strip().lower() == "true"
        )

        # Public-facing URL of this app (used e.g. as the OpenRouter HTTP-Referer,
        # and to build email verify/reset links).
        self.app_public_url = os.getenv("APP_PUBLIC_URL", "http://localhost:8000").strip()

        # Developer surfaces. OFF by default so a normal deployment shows only the
        # product UI. When true: the raw table console at /data, plus FastAPI's
        # auto-generated /docs, /redoc and /openapi.json, become available and are
        # linked in the nav. Never enable on an internet-facing instance.
        self.dev_mode = os.getenv("DEV_MODE", "false").strip().lower() == "true"

        # --- Multi-user (family & friends) account hardening ---
        # Transactional email (Resend-style API). Empty key => mailer logs to stdout
        # instead of sending, so dev/CI never send. Secret file wins over the env var.
        self.resend_api_key_file = os.getenv("RESEND_API_KEY_FILE", "/run/secrets/resend_api_key")
        self.mail_from = os.getenv("MAIL_FROM", "Aadyon Assist <onboarding@resend.dev>").strip()
        # Minutes a verify/reset email link stays valid.
        self.email_token_minutes = int(os.getenv("EMAIL_TOKEN_MINUTES", "60"))
        # Default monthly LLM token budget per user (0 or unset => unlimited).
        self.default_monthly_token_budget = int(os.getenv("DEFAULT_MONTHLY_TOKEN_BUDGET", "0"))

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

        # Max tool-calling rounds the assistant runs per turn (bounds the loop).
        self.agent_max_steps = int(os.getenv("AGENT_MAX_STEPS", "6"))
        # Fallback tier -> (provider, model) for model routing.
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

    @property
    def resend_api_key(self) -> str:
        """API key for transactional email (secret file or env; empty => log-only)."""
        if os.path.exists(self.resend_api_key_file):
            with open(self.resend_api_key_file) as f:
                return f.read().strip()
        return os.getenv("RESEND_API_KEY", "").strip()

    @property
    def s3_access_key(self) -> str:
        """Access key for S3 bucket."""
        if os.path.exists(self.s3_access_key_file):
            with open(self.s3_access_key_file) as f:
                return f.read().strip()
        return os.getenv("S3_ACCESS_KEY_ID", "").strip()

    @property
    def s3_secret_key(self) -> str:
        """Secret key for S3 bucket."""
        if os.path.exists(self.s3_secret_key_file):
            with open(self.s3_secret_key_file) as f:
                return f.read().strip()
        return os.getenv("S3_SECRET_ACCESS_KEY", "").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()
