import { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const color: Record<string, string> = {
  严重: "bg-danger text-white",
  高危: "bg-warning text-white",
  中危: "bg-primary text-white",
  低危: "bg-success text-white"
};

export function Badge({ className, children, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-1 text-xs font-medium", color[String(children)] ?? "bg-muted text-foreground", className)} {...props}>
      {children}
    </span>
  );
}
