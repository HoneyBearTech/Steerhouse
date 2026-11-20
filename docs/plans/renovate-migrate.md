# Plan: move dependency updates from Dependabot to Renovate

## What Sean asked for

"Remove Dependabot workflows, turn off Dependabot security updates, and turn on Renovate."

## What we found

- Dependabot is still set up here (`.github/dependabot.yml`) and is opening update pull requests (#55-#58).
- Renovate is installed for this repository but switched off, because the repository has no Renovate settings file. An earlier draft (#54, closed without merging) already wrote one. It still matches the current `main` exactly, but it never merges anything automatically.
- Today, a small workflow merges Dependabot's patch and minor updates by itself once the required checks pass. It never does this for container images. That workflow only reacts to Dependabot, so it stops doing anything once Dependabot is gone. Workflow files are outside what this job may change, so it stays.
- Dependabot security updates are already turned off for the repository. Dependabot *alerts* stay on: Renovate reads them to open its own security-fix pull requests.

## What we'll change

1. **Add `renovate.json`** at the top of the repository. It starts from the #54 draft and covers the same things Dependabot did:
   - backend Python packages, frontend npm packages, the Dockerfiles, both compose files and GitHub Actions;
   - the same two "always together" groups (react with react-dom, and the CodeQL actions);
   - weekly updates on Monday morning, assigned to Sean.

   It also tracks the pinned images inside the workflows, which Dependabot never saw.
   *Checked by:* the official Renovate config checker in strict mode, and a dry run against the branch that lists which updates it would propose.
2. **Merge safe small updates automatically, the same way as before.** Patch and minor updates to Python packages, npm packages and GitHub Actions merge by themselves, but only after GitHub's required checks pass, using the repository's normal squash merge. Three things always wait for Sean: container image updates, major version jumps and the uv tool group. A new release must also be at least 3 days old before it merges automatically. This guards against a bad release that gets pulled soon after it's published. Security fixes don't wait.
   *Checked by:* reading the dry-run output to confirm which updates would merge automatically and which would wait.
3. **Remove `.github/dependabot.yml`** in the same change. Both files land together, so the repository is never without an update tool. The OpenSSF Scorecard check for an update tool keeps passing.
   *Checked by:* the file is gone and `renovate.json` is present in the same commit range.
4. **Update the docs that name Dependabot**: `GOVERNANCE.md`, `docs/dependencies.md`, `docs/assurance-case.md`, the comment at the top of `backend/Dockerfile`, and a new `CHANGELOG.md` entry under Unreleased. Older changelog entries stay as they were.
   *Checked by:* a search for "Dependabot" outside `.github/workflows` and old changelog entries finds nothing out of date.

## Who's on it

Engineer, QA, Security Officer, Auditor, a second security review (this change decides how outside code arrives in the project), and the CEO.

## After merging (for Sean)

- Close the four open Dependabot pull requests (#55-#58). Renovate will open its own versions, grouped.
- Renovate opens a "Dependency Dashboard" issue on its first run. That is expected.
- Optional, any time: delete `.github/workflows/dependabot-auto-merge.yml` and the two workflow comments that still say "Dependabot" (`ci.yml` and `docker-build.yml`, lines 7-9). They're harmless but out of date. This job can't change workflow files.

## Risks

- Automatic merging relies on the required checks in the `main` branch rules. The team can't read those rules. `CONTRIBUTING.md` says the backend, frontend, layout, static analysis, dependency and image checks are required. If one of them isn't actually required, an automatic merge could happen before it finishes.
- A minor update can still break something that the tests don't cover. This was already true with Dependabot.

## Out of scope

- Any change under `.github/workflows`, including the old auto-merge workflow.
- Repository settings (security updates were already turned off by Sean).
- The other repositories that still use Dependabot. Each gets its own job after this pilot.
