# Guidelines for this repository

Steerhouse is a self-hosted, Dockerized web UI for running Ansible playbooks. The backend (`backend/`) is FastAPI on Python 3.12, managed with `uv`; the frontend (`frontend/`) is React, TypeScript, Vite and Tailwind. The default branch is `main`.

Job notes live in `docs/`: `roadmap.md`, `pass-map.md`, `decisions-log.md`, plans in `docs/plans/` and reviews in `docs/reports/`.

## Checks

These 9 checks are required on `main`:

- **Backend lint + test**
- **Frontend lint + typecheck + build**
- **Analyze (python)**
- **Analyze (javascript-typescript)**
- **Build backend (runtime)**
- **Build frontend (runtime)**
- **DCO sign-off**
- **Dependency review**
- **Layout + contrast (browser)**

## Commands

CI uses Python 3.12 (3.12.11 or later) and Node 26.

Backend, in `backend/`:

```sh
uv lock --check
uv sync --locked --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest -v --cov --cov-report=term-missing:skip-covered --cov-report=json:/tmp/coverage.json
uv run python scripts/check_branch_coverage.py /tmp/coverage.json 80    # 80% branch coverage floor
```

CI also audits the locked dependencies with `pip-audit`; the exact commands are in `.github/workflows/ci.yml`.

The tests need Postgres. CI runs it as a service container and points `TEST_DATABASE_URL` at it. Locally, `docker compose up -d postgres` is enough: the tests use it by default. To use another server, set `TEST_DATABASE_URL`. The database name must end in `_test`, because the tests drop and recreate that database.

The secret store tests are skipped unless `TEST_OPENBAO_ADDR` and `TEST_OPENBAO_ROOT_TOKEN` are set. CI sets both.

Frontend, in `frontend/`:

```sh
npm ci
npm audit --audit-level=moderate
npm run lint
npm run typecheck
npm run coverage       # tests, with an 80% statement coverage floor
npm run build
npm run test:layout    # needs Google Chrome
```

CI also builds a second time and fails if the two builds differ.

For coding detail, see the editor instruction files under `.github/`.

## Conventions

- Sign off every commit (`git commit -s`, Developer Certificate of Origin).
- One branch and one pull request per change. Never commit straight to `main`.
- Update `CHANGELOG.md` and the matching page in `docs/` with user-visible changes.
- Security comes first: this app runs Ansible against real hosts. Keep permission checks, secret handling and scrubbing, the run firewall and egress limits intact, and add a test when you touch them.
- This repository is public. Never commit secrets or private details: no private hostnames, IP addresses, home directory paths or personal email addresses.
- Only the owner changes workflow files under `.github/workflows/`.

## Merging

Renovate merges its own pull requests once every required check passes (see `renovate.json`), except the uv group, which the owner merges.

Everything else, including the team's own pull requests, is merged by the owner.
