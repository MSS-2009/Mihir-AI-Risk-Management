"use client";
import { useRef, useState } from "react";
import { uploadDocuments, type DocumentsResponse } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { Badge, Button, Card, Eyebrow } from "@/components/ui";
import { ErrorPanel, LoadingPanel } from "@/components/StatePanels";

export default function UploadPage() {
  const [result, setResult] = useState<DocumentsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handle = async (files: FileList | File[]) => {
    const arr = Array.from(files);
    if (!arr.length) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await uploadDocuments(arr));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative overflow-hidden">
      <div className="container-x relative py-12">
      <div className="max-w-2xl">
        <Eyebrow>Documents · the front door</Eyebrow>
        <h1 className="mt-2 font-display text-4xl font-bold tracking-tight text-ink">
          Upload your trade documents.
        </h1>
        <p className="mt-3 text-muted">
          We extract the parameters your models need and audit the set for completeness, purchase
          orders, commercial invoices, bills of lading, customs paperwork, supplier financials. You
          confirm every extracted value before anything runs.
        </p>
      </div>

      {/* Dropzone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handle(e.dataTransfer.files);
        }}
        className={`mt-8 rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
          dragging ? "border-brand bg-brand/[0.04]" : "border-rule bg-surface"
        }`}
      >
        <p className="font-display text-lg text-ink">Drag documents here</p>
        <p className="mt-1 text-sm text-muted">PDF, CSV, or text · analyzed locally by the engine</p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <Button onClick={() => inputRef.current?.click()}>Choose files</Button>
          <Button variant="outline" onClick={() => sampleUpload(handle)}>
            Use a sample invoice
          </Button>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.csv,.txt,.tsv"
          className="hidden"
          onChange={(e) => e.target.files && handle(e.target.files)}
        />
      </div>

      <div className="mt-8">
        {loading && <LoadingPanel title="Reading documents" detail="Extracting fields and auditing completeness." />}
        {error && !loading && <ErrorPanel error={error} />}
        {result && !loading && <Results result={result} />}
      </div>
      </div>
    </div>
  );
}

function Results({ result }: { result: DocumentsResponse }) {
  const cov = result.coverage;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      {/* Left: checklist */}
      <div>
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-bold text-ink">Completeness</h2>
          <span className="font-mono text-sm tabular-nums text-muted">
            {cov.required_present}/{cov.required_total} required documents
          </span>
        </div>
        <div className="mt-3 space-y-2">
          {result.checklist.map((c) => (
            <div
              key={c.id}
              className="flex items-start gap-3 rounded-lg border border-rule bg-surface p-3.5"
            >
              <span
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[0.7rem] ${
                  c.present
                    ? "bg-brand text-white"
                    : c.status === "missing"
                    ? "bg-amber/15 text-amber"
                    : "bg-rule text-muted"
                }`}
              >
                {c.present ? "✓" : c.status === "missing" ? "!" : "·"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-ink">{c.name}</span>
                  {!c.present && c.status === "missing" && <Badge tone="ochre">Required</Badge>}
                  {!c.present && c.status === "optional" && <Badge tone="muted">Optional</Badge>}
                </div>
                <p className="mt-0.5 text-xs text-muted">{c.present ? c.description : c.impact || c.description}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-5">
          <Button href="/start">Continue to industry selection →</Button>
        </div>
      </div>

      {/* Right: extracted + signals */}
      <div className="space-y-6">
        <Card className="p-5">
          <Eyebrow>Extracted documents</Eyebrow>
          <div className="mt-3 space-y-3">
            {(result.documents || []).map((d, i) => (
              <div key={i} className="border-b border-rule pb-3 last:border-0">
                <div className="flex items-center justify-between">
                  <span className="truncate text-sm font-medium text-ink">{d.filename}</span>
                  <Badge tone={d.extraction === "ai" ? "bordeaux" : "muted"}>
                    {titleCase(d.doc_type)}
                  </Badge>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[0.68rem] text-muted tnum">
                  {Object.entries(d.fields)
                    .filter(([, v]) => v !== null && v !== undefined && v !== "" && typeof v !== "object")
                    .slice(0, 4)
                    .map(([k, v]) => (
                      <span key={k}>
                        {k}: <span className="text-ink">{String(v)}</span>
                      </span>
                    ))}
                </div>
                {d.note && <p className="mt-1 text-[0.68rem] text-amber">{d.note}</p>}
              </div>
            ))}
          </div>
        </Card>

        {result.signals && result.signals.signals.length > 0 && (
          <Card className="p-5">
            <Eyebrow>Signals</Eyebrow>
            <div className="mt-3 space-y-2">
              {result.signals.signals.map((s, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg bg-raised p-2.5">
                  <Badge tone={s.severity === "critical" ? "ochre" : "muted"}>{s.type}</Badge>
                  <p className="text-xs text-ink/80">{s.message}</p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[0.66rem] text-muted">{result.signals.disclaimer}</p>
          </Card>
        )}
      </div>
    </div>
  );
}

// A realistic pre-filled example, one click away.
async function sampleUpload(handle: (f: File[]) => void) {
  const invoice = new File(
    [
      "COMMERCIAL INVOICE\nInvoice No: 88213\nSeller: Jiangsu Machine Works (China)\nBill To: Acme Industrial Distribution\nDescription: CNC hydraulic press units\nQuantity: 40\nUnit price: $105,000\nTotal: $4,200,000\nCountry of origin: China\nHS Code: 8462.99\n",
    ],
    "commercial_invoice.txt",
    { type: "text/plain" }
  );
  const bol = new File(
    [
      "BILL OF LADING\nShipper: Jiangsu Machine Works\nConsignee: Acme Industrial\nVessel: MV Orient Star\nPort of Loading: Shanghai\nPort of Discharge: Long Beach\nShipped: 2026-03-02  Arrived: 2026-04-19\n",
    ],
    "bill_of_lading.txt",
    { type: "text/plain" }
  );
  handle([invoice, bol]);
}
