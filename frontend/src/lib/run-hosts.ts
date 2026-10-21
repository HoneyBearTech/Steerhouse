import type { HostResult, HostStatus, HostTask, RunHosts } from "@/lib/api";

export const STATUS_LABEL: Record<HostStatus, string> = {
  ok: "ok",
  changed: "changed",
  failed: "failed",
  ignored: "failed (ignored)",
  skipped: "skipped",
  unreachable: "unreachable",
};

// Did the hosts of one run do different things in this task? (Hosts without a result don't count.)
export function hostsDiffer(task: HostTask): boolean {
  const seen = new Set(Object.values(task.results).map((result) => result.status));
  return seen.size > 1;
}

export type CellState = "same" | "changed" | "only-a" | "only-b";

export interface CompareCell {
  a: HostResult | undefined;
  b: HostResult | undefined;
  state: CellState;
}

export interface CompareRow {
  key: string;
  play: string;
  role: string | null;
  name: string;
  handler: boolean;
  cells: Record<string, CompareCell>;
  // The row is only in one of the runs, or at least one host did something different.
  differs: boolean;
  only: "a" | "b" | null;
}

export interface Comparison {
  hosts: string[];
  rows: CompareRow[];
}

function cellState(a: HostResult | undefined, b: HostResult | undefined): CellState {
  if (a && b) return a.status === b.status ? "same" : "changed";
  return a ? "only-a" : "only-b";
}

// Rows of A first, in its order, then those only B has; hosts are the union. A host with no result in a
// run (it wasn't targeted, or the task didn't reach it) is a difference from one that has.
export function compareRuns(a: RunHosts, b: RunHosts): Comparison {
  const byKeyB = new Map(b.tasks.map((task) => [task.key, task]));
  const seenKeys = new Set<string>();
  const rows: CompareRow[] = [];
  const hosts = [...new Set([...a.hosts, ...b.hosts])].toSorted();

  function row(task: HostTask, other: HostTask | undefined, only: "a" | "b" | null): CompareRow {
    const first = only === "b" ? other : task;
    const second = only === "b" ? task : other;
    const cells: Record<string, CompareCell> = {};
    let differs = only !== null;
    for (const host of hosts) {
      const left = first?.results[host];
      const right = second?.results[host];
      if (!left && !right) continue;
      const state = cellState(left, right);
      cells[host] = { a: left, b: right, state };
      if (state !== "same") differs = true;
    }
    return {
      key: task.key,
      play: task.play,
      role: task.role,
      name: task.name,
      handler: task.handler,
      cells,
      differs,
      only,
    };
  }

  for (const task of a.tasks) {
    seenKeys.add(task.key);
    const other = byKeyB.get(task.key);
    rows.push(row(task, other, other ? null : "a"));
  }
  for (const task of b.tasks) {
    if (!seenKeys.has(task.key)) rows.push(row(task, undefined, "b"));
  }
  return { hosts, rows };
}
