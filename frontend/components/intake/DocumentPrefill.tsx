"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { uploadDocuments, type Question } from "@/lib/api";
import { buildPrefill, withDefaults, type PrefillResult } from "@/lib/prefill";
import { money } from "@/lib/format";

/**
 * Upload the paperwork instead of retyping it.
 *
 * A large operator has the vendor book already, in purchase orders, invoices
 * and customs entries. Asking them to retype it into a table is the single
 * most likely reason they abandon intake, so this sits at the top of the form
 * rather than on a separate page they have to find.
 *
 * What it does NOT do is quietly overwrite their work. Extraction is
 * best-effort, so the panel shows exactly what it found, names the tables it
 * would fill, and requires an explicit click. Every filled row lands in an
 * editable table.
 */
export function DocumentPrefill({
  questions,
  onApply,
  currentAnswers,
}: {
  questions: Question[];
  onApply: (patch: Record<string, any[]>) => void;
  currentAnswers: Record<string, any>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PrefillResult | null>(null);
  const [applied, setApplied] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(true);
  const [names, setNames] = useState<string[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const entityQs = questions.filter((q) => q.type === "entity_list" && q.fields?.length);

  const handle = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);
    setError(null);
    setApplied(false);
    setNames(Array.from(files).map((f) => f.name));
    try {
      const res = await uploadDocuments(Array.from(files));
      setAiEnabled(res.ai_enabled !== false);
      setResult(buildPrefill(questions, (res.documents || []) as any));
    } catch (e: any) {
      setError(e.message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  const apply = () => {
    if (!result) return;
    const patch: Record<string, any[]> = {};
    for (const q of entityQs) {
      const found = result.rows[q.id];
      if (!found?.length) continue;
      patch[q.id] = found.map((r) => withDefaults(r, q.fields as any, q.default as any[]));
    }
    onApply(patch);
    setApplied(true);
  };

  const fillable = result ? Object.keys(result.rows) : [];
  const totalRows = result ? Object.values(result.rows).reduce((n, r) => n + r.length, 0) : 0;

  return (
    <div className="rounded-2xl border border-rule bg-raised/40 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-lg font-bold text-ink">
            Have the paperwork already? Upload it instead.
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Purchase orders, invoices, customs entries, packing lists or a CSV export. We read the
            counterparty, value, origin, HS code and lead time out of them and fill the tables below,
            so you correct a draft rather than type one.
          </p>
        </div>
        <button
          onClick={() => { setOpen((s) => !s); if (!open) setTimeout(() => inputRef.current?.click(), 60); }}
          aria-expanded={open}
          className="shrink-0 rounded-lg bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-deep"
        >
          Upload documents
        </button>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.csv,.txt,.json"
        onChange={(e) => handle(e.target.files)}
        className="sr-only"
        aria-label="Upload documents to fill the tables"
      />

      {open && (
        <div className="mt-4 border-t border-rule pt-4">
          {!result && !busy && !error && (
            <button
              onClick={() => inputRef.current?.click()}
              className="w-full rounded-xl border border-dashed border-rule px-4 py-6 text-sm text-muted transition-colors hover:border-brand hover:text-brand"
            >
              Choose files, or drop them on this panel. PDF, CSV or text.
            </button>
          )}

          {busy && (
            <p className="font-mono text-xs text-muted">
              Reading {names.length} file{names.length === 1 ? "" : "s"} and classifying each one…
            </p>
          )}

          {error && (
            <div className="rounded-lg border border-amber/40 bg-amber/10 px-3 py-2 text-sm text-ink">
              {error}
            </div>
          )}

          {result && !busy && (
            <div className="space-y-3">
              <p className="text-sm text-ink">
                Read {result.documentCount} document{result.documentCount === 1 ? "" : "s"} and found{" "}
                <span className="font-semibold text-brand">{result.supplierCount}</span> named
                {result.supplierCount === 1 ? " counterparty" : " counterparties"}
                {totalRows > 0 && <>, enough to fill <span className="font-semibold">{totalRows}</span> rows.</>}
                {totalRows === 0 && <>, but not enough figures to fill a table.</>}
              </p>

              <ul className="space-y-1">
                {entityQs.map((q) => {
                  const found = result.rows[q.id];
                  return (
                    <li key={q.id} className="flex items-baseline gap-2 font-mono text-[0.68rem]">
                      <span className={found ? "text-emerald" : "text-muted"}>{found ? "●" : "○"}</span>
                      <span className="text-ink">{q.label}</span>
                      <span className="text-muted">
                        {found ? `${found.length} row${found.length === 1 ? "" : "s"}` : result.skipped[q.id]}
                      </span>
                    </li>
                  );
                })}
              </ul>

              {!aiEnabled && (
                <p className="rounded-lg border border-amber/40 bg-amber/10 px-3 py-2 text-xs text-ink">
                  Running without an extraction key, so classification fell back to filename and
                  keyword matching and most fields will be blank. The figures below are the pack
                  defaults, not your documents.
                </p>
              )}

              {totalRows > 0 && (
                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <button
                    onClick={apply}
                    disabled={applied}
                    className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-deep disabled:cursor-default disabled:opacity-50"
                  >
                    {applied ? "Filled below" : "Replace the sample rows"}
                  </button>
                  <span className="font-mono text-[0.62rem] text-muted">
                    replaces the example rows; every value stays editable
                  </span>
                </div>
              )}

              <p className="border-t border-rule pt-2 font-mono text-[0.6rem] leading-relaxed text-muted">
                Extraction is best-effort and columns a document cannot evidence keep the pack
                default, so check the tables before you run. Files are held in memory for the
                request and never written to disk; document text is sent to the Anthropic API to
                be classified and read.{" "}
                <Link href="/upload" className="link-underline text-brand">
                  Full document checklist
                </Link>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
