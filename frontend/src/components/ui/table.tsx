import * as React from "react";

import { cn } from "@/lib/utils";

// Wide tables scroll inside their own box, so the page itself never scrolls sideways.
function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div className="w-full overflow-x-auto rounded-md border border-border">
      <table className={cn("w-full border-collapse text-sm", className)} {...props} />
    </div>
  );
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      className={cn("border-b border-border bg-muted/40 px-3 py-2 text-left font-medium", className)}
      {...props}
    />
  );
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return <td className={cn("border-b border-border px-3 py-2 align-top", className)} {...props} />;
}

export { Table, TableHead, TableCell };
