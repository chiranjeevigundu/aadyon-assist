## What & why

<!-- One or two sentences. Link any related task. -->

## Checklist

- [ ] `pytest` passes (CI runs it automatically on this PR)
- [ ] No personal / financial / immigration data added — the CI `guard` job must stay green
- [ ] Any new DB migration is named `code/db/init/<YYYYMMDDHHMM>_<name>.sql` (timestamped, not `NN_`)
- [ ] Any new third-party import is added, pinned, to `code/api/requirements.txt`
- [ ] For a behavior-preserving refactor: `scripts/verify.py` parity still holds
- [ ] Read **AGENTS.md** and followed the conventions there

## Notes for the reviewer / other agents

<!-- Anything another agent or human should know to avoid conflicts (touched files, shared modules). -->
