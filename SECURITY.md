# Security Policy

Aadyon Assist is a **self-hosted** application that stores personal financial and
immigration data. Its security model assumes you run it on infrastructure you
control, ideally reachable only over a private network (e.g. Tailscale).

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Instead, use
GitHub's private vulnerability reporting ("Report a vulnerability" under the
repository's Security tab). You'll get an acknowledgement within a week.

## Model summary

- **Auth:** JWT bearer tokens (`POST /api/auth/login`); every per-user table is
  isolated by Postgres Row-Level Security bound to the request's user.
- **Secrets:** Docker secrets (`secrets/db_password.txt`, `secrets/jwt_secret.txt`,
  optional `openrouter_api_key`, `email_key`) — never committed; config reads the
  secret file first, env var second.
- **Email credentials** are Fernet-encrypted at rest; mail access is read-only.
- **Agent actions** with real-world side effects (money, email, filings) are
  queued for explicit human approval — they never auto-execute.

## Secret scanning

CI runs [gitleaks](https://github.com/gitleaks/gitleaks) on every push/PR, and a
pre-commit hook runs it locally (`pre-commit install`). If you deploy a fork with
your own data, consider keeping a **private, uncommitted** gitleaks config with
personal denylist patterns (your names, hosts, account numbers) and running
`gitleaks detect -c <your-config>` before pushing anything public.
