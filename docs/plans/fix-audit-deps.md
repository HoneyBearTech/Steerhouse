# Plan: fix the three vulnerable backend packages

## What Sean asked for

"Open the small job to fix them": the three packages that make the backend dependency audit fail.

## What we found

- The "Backend lint + test" check fails at its dependency audit on `main` every night, and on every pull request (including #59). It reports 19 known vulnerabilities in three packages:
  - dnspython 2.8.0 (fixed in 2.9.2)
  - filelock 4.0.12 (fixed in 4.2.1)
  - pyasn1 0.6.4 (fixed in 0.6.5)
- None of the three is listed directly in `backend/pyproject.toml`. Other packages pull them in, and they're pinned only in `backend/uv.lock`.
- They have to be fixed together. A pull request that fixes only one of them still fails the audit because of the other two.

## What we'll change

1. **Update the three packages in `backend/uv.lock`** to their fixed versions or later, and change nothing else in the lock file. We use the same uv version that CI uses.
   *Checked by:* the lock file diff shows only those three packages changing; `uv lock --check` passes; the same dependency audit CI runs (`pip-audit` 2.10.1) finds nothing.
2. **Run the backend tests** to make sure nothing that uses these packages broke.
   *Checked by:* lint, format check and the test suite pass locally, then the full required checks pass on the pull request.
3. **Add a `CHANGELOG.md` entry** under Unreleased that names the three updates.

## Who's on it

Engineer, Security Officer, Auditor and the CEO. This is a small job, so there's no Researcher and no QA. The Auditor reruns the checks.

## Risks

- A newer filelock (4.0 → 4.2) or dnspython (2.8 → 2.9) could change behaviour the tests don't cover. Both are minor releases, so the risk is low.

## Out of scope

- Any other dependency update. Renovate will propose those once #59 is merged.
- Workflow files and repository settings.
