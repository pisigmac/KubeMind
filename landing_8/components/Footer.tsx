import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-line py-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 text-sm text-fog md:px-8">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <p className="flex items-baseline gap-2 font-[family-name:var(--font-display)] text-paper">
            KubeMind
            <span className="font-[family-name:var(--font-mono)] text-xs text-signal">
              kmind
            </span>
          </p>
          <nav className="flex flex-wrap gap-x-5 gap-y-2 font-[family-name:var(--font-mono)] text-xs">
            <Link href="/kmind" className="transition hover:text-paper">
              kmind
            </Link>
            <Link href="/mind" className="transition hover:text-paper">
              mind
            </Link>
            <Link href="/agents" className="transition hover:text-paper">
              agents
            </Link>
            <Link href="/sentinel" className="transition hover:text-paper">
              sentinel
            </Link>
          </nav>
          <p className="font-[family-name:var(--font-mono)] text-xs">MIT</p>
        </div>
        <p>Purpose → intent → route. Enforced governance. Self-hosted.</p>
      </div>
    </footer>
  );
}
