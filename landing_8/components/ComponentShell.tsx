import Link from "next/link";

type Feature = { title: string; body: string };

type Props = {
  name: string;
  port: string;
  role: string;
  headline: string;
  lede: string;
  features: Feature[];
  endpoints?: string[];
  next?: { href: string; label: string };
  prev?: { href: string; label: string };
};

export default function ComponentShell({
  name,
  port,
  role,
  headline,
  lede,
  features,
  endpoints,
  next,
  prev,
}: Props) {
  return (
    <main>
      <section className="relative overflow-hidden border-b border-line pb-16 pt-16 md:pb-24 md:pt-20">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 70% 50% at 85% 20%, #1a3a4a 0%, transparent 55%), linear-gradient(165deg, #071018 0%, #0c1824 50%, #071018 100%)",
          }}
        />
        <div className="relative z-10 mx-auto max-w-6xl px-6 md:px-8">
          <p className="font-[family-name:var(--font-mono)] text-xs uppercase tracking-[0.2em] text-signal">
            KubeMind · {name}
          </p>
          <h1 className="mt-4 max-w-3xl font-[family-name:var(--font-display)] text-4xl font-semibold tracking-tight text-paper sm:text-5xl md:text-6xl">
            <span className="font-[family-name:var(--font-mono)] text-signal">
              {name}
            </span>
          </h1>
          <p className="mt-4 max-w-2xl font-[family-name:var(--font-display)] text-xl font-medium text-paper/90 md:text-2xl">
            {headline}
          </p>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-fog md:text-lg">
            {lede}
          </p>
          <p className="mt-6 font-[family-name:var(--font-mono)] text-sm text-fog">
            {role}
            <span className="mx-2 text-line">·</span>
            port {port}
          </p>
        </div>
      </section>

      <section className="py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6 md:px-8">
          <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-paper md:text-3xl">
            What it does
          </h2>
          <ul className="mt-12 grid gap-10 md:grid-cols-2">
            {features.map((f) => (
              <li key={f.title} className="border-t border-line pt-6">
                <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold text-paper">
                  {f.title}
                </h3>
                <p className="mt-2 leading-relaxed text-fog">{f.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {endpoints && endpoints.length > 0 && (
        <section className="border-t border-line bg-ink-soft py-20 md:py-24">
          <div className="mx-auto max-w-6xl px-6 md:px-8">
            <h2 className="font-[family-name:var(--font-display)] text-2xl font-semibold tracking-tight text-paper">
              Surface
            </h2>
            <ul className="mt-8 space-y-3 font-[family-name:var(--font-mono)] text-sm text-sea">
              {endpoints.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <section className="border-t border-line py-14">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 md:flex-row md:items-center md:justify-between md:px-8">
          <div className="flex flex-wrap gap-4 text-sm">
            {prev && (
              <Link
                href={prev.href}
                className="rounded-sm border border-line px-5 py-2.5 text-paper transition hover:border-fog"
              >
                ← {prev.label}
              </Link>
            )}
            {next && (
              <Link
                href={next.href}
                className="rounded-sm border border-line px-5 py-2.5 text-paper transition hover:border-fog"
              >
                {next.label} →
              </Link>
            )}
          </div>
          <Link
            href="/#start"
            className="rounded-sm bg-signal px-5 py-2.5 text-sm font-semibold text-ink transition hover:bg-signal-hot"
          >
            Run the plane
          </Link>
        </div>
      </section>
    </main>
  );
}
