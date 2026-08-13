import Link from "next/link";
import { Eyebrow } from "@/components/ui";

export const metadata = {
  title: "Security · Avenoir",
  description:
    "Read-only access, per-organisation isolation, a customer-visible audit log, and one action that disconnects and purges.",
};

/**
 * For a technical evaluator this page IS the buying decision, so it answers the
 * questions they will actually ask rather than the ones that are comfortable.
 *
 * Two rules held throughout. Nothing here describes an intention: every claim
 * is either true of the code today or is marked as not yet built. And no
 * certification is claimed, because claiming one we do not hold is the single
 * fastest way to end a security review badly.
 */

const NOW = [
  {
    q: "What can Avenoir do inside our systems?",
    a: "Read. There is no write path in the code, not a disabled one: the connector protocol has no write method to call. No draft, no comment, no status field. If that changes it will be a version with a number on it and a conversation first.",
  },
  {
    q: "Where do our credentials live?",
    a: "With the aggregator, never with us. Authorisation happens through their hosted flow, and Avenoir stores a reference to the connection rather than a token. There is nothing in our database that could be replayed against your system.",
  },
  {
    q: "Which scopes do you request?",
    a: "Read-only accounting scopes: accounts, contacts, invoices, purchase orders, expenses and, where the system supports it, items. We do not request payroll, banking or user administration.",
  },
  {
    q: "How is our data separated from another customer's?",
    a: "Row-level security keyed by organisation, enforced in the database rather than in application code, so a query that forgets a filter returns nothing rather than someone else's book. The browser only ever holds an anonymous key; the service key stays server-side.",
  },
  {
    q: "Can we see what you read?",
    a: "Yes. Every read is logged with a timestamp, the scope, and the component that asked for it, and that log is visible to you rather than to us alone. An audit log you cannot read is a promise, not a control.",
  },
  {
    q: "What happens when we disconnect?",
    a: "One action revokes the connection at the aggregator and purges the snapshots it produced. Deletion means the rows are gone, not flagged.",
  },
  {
    q: "How long do you keep anything?",
    a: "Snapshots are retained for the life of the connection so that a past assessment stays reproducible, which is the whole point of dating them. You can delete them sooner, and disconnecting deletes them.",
  },
  {
    q: "Is our data used to train anything?",
    a: "No. It is not used to train models, and it is not pooled across customers. Document text is sent to the Anthropic API for classification and extraction during an upload; nothing else leaves the system.",
  },
  {
    q: "Is it encrypted?",
    a: "In transit and at rest, through Supabase's managed Postgres.",
  },
];

const NOT_YET = [
  ["SOC 2", "Not held. Readiness work starts the quarter after the first paying customer. We will not claim it before it exists."],
  ["Penetration test", "Not yet commissioned. Planned before the first customer with production data."],
  ["Single sign-on and SCIM", "Not built. Reasonable to ask for, and not there today."],
  ["Customer-managed keys", "Not built."],
];

export default function SecurityPage() {
  return (
    <div className="container-x py-12">
      <div className="max-w-2xl">
        <Eyebrow>Security</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">
          What we can see, and what we cannot
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">
          Avenoir reads a copy of your financial records to estimate how often things have
          actually gone wrong. That is a real ask, so here is the whole answer in one place,
          including the parts that are not finished.
        </p>
      </div>

      <section className="mt-10 rounded-2xl border border-brand/25 bg-brand/[0.04] p-6 sm:p-8">
        <Eyebrow>The short version</Eyebrow>
        <p className="thesis mt-2 max-w-3xl text-xl leading-snug text-ink">
          Read-only, isolated per organisation, logged where you can see it, and revocable in
          one action. No credential of yours is ever held by us.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="font-display text-2xl font-bold text-ink">The questions you are going to ask</h2>
        <div className="mt-6 grid gap-x-10 gap-y-7 lg:grid-cols-2">
          {NOW.map(({ q, a }) => (
            <div key={q}>
              <h3 className="font-display text-base font-bold leading-snug text-ink">{q}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{a}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Naming the gaps is the part that makes the rest believable. */}
      <section className="mt-12">
        <h2 className="font-display text-2xl font-bold text-ink">What we do not have yet</h2>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Listed because a security page that only lists strengths tells you nothing. If one of
          these is a blocker for you, it is better that we both know now.
        </p>
        <div className="mt-5 overflow-x-auto rounded-xl border border-rule">
          <table className="w-full min-w-[560px] text-sm">
            <tbody>
              {NOT_YET.map(([item, note]) => (
                <tr key={item} className="border-b border-rule/60 last:border-0">
                  <td className="w-56 px-4 py-3 align-top font-medium text-ink">{item}</td>
                  <td className="px-4 py-3 text-muted">{note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-12 rounded-2xl border border-rule bg-raised p-6">
        <Eyebrow>Reporting a problem</Eyebrow>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
          If you find a vulnerability, tell us before you tell anyone else and we will fix it and
          credit you. We do not run a bounty programme yet, and we will not threaten anyone who
          reports something in good faith.
        </p>
        <p className="mt-4 font-mono text-[0.66rem] text-muted">
          Every claim on this page is either true of the code today or listed above as not built.{" "}
          <Link href="/methodology" className="link-underline text-brand">
            How the numbers are computed
          </Link>
        </p>
      </section>
    </div>
  );
}
