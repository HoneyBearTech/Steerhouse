import { act, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FakeWebSocket } from "@/test/fake-websocket";
import { inventory, playbook, run, viewerUser } from "@/test/fixtures";
import { PAGE_ROUTES } from "@/test/pages";
import { renderApp } from "@/test/render";

const ROUTES = { "GET /users": [], "GET /runs": [run()], "GET /playbooks": [playbook()], "GET /inventories": [inventory()], "GET /run-templates": [], "GET /credentials": [] };

describe("header", () => {
  it("groups admin pages in a menu and keeps Account and Log out in the user menu", async () => {
    const { user, screen } = renderApp("/runs", { routes: ROUTES });
    const nav = await screen.findByRole("navigation", { name: "Main" });
    for (const name of ["Dashboard", "Playbooks", "Inventories", "Runs", "Templates", "Credentials", "Vault", "Galaxy"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
    expect(within(nav).getByRole("link", { name: "Runs" })).toHaveClass("text-primary");
    expect(within(nav).queryByRole("link", { name: "Users" })).not.toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: "Admin" }));
    for (const name of ["Projects", "Users", "Audit log", "Workers", "Notifications"]) {
      expect(await screen.findByRole("menuitem", { name })).toBeInTheDocument();
    }
    await user.click(screen.getByRole("menuitem", { name: "Users" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Users" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "admin" }));
    expect(await screen.findByText(/Signed in as/)).toHaveTextContent("Signed in as admin (global admin)");
    await user.click(screen.getByRole("menuitem", { name: "Account" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Account" })).toBeInTheDocument();
  });

  describe("log out", () => {
    afterEach(() => vi.unstubAllGlobals());

    it("goes on to the provider's logout page when the server says so", async () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      const { user, screen } = renderApp("/runs", {
        routes: { ...ROUTES, "POST /auth/logout": { ok: true, redirect: "https://idp.test/logout?client_id=c" } },
      });
      await user.click(await screen.findByRole("button", { name: "admin" }));
      await user.click(screen.getByRole("menuitem", { name: "Log out" }));
      await vi.waitFor(() => expect(assign).toHaveBeenCalledWith("https://idp.test/logout?client_id=c"));
    });

    it("just signs out when there is nowhere else to go", async () => {
      const assign = vi.fn();
      vi.stubGlobal("location", { ...window.location, assign });
      const { user, screen } = renderApp("/runs", {
        routes: { ...ROUTES, "POST /auth/logout": { ok: true, redirect: null } },
      });
      await user.click(await screen.findByRole("button", { name: "admin" }));
      await user.click(screen.getByRole("menuitem", { name: "Log out" }));
      expect(await screen.findByRole("button", { name: /sign in/i })).toBeInTheDocument();
      expect(assign).not.toHaveBeenCalled();
    });
  });

  it("shows no Admin menu to someone without admin pages", async () => {
    const { screen } = renderApp("/runs", { user: viewerUser(), routes: ROUTES });
    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(within(nav).queryByRole("button", { name: "Admin" })).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Credentials" })).not.toBeInTheDocument();
  });

  it("opens a menu with every page on small screens, and closes it on navigation", async () => {
    const { user, screen } = renderApp("/runs", { routes: ROUTES });
    const toggle = await screen.findByRole("button", { name: "Open menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
    const menu = document.getElementById("mobile-menu")!;
    expect(within(menu).getByText("Admin")).toBeInTheDocument();
    expect(within(menu).getByRole("link", { name: "Audit log" })).toHaveAttribute("href", "/audit");
    expect(within(menu).getByText("admin (global admin)")).toBeInTheDocument();
    await user.click(within(menu).getByRole("link", { name: "Playbooks" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Playbooks" })).toBeInTheDocument();
    expect(document.getElementById("mobile-menu")).toBeNull();
  });

  it("switches the theme from the user menu and remembers it", async () => {
    const { user, screen } = renderApp("/runs", { routes: ROUTES });
    await user.click(await screen.findByRole("button", { name: "admin" }));
    expect(screen.getByRole("menuitemradio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("menuitemradio", { name: "Light" }));
    expect(document.documentElement.dataset["theme"]).toBe("light");
    expect(localStorage.getItem("steerhouse-theme")).toBe("light");
    // The menu stays open, so the choice can be seen and changed again.
    expect(screen.getByRole("menuitemradio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("menuitemradio", { name: "Same as device" }));
    expect(document.documentElement.dataset["theme"]).toBe("system");
  });

  it("switches the theme from the small-screen menu", async () => {
    const { user, screen } = renderApp("/runs", { routes: ROUTES });
    await user.click(await screen.findByRole("button", { name: "Open menu" }));
    const theme = within(screen.getByRole("group", { name: "Theme" }));
    expect(theme.getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
    await user.click(theme.getByRole("button", { name: "Light" }));
    expect(theme.getByRole("button", { name: "Light" })).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement.dataset["theme"]).toBe("light");
    expect(localStorage.getItem("steerhouse-theme")).toBe("light");
  });

  it("switches the density from the user menu and remembers it", async () => {
    const { user, screen } = renderApp("/runs", { routes: ROUTES });
    await user.click(await screen.findByRole("button", { name: "admin" }));
    const density = within(screen.getByRole("group", { name: "Density" }));
    expect(density.getByRole("menuitemradio", { name: "Comfortable" })).toHaveAttribute("aria-checked", "true");
    await user.click(density.getByRole("menuitemradio", { name: "Compact" }));
    expect(document.documentElement.dataset["density"]).toBe("compact");
    expect(localStorage.getItem("steerhouse-density")).toBe("compact");
    // The menu stays open, as for the theme.
    expect(density.getByRole("menuitemradio", { name: "Compact" })).toHaveAttribute("aria-checked", "true");
    await user.click(density.getByRole("menuitemradio", { name: "Comfortable" }));
    expect(document.documentElement.dataset["density"]).toBe("comfortable");
    expect(localStorage.getItem("steerhouse-density")).toBe("comfortable");
  });

  it("switches the density from the small-screen menu", async () => {
    const { user, screen } = renderApp("/runs", { routes: ROUTES });
    await user.click(await screen.findByRole("button", { name: "Open menu" }));
    const density = within(screen.getByRole("group", { name: "Density" }));
    expect(density.getByRole("button", { name: "Comfortable" })).toHaveAttribute("aria-pressed", "true");
    await user.click(density.getByRole("button", { name: "Compact" }));
    expect(density.getByRole("button", { name: "Compact" })).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement.dataset["density"]).toBe("compact");
    expect(localStorage.getItem("steerhouse-density")).toBe("compact");
  });

  it("switches between the menu button and the full nav at 1280 px", async () => {
    // jsdom has no layout, so this pins the breakpoint classes: below xl the full nav no longer fits.
    const { screen } = renderApp("/runs", { routes: ROUTES });
    expect(await screen.findByRole("button", { name: "Open menu" })).toHaveClass("xl:hidden");
    const [desktopNav] = screen.getAllByRole("navigation", { name: "Main" });
    expect(desktopNav).toHaveClass("hidden", "xl:flex");
  });
});

describe("run output", () => {
  it("colours Ansible's lines, keeps their line breaks and follows only a live run", async () => {
    const { screen, container } = renderApp("/runs/7", { routes: { "GET /runs/:id": run() } });
    expect(await screen.findByRole("heading", { name: "Output" })).toBeInTheDocument();
    const socket = await FakeWebSocket.opened();
    act(() => {
      socket.open();
      socket.emit({ counter: 1, stdout: "TASK [Say hi] ****" });
      socket.emit({ counter: 2, stdout: "ok: [web1]\nchanged: [web2]\nskipping: [web3]\nfatal: [web4]: FAILED!" });
      socket.emit({ counter: 3, stdout: "PLAY RECAP ****\nweb1 : ok=1 changed=0 unreachable=0 failed=0\nweb2 : ok=1 changed=1 unreachable=0 failed=0\nweb4 : ok=0 changed=0 unreachable=0 failed=1" });
      socket.emit({ counter: 4, stdout: "<script>alert(1)</script>" });
    });
    expect(await screen.findByText("ok: [web1]")).toHaveClass("text-status-ok");
    expect(screen.getByText("changed: [web2]")).toHaveClass("text-status-changed");
    expect(screen.getByText("skipping: [web3]")).toHaveClass("text-status-skipped");
    expect(screen.getByText("fatal: [web4]: FAILED!")).toHaveClass("text-status-failed");
    expect(screen.getByText("TASK [Say hi] ****")).toHaveClass("font-semibold");
    expect(screen.getByText("web2 : ok=1 changed=1 unreachable=0 failed=0")).toHaveClass("text-status-changed");
    expect(screen.getByText("web4 : ok=0 changed=0 unreachable=0 failed=1")).toHaveClass("text-status-failed");
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument();
    const recap = screen.getByText("PLAY RECAP ****").parentElement!;
    expect(recap).toHaveClass("whitespace-pre-wrap");
    expect(recap.textContent).toContain("****\nweb1");
  });
});

describe("page width", () => {
  // jsdom has no layout, so this pins the classes that apply from 1536 px (2xl).
  it("widens list pages and the header on wide screens, and keeps forms at the normal width", async () => {
    const { user, screen } = renderApp("/runs", { routes: PAGE_ROUTES });
    await screen.findByRole("heading", { level: 1, name: "Runs" });
    const header = screen.getByRole("banner").firstElementChild;
    expect(screen.getByRole("main")).toHaveClass("max-w-6xl", "2xl:max-w-[90rem]");
    expect(header).toHaveClass("max-w-6xl", "2xl:max-w-[90rem]");

    await user.click(screen.getByRole("link", { name: "New run" }));
    await screen.findByRole("heading", { level: 1, name: "New run" });
    expect(screen.getByRole("main")).toHaveClass("max-w-6xl");
    expect(screen.getByRole("main")).not.toHaveClass("2xl:max-w-[90rem]");
    expect(header).toHaveClass("2xl:max-w-[90rem]");
  });
});
