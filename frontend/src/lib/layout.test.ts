import { describe, expect, it } from "vitest";

import { isWideRoute } from "./layout";

describe("isWideRoute", () => {
  it.each(["/runs", "/runs/", "/runs/7", "/inventories/1", "/inventories/1/graph", "/audit"])("%s is wide", (path) => {
    expect(isWideRoute(path)).toBe(true);
  });

  it.each([
    "/",
    "/runs/new",
    "/runs/new/",
    "/inventories",
    "/playbooks",
    "/playbooks/1",
    "/templates",
    "/account",
    "/users",
    "/audit/1",
    "/runs/7/hosts",
  ])("%s is not wide", (path) => {
    expect(isWideRoute(path)).toBe(false);
  });
});
