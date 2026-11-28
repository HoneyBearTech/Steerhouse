# Plan: denser-tables

## What Sean asked for

"start the team on the denser tables item" - the roadmap item "Denser tables for large lists on wide
screens".

## What we found

- Every page sits in one column about 1,150px wide (`max-w-6xl` in
  `frontend/src/components/app-shell.tsx`, lines 238 and 276), so on a wide monitor most of the screen is
  empty. The header and the page share that width, and all pages are drawn inside the same frame
  (`frontend/src/App.tsx`).
- Only one place uses the shared table component (`frontend/src/components/ui/table.tsx`): the run's
  per-host grid and compare view (`run-hosts-panel.tsx`). The other long lists - hosts in an inventory,
  runs, the audit log - are rows or cards with fixed spacing around them. So "denser" has to cover those
  lists too, or a setting would change almost nothing.
- The host list and audit log already load in pages; nothing renders very long lists in parts, and no new
  library is needed for this job.
- The theme choice (light/dark) is already remembered in the browser and applied before the page draws,
  from a small script file (`frontend/public/theme.js`); a density choice can work the same way.

## What we'll change

1. **Wider list pages on wide screens.** On screens 1,536px and wider, the frame decides the width from
   the page's address. These pages may use up to about 1,440px (`90rem`) instead of about 1,150px:
   - the runs list (`/runs`) and a run's page (`/runs/:id`, all its tabs, so the page doesn't change width
     when switching tabs);
   - an inventory's page and its group graph (`/inventories/:id`, `/inventories/:id/graph`);
   - the audit log (`/audit`).
   The header always uses the wider width on such screens, so it doesn't jump between pages; narrower
   pages stay centred under it. Forms (including "New run"), settings and every other page keep today's
   width, and nothing changes below 1,536px.
   Checked by: unit tests for which addresses are wide; the browser layout check gains a 1,920px width
   for every page, with no page scrolling sideways at any width.
2. **A Comfortable / Compact choice.** A "Density" choice in the user menu, next to Theme (and in the
   small-screen menu). It is remembered in the browser like the theme and applied before the page draws,
   from the same script file in `frontend/public/` (never inline in the page, which the security policy
   blocks). Comfortable (today's look) stays the default. Compact tightens the spacing of:
   - the run host grid and compare view;
   - the inventory host list and the inventory page's own Hosts card;
   - the runs list (which the dashboard's recent runs share);
   - the audit log.
   Buttons and links stay at least 24px tall, and larger on touch screens. The status buttons in the run
   host grid don't meet that today, so they get the same minimum size. No colours change.
   Checked by: unit tests that the choice switches, is remembered, and changes the spacing (with the test
   clean-up resetting it like the theme); the browser layout and contrast checks also run in Compact and
   at 1,920px; the test data gains a few audit events so the audit log isn't empty in those checks.
3. **Docs.** The user guide says where the Density choice is; the accessibility page and the frontend
   instruction file under `.github/instructions/` list the new 1,920px width; the changelog gets an entry
   under "Added".
   Checked by: review against the change.
4. **Record the job**: the roadmap item marked done in `docs/roadmap.md`, a row in `docs/pass-map.md`
   (the list of finished jobs) and an entry in `docs/decisions-log.md` (why this approach was chosen).

All existing checks must pass, including the 80% test coverage floor and the identical-build check.

## Who's on it

Researcher (done), Engineer, QA, Security Officer and Auditor, plus an independent plan check (done) and
a plain-English check of the final report.

## Risks

- A layout mistake could make a page scroll sideways on some screen size; the browser layout check covers
  every page at 375, 768, 1,024, 1,280 and now 1,920px.
- On wide screens, narrow pages sit centred under a wider header; that is intended, so the menu doesn't
  move between pages.
- Settings panels on an inventory's page get wider along with its host list.
- A second remembered preference only applies in the browser where it was chosen, like the theme.

## Out of scope

- Loading very long lists in parts (the runs list and run host grids show everything today). That needs
  a server change for the runs list and is only worth doing if it becomes slow; it can be its own job.
- Changing any other page's width, colours or the table component's look beyond spacing.
- Workflow files: the existing browser check already runs every test file, so no workflow change is
  needed.
