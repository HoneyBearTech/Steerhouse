import path from "node:path";

import { expect, type Page, test } from "@playwright/test";

import { resolve, type Routes } from "../src/test/api-routes";
import {
  adminUserRow,
  channel,
  credential,
  graph,
  hostTask,
  inventory,
  inventorySource,
  mergedHost,
  playbook,
  run,
  runHosts,
  runTemplate,
  sshCertCredential,
  sshCertificate,
  targets,
  vaultPassword,
} from "../src/test/fixtures";
import { baseRoutes, PAGE_ROUTES, PAGES } from "../src/test/pages";

// Every page at phone, tablet, laptop and desktop widths, filled with the long names, e-mail
// addresses and URLs real inventories have: nothing may scroll sideways, text must keep its contrast,
// and every "New/Add" (and "Edit reference", "Move to ...") dialog must fit a small phone with its buttons in reach.

const WIDTHS = [375, 768, 1024, 1280];
const PHONE = { width: 375, height: 667 };
const LONG = "production-europe-west-datacenter-frankfurt-primary";

const LONG_ROUTES: Routes = {
  ...PAGE_ROUTES,
  "GET /playbooks": [playbook({ name: `${LONG}-site.yml` })],
  "GET /playbooks/:id": playbook({ name: `${LONG}-site.yml` }),
  "GET /inventories": [inventory({ name: `${LONG}-inventory`, description: `Hosts in ${LONG}` })],
  "GET /inventories/:id": inventory({
    name: `${LONG}-inventory`,
    groups: [{ id: 1, name: `${LONG}-webservers` }, { id: 2, name: `${LONG}-databases` }],
    hosts: [{ id: 1, hostname: `web1.${LONG}.example.com`, vars: { ansible_user: "deploy" }, group_ids: [1, 2] }],
  }),
  "GET /inventories/:id/targets": targets({ groups: [{ name: `${LONG}-webservers`, hosts: 1, origin: "static" }] }),
  "GET /inventories/:id/sources": [
    inventorySource({ name: `${LONG}-netbox`, output_refreshed_at: "2026-10-05T12:00:00Z", output_host_count: 1200, output_group_count: 40 }),
    inventorySource({
      id: 2,
      name: `${LONG}-aws`,
      plugin: "amazon.aws.aws_ec2",
      last_error: `10-src2.aws_ec2.yml: Could not connect to the endpoint URL: "https://ec2.${LONG}.amazonaws.com/"`,
      last_finished_at: "2026-10-05T13:00:00Z",
      output_refreshed_at: "2026-10-05T12:00:00Z",
      output_host_count: 40,
      output_group_count: 5,
    }),
  ],
  "GET /inventories/:id/graph": graph({
    name: `${LONG}-inventory`,
    groups: [
      { name: `${LONG}-all`, hosts: 0, children: [`${LONG}-webservers`, `${LONG}-databases`], origin: "source" },
      { name: `${LONG}-databases`, hosts: 3, children: [], origin: "static" },
      { name: `${LONG}-webservers`, hosts: 12, children: [], origin: "both" },
    ],
  }),
  "GET /inventories/:id/hosts": {
    total: 1,
    hosts: [mergedHost({ name: `web1.${LONG}.example.com`, groups: [`${LONG}-webservers`], origin: "both" })],
  },
  "GET /secret-store/info": { enabled: true, label: "OpenBao", base_path: "secret/steerhouse/1/", path_rules: "letters, digits, - and _", move_enabled: true },
  "GET /credentials": [
    credential({ name: `${LONG}-deploy-key` }),
    credential({ id: 4, name: `${LONG}-vaulted`, store: "external", store_path: `${LONG}/ssh`, store_key: "private_key", store_location: `secret/steerhouse/1/${LONG}/ssh#private_key` }),
    credential({ id: 2, name: `${LONG}-cloud`, kind: "env", env_names: [`AWS_SECRET_ACCESS_KEY_FOR_${LONG.toUpperCase().replaceAll("-", "_")}`] }),
    sshCertCredential({ name: `${LONG}-cert`, store_location: `ssh/sign/steerhouse-1-${LONG}-webservers`, ssh_principals: [`deploy-${LONG}`, "ansible"] }),
  ],
  "GET /vault-passwords": [
    vaultPassword({ name: `${LONG}-vault` }),
    vaultPassword({ id: 2, name: `${LONG}-vaulted`, store: "external", store_path: `${LONG}/vault`, store_key: "password", store_location: `secret/steerhouse/1/${LONG}/vault#password` }),
  ],
  "GET /runs": [run({ playbook_name: `${LONG}-site.yml`, inventory_name: `${LONG}-inventory`, group_name: `${LONG}-webservers`, limit: `web1.${LONG}.example.com` })],
  "GET /runs/:id": run({ playbook_name: `${LONG}-site.yml`, inventory_name: `${LONG}-inventory`, group_name: `${LONG}-webservers`, credential_name: `${LONG}-deploy-key`, ssh_certificate: sshCertificate({ principals: [`deploy-${LONG}`, "ansible"], capped: true }), secret_reads: [{ what: "credential", name: `${LONG}-vaulted`, location: `secret/steerhouse/1/${LONG}/ssh#private_key`, version: 12 }] }),
  "GET /run-templates": [runTemplate({ name: `Nightly baseline for ${LONG}` })],
  "GET /users": [adminUserRow({ username: "a-very-long-username-for-layout", email: `someone.with.a.long.address@${LONG}.example.com`, sso_linked: true, totp_enabled: true })],
  "GET /notifications/channels": [channel({ name: "Webhook", kind: "webhook", target: `https://hooks.${LONG}.example.com/services/T000/B000/XXXXXXXXXXXXXXXXXXXXXXXX` })],
};

/** Serves the fake API to the page; returns the requests nothing answered. */
async function fakeApi(page: Page, routes: Routes) {
  const unhandled: string[] = [];
  const table = { ...baseRoutes(), ...routes };
  await page.addInitScript(() => localStorage.setItem("steerhouse.activeProject", "1"));
  await page.routeWebSocket(/\/api\//, () => {}); // live run output: stays silent
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const resolved = await resolve(table, {
      method: request.method(),
      path: url.pathname.replace(/^\/api/, ""),
      query: url.searchParams,
      body: request.postDataJSON() as unknown,
    });
    if (!resolved) {
      unhandled.push(`${request.method()} ${url.pathname}`);
      await route.fulfill({ status: 404, json: { detail: "unhandled" } });
      return;
    }
    await route.fulfill({ status: resolved.status, json: resolved.body });
  });
  return unhandled;
}

async function open(page: Page, url: string) {
  await page.goto(url);
  await expect(page.locator("h1")).toBeVisible();
  await page.waitForLoadState("networkidle");
}

for (const [url] of PAGES) {
  test.describe(url, () => {
    for (const width of WIDTHS) {
      test(`fits ${width} px`, async ({ page }) => {
        const unhandled = await fakeApi(page, LONG_ROUTES);
        await page.setViewportSize({ width, height: 900 });
        await open(page, url);
        const sideways = await page.evaluate(() => {
          const root = document.documentElement;
          // (The diagram's canvas clips what lies beyond its own box: only the box itself counts.)
          const out = [...document.querySelectorAll("body *")]
            .filter((el) => !el.parentElement?.closest("[data-diagram]"))
            .filter((el) => el.getBoundingClientRect().right > root.clientWidth + 1)
            .map((el) => `${el.tagName.toLowerCase()} "${(el.textContent ?? "").trim().slice(0, 40)}"`);
          return { overflow: root.scrollWidth - root.clientWidth, out: out.slice(0, 5) };
        });
        expect(sideways, `scrolls sideways at ${width} px`).toEqual({ overflow: 0, out: [] });
        expect(unhandled).toEqual([]);
      });
    }

    test("has enough colour contrast", async ({ page }) => {
      await fakeApi(page, LONG_ROUTES);
      await page.setViewportSize({ width: 1280, height: 900 });
      await open(page, url);
      await page.addScriptTag({ path: path.resolve("node_modules/axe-core/axe.min.js") });
      const violations = await page.evaluate(async () => {
        const result = await window.axe.run(document, { runOnly: ["color-contrast"] });
        return result.violations.flatMap((v) => v.nodes.map((n) => `${n.target.join(" ")}: ${n.failureSummary ?? ""}`));
      });
      expect(violations).toEqual([]);
    });

    test("dialogs fit a phone", async ({ page }) => {
      await fakeApi(page, LONG_ROUTES);
      await page.setViewportSize(PHONE);
      await open(page, url);
      const names = await page
        .locator("main button")
        .evaluateAll((els) => [...new Set(els.map((e) => (e.textContent ?? "").trim()).filter((t) => /^(New|Add|Edit reference|Move to)\b/.test(t)))]);
      for (const name of names) {
        await open(page, url);
        await page.locator("main button", { hasText: name }).first().click();
        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();
        const fit = await dialog.evaluate((d) => {
          const box = d.getBoundingClientRect();
          d.scrollTop = d.scrollHeight;
          const buttons = [...d.querySelectorAll("button")].filter((b) => b.offsetParent && b.textContent?.trim() !== "Close");
          const last = buttons.at(-1)?.getBoundingClientRect();
          const inside = box.left >= 0 && box.top >= 0 && box.right <= innerWidth && box.bottom <= innerHeight;
          const reachable = !last || (last.top >= 0 && last.bottom <= innerHeight);
          const wide = [...d.querySelectorAll("*")].some((e) => e.getBoundingClientRect().right > box.right + 1);
          return { inside, reachable, wide };
        });
        expect(fit, `"${name}" dialog`).toEqual({ inside: true, reachable: true, wide: false });
        await page.keyboard.press("Escape");
      }
    });
  });
}

declare global {
  interface Window {
    axe: typeof import("axe-core");
  }
}

test.describe("the group diagram", () => {
  const URL = "/inventories/1/graph?view=diagram";

  test("draws the groups, and a group is picked with the keyboard", async ({ page }) => {
    await fakeApi(page, LONG_ROUTES);
    await page.setViewportSize({ width: 1280, height: 900 });
    await open(page, URL);
    const nodes = page.locator("[data-diagram] .react-flow__node");
    await expect(nodes.first()).toBeVisible();
    expect(await nodes.count()).toBeGreaterThanOrEqual(3); // the fixture's groups, laid out by dagre
    const xs = await nodes.evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().x)));
    expect(new Set(xs).size).toBeGreaterThan(1); // more than one level, left to right

    const pick = page.locator("[data-diagram]").getByRole("button", { name: new RegExp(`${LONG}-databases`) }).first();
    await pick.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/group=/);
    await expect(page.getByRole("heading", { level: 2, name: `${LONG}-databases` })).toBeVisible();
    await expect(page).toHaveURL(/view=diagram/);
  });

  for (const width of [375, 1280]) {
    test(`stays inside its box at ${width} px and keeps the page from scrolling sideways`, async ({ page }) => {
      await fakeApi(page, LONG_ROUTES);
      await page.setViewportSize({ width, height: 800 });
      await open(page, URL);
      await expect(page.locator("[data-diagram] .react-flow__node").first()).toBeVisible();
      const box = await page.locator("[data-diagram]").boundingBox();
      expect(box && box.x >= 0 && box.x + box.width <= width + 1).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);
    });
  }
});

test.describe("the run's results by host", () => {
  // Twelve hosts with long names and one long task name: the grid scrolls inside its own box.
  const hosts = Array.from({ length: 12 }, (_, n) => `${LONG}-web${n}.example.com`);
  const result = { status: "ok" as const, changed: false, msg: null };
  const ROUTES = {
    ...LONG_ROUTES,
    "GET /runs/:id/hosts": runHosts({
      hosts,
      tasks: [
        hostTask({
          key: "a",
          name: `${LONG} task with a long name`,
          results: Object.fromEntries(hosts.map((host, n) => [host, n % 3 ? result : { ...result, status: "failed" as const }])),
        }),
      ],
    }),
  };

  for (const width of [375, 1280]) {
    test(`keeps the page from scrolling sideways at ${width} px`, async ({ page }) => {
      await fakeApi(page, ROUTES);
      await page.setViewportSize({ width, height: 800 });
      await open(page, "/runs/7?view=hosts");
      await expect(page.getByRole("columnheader").nth(1)).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);
    });
  }
});
