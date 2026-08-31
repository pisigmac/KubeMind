"use client";

import { usePathname } from "next/navigation";
import { Nav } from "@/components/ui/nav";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname?.startsWith("/landing");

  if (isLanding) {
    return <div className="min-h-screen w-full bg-[#080B11]">{children}</div>;
  }

  return (
    <div className="min-h-screen flex">
      <Nav />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
