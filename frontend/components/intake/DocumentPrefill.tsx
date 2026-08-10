"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { uploadDocuments, type DocumentsResponse, type Question } from "@/lib/api";

/**
 * Upload the paperwork instead of retyping it.
 *
 * A large operator has the book already, in whatever their industry calls
 * paperwork: purchase orders for a distributor, protocols and enrollment
 * reports for a CRO. Asking them to retype it is the single most likely reason
 * they abandon intake, so this sits at the top of the form.
 *
 * The reading is done server-side because the industry decides what a document
 * even is. The panel's job is to show what came back, name the tables it could
 * not fill and why, and require an explicit click before anything is replaced.
 */
export function DocumentPrefill({
  industry,
  questions,
  onApply,
}: {
  industry: string;
  questions: Question[];
  onApply: (patch: Record<string, any[]>) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<DocumentsResponse | null>(null);
  const [applied, setApplied] = useState(false);
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
      setRes(await uploadDocuments(Array.from(files), industry));
    } catch (e: any) {
      setError(e.message || "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  const apply = () => {
    const prefill = res?.prefill;
    if (!prefill) return;
    const patch: Record<string, any[]> = {};
    for (const [qid, table] of Object.entries(prefill)) {
      if (table.rows?.length) patch[qid] = table.rows;
    }
    onApply(patch);
    setApplied(true);
  };

  const prefill = res?.prefill || {};
  const totalRows = Object.values(prefill).reduce((n, t) => n + (t.rows?.length || 0), 0);
  const unevidenced = Array.from(
    new Set(Object.values(prefill).flatMap((t) => t.unevidenced || []))
  );

  return (
    <div className="rounded-2xl border border-rule bg-raised/40 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-lg font-bold text-ink">
            Have the paperwork already? Upload it instead.
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted">
            We read the documents your industry actually keeps and fill the tables below, so you
            correct a draft rather than type one.
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
          {!res && !busy && !error && (
            <button
              onClick={() => inputRef.current?.click()}
              className="w-full rounded-xl border border-dashed border-rule px-4 py-6 text-sm text-muted transition-colors hover:border-brand hover:text-brand"
            >
              Choose files. PDF, CSV or text.
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

          {res && !busy && (
            <div className="space-y-3">
              <p className="text-sm text-ink">
                Read {res.documents?.length ?? 0} document
                {(res.documents?.length ?? 0) === 1 ? "" : "s"}
                {totalRows > 0
                  ? <>, enough to fill <span className="font-semibold text-brand">{totalRows}</span> rows.</>
                  : <>, but nothing in them fills a table.</>}
              </p>

              {/* What each document was taken to be, so a wrong read is visible. */}
              {!!res.documents?.length && (
                <ul className="space-y-0.5">
                  {res.documents.map((d) => (
                    <li key={d.filename} className="flex flex-wrap items-baseline gap-2 font-mono text-[0.62rem]">
                      <span className="text-muted">{d.filename}</span>
                      <span className="text-ink">{String(d.doc_type || "unclassified").replace(/_/g, " ")}</span>
                      {typeof d.confidence === "number" && (
                        <span className="text-muted">{Math.round(d.confidence * 100)}% confident</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              <ul className="space-y-1 border-t border-rule pt-2">
                {entityQs.map((q) => {
                  const t = prefill[q.id];
                  return (
                    <li key={q.id} className="flex items-baseline gap-2 font-mono text-[0.68rem]">
                      <span className={t ? "text-emerald" : "text-muted"}>{t ? "●" : "○"}</span>
                      <span className="text-ink">{q.label}</span>
                      <span className="text-muted">
                        {t ? `${t.rows.length} row${t.rows.length === 1 ? "" : "s"}` : res.skipped?.[q.id]}
                      </span>
                    </li>
                  );
                })}
              </ul>

              {res.ai_enabled === false && (
                <p className="rounded-lg border border-amber/40 bg-amber/10 px-3 py-2 text-xs text-ink">
                  Running without an extraction key, so classification fell back to filename and
                  keyword matching and most fields will be blank.
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

              {unevidenced.length > 0 && (
                <p className="font-mono text-[0.6rem] leading-relaxed text-amber">
                  Not stated in your documents, so these kept this industry&apos;s default and are worth
                  checking: {unevidenced.join(", ")}.
                </p>
              )}

              <p className="border-t border-rule pt-2 font-mono text-[0.6rem] leading-relaxed text-muted">
                Extraction is best-effort, so check the tables before you run. Files are held in
                memory for the request and never written to disk; document text is sent to the
                Anthropic API to be classified and read.{" "}
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
