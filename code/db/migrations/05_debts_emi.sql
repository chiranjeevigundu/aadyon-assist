-- Aadyon Assist — Phase 1d: debts get a real due DATE + EMI / BNPL fields
-- (e.g. Affirm: fixed monthly installments over a term). Idempotent.

-- Recreate the dependent view first so column changes are safe.
DROP VIEW IF EXISTS debt_summary;

-- due_day (day-of-month int) -> due_date (actual next-due date).
ALTER TABLE debts ADD COLUMN IF NOT EXISTS due_date date;
ALTER TABLE debts DROP COLUMN IF EXISTS due_day;

-- EMI / installment plan fields (used when kind = 'emi'; null for cards/loans).
ALTER TABLE debts ADD COLUMN IF NOT EXISTS installment_amount numeric(12,2);  -- monthly EMI
ALTER TABLE debts ADD COLUMN IF NOT EXISTS term_months        int;            -- total installments
ALTER TABLE debts ADD COLUMN IF NOT EXISTS installments_paid  int;            -- paid so far

-- Rebuilt view: adds due_date, the EMI fields, remaining installments, and a
-- single "monthly_payment" (the EMI if present, else the card/loan minimum).
CREATE VIEW debt_summary AS
SELECT
  name, kind, balance, apr, min_payment, credit_limit, due_date,
  installment_amount, term_months, installments_paid,
  CASE WHEN term_months IS NOT NULL
       THEN GREATEST(term_months - COALESCE(installments_paid, 0), 0) END AS installments_remaining,
  COALESCE(installment_amount, min_payment) AS monthly_payment,
  priority_rank,
  CASE WHEN credit_limit > 0 THEN round(balance / credit_limit * 100, 1) END AS utilization_pct,
  round(balance * apr / 100 / 12, 2) AS est_monthly_interest
FROM debts
ORDER BY priority_rank NULLS LAST, apr DESC;

-- Example (add via the Data admin, not seeded — no invented numbers):
--   kind='emi', balance=remaining, installment_amount=monthly, term_months=12,
--   installments_paid=3, apr=0, due_date=next payment date, name='Affirm — <item>'.
