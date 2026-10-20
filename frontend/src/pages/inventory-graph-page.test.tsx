import { within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { graph, inventory, mergedHost } from "@/test/fixtures";
import { renderApp } from "@/test/render";

// jsdom can't lay out React Flow (no ResizeObserver, no sizes): the page test stands in for it with
// a list of buttons; the real component is checked in a browser (frontend/e2e/layout.spec.ts).
vi.mock("@/components/inventory-diagram", () => ({
  default: ({ graph: g, selected, onSelect }: { graph: { groups: { name: string }[] }; selected: string | null; onSelect: (n: string) => void }) => (
    <section aria-label="Group diagram" data-selected={selected ?? ""}>
      {g.groups.map((group) => (
        <button key={group.name} type="button" onClick={() => onSelect(group.name)}>
          diagram {group.name}
        </button>
      ))}
    </section>
  ),
}));

// No "GET /inventories/:id": its host vars aren't masked, and this page has no use for them.
const ROUTES = {
  "GET /inventories/:id/graph": graph(),
  "GET /inventories/:id/hosts": { total: 1, hosts: [mergedHost()] },
};

function rows(screen: ReturnType<typeof renderApp>["screen"]) {
  return screen.getAllByRole("treeitem").map((item) => item.querySelector(".font-mono")?.textContent);
}

describe("inventory group graph", () => {
  it("is linked from the inventory page", async () => {
    const { screen } = renderApp("/inventories/1", {
      routes: { "GET /inventories/:id": inventory(), "GET /inventories/:id/sources": [], "GET /inventories/:id/targets": {} },
    });
    expect(await screen.findByRole("link", { name: "Group graph" })).toHaveAttribute("href", "/inventories/1/graph");
  });

  it("starts with the top-level groups and opens them with the keyboard", async () => {
    const { screen, user, api } = renderApp("/inventories/1/graph", { routes: ROUTES });
    expect(await screen.findByRole("heading", { level: 1, name: "Group graph" })).toBeInTheDocument();
    expect(screen.getByText(/5 groups and 6 hosts, 1 of them in no group/)).toBeInTheDocument();
    const tree = screen.getByRole("tree", { name: "Groups" });
    expect(rows(screen)).toEqual(["eu", "prod"]);

    await user.click(screen.getByRole("textbox", { name: "Search groups" }));
    await user.tab(); // Expand all
    await user.tab(); // Collapse all is disabled, so the tree's one tab stop is next
    const eu = within(tree).getAllByRole("treeitem")[0]!;
    expect(eu).toHaveFocus();
    expect(eu).toHaveAttribute("aria-expanded", "false");
    expect(eu).toHaveAttribute("aria-level", "1");

    await user.keyboard("{ArrowRight}");
    expect(eu).toHaveAttribute("aria-expanded", "true");
    expect(rows(screen)).toEqual(["eu", "web", "prod"]);
    await user.keyboard("{ArrowRight}"); // into the first child
    const web = screen.getAllByRole("treeitem")[1]!;
    expect(web).toHaveFocus();
    expect(web).toHaveAttribute("aria-level", "2");
    expect(within(web).getByText("also under prod")).toBeInTheDocument();

    await user.keyboard("{ArrowRight}{ArrowDown}");
    expect(rows(screen)).toEqual(["eu", "web", "web_eu", "prod"]);
    expect(screen.getAllByRole("treeitem")[2]).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { level: 2, name: "web_eu" })).toBeInTheDocument();
    expect(screen.getAllByRole("treeitem")[2]).toHaveAttribute("aria-selected", "true");
    await screen.findByText("web1.example");
    expect(api.calls.some((c) => c.path === "/inventories/1/hosts" && c.query.get("group") === "web_eu")).toBe(true);
    expect(api.unhandled).toEqual([]);

    await user.keyboard("{ArrowLeft}"); // to the parent
    expect(screen.getAllByRole("treeitem")[1]).toHaveFocus();
    await user.keyboard("{ArrowLeft}"); // closes it
    expect(rows(screen)).toEqual(["eu", "web", "prod"]);
    await user.keyboard("{End}");
    expect(screen.getAllByRole("treeitem").at(-1)).toHaveFocus();
    await user.keyboard("{Home}");
    expect(screen.getAllByRole("treeitem")[0]).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Expand all" }));
    // prod > web > web_eu and prod > db; eu > web > web_eu: web appears under both parents
    expect(rows(screen)).toEqual(["eu", "web", "web_eu", "prod", "web", "web_eu", "db"]);
    await user.click(screen.getByRole("button", { name: "Collapse all" }));
    expect(rows(screen)).toEqual(["eu", "prod"]);
  });

  it("opens at a linked group with its parents, children and hosts", async () => {
    const { screen, user, api } = renderApp("/inventories/1/graph?group=web", { routes: ROUTES });
    const where = await screen.findByRole("figure", { name: "Where web sits" });
    const parents = within(where).getByRole("list", { name: "Parent groups" });
    expect(within(parents).getAllByRole("button").map((b) => b.textContent)).toEqual(["eu0", "prod0"]);
    const children = within(where).getByRole("list", { name: "Child groups" });
    expect(within(children).getByRole("button")).toHaveTextContent("web_eu2");
    expect(await screen.findByText("Hosts in web and the groups below it (1)")).toBeInTheDocument();
    expect(screen.getByText("source + inventory")).toHaveAttribute("title", "Defined by the inventory and by a source");

    await user.click(within(parents).getByRole("button", { name: /prod/ }));
    expect(await screen.findByRole("figure", { name: "Where prod sits" })).toBeInTheDocument();
    expect(screen.getByText("Top level: no parent group.")).toBeInTheDocument();
    // The previous group's hosts are gone at once; prod's arrive with their own request.
    expect(screen.getByText("Hosts in prod and the groups below it")).toBeInTheDocument();
    await screen.findByText("Hosts in prod and the groups below it (1)");
    expect(api.calls.some((c) => c.path === "/inventories/1/hosts" && c.query.get("group") === "prod")).toBe(true);
  });

  it("searches groups and caps the list", async () => {
    const many = graph({
      groups: Array.from({ length: 250 }, (_, i) => ({ name: `node-${i}`, hosts: 1, children: [], origin: "source" as const })),
    });
    const { screen, user } = renderApp("/inventories/1/graph", { routes: { ...ROUTES, "GET /inventories/:id/graph": many } });
    const search = await screen.findByRole("textbox", { name: "Search groups" });
    await user.type(search, "node");
    expect(within(screen.getByRole("list", { name: "Matching groups" })).getAllByRole("button")).toHaveLength(200);
    expect(screen.getByText("Showing 200 of 250 matches: narrow your search.")).toBeInTheDocument();
    await user.clear(search);
    expect(screen.getByRole("tree", { name: "Groups" })).toBeInTheDocument();
  });

  it("finds a nested group by name and selects it", async () => {
    const { screen, user } = renderApp("/inventories/1/graph", { routes: ROUTES });
    await user.type(await screen.findByRole("textbox", { name: "Search groups" }), "web");
    const matches = screen.getByRole("list", { name: "Matching groups" });
    expect(within(matches).getAllByRole("button").map((b) => b.querySelector(".font-mono")?.textContent)).toEqual(["web", "web_eu"]);
    expect(within(matches).getByText("under eu, prod")).toBeInTheDocument();
    await user.click(within(matches).getByRole("button", { name: /web_eu/ }));
    expect(await screen.findByRole("figure", { name: "Where web_eu sits" })).toBeInTheDocument();
    expect(screen.getByText("No child groups.")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Search groups" }), "zzz");
    expect(screen.getByText("No groups match.")).toBeInTheDocument();
  });

  it("shows big levels a hundred at a time", async () => {
    const wide = graph({
      groups: Array.from({ length: 150 }, (_, i) => ({ name: `g${String(i).padStart(3, "0")}`, hosts: 0, children: [], origin: "static" as const })),
    });
    const { screen, user } = renderApp("/inventories/1/graph", { routes: { ...ROUTES, "GET /inventories/:id/graph": wide } });
    const more = await screen.findByRole("treeitem", { name: "Show 50 more of 50" });
    expect(screen.getAllByRole("treeitem")).toHaveLength(101);
    expect(screen.getAllByRole("treeitem")[0]).toHaveAttribute("aria-setsize", "150");
    await user.click(more);
    expect(screen.getAllByRole("treeitem")).toHaveLength(150);
    expect(screen.getByRole("button", { name: "Expand all" })).toBeDisabled(); // nothing to open
  });

  it("works for an inventory without sources or groups", async () => {
    const flat = graph({
      hosts: 2,
      ungrouped: 0,
      groups: [{ name: "web", hosts: 2, children: [], origin: "static" }],
      snapshot_id: null,
      snapshot_at: null,
    });
    const { screen } = renderApp("/inventories/1/graph", { routes: { ...ROUTES, "GET /inventories/:id/graph": flat } });
    expect(await screen.findByText(/1 group and 2 hosts\. Counts/)).toBeInTheDocument();
    expect(screen.queryByText(/Sources as of/)).not.toBeInTheDocument();
    expect(within(screen.getByRole("treeitem")).getByText("inventory")).toBeInTheDocument();
    expect(await screen.findByText("Hosts a run sees (1)")).toBeInTheDocument();
  });

  it("says when there are no groups", async () => {
    const empty = graph({ hosts: 0, ungrouped: 0, groups: [], snapshot_id: null, snapshot_at: null });
    const { screen } = renderApp("/inventories/1/graph", { routes: { ...ROUTES, "GET /inventories/:id/graph": empty } });
    expect(await screen.findByText("This inventory has no groups.")).toBeInTheDocument();
    expect(screen.queryByRole("tree")).not.toBeInTheDocument();
  });

  it("says when a linked group doesn't exist", async () => {
    const { screen } = renderApp("/inventories/1/graph?group=nope", { routes: ROUTES });
    expect(await screen.findByText(/This inventory has no group named/)).toHaveTextContent("nope");
  });

  it("switches between the tree and the diagram, keeping both on the page and the group picked", async () => {
    const { screen, user } = renderApp("/inventories/1/graph", { routes: ROUTES });
    await screen.findByRole("heading", { level: 1, name: "Group graph" });
    const tree = screen.getByRole("button", { name: "Tree" });
    const diagram = screen.getByRole("button", { name: "Diagram" });
    expect(tree).toHaveAttribute("aria-pressed", "true");
    expect(diagram).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("region", { name: "Group diagram" })).not.toBeInTheDocument();

    await user.click(diagram);
    expect(await screen.findByRole("region", { name: "Group diagram" })).toBeInTheDocument();
    expect(diagram).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("tree", { name: "Groups" })).toBeInTheDocument(); // the accessible way in stays

    await user.click(screen.getByRole("button", { name: "diagram web_eu" }));
    expect(await screen.findByRole("heading", { level: 2, name: "web_eu" })).toBeInTheDocument();
    expect(diagram).toHaveAttribute("aria-pressed", "true"); // picking a group keeps the view
    expect(screen.getByRole("region", { name: "Group diagram" })).toHaveAttribute("data-selected", "web_eu");

    await user.click(tree);
    expect(screen.queryByRole("region", { name: "Group diagram" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "web_eu" })).toBeInTheDocument(); // and so does the group
  });

  it("opens on the diagram from a link, with the group selected", async () => {
    const { screen } = renderApp("/inventories/1/graph?view=diagram&group=web", { routes: ROUTES });
    const region = await screen.findByRole("region", { name: "Group diagram" });
    expect(region).toHaveAttribute("data-selected", "web");
    expect(screen.getByRole("button", { name: "Diagram" })).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByRole("heading", { level: 2, name: "web" })).toBeInTheDocument();
  });
});
