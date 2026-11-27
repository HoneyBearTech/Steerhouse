import { render, screen as page } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import css from "@/index.css?raw";
import { hostTask, run, runHosts } from "@/test/fixtures";
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
