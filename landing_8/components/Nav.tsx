"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/kmind", label: "kmind" },
  { href: "/mind", label: "mind" },
  { href: "/agents", label: "agents" },
  { href: "/sentinel", label: "sentinel" },
];

export default function Nav() {
  const pathname = usePathname();
  const onHome = pathname === "/";

  return (
    <header
      className={
        onHome
          ? "absolute inset-x-0 top-0 z-20"
          : "sticky top-0 z-20 border-b border-line bg-ink/90 backdrop-blur-md"
      }
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5 md:px-8">
        <Link
          href="/"
          className="flex items-baseline gap-2.5 font-[family-name:var(--font-display)] text-lg font-semibold tracking-tight text-paper"
        >
          KubeMind
          <span className="font-[family-name:var(--font-mono)] text-xs font-medium tracking-wide text-signal">
            kmind
          </span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-fog lg:flex">
          {links.map((l) => {
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={
                  active
                    ? "font-[family-name:var(--font-mono)] text-signal"
                    : "font-[family-name:var(--font-mono)] transition hover:text-paper"
                }
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <Link
          href={onHome ? "#start" : "/#start"}
          className="rounded-sm bg-signal px-4 py-2 text-sm font-medium text-ink transition hover:bg-signal-hot"
        >
          Get started
        </Link>
      </div>
    </header>
  );
}
