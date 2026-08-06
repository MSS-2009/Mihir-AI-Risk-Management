"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getIndustries, type Industry, type Question } from "@/lib/api";
import { money, pct } from "@/lib/format";
import { useSession } from "@/lib/session";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";
import { Eyebrow } from "@/components/ui";
import { EntityTable } from "@/components/EntityTable";
import { DocumentPrefill } from "@/components/intake/DocumentPrefill";

/**
 * The questionnaire. Every question states which model it moves, because a
 * questionnaire whose answers change nothing would be theatre. Questions that
 * are genuinely context only say so rather than pretending otherwise.
 */
export default function IntakePage() {
  const router = useRouter();
  const { industry, answers, ready, setAnswers } = useSession();
  const [packs, setPacks] = useState<Industry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [local, setLocal] = useState<Record<string, any>>({});

  useEffect(() => {
    getIndustries().then((r) => setPacks(r.industries)).catch((e) => setError(e.message));
  }, []);

  const pack = useMemo(() => packs?.find((p) => p.id === industry) || null, [packs, industry]);

  useEffect(() => {
    if (!pack) return;
    const init: Record<string, any> = {};
    pack.questions.forEach((q) => (init[q.id] = answers[q.id] ?? q.default));
    setLocal(init);
  }, [pack]); // eslint-disable-line react-hooks/exhaustive-deps

  if (ready && !industry) {
    return (
      <div className="container-x py-20 text-center">
        <h1 className="font-display text-2xl font-bold text-ink">Pick an industry first</h1>
        <p className="mt-2 text-muted">The questions depend on which one you choose.</p>
        <Link href="/start" className="mt-5 inline-block rounded-lg bg-brand px-5 py-3 font-semibold text-white hover:bg-brand-deep">
          Choose your industry
        </Link>
      </div>
    );
  }

  const set = (id: string, v: any) => setLocal((s) => ({ ...s, [id]: v }));

  const submit = () => {
    setAnswers(local);
    router.push("/dashboard?run=1");
  };

  const changed = pack
    ? pack.questions.filter((q) => !q.context_only && local[q.id] !== q.default).length
    : 0;

  return (
    <div className="container-x py-12">
      <div className="max-w-2xl">
        <Eyebrow>Step 2 of 3 · {pack?.name || ""}</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink">
          Tell us about your operation
        </h1>
        <p className="mt-3 text-muted">
          Every answer below moves a specific parameter, and we show you which one. Leave anything at
          its default and you get our published starting estimate for that item, unchanged.
        </p>
      </div>

      {error && <div className="mt-8"><ErrorPanel error={error} /></div>}
      {!pack && !error && <div className="mt-8"><LoadingPanel title="Loading questions" detail="Reading this industry's intake pack." /></div>}

      {pack && (
        <>
          {/* Before the form, not after it: a large operator will not retype a
              vendor book that already exists in their purchase orders. */}
          <div className="mt-8">
            <DocumentPrefill
              questions={pack.questions}
              currentAnswers={local}
              onApply={(patch) => setLocal((s) => ({ ...s, ...patch }))}
            />
          </div>

          <div className="mt-10 space-y-10">
            {Object.entries(
              pack.questions.reduce((acc: Record<string, typeof pack.questions>, q) => {
                const g = q.group || "Your operation";
                (acc[g] ||= []).push(q);
                return acc;
              }, {})
            ).map(([group, qs]) => (
              <section key={group}>
                <h2 className="font-mono text-[0.68rem] uppercase tracking-[0.18em] text-brand">{group}</h2>
                <div className="mt-4 grid gap-x-10 gap-y-7 lg:grid-cols-2">
                  {qs.map((q) => (
                    <div key={q.id} className={q.type === "entity_list" ? "lg:col-span-2" : ""}>
                      <QuestionField q={q} value={local[q.id]} onChange={(v) => set(q.id, v)} pack={pack} />
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>

          <div className="mt-10 flex flex-wrap items-center gap-4 border-t border-rule pt-6">
            <button
              onClick={submit}
              className="rounded-lg bg-brand px-5 py-3 font-semibold text-white transition-colors hover:bg-brand-deep"
            >
              Run the assessment →
            </button>
            <Link href="/start" className="link-underline text-sm text-muted">
              Change industry
            </Link>
            <span className="font-mono text-[0.68rem] text-muted tnum">
              {changed === 0
                ? "All defaults. You will get the published starting calibration."
                : `${changed} answer${changed === 1 ? "" : "s"} differ from the default.`}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

function QuestionField({
  q,
  value,
  onChange,
  pack,
}: {
  q: Question;
  value: any;
  onChange: (v: any) => void;
  pack: Industry;
}) {
  const engineLabel = (key: string) =>
    key === "*" ? "every model" : pack.engines.find((e) => e.engine === key)?.label || key;

  const affects = q.context_only
    ? null
    : q.targets.map(engineLabel).join(", ");

  return (
    <div>
      <label className="block">
        <span className="block text-sm font-medium text-ink">{q.label}</span>

        {q.type === "currency" && (
          <div className="mt-1.5 flex items-center rounded-lg border border-rule bg-surface focus-within:border-brand">
            <span className="pl-3 font-mono text-sm text-muted">$</span>
            <input
              inputMode="numeric"
              value={Number(value || 0).toLocaleString("en-US")}
              onChange={(e) => onChange(parseFloat(e.target.value.replace(/[^0-9.]/g, "")) || 0)}
              className="w-full bg-transparent px-2 py-2 font-mono text-sm tabular-nums text-ink outline-none"
            />
          </div>
        )}

        {q.type === "percent" && (
          <>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="font-mono text-sm tabular-nums text-brand">{pct(Number(value || 0), 0)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={Number(value || 0)}
              onChange={(e) => onChange(parseFloat(e.target.value))}
              className="mt-1 w-full accent-brand"
              aria-label={q.label}
            />
          </>
        )}

        {(q.type === "int" || q.type === "number") && (
          <div className="mt-1.5 flex items-center rounded-lg border border-rule bg-surface focus-within:border-brand">
            <input
              type="number"
              value={Number(value ?? 0)}
              onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
              className="w-full bg-transparent px-3 py-2 font-mono text-sm tabular-nums text-ink outline-none"
            />
            {q.unit && <span className="pr-3 font-mono text-xs text-muted">{q.unit}</span>}
          </div>
        )}

        {q.type === "entity_list" && (
          <div className="mt-3">
            <EntityTable
              rows={(value as any[]) || []}
              fields={(q.fields as any) || []}
              onChange={onChange}
              addLabel={q.label.toLowerCase()}
            />
          </div>
        )}

        {q.type === "choice" && (
          <select
            value={String(value ?? "")}
            onChange={(e) => onChange(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-rule bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-brand"
          >
            {(q.choices || []).map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        )}
      </label>

      {q.help && <p className="mt-1.5 text-xs text-muted">{q.help}</p>}

      <p className="mt-1 font-mono text-[0.62rem] uppercase tracking-wide text-muted">
        {affects ? (
          <>
            Moves <span className="text-brand">{affects}</span>
            {value !== q.default && <span className="text-amber"> · changed from default</span>}
          </>
        ) : (
          <span>Context only. Recorded, but moves no number.</span>
        )}
      </p>
    </div>
  );
}
