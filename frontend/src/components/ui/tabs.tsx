import * as React from "react";

import { tabId } from "@/lib/tabs";
import { cn } from "@/lib/utils";

export interface TabItem {
  value: string;
  label: string;
}

// A row of tabs (WAI-ARIA tabs pattern: arrows, Home and End move between them). The panel is the
// caller's: render it with role="tabpanel" and aria-labelledby={tabId(value)} (lib/tabs).

export function Tabs({
  tabs,
  value,
  onValueChange,
  label,
}: {
  tabs: TabItem[];
  value: string;
  onValueChange: (value: string) => void;
  label: string;
}) {
  const refs = React.useRef<Record<string, HTMLButtonElement | null>>({});

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    const last = tabs.length - 1;
    const next =
      event.key === "ArrowRight"
        ? index === last
          ? 0
          : index + 1
        : event.key === "ArrowLeft"
          ? index === 0
            ? last
            : index - 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : null;
    if (next === null) return;
    event.preventDefault();
    const target = tabs[next];
    if (!target) return;
    onValueChange(target.value);
    refs.current[target.value]?.focus();
  }

  return (
    <div role="tablist" aria-label={label} className="flex gap-1 border-b border-border">
      {tabs.map((tab, index) => {
        const selected = tab.value === value;
        return (
          <button
            key={tab.value}
            ref={(element) => {
              refs.current[tab.value] = element;
            }}
            id={tabId(tab.value)}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onValueChange(tab.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              selected
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
