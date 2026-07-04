-- The assistant's update_debt tool needs a row id to target, but debt_summary
-- (what get_snapshot shows the model) hid it — same gap that broke milestone
-- progress updates. Append id (end position keeps CREATE OR REPLACE legal).
CREATE OR REPLACE VIEW debt_summary
  WITH (security_invoker = true) AS
SELECT
  name, kind, balance, apr, min_payment, credit_limit, priority_rank,
  CASE WHEN credit_limit > 0 THEN round(balance / credit_limit * 100, 1) END AS utilization_pct,
  round(balance * apr / 100 / 12, 2) AS est_monthly_interest,
  id
FROM debts
ORDER BY priority_rank NULLS LAST, apr DESC;
