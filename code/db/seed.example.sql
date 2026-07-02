-- Aadyon Assist — EXAMPLE seed (safe to commit; placeholder data only).
-- This file is NOT auto-run. To seed the app with your own data:
--   1) copy this file to code/db/seed/99_seed_local.sql (that dir is gitignored),
--   2) replace the placeholders with your real values,
--   3) run `just seed` against the running stack.
-- Seed SQL is applied manually, never as a migration — your real data never enters git.
-- NOTE (multi-user): rows need a user_id; sign up first, then set
--   user_id = (SELECT id FROM users WHERE email = 'you@example.com') in your inserts,
-- or run the inserts with app.current_user_id set (see SYSTEM.md §8).

-- ---- DEADLINES -------------------------------------
INSERT INTO deadlines (title, category, due_date, status, priority, blocked_on, notes) VALUES
('Example deadline', 'general', CURRENT_DATE + 30, 'open', 3, NULL, 'Replace with your own.');

-- ---- DEBTS -----------------------------------------
INSERT INTO debts (name, kind, balance, apr, min_payment, credit_limit, priority_rank, notes) VALUES
('Example card', 'card', 1000.00, 24.99, 35.00, 2000.00, 1, 'Replace with your own.');

-- ---- PROFILE ---------------------------------
INSERT INTO profile (full_name, birthdate, location, nationality, headline,
                     visa_type, target_role, target_salary, current_income,
                     remittance_pct, goal_title, goal_target_date, life_expectancy_years)
SELECT 'Your Name', DATE '1990-01-01', 'Your City', 'Your Country',
       'Your one-line headline', 'visa/status', 'Target role', 100000.00, 0, 0,
       'Your before-30 (or other) goal', DATE '2030-01-01', 80
WHERE NOT EXISTS (SELECT 1 FROM profile);

-- ---- MILESTONES ------------------------------
INSERT INTO milestones (title, category, milestone_date, achieved, notes) VALUES
('Born', 'life', DATE '1990-01-01', true, 'Replace with your own.');

-- ---- JOBS ------------------------------------
INSERT INTO jobs (employer, role, kind, status, hourly_rate, remittance_pct, notes)
SELECT 'Example employer', 'Role', 'part_time_hourly', 'active', 15.00, 0, 'Replace with your own.'
WHERE NOT EXISTS (SELECT 1 FROM jobs WHERE employer = 'Example employer');
