import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth/provider";
import { Nav } from "@/components/ui/nav";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "KubeMind — AI Builder Stack",
  description: "Unified platform for building AI products",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.variable} font-sans`}>
        <AuthProvider>
          <div className="min-h-screen flex">
            <Nav />
            <main className="flex-1 p-6">{children}</main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
