"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signIn, signOut, useSession } from "next-auth/react";
import { LayoutDashboard, Bot, Database, Network, Activity, LogOut, LogIn, Cpu } from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/knowledge", label: "Knowledge", icon: Database },
  { href: "/gateway", label: "Gateway", icon: Network },
  { href: "/observability", label: "Observability", icon: Activity },
];

export function Nav() {
  const pathname = usePathname();
  const { data: session } = useSession();

  return (
    <nav className="w-64 bg-[#0F172A] border-r border-[#1E293B] flex flex-col justify-between h-screen sticky top-0 shrink-0">
      <div>
        {/* Brand Header */}
        <div className="p-6 border-b border-[#1E293B] flex items-center gap-3">
          <img 
            src="/logo.jpg" 
            alt="KubeMind Logo" 
            className="w-9 h-9 rounded-xl object-cover border border-[#0066FF]/40 shadow-md shadow-[#0066FF]/20" 
          />
          <div>
            <Link href="/" className="text-lg font-black tracking-wider text-white font-mono flex items-center gap-1.5">
              KUBEMIND
            </Link>
            <p className="text-[10px] uppercase font-bold tracking-widest text-[#0066FF]">AI Operating Console</p>
          </div>
        </div>

        {/* Navigation Links */}
        <div className="p-3 space-y-1.5 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                  active
                    ? "bg-[#0066FF] text-white shadow-lg shadow-[#0066FF]/25"
                    : "text-slate-400 hover:text-white hover:bg-[#1E293B]/70"
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? "text-white" : "text-slate-400"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* User / Auth Section */}
      <div className="p-4 border-t border-[#1E293B]">
        {session?.user ? (
          <div className="space-y-3">
            <div className="px-3 py-2 rounded-xl bg-[#1E293B]/60 border border-[#334155]">
              <p className="text-xs text-slate-400 font-mono">Signed in as</p>
              <p className="text-sm font-bold text-white truncate">{session.user.email}</p>
            </div>
            <button 
              onClick={() => signOut()} 
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-[#1E293B] hover:bg-rose-500/20 hover:text-rose-400 border border-[#334155] hover:border-rose-500/40 text-xs font-bold text-slate-300 transition-all"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign out</span>
            </button>
          </div>
        ) : (
          <button 
            onClick={() => signIn()} 
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-[#0066FF] hover:bg-[#0052CC] text-white text-xs font-bold transition-all shadow-md shadow-[#0066FF]/20"
          >
            <LogIn className="w-4 h-4" />
            <span>Sign in to Platform</span>
          </button>
        )}
      </div>
    </nav>
  );
}
