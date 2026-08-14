"use client";
import { useState } from "react";
import Link from "next/link";
import { createOrganization, orgGet, type AuditEntry, type CreateOrgResponse } from "@/lib/api";
import { Eyebrow } from "@/components/ui";

/**
 * The front door. In v2 this product was a form you filled in; in v3 it is
 * something that lives inside a customer's systems, so this page is the one
 * that matters and the questionnaire moved to the back.
 *
 * Two ways in, deliberately different in kind rather than in brand:
 *
 * Hosted connectors reach systems that live on the internet. We pull, on a
 * schedule, through an aggregator, and no credential of theirs is ever held by
 * us.
 *
 * The MCP server reaches everything else, and is the more interesting half. It
 * runs inside their network and pushes outbound, so an on-premise ERP or a
 * warehouse behind a firewall becomes reachable without opening anything. The
 * same install also lets their own agents query us, which is the part that
 * turns Avenoir from a site someone remembers to visit into infrastructure.
 *
 * The transparency panel is not a footnote. Anyone deciding whether to connect a
 * finance system wants to know exactly what is read and what is refused, so
 * that is on this page rather than linked from it.
 */

const CONNECTORS = [
  { id: "quickbooks", name: "QuickBooks Online", grade: "Common", note: "Invoices, vendors, expenses and cash. Usually no purchase order promise dates." },
  { id: "xero", name: "Xero", grade: "Common", note: "Invoices, contacts, expenses and cash." },
  { id: "netsuite", name: "NetSuite", grade: "Rich", note: "Adds purchase orders with promise and receipt dates, and item-level detail." },
  { id: "intacct", name: "Sage Intacct", grade: "Rich", note: "Adds purchase orders and order history." },
  { id: "dynamics", name: "Microsoft Dynamics 365", grade: "Rich", note: "Adds purchase orders and inventory." },
];

const MCP_TOOLS = [
  ["get_risk_profile", "Your expected annual loss, the percentile curve, and how much of it is measured from your own history."],
  ["explain_parameter", "Where one number came from: the observations behind it, the window, and the weight on your data."],
  ["price_decision", "Price a decision against your live profile, including its effect on your tail."],
  ["list_changes", "What moved since the last sync, and the parameter that moved it."],
  ["read_local_csv_folder", "Read local extracts and show you what they contain. Sends nothing."],
  ["push_records", "The only tool that transmits. Writes one dated, immutable snapshot."],
];

export default function ConnectPage() {
  const [created, setCreated] = useState<CreateOrgResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  const [name, setName] = useState("My company");
  const [pack, setPack] = useState("industrial_distribution");

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      setCreated(await createOrganization({ name, industry_pack: pack }));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const loadAudit = async () => {
    if (!created) return;
    try {
      const r = await orgGet<{ entries: AuditEntry[] }>(
        created.organization.id, "/audit", created.token
      );
      setAudit(r.entries);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const config = created
    ? JSON.stringify(
        {
          mcpServers: {
            avenoir: {
              command: "python",
              args: ["-m", "avenoir_mcp.server"],
              env: {
                AVENOIR_API_URL: process.env.NEXT_PUBLIC_API_URL || "https://avenoir-api.onrender.com",
                AVENOIR_ORG_ID: created.organization.id,
                AVENOIR_TOKEN: created.token,
              },
            },
          },
        },
        null,
        2
      )
    : "";

  return (
    <div className="container-x py-12">
      <div className="max-w-2xl">
        <Eyebrow>Connect</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink sm:text-5xl">
          Point it at your systems
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">
          Avenoir is not something you open once a quarter. It reads a copy of your financial
          records, estimates how often things have actually gone wrong from your own history, and
          tells you when something material changes. Connect it once.
        </p>
      </div>

      {/* ---- 1. Hosted connectors ---- */}
      <section className="mt-12">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <Eyebrow>One</Eyebrow>
            <h2 className="mt-1 font-display text-2xl font-bold text-ink">
              Hosted accounting and ERP
            </h2>
          </div>
          <p className="max-w-md text-sm text-muted">
            Read-only, through an aggregator. Authorisation happens on their side, so no password
            of yours ever reaches us and we store a reference rather than a token.
          </p>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {CONNECTORS.map((c) => (
            <div key={c.id} className="rounded-xl border border-rule bg-surface p-4 shadow-card">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium text-ink">{c.name}</span>
                <span
                  className={`rounded-full px-2 py-0.5 font-mono text-[0.55rem] uppercase tracking-wide ${
                    c.grade === "Rich" ? "bg-brand/12 text-brand" : "bg-rule text-muted"
                  }`}
                >
                  {c.grade}
                </span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted">{c.note}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 font-mono text-[0.62rem] leading-relaxed text-muted">
          The grade is not marketing. A connection without purchase order promise dates cannot
          evidence a late delivery, so two of the four measurable frequencies stay on our published
          estimate, and the dashboard says so per parameter rather than quietly averaging it away.
        </p>
      </section>

      {/* ---- 2. The MCP server ---- */}
      <section className="mt-14">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <Eyebrow>Two</Eyebrow>
            <h2 className="mt-1 font-display text-2xl font-bold text-ink">
              The MCP server, for everything else
            </h2>
          </div>
          <p className="max-w-md text-sm text-muted">
            Runs inside your network and sends outbound. No inbound rule, no VPN, and it reaches the
            on-premise systems an aggregator cannot see.
          </p>
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-2xl border border-rule bg-surface p-5 shadow-card">
            <div className="eyebrow">What it gives your own agents</div>
            <ul className="mt-3 space-y-2.5">
              {MCP_TOOLS.map(([tool, what]) => (
                <li key={tool}>
                  <code className="font-mono text-[0.7rem] text-brand">{tool}</code>
                  <p className="mt-0.5 text-xs leading-relaxed text-muted">{what}</p>
                </li>
              ))}
            </ul>
            <p className="mt-4 border-t border-rule pt-3 text-xs leading-relaxed text-muted">
              Reading and sending are separate tools on purpose. The one that reads your local files
              has no ability to transmit, so a person can see exactly what would leave the building
              before any of it does.
            </p>
          </div>

          <div className="rounded-2xl border border-rule bg-raised/50 p-5">
            <div className="eyebrow">Install</div>
            {!created ? (
              <>
                <p className="mt-2 text-sm leading-relaxed text-muted">
                  Create an organisation to get a scoped token. It is shown once and stored only as
                  a hash, so it cannot be recovered from us, only replaced.
                </p>
                <div className="mt-4 space-y-3">
                  <label className="block">
                    <span className="font-mono text-[0.6rem] uppercase tracking-wide text-muted">
                      Company
                    </span>
                    <input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-rule bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand"
                    />
                  </label>
                  <label className="block">
                    <span className="font-mono text-[0.6rem] uppercase tracking-wide text-muted">
                      Industry
                    </span>
                    <select
                      value={pack}
                      onChange={(e) => setPack(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-rule bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand"
                    >
                      <option value="industrial_distribution">Industrial Distribution</option>
                      <option value="automotive_manufacturing">Automotive &amp; Manufacturing</option>
                      <option value="clinical_research">Clinical Research &amp; Healthcare</option>
                      <option value="property_data">Property &amp; Data Analytics</option>
                      <option value="wealth_management">Wealth Management &amp; Finance</option>
                    </select>
                  </label>
                  <button
                    onClick={create}
                    disabled={busy}
                    className="w-full rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-deep disabled:opacity-50"
                  >
                    {busy ? "Creating…" : "Create organisation and token"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="mt-2 text-sm text-ink">
                  Add this to your MCP client configuration, then restart it.
                </p>
                <pre className="mt-3 max-h-64 overflow-auto rounded-lg border border-rule bg-surface p-3 font-mono text-[0.6rem] leading-relaxed text-ink">
{config}
                </pre>
                <p className="mt-2 font-mono text-[0.58rem] leading-relaxed text-amber">
                  {created.note}
                </p>
                <button
                  onClick={loadAudit}
                  className="mt-3 font-mono text-[0.62rem] uppercase tracking-wide text-muted hover:text-brand"
                >
                  show what we have read so far
                </button>
              </>
            )}
            {error && (
              <p className="mt-3 rounded-lg border border-amber/40 bg-amber/10 px-3 py-2 text-xs text-ink">
                {error}
              </p>
            )}
          </div>
        </div>
      </section>

      {/* ---- 3. Transparency ---- */}
      <section className="mt-14">
        <Eyebrow>What you can see</Eyebrow>
        <h2 className="mt-1 font-display text-2xl font-bold text-ink">
          Every read is logged, and the log is yours
        </h2>
        <div className="mt-5 grid gap-4 lg:grid-cols-3">
          {[
            ["Every access", "Timestamp, what was read, which component asked, and under which token. Reading the log is not itself logged, so it cannot grow by inspecting it."],
            ["Every snapshot", "Dated and immutable. A correction arrives as a new snapshot, so any past number reproduces exactly and 'why did this change' is a diff rather than an argument."],
            ["Every parameter", "Measured, blended or our estimate, with the observation count and window behind it, and the reason when it is still ours."],
          ].map(([h, b]) => (
            <div key={h} className="rounded-xl border border-rule bg-surface p-4 shadow-card">
              <div className="font-display text-base font-bold text-ink">{h}</div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted">{b}</p>
            </div>
          ))}
        </div>

        {audit && (
          <div className="mt-5 overflow-x-auto rounded-xl border border-rule">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-rule bg-raised">
                  {["When", "Action", "Component", "Detail"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-mono text-[0.55rem] uppercase tracking-wide text-muted">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono text-[0.68rem]">
                {audit.map((e) => (
                  <tr key={e.id} className="border-b border-rule/60 last:border-0">
                    <td className="px-3 py-2 tabular-nums text-muted">{e.at.slice(0, 19).replace("T", " ")}</td>
                    <td className="px-3 py-2 text-ink">{e.action}</td>
                    <td className="px-3 py-2 text-muted">{e.component}</td>
                    <td className="px-3 py-2 text-muted">{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-4 font-mono text-[0.62rem] leading-relaxed text-muted">
          Read-only throughout: there is no write method on the connector protocol to call, so there
          is no write path to disable.{" "}
          <Link href="/security" className="link-underline text-brand">
            The full security posture
          </Link>
          , including what we do not have yet.
        </p>
      </section>

      <section className="mt-14 rounded-2xl border border-rule bg-raised p-6">
        <Eyebrow>No systems to connect yet?</Eyebrow>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
          You can still get a full assessment by entering your book by hand, or by uploading the
          paperwork you already keep. It is the same engine and the same output; the only difference
          is that parameters stay on our published estimates until real history arrives.
        </p>
        <Link
          href="/manual"
          className="mt-4 inline-block rounded-lg border border-rule px-4 py-2.5 text-sm font-medium text-ink transition-colors hover:border-brand hover:text-brand"
        >
          Enter it manually instead →
        </Link>
      </section>
    </div>
  );
}
