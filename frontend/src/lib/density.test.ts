import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { setDensity, useDensity } from "./density";

describe("density", () => {
  it("is comfortable until chosen otherwise", () => {
    expect(renderHook(() => useDensity()).result.current).toBe("comfortable");
  });

  it("marks the page, remembers the choice and tells every user of the hook", () => {
    const first = renderHook(() => useDensity());
    const second = renderHook(() => useDensity());
    act(() => setDensity("compact"));
    expect(document.documentElement.dataset["density"]).toBe("compact");
    expect(localStorage.getItem("steerhouse-density")).toBe("compact");
    expect(first.result.current).toBe("compact");
    expect(second.result.current).toBe("compact");

    act(() => setDensity("comfortable"));
    expect(document.documentElement.dataset["density"]).toBe("comfortable");
    expect(localStorage.getItem("steerhouse-density")).toBe("comfortable");
    expect(first.result.current).toBe("comfortable");
  });

  it("still switches when the browser has no storage", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    const { result } = renderHook(() => useDensity());
    act(() => setDensity("compact"));
    expect(result.current).toBe("compact");
  });
});
