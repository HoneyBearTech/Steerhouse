# Plan: contributing-node-26

## What Sean asked for

"fix the two follow-ups" (from #69: the Node version in the contributor guide, and a stale comment in
`ci.yml`).

## What we found

- `CONTRIBUTING.md` line 26 tells contributors to use Node.js 24 for the frontend. CI
  (`.github/workflows/ci.yml`, `node-version: "26"`), the frontend image (`frontend/Dockerfile`), the
  repo's guidelines file and the changelog all say Node 26.
- The second follow-up is a comment in `.github/workflows/ci.yml` (line 123) that calls the layout check
  "Not a required check (yet)", though it is required on `main`. Workflow files are changed only by the
  owner, so the team leaves that one to him (see Out of scope).

## What we'll change

1. **Contributor guide:** in `CONTRIBUTING.md`, change "Node.js 24" to "Node.js 26".
   Checked by: the line matches `node-version` in `ci.yml` and the Node version in `frontend/Dockerfile`,
   and no other contributor-facing page still names Node 24.
2. **Record the job** in `docs/pass-map.md` and `docs/decisions-log.md`.

## Who's on it

Engineer (makes the edit), Security Officer and Auditor (check it). No Researcher, because the job is a
one-line fix.

## Risks

- None for the app: it changes one line of documentation.

## Out of scope

- The comment in `.github/workflows/ci.yml`: the owner edits workflow files himself.
