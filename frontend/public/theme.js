// The saved theme ("dark", "light" or "system"; src/lib/theme.ts), applied before the first paint
// so a light page never flashes dark. A file, not an inline script: the CSP allows 'self' only.
try {
  var theme = localStorage.getItem("steerhouse-theme");
  if (theme === "light" || theme === "system") document.documentElement.dataset.theme = theme;
} catch {
  // No storage (blocked or private browsing): the dark default stays.
}
