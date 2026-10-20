import { Graph, layout } from "@dagrejs/dagre";

import type { GroupIndex } from "@/lib/group-graph";
import type { HostOrigin, InventoryGraph } from "@/lib/api";

// Node boxes are a fixed size, so the layout needs no measuring pass.
export const GROUP_WIDTH = 240;
export const GROUP_HEIGHT = 52;
export const HOST_WIDTH = 176;
export const HOST_HEIGHT = 32;
// Hosts drawn under the selected group, and a group count above which only the roots and
// their children start expanded.
export const MAX_HOSTS = 25;
export const COLLAPSE_ABOVE = 60;

export interface GroupNodeData extends Record<string, unknown> {
  name: string;
  hosts: number;
  origin: HostOrigin;
  /** Children that exist, whether or not they are drawn. */
  children: number;
  expanded: boolean;
  selected: boolean;
}

export interface HostNodeData extends Record<string, unknown> {
  hostname: string;
  group: string;
}

export interface MoreNodeData extends Record<string, unknown> {
  remaining: number;
  group: string;
}

export type DiagramNode =
  | { id: string; type: "group"; position: Position; data: GroupNodeData }
  | { id: string; type: "host"; position: Position; data: HostNodeData }
  | { id: string; type: "more"; position: Position; data: MoreNodeData };

interface Position {
  x: number;
  y: number;
}

export interface DiagramEdge {
  id: string;
  source: string;
  target: string;
  /** On the way from a root to the selected group: drawn in the accent colour. */
  highlighted: boolean;
}

export interface Diagram {
  nodes: DiagramNode[];
  edges: DiagramEdge[];
  /** Groups in the inventory that are not drawn because an ancestor is collapsed. */
  hidden: number;
}

const GROUP_PREFIX = "g:";
const HOST_PREFIX = "h:";
const MORE_PREFIX = "m:";

export const groupNodeId = (name: string) => `${GROUP_PREFIX}${name}`;

/** The groups that start expanded: all of them for a small inventory, else the roots only. */
export function initialExpanded(graph: InventoryGraph, index: GroupIndex): Set<string> {
  return new Set(graph.groups.length > COLLAPSE_ABOVE ? index.roots : graph.groups.map((g) => g.name));
}

/** `name` and every group above it: expanding all of them makes `name` visible. */
export function ancestorsOf(name: string, index: GroupIndex): Set<string> {
  const seen = new Set<string>();
  const visit = (current: string) => {
    for (const parent of index.parents.get(current) ?? []) {
      if (seen.has(parent)) continue;
      seen.add(parent);
      visit(parent);
    }
  };
  visit(name);
  return seen;
}

/**
 * The nodes and edges to draw, laid out left to right. A group is drawn when it is a root or a
 * child of an expanded drawn group; a group with several parents is drawn once, with an edge
 * from each drawn parent. The selected group's hosts hang under it when `hosts` is given.
 */
export function buildDiagram(options: {
  graph: InventoryGraph;
  index: GroupIndex;
  expanded: ReadonlySet<string>;
  selected: string | null;
  hosts?: { group: string; names: string[]; total: number } | null;
}): Diagram {
  const { graph, index, expanded, selected, hosts } = options;
  const drawn = new Set<string>();
  const queue = [...index.roots];
  const edges: DiagramEdge[] = [];
  const onPath = selected ? new Set([selected, ...ancestorsOf(selected, index)]) : new Set<string>();
  while (queue.length > 0) {
    const name = queue.shift()!;
    if (drawn.has(name)) continue;
    drawn.add(name);
    if (!expanded.has(name)) continue;
    for (const child of index.childrenOf(name)) {
      edges.push({
        id: `e:${name}>${child}`,
        source: groupNodeId(name),
        target: groupNodeId(child),
        highlighted: onPath.has(name) && onPath.has(child),
      });
      queue.push(child);
    }
  }

  const g = new Graph();
  g.setGraph({ rankdir: "LR", nodesep: 14, ranksep: 64 });
  g.setDefaultEdgeLabel(() => ({}));
  const sizes = new Map<string, { width: number; height: number }>();
  const add = (id: string, width: number, height: number) => {
    sizes.set(id, { width, height });
    g.setNode(id, { width, height });
  };
  for (const name of drawn) add(groupNodeId(name), GROUP_WIDTH, GROUP_HEIGHT);
  for (const edge of edges) g.setEdge(edge.source, edge.target);

  const hostNodes: DiagramNode[] = [];
  if (hosts && drawn.has(hosts.group)) {
    const parent = groupNodeId(hosts.group);
    const shown = hosts.names.slice(0, MAX_HOSTS);
    for (const hostname of shown) {
      const id = `${HOST_PREFIX}${hosts.group}\u001f${hostname}`;
      add(id, HOST_WIDTH, HOST_HEIGHT);
      g.setEdge(parent, id);
      hostNodes.push({ id, type: "host", position: { x: 0, y: 0 }, data: { hostname, group: hosts.group } });
      edges.push({ id: `e:${id}`, source: parent, target: id, highlighted: false });
    }
    const remaining = hosts.total - shown.length;
    if (remaining > 0) {
      const id = `${MORE_PREFIX}${hosts.group}`;
      add(id, HOST_WIDTH, HOST_HEIGHT);
      g.setEdge(parent, id);
      hostNodes.push({ id, type: "more", position: { x: 0, y: 0 }, data: { remaining, group: hosts.group } });
      edges.push({ id: `e:${id}`, source: parent, target: id, highlighted: false });
    }
  }

  layout(g);
  const place = (id: string): Position => {
    const at = g.node(id) as { x: number; y: number };
    const size = sizes.get(id)!;
    return { x: Math.round(at.x - size.width / 2), y: Math.round(at.y - size.height / 2) };
  };

  const nodes: DiagramNode[] = [...drawn].map((name) => {
    const group = index.byName.get(name)!;
    return {
      id: groupNodeId(name),
      type: "group",
      position: place(groupNodeId(name)),
      data: {
        name,
        hosts: group.hosts,
        origin: group.origin,
        children: group.children.length,
        expanded: expanded.has(name),
        selected: name === selected,
      },
    };
  });
  for (const node of hostNodes) nodes.push({ ...node, position: place(node.id) } as DiagramNode);
  return { nodes, edges, hidden: graph.groups.length - drawn.size };
}
