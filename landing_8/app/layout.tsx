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
  title: "KubeMind — kmind finds intent and routes your prompt",
  description:
    "KubeMind is the self-hosted AI control plane. kmind is the router: it gives your prompt a purpose, finds the intent, and routes it — with governance enforced before any model call.",
  openGraph: {
    title: "KubeMind — kmind finds intent and routes your prompt",
    description:
      "Purpose → intent → route. Enforced governance. Self-hosted. Kubernetes-native.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${syne.variable} ${outfit.variable} ${mono.variable}`}>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
