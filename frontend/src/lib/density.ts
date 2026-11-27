import * as React from "react";

/** How tightly lists and tables are spaced: comfortable (the default) or compact. */
export type Density = "comfortable" | "compact";

export const DENSITIES: { value: Density; label: string }[] = [
  { value: "comfortable", label: "Comfortable" },
  { value: "compact", label: "Compact" },
];

// public/theme.js reads the same key before the first paint.
const STORAGE_KEY = "steerhouse-density";
const listeners = new Set<() => void>();

function currentDensity(): Density {
  return document.documentElement.dataset["density"] === "compact" ? "compact" : "comfortable";
}

function subscribe(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

/** Switches the density now and remembers it in this browser. */
export function setDensity(density: Density) {
  document.documentElement.dataset["density"] = density;
  try {
    localStorage.setItem(STORAGE_KEY, density);
  } catch {
    // No storage: the choice lasts until the page is reloaded.
  }
  listeners.forEach((listener) => listener());
}

/** The chosen density. The spacing itself is CSS: the `compact:` variant in index.css. */
export function useDensity(): Density {
  return React.useSyncExternalStore(subscribe, currentDensity);
}
