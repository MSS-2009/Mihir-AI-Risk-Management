import Link from "next/link";
import { Eyebrow } from "@/components/ui";

export const metadata = {
  title: "Manual entry · Avenoir",
  description: "Enter your book by hand or upload documents, when there is no system to connect.",
};

/**
 * The old front door, now the back one.
 *
 * v2 was a questionnaire, so the questionnaire was the product. v3 lives inside
 * a customer's systems, so this path stays because it is genuinely useful, not
 * because it used to be first: a prospect in a meeting with no credentials to
 * hand still needs to see a real number, and some operators keep the book that
 * matters in a spreadsheet rather than a system anyone can connect to.
 *
 * The only difference is what it can claim. Without observed history every
 * parameter stays a published estimate, and that is stated here rather than
 * discovered later on the dashboard.
 */
export default function ManualPage() {
  return (
    <div className="container-x py-12">
      <div className="max-w-2xl">
        <Eyebrow>Manual entry</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">
          No system to connect? Enter it by hand.
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">
          The same engine and the same output as a connected assessment. The difference is what it
          can honestly claim: without observed history every parameter stays our published starting
          estimate, and the dashboard will say so per parameter rather than implying otherwise.
        </p>
      </div>

      <div className="mt-10 grid gap-5 lg:grid-cols-2">
        <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
          <div className="eyebrow">Fastest</div>
          <h2 className="mt-1 font-display text-xl font-bold text-ink">Upload the paperwork</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Purchase orders, invoices, protocols, sponsor schedules, vendor registers: whatever your
            industry actually keeps. We read them in your industry&apos;s own vocabulary and fill the
            tables, so you correct a draft rather than type one.
          </p>
          <Link
            href="/start"
            className="mt-4 inline-block rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-deep"
          >
            Choose your industry →
          </Link>
        </div>

        <div className="rounded-2xl border border-rule bg-surface p-6 shadow-card">
          <div className="eyebrow">Most control</div>
          <h2 className="mt-1 font-display text-xl font-bold text-ink">Type your book in</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted">
            Vendors, import lines, sites, trials, advisors, whichever entities your industry runs on.
            Every field states which model it moves, and every value stays editable.
          </p>
          <Link
            href="/intake"
            className="mt-4 inline-block rounded-lg border border-rule px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-brand hover:text-brand"
          >
            Go to the questionnaire →
          </Link>
        </div>
      </div>

      <section className="mt-10 rounded-2xl border border-brand/25 bg-brand/[0.04] p-6">
        <Eyebrow>Worth knowing</Eyebrow>
        <p className="thesis mt-2 max-w-3xl text-lg leading-snug text-ink">
          Connecting a system is what turns our estimates into your measurements. Typed answers move
          a published starting estimate; observed history replaces it.
        </p>
        <Link href="/connect" className="mt-3 inline-block link-underline text-sm text-brand">
          Connect a system instead
        </Link>
      </section>
    </div>
  );
}
