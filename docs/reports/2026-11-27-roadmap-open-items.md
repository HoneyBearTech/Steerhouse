# Roadmap open items - status check (2026-11-27)

**What the owner asked for:** "check open items on the roadmap"

This report covers the five items under "Over the following year" in [roadmap.md](../roadmap.md). For
each one it says what exists today, what is left to do and roughly how big it is. It was checked against
`main` at `9302577`. Nothing in the app was changed.

## Summary

| Item | Started? | Size of what's left | Risk |
| --- | --- | --- | --- |
| A. Editor: completion and lint fixes as edits | No | Medium (completion), medium to large (fixes) | Low |
| B. Denser tables on wide screens | No | Small to medium | Low |
| C. Firewall helper so the worker can drop `NET_ADMIN` | No | Large | High, security-sensitive |
| D. Sign-in checked against more real providers | No | Medium, mostly testing and docs | Medium, security-sensitive |
| E. More inventory plugins and alert services | Partly; some already ship | Small per addition, open-ended | Low |

There is no unfinished work on any of these in other branches. The only open GitHub issue is Renovate's
dependency dashboard, so nobody has asked for a particular plugin or alert service yet.

## A. Editor: completion of module names and options, and ansible-lint fixes as edits

- **Today:** the editor (`frontend/src/components/code-editor.tsx`) highlights YAML and shows ansible-lint
  markers in the margin. ansible-lint runs in an isolated worker as a queued job (`backend/app/lint.py`,
  `backend/app/run_worker.py`). The worker refuses a repository's own ansible-lint config, because that
  config could make ansible-lint rewrite files. The frontend has no completion package
  (`@codemirror/autocomplete` is not in `frontend/package.json`).
- **What's left:**
  - **Completion (medium).** Choose where the list of modules and options comes from: either a list built
    when the image is built, or one fetched from a worker. Then add the editor's completion package and a
    backend endpoint or build step.
  - **Fixes as edits (medium to large).** The lint results would need to carry the proposed fix. The editor
    would then offer an "apply fix" action. The rule that ansible-lint never writes files itself must stay.
- **Notes:** completion can ship on its own, first. Fixes must never be applied silently to a playbook
  synced from git.

## B. Denser tables for large lists on wide screens

- **Today:** there is one shared table component (`frontend/src/components/ui/table.tsx`). The page width
  is capped at a medium size (`max-w-6xl` in `frontend/src/components/app-shell.tsx`), so wide screens are
  not used. There is no compact or density setting.
- **What's left (small to medium):** let the page use more width on large screens, and add a
  compact/comfortable choice for tables. Optionally, render very long host lists in parts so the page stays
  fast. Add wide-screen cases to the browser layout tests.
- **Open question:** whether "denser" means a user setting, or only using the extra width.

## C. Worker firewall changes in a helper of their own, so the worker can drop `NET_ADMIN`

- **Today:** the worker sets up its own firewall rules with nftables (`backend/app/worker/egress.py`).
  These rules keep runs away from the API and cloud metadata. To do that, it needs the `NET_ADMIN`
  permission (`docker-compose.yml`, `deploy/compose.yaml`). In production, a worker without it refuses to
  start unless the filter is turned off.
- **What's left (large):** a small helper process that alone keeps `NET_ADMIN` and accepts only narrow,
  validated requests from the worker. The worker would then run without `NET_ADMIN`. This changes both
  compose files, the image, the start-up checks, the docs and the upgrade guide, because existing installs
  must change their compose file.
- **Risks:** this is the firewall that separates runs from the rest of the system, so a mistake here would
  quietly weaken it. The channel between worker and helper must not be reachable from runs. The real
  firewall tests run only in the container build check in CI, so that check (a workflow file) would need
  updating too. Workflow files are changed only by the owner. Needs the full plan review and a security
  review.

## D. Single sign-on checked against more real providers

- **Today:** sign-in with any OpenID Connect provider (up to 8 at once), groups mapped to project roles,
  logout at the provider, and GitHub sign-in (`backend/app/oidc.py`, `backend/app/github_login.py`). The
  automated tests use a stand-in provider (`backend/tests/fake_oidc.py`), not real ones. The README names
  Google, Microsoft Entra, Keycloak, Authentik and Dex. Only Entra has a full walk-through, and no document
  records which providers were actually tried.
- **What's left (medium, mostly testing and docs):**
  - Record which providers have been tried.
  - Test against more real ones. Keycloak, Dex and Authentik can run in a throwaway container with no
    account. Google, Okta, Auth0 and Entra need a real account or tenant.
  - Publish a table of what works with each provider, and fix any quirks found.
- **Risks:** sign-in code is security-sensitive. A quirk fix must not loosen the rule that an account is
  linked only by a verified email. Running providers in CI would need a workflow change, which the owner
  makes.

## E. More dynamic-inventory plugins and notification services

- **Today, already shipping:**
  - Alerts go to email, Pushbullet, Pushover, ntfy, Gotify, Discord, Slack, Teams and plain webhooks
    (`backend/app/notifications/channels.py`).
  - Any inventory plugin in the bundled Ansible package can be named. The AWS and Proxmox plugins' extra
    Python packages are in the image and tested (`backend/tests/test_inventory_plugin_packages.py`).
  - Other plugins, such as Azure, Google Cloud, VMware and Kubernetes, will fail when they refresh, because
    their Python packages are not in the image.
- **What's left (small per addition):**
  - **Each plugin:** add its package, a test that it loads, and an example.
  - **Each alert service:** a check of its settings, a sender, form fields and a test. Outbound calls go
    through the existing address checks (`backend/app/notifications/safe_http.py`).
  - Candidates: Azure, Google Cloud and Kubernetes inventories; Telegram, Matrix and Mattermost alerts.
- **Notes:** the roadmap says "where people ask for them", and no one has asked yet. Each new package makes
  the image bigger and adds dependencies that are scanned for vulnerabilities.

## Other open work found (not on the roadmap)

- **Accessibility gaps** listed in [accessibility.md](../accessibility.md):
  - There is no high-contrast theme, and forced-colours mode is untested.
  - The interface is English only.
  - The group diagram can't be explored by keyboard or screen reader (the tree view is the accessible
    alternative).
  - No full screen-reader walk-through has been done.
- **Kubernetes:** the docs mention it, but the repo ships only compose files. This matters for item C.
- **Housekeeping:** old Dependabot branches are still on GitHub, left over from before the move to
  Renovate.
- No TODO or FIXME markers in the code or docs.

## Recommended order

1. **E, one addition at a time, when someone asks for one.** It is the smallest and safest, and follows an
   existing pattern.
2. **B.** Small, frontend only, easy to check in the browser tests.
3. **A, completion first, then fixes.** A visible feature with low risk.
4. **D.** Can start any time with self-hosted providers. Hosted ones need accounts from the owner.
5. **C last.** The biggest and riskiest, and it needs the owner to update a CI workflow.
