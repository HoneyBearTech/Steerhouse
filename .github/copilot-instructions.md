# Copilot instructions for Steerhouse

Steerhouse is a self-hosted, Dockerized web UI for running Ansible playbooks. The backend is FastAPI
on Python 3.12, managed with `uv` (`backend/`). The frontend is React, TypeScript, Vite and
Tailwind v4 (`frontend/`). The default branch is `main`.

## Ground rules

- Never commit secrets, private keys, vault passwords or `.env` files. Extend `.gitignore` when a new
  kind of local file appears.
- Dependencies come only from `backend/uv.lock` and `frontend/package-lock.json`. Don't add a
  dependency without saying why; see `docs/dependencies.md`.
- Security comes first: this app runs Ansible against real hosts. Keep permission checks, secret
  scrubbing, egress limits and process hardening intact, and add a test when you touch them.
- The UI is dark mode first.
- Write plain, short English in docs, comments, commit messages and UI text.

## Commits and pull requests

- Every commit needs a DCO sign-off (`git commit -s`); CI rejects commits without one.
- Never commit straight to `main`: branch and open a pull request.
- Update `CHANGELOG.md` for user-visible changes, and the matching page in `docs/` when behaviour
  changes.

## Checks to run before you finish

Backend (in `backend/`):

```sh
uv sync --all-groups
uv run ruff check . && uv run ruff format --check .
uv run pytest            # needs the compose Postgres: docker compose up -d postgres
```

Frontend (in `frontend/`):

```sh
npm install
npm run lint && npm run typecheck
npm test
```

Coverage floors are 80% of backend branches and 80% of frontend statements; don't lower them.
