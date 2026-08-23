"use client";

/** Full-bleed kmind routing visualization — the dominant hero visual plane. */
export default function HeroMesh() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      <div
        className="absolute inset-0 opacity-90"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 70% 40%, #1a3a4a 0%, transparent 55%), radial-gradient(ellipse 50% 40% at 20% 80%, #2a2418 0%, transparent 50%), linear-gradient(165deg, #071018 0%, #0c1824 45%, #071018 100%)",
        }}
      />
      <svg
        className="hero-mesh absolute inset-0 h-full w-full opacity-70"
        viewBox="0 0 1200 800"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <linearGradient id="pathGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#d4a24c" stopOpacity="0.1" />
            <stop offset="50%" stopColor="#d4a24c" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#5cdba8" stopOpacity="0.7" />
          </linearGradient>
          <filter id="soft">
            <feGaussianBlur stdDeviation="1.2" />
          </filter>
        </defs>

        {Array.from({ length: 12 }).map((_, i) => (
          <line
            key={`h-${i}`}
            x1="0"
            y1={80 + i * 58}
            x2="1200"
            y2={80 + i * 58}
            stroke="#243647"
            strokeWidth="1"
            opacity={0.35}
          />
        ))}
        {Array.from({ length: 16 }).map((_, i) => (
          <line
            key={`v-${i}`}
            x1={40 + i * 75}
            y1="0"
            x2={40 + i * 75}
            y2="800"
            stroke="#243647"
            strokeWidth="1"
            opacity={0.25}
          />
        ))}

        {/* kmind routes: purpose → intents */}
        <path
          className="route-path"
          d="M120 420 C 320 420, 380 220, 560 240 C 720 260, 760 480, 980 460"
          fill="none"
          stroke="url(#pathGrad)"
          strokeWidth="2.5"
          filter="url(#soft)"
        />
        <path
          className="route-path"
          style={{ animationDelay: "0.8s" }}
          d="M120 420 C 300 500, 400 620, 620 580 C 820 540, 880 300, 1080 280"
          fill="none"
          stroke="#5cdba8"
          strokeOpacity="0.55"
          strokeWidth="1.5"
        />
        <path
          className="route-path"
          style={{ animationDelay: "1.6s" }}
          d="M120 420 C 280 300, 340 160, 520 140"
          fill="none"
          stroke="#e85d4c"
          strokeOpacity="0.5"
          strokeWidth="1.5"
        />

        <circle cx="120" cy="420" r="10" fill="#d4a24c" />
        <circle cx="560" cy="240" r="6" fill="#5cdba8" />
        <circle cx="980" cy="460" r="6" fill="#d4a24c" />
        <circle cx="620" cy="580" r="5" fill="#9aafc0" />
        <circle cx="520" cy="140" r="5" fill="#e85d4c" />

        <text
          x="96"
          y="452"
          fill="#d4a24c"
          fontSize="14"
          fontFamily="IBM Plex Mono, monospace"
          fontWeight="500"
        >
          kmind
        </text>
        <text
          x="560"
          y="220"
          fill="#5cdba8"
          fontSize="13"
          fontFamily="IBM Plex Mono, monospace"
        >
          local
        </text>
        <text
          x="980"
          y="440"
          fill="#d4a24c"
          fontSize="13"
          fontFamily="IBM Plex Mono, monospace"
        >
          retrieve
        </text>
        <text
          x="520"
          y="120"
          fill="#e85d4c"
          fontSize="13"
          fontFamily="IBM Plex Mono, monospace"
        >
          block
        </text>
      </svg>

      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(to bottom, transparent 55%, #071018 96%), linear-gradient(to right, #071018 0%, transparent 28%)",
        }}
      />
    </div>
  );
}
