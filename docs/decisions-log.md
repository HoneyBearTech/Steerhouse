# Decisions log

Maintenance decisions, why they were made, and what was considered instead.

## 2026-11-20 - Renovate replaces Dependabot (renovate-migrate, #59)

**Decision.** Renovate (`renovate.json`) now proposes all dependency updates. `.github/dependabot.yml` is
removed in the same change, so the repository always has an update tool (the OpenSSF Scorecard
Dependency-Update-Tool check keeps passing). Dependabot security updates were turned off in the repository
settings; Dependabot alerts stay on, and Renovate reads them to open security-fix pull requests.

**Automatic merging.** Patch and minor updates of Python packages, npm packages and GitHub Actions merge by
themselves (GitHub auto-merge, squash). This mirrors what `dependabot-auto-merge.yml` did, with an added
3-day minimum release age. Container images (including digests), major versions and the uv group always wait
for the maintainer. Security fixes skip the age wait and the weekly schedule. The `main` ruleset requires
nine checks (backend, frontend, both CodeQL analyses, both image builds, DCO, dependency review, layout) with
no bypass actors, so an automatic merge can't land before they pass.

**Why.** The owner wanted one update tool. Renovate was already installed for the repository but switched
off, for lack of a config file. The earlier draft (#54) was reused as the starting point.

**Alternatives rejected.**
- A minimal config (recommended preset only): it would have dropped tracking of the images pinned in the
  workflows and the uv group.
- No automatic merging, as in the #54 draft: the owner asked for small safe updates to keep merging on their own.

**Left as is.** `.github/workflows/dependabot-auto-merge.yml` and two workflow comments that still name
Dependabot (`ci.yml` and `docker-build.yml`) are unchanged, because workflow files are outside this job. The
workflow only acts on Dependabot's pull requests, so it no longer runs. The owner can remove them later.

**Review findings rejected.**
- "The uv version in `ci.yml` and `fuzz.yml` isn't tracked": wrong. Renovate's GitHub Actions manager reads
  the `version` input of `astral-sh/setup-uv`. It was missed only because local dry runs had no GitHub access.
- "Exclude the actions used by the publish workflow from automatic merging": not done. Dependabot merged
  these with no wait at all, the 3-day age is already stricter, and the required checks still apply.
- "Hold back security fixes, or stop them merging on their own": not done. Security fixes are meant to land
  quickly, and the required checks still gate them.
- "Add lock file maintenance": out of scope. Dependabot didn't do it either, and the audits in CI catch known
  vulnerabilities in indirect dependencies.

**Findings fixed during review.** The uv group's two entries now become eligible at the same time, so the
image and the workflow version are always proposed together. Service images in `ci.yml` no longer join the
GitHub Actions group, where they would have blocked its automatic merge. Two sentences in the docs were
corrected.

## 2026-11-20 - Fix the three vulnerable backend dependencies (fix-audit-deps, #60)

**Decision.** dnspython (2.8.0 to 2.9.2), filelock (4.0.12 to 4.2.12) and pyasn1 (0.6.4 to 0.6.5) were
updated in `backend/uv.lock` only, to the first versions that fix the vulnerabilities the dependency audit
reported. No other package moved.

**Why.** The backend check failed on `main` and on #59 because the audit found known vulnerabilities in these
three indirect dependencies. Fixing them in their own small pull request kept the Renovate change separate
and let both pass their checks.

**Alternatives rejected.**
- Refreshing the whole lock file: it would have moved many unrelated packages at once.
- Waiting for Renovate's first run to propose the fixes: #59 couldn't pass its required checks until then.

**Note.** The lock file's format number went from 3 to 5; the uv versions used in CI and in the backend
image both read it. Review findings rejected: none.

## 2026-11-20: Renovate merges its own pull requests

Job `renovate-automerge` (#61).

**Decision.** Renovate merges its pull requests itself once every check passes,
majors included; new versions wait 3 days, security fixes and image rebuilds
don't, on the model homelab-atlas already uses. Kept manual: the uv group stays
manual. `platformAutomerge` is true; replaces the earlier minor/patch-only rule.

**Why.** The owner asked for every repo with Renovate to merge its updates
automatically (2026-11-20) and chose this model, majors included, over keeping
majors manual.

**Not done.** Repository settings and branch rules (owner only) and workflows
are unchanged. A group merges automatically only when every update in it may, so
each manual exception gets its own pull request.

**Review findings.** Fixed: stale docs that still promised a manual review or
named Dependabot, and (where it applied) exceptions that sat inside the update
group. None declined.

## 2026-11-27 - Status check of the open roadmap items (roadmap-open-items)

**Decision.** The roadmap's five open items stay as they are. A status report records what exists, what is
left and a suggested order: further inventory plugins and alert services first (when asked for), then denser
tables, editor completion, real-provider sign-in checks, and the firewall helper last.

**Why.** The firewall helper is the largest and riskiest change: it moves the boundary that keeps runs away
from the API, changes the compose files and the upgrade steps, and needs a CI workflow update that only the
owner makes. The other items are smaller and independent of it.

**Alternatives rejected.** Starting with the firewall helper for its security value: it would hold up
smaller work and needs an owner-made workflow change first.

**Review findings.** None declined.
