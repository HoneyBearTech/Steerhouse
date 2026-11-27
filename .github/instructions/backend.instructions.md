---
applyTo: "backend/**"
---

# Backend (FastAPI, Python 3.12)

- Code lives in `backend/app/`, one module per concern (for example `permissions.py`, `vault.py`,
  `run_executor.py`). Put new code in the module that owns the concern before creating a new one.
- Ruff is strict (see `[tool.ruff]` in `pyproject.toml`): line length 100, bandit rules, timezone-aware
  datetimes, no `print` outside `scripts/`, `fuzz/` and `app/cli.py`. Fix findings instead of adding
  `noqa`; if a `noqa` is truly needed, give the reason on the same line.
- Exceptions are named for what happened (`RateLimited`, `RunRefused`), without an `Error` suffix.
- Database changes need an Alembic migration in `backend/migrations/`.
- Subprocesses (`ansible-playbook`, `git`, `ssh`) go through the existing helpers in
  `subprocess_env.py`, `run_isolation.py` and `process_hardening.py`; never build a shell string.
- Anything that could log or return a secret must pass through `scrub.py`.
- Tests live in `backend/tests/` and use pytest. Every endpoint change needs a test, including the
  permission-denied case.
