-- Goals set on the profile BEFORE the goal->milestone mirror (tools._update_profile)
-- existed have a goal_title but no milestone, so the Goal dimension scores them 0
-- and restating the identical goal is a no-op (the assistant sees no profile change).
-- Backfill a tracking milestone (0%) for every such profile so the Goal card lists
-- the goal and can be scored. Idempotent: the NOT EXISTS guard makes re-runs safe,
-- and it dedupes against any already-tracked open milestone of the same title.
-- Runs as the migrate superuser (RLS bypassed), so it spans all users; user_id is
-- carried through explicitly so each milestone lands under its owner.
INSERT INTO milestones (user_id, title, category, milestone_date, progress_pct)
SELECT p.user_id, p.goal_title, 'goal', p.goal_target_date, 0
FROM profile p
WHERE p.goal_title IS NOT NULL
  AND p.goal_title <> ''
  AND NOT EXISTS (
    SELECT 1 FROM milestones m
    WHERE m.user_id = p.user_id
      AND m.title = p.goal_title
      AND NOT m.achieved
  );
