import { cn } from "@/lib/utils";

// The same drawing as public/favicon.svg, in the theme's accent.
/** The Steerhouse mark: the wheelhouse seen from above, a bow outline around a compass needle. */
export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false" className={cn("size-7 shrink-0", className)}>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <path
        d="M16 4.6 25 11.8v13.6a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V11.8Z"
        fill="none"
        strokeWidth="2.3"
        strokeLinejoin="round"
        className="stroke-primary-foreground"
      />
      <path d="m20.6 12.4-3.2 7.8-6 3.2 3.2-7.8Z" className="fill-primary-foreground" />
      <circle cx="16" cy="17.9" r="1.35" className="fill-primary" />
    </svg>
  );
}
