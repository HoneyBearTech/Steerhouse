// The saved theme ("dark", "light" or "system"; src/lib/theme.ts) and list density ("comfortable" or
// "compact"; src/lib/density.ts), applied before the first paint so a light page never flashes dark
// and rows don't jump. A file, not an inline script: the CSP allows 'self' only.
try {
  var theme = localStorage.getItem("steerhouse-theme");
  if (theme === "light" || theme === "system") document.documentElement.dataset.theme = theme;
  if (localStorage.getItem("steerhouse-density") === "compact") document.documentElement.dataset.density = "compact";
} catch {
  // No storage (blocked or private browsing): the dark, comfortable defaults stay.
}
