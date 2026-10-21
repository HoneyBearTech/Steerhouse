import { describe, expect, it } from "vitest";

import { compareRuns, hostsDiffer } from "@/lib/run-hosts";
import { hostTask, runHosts } from "@/test/fixtures";

const ok = { status: "ok" as const, changed: false, msg: null };
const changed = { status: "changed" as const, changed: true, msg: null };
const failed = { status: "failed" as const, changed: false, msg: "boom" };

describe("hostsDiffer", () => {
  it("is true only when hosts with a result disagree", () => {
    expect(hostsDiffer(hostTask({ results: { a: ok, b: ok } }))).toBe(false);
    expect(hostsDiffer(hostTask({ results: { a: ok, b: failed } }))).toBe(true);
    expect(hostsDiffer(hostTask({ results: { a: ok } }))).toBe(false);
  });
});

describe("compareRuns", () => {
  const first = runHosts({
    hosts: ["a", "b"],
    tasks: [
      hostTask({ key: "one", name: "one", results: { a: ok, b: ok } }),
      hostTask({ key: "two", name: "two", results: { a: changed, b: failed } }),
      hostTask({ key: "gone", name: "gone", results: { a: ok } }),
    ],
  });
  const second = runHosts({
    hosts: ["b", "c"],
    tasks: [
      hostTask({ key: "one", name: "one", results: { b: ok, c: ok } }),
      hostTask({ key: "two", name: "two", results: { b: failed } }),
      hostTask({ key: "new", name: "new", results: { c: ok } }),
    ],
  });

  it("matches rows by key and takes the union of the hosts", () => {
    const { hosts, rows } = compareRuns(first, second);
    expect(hosts).toEqual(["a", "b", "c"]);
    expect(rows.map((row) => row.key)).toEqual(["one", "two", "gone", "new"]);
  });

  it("marks a host that did the same as the same, and one that differs, or is missing, as different", () => {
    const [one, two, gone, added] = compareRuns(first, second).rows;
    expect(one?.cells["b"]?.state).toBe("same");
    expect(one?.cells["a"]?.state).toBe("only-a");
    expect(one?.cells["c"]?.state).toBe("only-b");
    expect(one?.differs).toBe(true); // hosts a and c are in only one run each
    expect(two?.cells["b"]?.state).toBe("same");
    expect(two?.cells["a"]?.state).toBe("only-a");
    expect(gone?.only).toBe("a");
    expect(added?.only).toBe("b");
  });

  it("calls two identical runs identical, and a changed outcome changed", () => {
    expect(compareRuns(first, first).rows.every((row) => !row.differs)).toBe(true);
    const worse = runHosts({
      hosts: ["a", "b"],
      tasks: [hostTask({ key: "one", name: "one", results: { a: ok, b: failed } })],
    });
    const only = compareRuns(runHosts({ hosts: ["a", "b"], tasks: [first.tasks[0]!] }), worse).rows[0];
    expect(only?.cells["b"]?.state).toBe("changed");
    expect(only?.cells["a"]?.state).toBe("same");
    expect(only?.differs).toBe(true);
  });
});
