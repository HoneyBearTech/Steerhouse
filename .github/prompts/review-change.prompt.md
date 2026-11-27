---
mode: agent
description: Review the current change against Steerhouse's security and quality rules
---

Review the current change (the open pull request, or the uncommitted diff) for Steerhouse.

Check, in this order:

1. **Security**: missing permission checks, secrets that could be logged or returned without
   `scrub.py`, shell strings built for subprocesses, new network egress, weakened hardening.
2. **Correctness**: bugs, unhandled errors, missing Alembic migrations for model changes.
3. **Tests**: every behaviour change has a test, including the permission-denied case; coverage
   floors still hold.
4. **Docs**: `CHANGELOG.md` and the matching `docs/` page are updated for user-visible changes.
5. **Style**: ruff and oxlint would pass; plain, short English in text.

List each finding with the file and line, why it matters and a suggested fix. Say plainly if you
found nothing.
