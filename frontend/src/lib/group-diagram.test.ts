import { describe, expect, it } from "vitest";

import type { InventoryGraph } from "@/lib/api";
import {
  ancestorsOf,
  buildDiagram,
  COLLAPSE_ABOVE,
  GROUP_HEIGHT,
  groupNodeId,
  initialExpanded,
  MAX_HOSTS,
} from "@/lib/group-diagram";
import { indexGroups } from "@/lib/group-graph";
import { graph } from "@/test/fixtures";

const G = graph(); // eu -> web, prod -> web, prod -> db, web -> web_eu
const INDEX = indexGroups(G);
const ALL = new Set(G.groups.map((g) => g.name));

function at(diagram: ReturnType<typeof buildDiagram>, name: string) {
  const node = diagram.nodes.find((n) => n.id === groupNodeId(name));
  if (!node) throw new Error(`${name} is not drawn`);
  return node.position;
}

describe("group diagram", () => {
  it("draws every group once, with an edge from each parent, left to right", () => {
    const diagram = buildDiagram({ graph: G, index: INDEX, expanded: ALL, selected: null });
    expect(diagram.nodes.map((n) => n.id).toSorted()).toEqual(G.groups.map((g) => groupNodeId(g.name)).toSorted());
    expect(diagram.edges.map((e) => `${e.source}>${e.target}`).toSorted()).toEqual(
      ["g:eu>g:web", "g:prod>g:db", "g:prod>g:web", "g:web>g:web_eu"].toSorted(),
    );
    expect(diagram.hidden).toBe(0);
    expect(at(diagram, "eu").x).toBeLessThan(at(diagram, "web").x);
    expect(at(diagram, "web").x).toBeLessThan(at(diagram, "web_eu").x);
  });

  it("never lays two nodes of one level on top of each other", () => {
    const { nodes } = buildDiagram({ graph: G, index: INDEX, expanded: ALL, selected: null });
    for (const a of nodes) {
      for (const b of nodes) {
        if (a.id < b.id && a.position.x === b.position.x) {
          expect(Math.abs(a.position.y - b.position.y)).toBeGreaterThanOrEqual(GROUP_HEIGHT);
        }
      }
    }
  });

  it("folds away what an unexpanded group would show, and says how many", () => {
    const folded = buildDiagram({ graph: G, index: INDEX, expanded: new Set(), selected: null });
    expect(folded.nodes.map((n) => n.id).toSorted()).toEqual(["g:eu", "g:prod"]);
    expect(folded.edges).toEqual([]);
    expect(folded.hidden).toBe(3);
    const prod = buildDiagram({ graph: G, index: INDEX, expanded: new Set(["prod"]), selected: null });
    expect(prod.nodes.map((n) => n.id).toSorted()).toEqual(["g:db", "g:eu", "g:prod", "g:web"]);
    expect(prod.hidden).toBe(1); // web_eu, under the still folded web
    const data = prod.nodes.find((n) => n.id === "g:web")!.data as { children: number; expanded: boolean };
    expect(data).toMatchObject({ children: 1, expanded: false });
  });

  it("highlights the way from the roots to the selected group", () => {
    const diagram = buildDiagram({ graph: G, index: INDEX, expanded: ALL, selected: "web_eu" });
    const lit = diagram.edges.filter((e) => e.highlighted).map((e) => `${e.source}>${e.target}`).toSorted();
    expect(lit).toEqual(["g:eu>g:web", "g:prod>g:web", "g:web>g:web_eu"]);
    expect(diagram.nodes.filter((n) => n.type === "group" && n.data.selected).map((n) => n.id)).toEqual(["g:web_eu"]);
  });

  it("hangs at most MAX_HOSTS hosts under a group, then says how many more", () => {
    const names = Array.from({ length: 40 }, (_, i) => `host${i}.example`);
    const diagram = buildDiagram({
      graph: G,
      index: INDEX,
      expanded: ALL,
      selected: "web",
      hosts: { group: "web", names, total: 40 },
    });
    expect(diagram.nodes.filter((n) => n.type === "host")).toHaveLength(MAX_HOSTS);
    const more = diagram.nodes.find((n) => n.type === "more");
    expect(more?.data).toMatchObject({ remaining: 40 - MAX_HOSTS, group: "web" });
    const fromWeb = diagram.edges.filter((e) => e.source === "g:web" && !e.target.startsWith("g:"));
    expect(fromWeb).toHaveLength(MAX_HOSTS + 1);
    const few = buildDiagram({
      graph: G,
      index: INDEX,
      expanded: ALL,
      selected: "web",
      hosts: { group: "web", names: names.slice(0, 3), total: 3 },
    });
    expect(few.nodes.some((n) => n.type === "more")).toBe(false);
  });

  it("draws no hosts for a group that is not drawn", () => {
    const diagram = buildDiagram({
      graph: G,
      index: INDEX,
      expanded: new Set(),
      selected: "web_eu",
      hosts: { group: "web_eu", names: ["a"], total: 1 },
    });
    expect(diagram.nodes.some((n) => n.type === "host")).toBe(false);
  });

  it("finds every group above one", () => {
    expect([...ancestorsOf("web_eu", INDEX)].toSorted()).toEqual(["eu", "prod", "web"]);
    expect([...ancestorsOf("eu", INDEX)]).toEqual([]);
  });

  it("starts a small inventory fully open and a big one at its roots", () => {
    expect(initialExpanded(G, INDEX)).toEqual(ALL);
    const many: InventoryGraph = {
      ...G,
      groups: [
        { name: "all", hosts: 0, children: Array.from({ length: COLLAPSE_ABOVE }, (_, i) => `g${i}`), origin: "static" },
        ...Array.from({ length: COLLAPSE_ABOVE }, (_, i) => ({ name: `g${i}`, hosts: 1, children: [], origin: "static" as const })),
      ],
    };
    expect(initialExpanded(many, indexGroups(many))).toEqual(new Set(["all"]));
  });
});
