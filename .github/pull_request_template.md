## What & why

<!-- One or two sentences. Link any related issue. -->

## Checklist

- [ ] `just test` passes (CI runs pytest automatically on this PR)
- [ ] No personal / financial / immigration data added — the gitleaks job must stay green
- [ ] Any new DB migration was created with `just new-migration <name>` (timestamped, not `NN_`)
      and has an RLS policy if it holds per-user data
- [ ] Any new third-party import is pinned in `code/api/requirements.txt` (or `-dev.txt` for tooling)
- [ ] For a behavior-preserving refactor: `scripts/verify.py` parity still holds
- [ ] Read **AGENTS.md** and followed the conventions there

## Notes for the reviewer / other agents

<!-- Anything another agent or human should know to avoid conflicts (touched files, shared modules). -->
