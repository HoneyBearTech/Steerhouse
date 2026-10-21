import { act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { hostTask, run, runHosts, viewerUser } from "@/test/fixtures";
import { renderApp } from "@/test/render";

const ok = { status: "ok" as const, changed: false, msg: null };
const failed = { status: "failed" as const, changed: false, msg: "disk full on web2" };

const results = runHosts({
  hosts: ["web1", "web2"],
  tasks: [
    hostTask({ key: "a", name: "install", results: { web1: ok, web2: ok } }),
    hostTask({ key: "b", name: "restart", results: { web1: ok, web2: failed } }),
  ],
});

const runRoute = { "GET /runs/:id": run() };

afterEach(() => vi.useRealTimers());

describe("run, by host", () => {
  it("shows a grid of hosts by tasks, marks tasks where hosts differ, and filters to them", async () => {
    const { screen, user } = renderApp("/runs/7?view=hosts", {
      routes: { ...runRoute, "GET /runs/:id/hosts": results },
    });
    expect(await screen.findByRole("columnheader", { name: "web2" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "web1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "restart on web2" })).toHaveTextContent("failed");
    expect(screen.getByText(/restart/)).toHaveTextContent("(hosts differ)");
    expect(screen.getByText("install")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: "Only tasks where hosts differ" }));
    expect(screen.queryByText("install")).not.toBeInTheDocument();
    expect(screen.getByText(/restart/)).toBeInTheDocument();
  });

  it("opens a cell to show the module's message", async () => {
    const { screen, user } = renderApp("/runs/7?view=hosts", {
      routes: { ...runRoute, "GET /runs/:id/hosts": results },
    });
    await user.click(await screen.findByRole("button", { name: "restart on web2" }));
    expect(await screen.findByText("disk full on web2")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toHaveTextContent("on web2");
  });

  it("says when nothing has reported, and when results are missing", async () => {
    const { screen } = renderApp("/runs/7?view=hosts", {
      routes: { ...runRoute, "GET /runs/:id/hosts": runHosts({ lost_events: 2, truncated: true }) },
    });
    expect(await screen.findByText("This run has no task results.")).toBeInTheDocument();
    expect(screen.getByText(/2 events too large to keep/)).toBeInTheDocument();
    expect(screen.getByText(/more tasks or hosts than are listed/)).toBeInTheDocument();
  });

  it("keeps refreshing until the run has finished", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { screen, api } = renderApp("/runs/7?view=hosts", {
      routes: { "GET /runs/:id": run({ status: "running" }), "GET /runs/:id/hosts": runHosts({ complete: false }) },
    });
    expect(await screen.findByText("No task has reported yet.")).toBeInTheDocument();
    api.set({ "GET /runs/:id/hosts": results });
    await act(() => vi.advanceTimersByTimeAsync(3100));
    expect(await screen.findByRole("button", { name: "restart on web2" })).toBeInTheDocument();
    const before = api.requests("GET /runs/7/hosts").length;
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(api.requests("GET /runs/7/hosts")).toHaveLength(before); // complete: no more asking
  });

  it("switches between the output and the grid with the tabs", async () => {
    const { screen, user } = renderApp("/runs/7", { routes: { ...runRoute, "GET /runs/:id/hosts": results } });
    expect(await screen.findByRole("tab", { name: "Run output", selected: true })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "By host" }));
    expect(await screen.findByRole("tab", { name: "By host", selected: true })).toBeInTheDocument();
    expect(await screen.findByRole("columnheader", { name: "web1" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Run output" }));
    expect(screen.queryByRole("columnheader", { name: "web1" })).not.toBeInTheDocument();
  });

  it("is available to viewers", async () => {
    const { screen } = renderApp("/runs/7?view=hosts", {
      user: viewerUser(),
      routes: { ...runRoute, "GET /runs/:id/hosts": results },
    });
    expect(await screen.findByRole("columnheader", { name: "web1" })).toBeInTheDocument();
  });
});

describe("compare with another run", () => {
  const earlier = runHosts({
    hosts: ["web1", "web2"],
    tasks: [
      hostTask({ key: "a", name: "install", results: { web1: ok, web2: ok } }),
      hostTask({ key: "b", name: "restart", results: { web1: ok, web2: ok } }),
    ],
  });
  const routes = {
    "GET /runs": [run({ id: 7 }), run({ id: 6, status: "failed" }), run({ id: 3 })],
    "GET /runs/:id": run({ id: 7 }),
    "GET /runs/:id/hosts": results,
  };

  it("offers the same playbook's other runs, the one before preselected, and shows the differences", async () => {
    const { screen, user, api } = renderApp("/runs/7?view=hosts", { routes });
    await user.click(await screen.findByRole("button", { name: "Compare with…" }));
    expect(await screen.findByText("Runs of site.yml, newest first.")).toBeInTheDocument();
    expect(api.requests("GET /runs").at(-1)?.query.get("playbook_id")).toBe("1");
    expect(await screen.findByRole("combobox", { name: "Run" })).toHaveTextContent("#6");

    api.set({ "GET /runs/:id/hosts": ({ params }: { params: Record<string, string> }) => (params["id"] === "6" ? earlier : results) });
    await user.click(screen.getByRole("button", { name: "Compare" }));
    expect(await screen.findByText(/Comparing run #7 with/)).toBeInTheDocument();
    // Only the task that differs is listed: restart on web2 was ok in run 6 and failed in run 7.
    expect(await screen.findByRole("button", { name: "restart on web2" })).toBeInTheDocument();
    expect(screen.queryByText("install")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "restart on web2" })).toHaveTextContent("ok");
    expect(screen.getByRole("button", { name: "restart on web2" })).toHaveTextContent("failed");

    await user.click(screen.getByRole("checkbox", { name: "Only tasks that differ between the runs" }));
    expect(await screen.findByText("install")).toBeInTheDocument();
  });

  it("can list every run in the project, and stop comparing", async () => {
    const { screen, user, api } = renderApp("/runs/7?view=hosts&compare=6", { routes });
    expect(await screen.findByText(/Comparing run #7 with/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Compare with another run…" }));
    await user.click(await screen.findByRole("checkbox", { name: "Show every run in this project" }));
    expect(await screen.findByText("Any run in this project, newest first.")).toBeInTheDocument();
    expect(api.requests("GET /runs").at(-1)?.query.has("playbook_id")).toBe(false);
  });
});
