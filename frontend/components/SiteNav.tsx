"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import { AvenoirMark } from "./AvenoirMark";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/upload", label: "Upload" },
  { href: "/methodology", label: "Methodology" },
  { href: "/pricing", label: "Pricing" },
];

export function SiteNav() {
  const pathname = usePathname();
  const [ai, setAi] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => setAi(h.ai_enabled))
      .catch(() => setAi(null));
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b border-mist bg-paper/85 backdrop-blur">
      <div className="container-x flex h-16 items-center justify-between gap-2">
        <Link href="/" className="flex shrink-0 items-center gap-2.5" aria-label="Avenoir home">
          <AvenoirMark className="h-8 w-8" />
          <span className="flex flex-col leading-none">
            <span className="font-display text-lg font-extrabold tracking-[0.14em] text-ink">AVENOIR</span>
            <span className="mt-0.5 hidden font-mono text-[0.55rem] uppercase tracking-[0.22em] text-bordeaux sm:inline">
              Predict. Protect. Perfect.
            </span>
          </span>
        </Link>

        <nav className="flex items-center gap-1 overflow-x-auto sm:gap-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {LINKS.map((l) => {
            const active = pathname === l.href || pathname.startsWith(l.href + "/");
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`shrink-0 rounded-md px-2.5 py-1.5 text-sm transition-colors sm:px-3 ${
                  active ? "bg-bordeaux/8 font-semibold text-bordeaux" : "text-ink/70 hover:text-ink"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
          <Link
            href="/upload"
            className="ml-1 hidden shrink-0 rounded-md bg-bordeaux px-3.5 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-bordeaux-deep sm:inline-block"
          >
            Run analysis
          </Link>
        </nav>
      </div>
      {ai === false && (
        <div className="border-t border-ochre/20 bg-ochre/8">
          <div className="container-x py-1 text-center font-mono text-[0.68rem] text-ochre">
            Analysis engine is running without an AI key, narratives use the deterministic fallback.
          </div>
        </div>
      )}
    </header>
  );
}
