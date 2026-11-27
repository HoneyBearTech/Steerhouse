# Plan: guidelines-file

## What Sean asked for

"add the missing guidelines file"

## What we found

- Steerhouse has no guidelines file at the top of the repo. Other HoneyBearTech repos have one (for
  example metrics and plex-director-mcp). It tells anyone working on the repo how it's built, how to
  test it, and who may merge what.
- The team's process reads a repo's merge rules from that file. Without it, the team can't tell which
  checks are required or who merges.
- The editor instruction files under `.github/` (added in #67) already cover coding rules and test
  commands for one editor. The new file links to them rather than copying them.
- `main` requires 9 checks: Backend lint + test, Frontend lint + typecheck + build, Analyze (python),
  Analyze (javascript-typescript), Build backend (runtime), Build frontend (runtime), DCO sign-off,
  Dependency review, and Layout + contrast (browser). Renovate merges its own pull requests once those
  pass (`renovate.json`), except the uv group, which the owner merges.

## What we'll change

1. **Add the repo's guidelines file** at the top of the repo, written for a public repo, under the same
   file name the other HoneyBearTech repos use. It contains:
   - **What Steerhouse is**, in one or two lines, and where the job notes live: `docs/roadmap.md`,
     `docs/pass-map.md`, `docs/decisions-log.md`, plans in `docs/plans/` and reviews in `docs/reports/`.
   - **Checks:** the 9 required checks above, by name.
   - **Commands:** how to install, test, lint and build the backend and the frontend, matching what CI
     runs (Python 3.12, Node 26, the Postgres the backend tests need, and the 80% coverage floors).
   - **Conventions:** DCO sign-off on every commit, one branch and pull request per change, the
     changelog and docs updated with user-visible changes, security first (permission checks, secret
     handling, the run firewall), no secrets or private details in this public repo, and workflow files
     changed only by the owner.
   - **Merging:** Renovate merges its own pull requests once every required check passes, except the uv
     group. Everything else, including the team's own pull requests, is merged by the owner. This
     writes down how things work today; it gives no one new permission to merge.

   Checked by: the file exists, each check name matches the branch rules, each command matches
   `.github/workflows/ci.yml` and `frontend/package.json`, and a security review finds no private
   hostnames, home paths or tool names in it.
2. **Record the job** in `docs/pass-map.md` and `docs/decisions-log.md`.

Nothing else changes: no code, no workflows, no settings.

## Who's on it

Engineer (writes the file), Security Officer and Auditor (check it). No Researcher, because the facts
above were gathered while planning.

## Risks

- If the file names the wrong checks or commands, people working on the repo follow wrong instructions.
  The review compares each one against CI.
- The file is public, so it must not mention the private notes, home paths or internal hosts.

## Out of scope

- Changing the editor instruction files from #67.
- Any change to merge permissions, branch rules or workflows.
