import { describe, expect, it } from "vitest";

import css from "../index.css?raw";

// The WCAG 2.1 contrast of every colour pair the UI draws, in both themes (index.css). Body text
// needs 4.5:1; input borders, focus rings and other parts of a control need 3:1. The browser check
// (e2e/layout.spec.ts) measures what each page really shows; this one covers the palette itself.

function block(selector: string): Record<string, string> {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no ${selector} block in index.css`);
  const body = css.slice(start, css.indexOf("}", start));
  return Object.fromEntries([...body.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6});/g)].map((m) => [m[1], m[2]]));
}

function luminance(hex: string): number {
  const [r = 0, g = 0, b = 0] = [1, 3, 5]
    .map((i) => channel(hex, i) / 255)
    .map((c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function channel(hex: string, at: number): number {
  return parseInt(hex.slice(at, at + 2), 16);
}

// A colour laid over a surface at some opacity (Tailwind's bg-status-ok/15 and the like).
function tint(hex: string, over: string, opacity: number): string {
  return `#${[1, 3, 5]
    .map((i) => Math.round(opacity * channel(hex, i) + (1 - opacity) * channel(over, i)))
    .map((c) => c.toString(16).padStart(2, "0"))
    .join("")}`;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].toSorted((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const dark = block(":root");
const light = block(':root[data-theme="light"]');
const system = block('  :root[data-theme="system"]');

const TEXT = 4.5;
const UI = 3;
// Where text and controls sit: the page, cards, popovers and raised rows, muted panels (run output), fields.
const SURFACES = ["background", "card", "popover", "secondary", "muted", "field"];
const STATUSES = ["status-ok", "status-changed", "status-failed", "status-skipped"];

const PAIRS: [string, string[], number][] = [
  ["foreground", SURFACES, TEXT],
  ["muted-foreground", SURFACES, TEXT],
  ["card-foreground", ["card"], TEXT],
  ["popover-foreground", ["popover"], TEXT],
  ["secondary-foreground", ["secondary"], TEXT],
  ["primary", SURFACES, TEXT], // links, the active page, the mark
  ["primary-foreground", ["primary"], TEXT], // primary buttons
  ["accent-foreground", ["accent"], TEXT],
  ["destructive", SURFACES, TEXT],
  ["destructive-foreground", ["destructive"], TEXT],
  ...STATUSES.map((status): [string, string[], number] => [status, SURFACES, TEXT]),
  ["input", ["background", "card", "popover", "field"], UI], // the edge of a text box, select or outline button
  ["ring", ["background", "card", "popover"], UI],
];

describe.each([
  ["dark", dark],
  ["light", light],
])("the %s theme", (_name, theme) => {
  it.each(PAIRS.flatMap(([fg, bgs, needed]) => bgs.map((bg) => [fg, bg, needed] as const)))(
    "%s on %s reaches %s:1",
    (fg, bg, needed) => {
      expect(theme[fg], `--${fg}`).toBeDefined();
      expect(theme[bg], `--${bg}`).toBeDefined();
      expect(contrast(theme[fg]!, theme[bg]!)).toBeGreaterThanOrEqual(needed);
    },
  );
});

// Status badges and coloured run output: the colour on a 15% wash of itself, over every surface.
describe.each([
  ["dark", dark],
  ["light", light],
])("the %s theme's tinted badges", (_name, theme) => {
  it.each(STATUSES.flatMap((status) => SURFACES.map((surface) => [status, surface] as const)))(
    "%s on its own tint over %s reaches 4.5:1",
    (status, surface) => {
      expect(contrast(theme[status]!, tint(theme[status]!, theme[surface]!, 0.15))).toBeGreaterThanOrEqual(TEXT);
    },
  );
});

describe("the palette", () => {
  it("defines the same colours in both themes", () => {
    expect(Object.keys(light).toSorted()).toEqual(Object.keys(dark).toSorted());
  });

  it("follows the device's light setting with exactly the light theme", () => {
    expect(system).toEqual(light);
  });

  it("measures contrast as WCAG does", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrast("#777777", "#ffffff")).toBeCloseTo(4.48, 2);
  });
});
