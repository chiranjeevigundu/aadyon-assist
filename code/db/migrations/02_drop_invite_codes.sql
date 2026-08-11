-- Drop the invite system. Signup is open now, so nothing can mint an invite code
-- and nothing can redeem one — the table is unreachable from the application.
-- Holds only generated codes, never user or financial data.
-- transaction

DROP TABLE IF EXISTS public.invite_codes;
