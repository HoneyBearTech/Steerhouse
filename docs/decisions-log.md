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
