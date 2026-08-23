import type { Metadata } from "next";
import { Syne, Outfit, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "KubeMind — Intent-Aware AI Gateway & Pre-Dispatch Governance Control Plane",
  description:
    "Self-hosted, Kubernetes-native AI gateway. Enforce pre-dispatch sensitivity gating, offline NER pseudonymization, intent classification, pgvector memory, and SHA-256 tamper-evident audit ledgers.",
  keywords: [
    "AI gateway",
    "LLM router",
    "intent routing",
    "pre-dispatch governance",
    "PII redaction",
    "reversible pseudonymization",
    "local NER",
    "Kubernetes AI control plane",
    "tamper-evident audit ledger",
    "semantic cache",
    "KubeMind",
    "kmind",
  ],
  authors: [{ name: "KubeMind Team" }],
  creator: "KubeMind",
  publisher: "KubeMind",
  metadataBase: new URL("https://kubemind.io"),
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "KubeMind — Self-Hosted Intent Gateway & Deterministic AI Governance",
    description:
      "Purpose → intent → route. Enforced data sovereignty, local-first PII pseudonymization, and cryptographic audit ledgers before any cloud model call.",
    url: "https://kubemind.io",
    siteName: "KubeMind",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "KubeMind AI Gateway & Control Plane",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "KubeMind — Intelligent AI Gateway & Governance Control Plane",
    description:
      "Classify intent, tokenize PII offline, and cryptographically audit every model invocation with KubeMind.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "KubeMind",
  "operatingSystem": "Linux, Kubernetes",
  "applicationCategory": "DeveloperApplication, SecurityApplication",
  "description":
    "Self-hosted, Kubernetes-native AI gateway that classifies prompt intent, enforces pre-dispatch sensitivity policies, and maintains a cryptographic audit ledger.",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${syne.variable} ${outfit.variable} ${mono.variable}`}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
