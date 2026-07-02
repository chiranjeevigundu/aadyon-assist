-- 202607022210_proactive_alerts
-- P5 proactive intelligence: each user may have their own ntfy topic; the
-- briefing worker pushes alert digests there (fallback: the global NTFY_TOPIC).
-- users is the auth table (no RLS) — the column is written via /api/auth/me only.

ALTER TABLE users ADD COLUMN IF NOT EXISTS ntfy_topic text;
