import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-rule bg-raised">
      <div className="container-x flex flex-col gap-6 py-10 sm:flex-row sm:items-start sm:justify-between">
        <div className="max-w-sm">
          <div className="font-display text-xl font-semibold text-brand">Avenoir</div>
          <p className="mt-2 text-sm text-muted">
            Risk quantification for mid-market companies. Every number is a seeded,
            deterministic simulation you can interrogate, not a color on a dashboard.
          </p>
        </div>
        <nav className="grid grid-cols-2 gap-x-12 gap-y-2 text-sm">
          <Link href="/dashboard" className="link-underline">Dashboard</Link>
          <Link href="/start" className="link-underline">Choose your industry</Link>
          <Link href="/methodology" className="link-underline">Methodology</Link>
          <Link href="/pricing" className="link-underline">Pricing</Link>
          <Link href="/security" className="link-underline">Security</Link>
        </nav>
      </div>
      <div className="border-t border-rule">
        <div className="container-x flex flex-col gap-1 py-4 font-mono text-[0.68rem] text-muted sm:flex-row sm:justify-between">
          <span>© {new Date().getFullYear()} Avenoir. Illustrative figures for demonstration.</span>
          <span>Deterministic · seeded · traceable to model, version &amp; seed.</span>
        </div>
      </div>
    </footer>
  );
}
