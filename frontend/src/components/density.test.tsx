import { render, screen as page, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import css from "@/index.css?raw";
import { hostTask, run, runHosts } from "@/test/fixtures";
import { PAGE_ROUTES } from "@/test/pages";
import { renderApp } from "@/test/render";

import { Table, TableCell, TableHead } from "./ui/table";

// jsdom applies no Tailwind, so these pin the compact: classes and the selector that switches them on.
describe("compact density", () => {
  it("is switched on by the page's data-density attribute", () => {
    expect(css).toContain('@custom-variant compact (&:where([data-density="compact"] *));');
  });

  it("tightens the shared table's cells", () => {
    render(
      <Table>
        <tbody>
          <tr>
            <TableHead scope="row">Task</TableHead>
            <TableCell>ok</TableCell>
          </tr>
        </tbody>
      </Table>,
    );
    expect(page.getByRole("rowheader", { name: "Task" })).toHaveClass("py-2", "compact:py-1");
    expect(page.getByRole("cell", { name: "ok" })).toHaveClass("py-2", "compact:py-1");
  });

  it("tightens a run's row", async () => {
    const { screen } = renderApp("/runs", { routes: { "GET /runs": [run()] } });
    const row = await screen.findByRole("link", { name: /site\.yml/ });
    expect(row.querySelector(".p-4")).toHaveClass("compact:py-2");
  });

  it.each(["/runs", "/"])("tightens the gap between run rows on %s", async (path) => {
    const { screen } = renderApp(path, { routes: { "GET /runs": [run()] } });
    const rows = await screen.findAllByRole("link", { name: /site\.yml/ });
    for (const row of rows) expect(row.parentElement).toHaveClass("gap-2", "compact:gap-1");
  });

  it("tightens the inventory's host list", async () => {
    const { screen } = renderApp("/inventories/1/graph", { routes: PAGE_ROUTES });
    const summary = (await screen.findByText("web1.example")).closest("summary");
    expect(summary).toHaveClass("compact:min-h-6", "compact:gap-y-1", "compact:pointer-coarse:min-h-10");
    expect(summary?.parentElement).toHaveClass("py-2", "compact:py-1");
  });

  it("tightens the host list's empty message", async () => {
    const { screen } = renderApp("/inventories/1/graph", {
      routes: { ...PAGE_ROUTES, "GET /inventories/:id/hosts": { total: 0, hosts: [] } },
    });
    expect(await screen.findByText("No hosts match.")).toHaveClass("py-2", "compact:py-1");
  });

  it("tightens the inventory page's Hosts card", async () => {
    const { screen } = renderApp("/inventories/1", { routes: PAGE_ROUTES });
    const heading = await screen.findByRole("heading", { level: 2, name: "Hosts" });
    const header = heading.parentElement;
    const content = header?.nextElementSibling;
    expect(header).toHaveClass("compact:py-3");
    expect(content).toHaveClass("gap-3", "compact:gap-1.5", "compact:pb-3");
    const hostname = within(content as HTMLElement).getByText("web1.example");
    expect(hostname.parentElement).toHaveClass("gap-1", "compact:gap-0.5");
  });

  it("tightens the audit log's cards and the gap between them", async () => {
    const { screen } = renderApp("/audit", { routes: PAGE_ROUTES });
    const content = (await screen.findByText("credential.create")).closest(".p-4");
    expect(content).toHaveClass("gap-1", "compact:gap-0.5", "compact:py-2");
    // The card, then the list of cards.
    expect(content?.parentElement?.parentElement).toHaveClass("gap-2", "compact:gap-1");
  });

  it("keeps the run's status buttons at least 24 px tall, larger on touch screens", async () => {
    const { screen } = renderApp("/runs/7?view=hosts", {
      routes: {
        "GET /runs/:id": run(),
        "GET /runs/:id/hosts": runHosts({
          hosts: ["web1"],
          tasks: [hostTask({ name: "install", results: { web1: { status: "failed", changed: false, msg: null } } })],
        }),
      },
    });
    expect(await screen.findByRole("button", { name: "install on web1" })).toHaveClass("min-h-6", "pointer-coarse:min-h-10");
  });
});
