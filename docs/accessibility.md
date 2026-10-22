# Accessibility

Steerhouse aims to meet the [Web Content Accessibility Guidelines (WCAG) 2.1](https://www.w3.org/TR/WCAG21/)
at level AA, so that people who use a keyboard, a screen reader or other assistive technology can run
playbooks too. This page says what is checked, how, and what is known not to be covered yet. Problems are
bugs: please report them in [GitHub Issues](https://github.com/HoneyBearTech/Steerhouse/issues).

## What is checked

- **Every pull request** runs [axe-core](https://github.com/dequelabs/axe-core) against every page and the
  sign-in screen in the frontend test suite (`frontend/src/test/a11y.test.tsx`), with the WCAG 2.0 and
  2.1 A and AA rules and axe's best practices. A violation fails CI. The tests also find controls the way
  assistive technology does, by their accessible names and roles, so an unlabelled control usually
  breaks a test too.
- **Colour contrast** is checked twice on every pull request. The palette test
  (`frontend/src/test/contrast.test.ts`) computes the WCAG ratio of every colour pair the UI draws, in both
  themes: text and links on each surface, button text on its button, each run status on the surfaces and on
  its own tinted badge, input borders and the focus ring (see the table below). Then axe measures what each
  page really shows in Google Chrome against the built app, on every page and the sign-in screen, in the dark
  and the light theme (`frontend/e2e/layout.spec.ts`). The main dialogs and the full rule set are checked in
  the same browser by hand when the UI changes.
- **Keyboard use** was checked in the same browser: everything can be reached with Tab in a sensible order
  and shows a visible focus ring; dialogs take focus, keep it inside while open, close with Escape and
  return focus to the control that opened them; selects open and choose with the keyboard. The
  focus-return behaviour has a regression test.
- **Small screens** are checked on every pull request in the same browser run, at 375, 768, 1024 and
  1280 px wide with long names, e-mail addresses and URLs: no page may scroll sideways, and every "New"
  or "Add" dialog must fit a 375 × 667 phone screen (scrolling inside itself when it is taller) with its
  buttons in reach. Below 1280 px the navigation moves into a menu button.
- **Touch targets** are at least 24 × 24 px (WCAG 2.2, 2.5.8). On touch screens, small buttons, selects
  and menu links grow to about 40 px. Links inside a sentence are the usual exception.
- **The code editor** (playbooks, inventory source configs, Galaxy requirements) is a labelled multi-line
  text box that doesn't capture Tab, so keyboard users can always move on; read-only text is announced as
  read-only and can still be selected. Check results are a list with headings and a live summary, and
  each finding says "Error" or "Warning" in words next to its colour and icon. Ctrl+Shift+M (⌘ on a Mac)
  opens the editor's own list of the marked findings.

## How the UI is built for it

- **Two themes.** Steerhouse opens in a dark theme; the account menu (your user name in the header, or the
  menu button on a phone) switches to **Light** or **Same as device**, which follows the system's light or
  dark setting. The choice is remembered in this browser and applied before the page is drawn, so a light
  page never flashes dark. Both themes use the same checked pairs:

  | Colour | Dark | Light | Needs |
  | --- | --- | --- | --- |
  | Text on the page, cards, menus, panels and fields | `#e6e9f0` | `#121722` | 4.5:1 |
  | Secondary text | `#97a2b5` | `#515b6c` | 4.5:1 |
  | Accent: links, the current page, focus ring | `#a99bff` | `#5a3fd6` | 4.5:1 |
  | Text on a primary button | `#0b0f16` on `#a99bff` | `#ffffff` on `#5a3fd6` | 4.5:1 |
  | ok | `#4ade80` | `#106a36` | 4.5:1, also on its badge |
  | changed | `#facc15` | `#835204` | 4.5:1, also on its badge |
  | failed, unreachable, delete | `#f87171` | `#b21b1b` | 4.5:1, also on its badge |
  | skipped | `#38bdf8` | `#036194` | 4.5:1, also on its badge |
  | Input and outline-button borders | `#68748a` | `#7a8394` | 3:1 |

  The surfaces are `#0b0f16`, `#121722`, `#161b26` and `#1a2030` in the dark theme, and `#f5f6f9`,
  `#ffffff`, `#eef0f4` and `#eceff4` in the light one. The run statuses keep Ansible's own colours (green,
  yellow, red, cyan) and the accent is violet, so a link or the current page never looks like a status.
- **Type.** The UI is set in Geist Sans, and run output, playbooks and inventories in Geist Mono, whose
  zero, capital O, one and lower-case l are easy to tell apart. Both are served by Steerhouse itself.
- Components are built on [Radix UI](https://www.radix-ui.com/) primitives, which implement the WAI-ARIA
  patterns (dialog, select, checkbox, switch) including focus management and keyboard support.
- Every form control has a visible label tied to it (or an `aria-label` where the visible text is
  elsewhere, such as a row's role selector), every page has one `<h1>` with section headings below it,
  and the app has header, navigation and main landmarks.
- Run output keeps its colours (ANSI) but never relies on colour alone: statuses are written out
  ("failed", "changed", "unreachable") next to their colour.
- Lint rules (`jsx-a11y` in oxlint) catch common mistakes such as missing labels or misused roles.

## Known gaps

- **No high-contrast theme.** Dark and light are checked to WCAG AA; there is no separate high-contrast
  theme, and Windows' forced-colours mode isn't tested.
- **English only.** The UI isn't translated, and its text isn't yet extracted for translation.
- **The group diagram is visual.** The inventory's **Diagram** view (React Flow) can be used with the keyboard
  (Tab to a box's buttons, Enter to pick it or to open and close it), and zoomed with its buttons, but it does
  not announce how boxes connect, and arrow keys do not move between boxes. The **Tree** beside it has the same
  groups and is the accessible way to explore them. It respects the reduced-motion setting.
- **No screen-reader walk-through yet.** The checks above are automated plus a keyboard pass; nobody has
  yet tested complete tasks with a screen reader such as NVDA, JAWS or VoiceOver. Reports from people who
  do are very welcome.
