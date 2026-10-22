import * as React from "react";

/** The colour theme: dark (the default), light, or whatever the device prefers. */
export type Theme = "dark" | "light" | "system";

export const THEMES: { value: Theme; label: string }[] = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "system", label: "Same as device" },
];

// public/theme.js reads the same key before the first paint.
const STORAGE_KEY = "steerhouse-theme";
const LIGHT_QUERY = "(prefers-color-scheme: light)";
const listeners = new Set<() => void>();

function currentTheme(): Theme {
  const theme = document.documentElement.dataset["theme"];
  return theme === "light" || theme === "system" ? theme : "dark";
}

function deviceIsLight(): boolean {
  return window.matchMedia?.(LIGHT_QUERY).matches ?? false;
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  const query = window.matchMedia?.(LIGHT_QUERY);
  query?.addEventListener("change", onChange);
  return () => {
    listeners.delete(onChange);
    query?.removeEventListener("change", onChange);
  };
}

/** Switches the theme now and remembers it in this browser. */
export function setTheme(theme: Theme) {
  document.documentElement.dataset["theme"] = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // No storage: the choice lasts until the page is reloaded.
  }
  listeners.forEach((listener) => listener());
}

/** The chosen theme, and the one actually shown ("system" resolved against the device). */
export function useTheme(): { theme: Theme; resolved: "dark" | "light" } {
  const theme = React.useSyncExternalStore(subscribe, currentTheme);
  const light = React.useSyncExternalStore(subscribe, deviceIsLight);
  return { theme, resolved: theme === "system" ? (light ? "light" : "dark") : theme };
}
