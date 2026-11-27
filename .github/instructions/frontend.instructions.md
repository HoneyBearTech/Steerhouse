---
applyTo: "frontend/**"
---

# Frontend (React, TypeScript, Vite, Tailwind v4)

- Pages live in `frontend/src/pages/`, shared pieces in `frontend/src/components/`, helpers in
  `frontend/src/lib/` and app-wide state in `frontend/src/context/`.
- TypeScript is strict; don't use `any` or non-null assertions to silence the compiler.
- `oxlint --deny-warnings` must pass, so warnings count as errors.
- The UI is dark mode first. Use the existing Tailwind tokens and components instead of new colours.
- Every page must work at 375, 768, 1024, 1280 and 1920 px wide with no sideways scrolling, and pass axe
  (colour contrast, labels). "New" and "Add" dialogs must fit a phone screen.
- Tests are Vitest (`*.test.tsx`) through the real routing and permission checks against the fake API;
  layout tests are Playwright in `frontend/e2e/`.
