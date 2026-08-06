import type { Question } from "./api";

/**
 * Turn extracted document fields into entity-table rows.
 *
 * A large operator will not retype a vendor book that already exists in their
 * purchase orders, so the tables have to be fillable from the documents. The
 * mapping is deliberately conservative: it fills the columns a document can
 * actually evidence and leaves the rest at the pack default, because a
 * confidently wrong lead time is worse than an obviously missing one.
 *
 * Everything produced here lands in an editable table and is labelled as coming
 * from documents, so the operator confirms rather than trusts.
 */

/** Entity column name -> extraction fields that can fill it, best first. */
const SOURCES: Record<string, string[]> = {
  name: ["supplier_name"],
  vendor: ["supplier_name"],
  supplier: ["supplier_name"],
  provider: ["supplier_name"],
  country: ["country"],
  origin: ["country"],
  annual_spend: ["total_value_usd"],
  annual_import_value: ["total_value_usd"],
  annual_cost: ["total_value_usd"],
  lead_time_days: ["lead_time_days"],
  hs_chapter: ["hs_code"],
};

/**
 * Money the operator pays out. This gate is the whole safety of the feature.
 *
 * Every document type the extractor understands is procurement paperwork: a
 * purchase order, an invoice, a customs entry. Those evidence a counterparty
 * you BUY from and nothing else. Matching on column names alone would happily
 * turn a supplier invoice into a wealth-management advisor holding $968,200 of
 * client AUM, or a clinical trial funded by a bearings manufacturer, because
 * "name plus an amount" fits those shapes too.
 *
 * So a table is fillable only if it records what you spend. Revenue-side
 * tables (clients, relationships, AUM, trial value) are never inferred from a
 * purchase order, and the panel says why.
 */
const SPEND_COLUMNS = new Set(["annual_spend", "annual_import_value", "annual_cost"]);

export interface DocRow {
  filename: string;
  doc_type: string;
  confidence: number;
  fields: Record<string, any>;
}

export interface PrefillResult {
  /** question id -> rows we can offer for that table */
  rows: Record<string, Record<string, any>[]>;
  /** question id -> why nothing was produced, when nothing was */
  skipped: Record<string, string>;
  supplierCount: number;
  documentCount: number;
}

function num(v: any): number | null {
  const n = typeof v === "string" ? parseFloat(v.replace(/[^0-9.\-]/g, "")) : v;
  return typeof n === "number" && isFinite(n) ? n : null;
}

/** Group documents by the counterparty they name. One party, one row. */
function groupBySupplier(docs: DocRow[]) {
  const groups = new Map<string, Record<string, any>[]>();
  for (const d of docs) {
    const name = String(d.fields?.supplier_name || "").trim();
    if (!name) continue;
    const key = name.toLowerCase();
    groups.set(key, [...(groups.get(key) || []), d.fields]);
  }
  return groups;
}

export function buildPrefill(questions: Question[], docs: DocRow[]): PrefillResult {
  const entityQs = questions.filter((q) => q.type === "entity_list" && q.fields?.length);
  const groups = groupBySupplier(docs);
  const rows: Record<string, Record<string, any>[]> = {};
  const skipped: Record<string, string> = {};

  for (const q of entityQs) {
    const fields = q.fields || [];
    // A table is fillable only if documents can evidence its identifying column.
    const idField = fields.find((f) => SOURCES[f.name]?.includes("supplier_name"));
    if (!idField) {
      skipped[q.id] = "these documents do not describe this";
      continue;
    }
    if (!fields.some((f) => SPEND_COLUMNS.has(f.name))) {
      skipped[q.id] = "purchase documents evidence what you buy, not this";
      continue;
    }
    if (groups.size === 0) {
      skipped[q.id] = "no counterparty named in these documents";
      continue;
    }

    const built: Record<string, any>[] = [];
    groups.forEach((entries, key) => {
      const row: Record<string, any> = {};
      let evidenced = 0;

      for (const f of fields) {
        const sources = SOURCES[f.name];
        if (!sources) continue;
        for (const src of sources) {
          const values = entries.map((e) => e?.[src]).filter((v) => v !== null && v !== undefined && v !== "");
          if (!values.length) continue;

          if (src === "total_value_usd") {
            // Documents are individual orders, so the book value is their sum,
            // but one shipment usually arrives as several documents: a PO, its
            // invoice and the customs entry all carry the same figure. Summing
            // those would report spend at two or three times the truth, which
            // is the kind of error a buyer spots immediately. Identical values
            // from one counterparty are treated as one transaction.
            const seen = new Set<number>();
            let total = 0;
            for (const v of values.map(num)) {
              if (v === null || v <= 0) continue;
              const key = Math.round(v * 100);
              if (seen.has(key)) continue;
              seen.add(key);
              total += v;
            }
            if (total > 0) { row[f.name] = Math.round(total); evidenced++; }
          } else if (src === "lead_time_days") {
            const ns = values.map(num).filter((n): n is number => n !== null);
            if (ns.length) { row[f.name] = Math.round(Math.max(...ns)); evidenced++; }
          } else if (src === "hs_code") {
            const code = String(values[0]).replace(/\D/g, "").slice(0, 4);
            if (code.length === 4) { row[f.name] = code; evidenced++; }
          } else {
            row[f.name] = String(values[0]); evidenced++;
          }
          break;
        }
      }

      // Name the row after whatever actually identifies it. A supplier name is
      // right for a vendor table and wrong for an import line, where the
      // classification and origin are what distinguish one line from another.
      if (row.hs_chapter) {
        const origin = row.origin || row.country || entries[0]?.country;
        row[idField.name] = origin ? `HS ${row.hs_chapter} from ${origin}` : `HS ${row.hs_chapter}`;
      } else if (!row[idField.name]) {
        row[idField.name] = entries[0]?.supplier_name || key;
      }
      // One column alone is a name with no numbers behind it, which is noise.
      if (evidenced >= 2) built.push(row);
    });

    if (built.length) rows[q.id] = built;
    else skipped[q.id] = "documents named a counterparty but carried no usable figures";
  }

  return {
    rows,
    skipped,
    supplierCount: groups.size,
    documentCount: docs.length,
  };
}

/**
 * Fill a table's blanks so no row is half-empty, without inventing risk.
 *
 * The rule that matters is the boolean one. Copying the first sample row would
 * mark every extracted vendor sole-source, because the pack's first example
 * vendor happens to be, and nothing in a purchase order says otherwise. That
 * one inherited flag roughly doubles derived sole-source exposure and inflates
 * the operator's number on evidence that does not exist. An unevidenced flag
 * is therefore false, and the operator ticks the ones that are true.
 *
 * Numbers fall back to the median of the pack's own examples rather than
 * whichever row happened to be first, so an unevidenced column lands on a
 * typical value instead of an arbitrary one.
 */
export function withDefaults(
  row: Record<string, any>,
  fields: { name: string; type: string }[],
  samples: Record<string, any>[] | undefined
): Record<string, any> {
  const out: Record<string, any> = {};
  const rows = samples || [];
  for (const f of fields) {
    if (row[f.name] !== undefined) {
      out[f.name] = row[f.name];
      continue;
    }
    if (f.type === "bool") {
      out[f.name] = false;
      continue;
    }
    const vals = rows.map((s) => s?.[f.name]).filter((v) => v !== undefined && v !== null);
    if (!vals.length) {
      out[f.name] = f.type === "text" ? "" : 0;
      continue;
    }
    if (f.type === "text" || f.type === "choice") {
      out[f.name] = vals[0];
    } else {
      const ns = vals.map(num).filter((n): n is number => n !== null).sort((a, b) => a - b);
      out[f.name] = ns.length ? ns[Math.floor(ns.length / 2)] : 0;
    }
  }
  return out;
}
