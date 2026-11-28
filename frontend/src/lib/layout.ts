import { matchPath } from "react-router-dom";

// The list pages that use the extra room on wide screens (2xl). Forms, settings and every other page
// keep the normal width.
const WIDE_ROUTES = ["/runs", "/runs/:id", "/inventories/:id", "/inventories/:id/graph", "/audit"];

/** Whether the page at this path is drawn wider on wide screens. Decided from the address alone. */
export function isWideRoute(pathname: string): boolean {
  // "New run" is a form, though its address also fits /runs/:id.
  if (matchPath("/runs/new", pathname)) return false;
  return WIDE_ROUTES.some((pattern) => matchPath(pattern, pathname) !== null);
}
