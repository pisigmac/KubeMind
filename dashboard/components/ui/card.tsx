import { cn } from "@/lib/utils";
import React from "react";

export function Card({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("bg-card border border-border rounded-md", className)} {...props}>
      {children}
    </div>
  );
}
