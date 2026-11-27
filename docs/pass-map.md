# Pass map

A short record of each piece of maintenance work: when it happened, what shipped, and where.

| Date | Job | What shipped | PR |
| --- | --- | --- | --- |
| 2026-11-20 | renovate-migrate | Dependency updates moved from Dependabot to Renovate (`renovate.json`; `.github/dependabot.yml` removed). Patch and minor updates of Python packages, npm packages and GitHub Actions merge by themselves after the required checks pass and a 3-day release age. Container images, majors and the uv group wait for the maintainer. Docs updated. | [#59](https://github.com/HoneyBearTech/Steerhouse/pull/59) |
| 2026-11-20 | fix-audit-deps | Three backend dependencies with known vulnerabilities updated in `backend/uv.lock` (dnspython 2.9.2, filelock 4.2.12, pyasn1 0.6.5), so the backend dependency audit passes again. | [#60](https://github.com/HoneyBearTech/Steerhouse/pull/60) |
| 2026-11-20 | `renovate-automerge` | Renovate merges its pull requests itself once every check passes, majors included; new versions wait 3 days, security fixes and image rebuilds don't. The uv group stays manual. `platformAutomerge` is true; replaces the earlier minor/patch-only rule. | #61 |
| 2026-11-27 | `roadmap-open-items` | Status check of the five open roadmap items: none started, except that some inventory plugins and alert services already ship. Report with what is left, sizes and a suggested order in `docs/reports/2026-11-27-roadmap-open-items.md`. Nothing in the app changed. | [#68](https://github.com/HoneyBearTech/Steerhouse/pull/68) |
| 2026-11-27 | `guidelines-file` | The repo's guidelines file added at the root: what Steerhouse is, where the job notes live, the 9 required checks, the backend and frontend commands CI runs, conventions (sign-off, one pull request per change, public-repo rules, workflow files changed only by the owner) and who merges. Writes down current practice; no new merge permission. No code, workflow or setting changed. | [#69](https://github.com/HoneyBearTech/Steerhouse/pull/69) |
| 2026-11-27 | `contributing-node-26` | `CONTRIBUTING.md` now says Node.js 26 for the frontend, matching CI and the frontend image (it still said 24). The stale comment in `ci.yml` that calls the layout check optional is left for the owner, who edits workflow files. | [#70](https://github.com/HoneyBearTech/Steerhouse/pull/70) |
