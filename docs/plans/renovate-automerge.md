# Plan: renovate-automerge

## What Sean asked for

"Ensure that all my repos that have renovate allow the renovate PRs to auto
merge", on the homelab-atlas model: every update, majors included, merges once
all checks pass, after a 3-day wait.

## What we found

- Minor and patch updates of non-Docker packages already merge automatically
  after 3 days; images, digests and majors are still manual.
- Does a merge deploy? No: images publish only on release tags.

## What we'll change

1. `renovate.json`: turn on auto-merge for every update, majors included, the
   way homelab-atlas does it: `automerge: true`, squash merges,
   `platformAutomerge: true` (GitHub merges as soon as the required checks
   pass); new versions wait 3 days before they are proposed
   (`minimumReleaseAge`, with `timestamp-optional` so a registry without release
   dates doesn't hold an update forever); security fixes and image rebuilds
   (digest updates) skip the wait. Check: Renovate's config validator passes,
   and a local Renovate dry run shows auto-merge on for ordinary updates and off
   for the exceptions below.
2. Docs that say updates are merged by hand, or by Dependabot:
   docs/dependencies.md, GOVERNANCE.md, and the rule descriptions in
   renovate.json. Say instead that Renovate merges updates once every check
   passes, and name the exceptions.
3. Record the job in `docs/` (pass map, decisions log, roadmap; created if
   missing).

## Kept manual

- The uv group (image and tool version proposed together) stays manual, as its
  rule says.

Each exception is an earlier decision by the owner; to drop one, say so on this
pull request.

## Who's on it

Engineer, Security Officer, Auditor.

## Risks

- Majors now merge once CI passes; a release is still a separate, manual step.
- Renovate's schedule is unchanged, so updates still arrive once a week.

## Out of scope

Repository settings and branch rules (only the owner changes those), and the
workflows under `.github/workflows` (a leftover Dependabot auto-merge workflow
stays as it is).
