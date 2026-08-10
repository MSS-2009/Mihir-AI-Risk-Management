"""Turn extracted documents into rows for the industry pack's own tables.

This runs on the server because the pack lives here: the tables, their columns
and their published defaults are all one import away, and the alternative was a
pile of column-name guessing in the browser.

Three rules decide whether a row is honest, and all three came from watching it
get them wrong:

  One shipment, several documents. A purchase order, its invoice and the
  customs entry all carry the same figure. Summing them reported a $1.18M order
  as $2.37M of spend, so identical values from one entity count once.

  Stocks are not flows. Two custodial statements for one client are that
  client's money counted twice if you add them, and the same is true of record
  counts and annual contract values. Those take the latest or largest value
  rather than a sum; only genuinely transactional amounts sum.

  Never invent a risk flag. Filling blanks from the pack's first example row
  marked every extracted vendor sole-source, because the first example vendor
  is, which roughly doubled derived exposure on no evidence at all. A column no
  document speaks to falls back to the pack's own published default, and is
  reported as unevidenced so the operator checks it.
"""
from __future__ import annotations

from collections import Counter

from .profiles import ANY, FIRST, MAX, SUM, get_profile


def _num(x):
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(str(x).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None
    return v if v == v else None  # drop NaN


def _truthy(x) -> bool:
    if isinstance(x, bool):
        return x
    return str(x).strip().lower() in {"true", "yes", "y", "1"}


def _combine(values: list, how: str):
    """Fold the values several documents gave for one column."""
    if how == ANY:
        return any(_truthy(v) for v in values if v is not None)
    clean = [v for v in values if v is not None and v != ""]
    if not clean:
        return None
    if how == FIRST:
        return str(clean[0])
    nums = [n for n in (_num(v) for v in clean) if n is not None and n > 0]
    if not nums:
        return None
    if how == MAX:
        return max(nums)
    # SUM, with identical values treated as one transaction described twice.
    seen, total = set(), 0.0
    for n in nums:
        k = round(n, 2)
        if k in seen:
            continue
        seen.add(k)
        total += n
    return total


def _median(vals: list[float]) -> float:
    ordered = sorted(vals)
    return ordered[len(ordered) // 2]


def _pack_default(samples: list[dict], column: str, kind: str, scale: float = 1.0):
    """The pack's own published stance on a column no document evidenced.

    Booleans take the majority of the pack's examples rather than False, because
    forcing False is only neutral for flags that raise risk. `has_fallback` and
    `has_successor` lower it, so defaulting those to False would quietly make
    every uploaded book look worse than the pack claims a typical one is.

    Counts are scaled to the size of the row they land in. A raw pack median put
    240 subjects enrolled into a trial with a target of 210, which is not merely
    wrong but impossible, and it read as zero enrollment risk on the trial that
    had the least evidence behind it. Scaling by the row's own evidenced size
    keeps an unevidenced count in proportion to the rest of its row.
    """
    vals = [s.get(column) for s in samples if s.get(column) is not None]
    # Free text is left blank, never borrowed. The pack's example sponsor is
    # "Meridian Bio", and copying that into an operator's real trials put an
    # invented company name in their book and collapsed sponsor concentration
    # to a single counterparty. A categorical column is different: its default
    # is one of a fixed set the pack publishes, not a proper noun.
    if kind == "text":
        return ""
    if kind == "bool":
        return Counter([v for v in vals if isinstance(v, bool)]).most_common(1)[0][0] if any(
            isinstance(v, bool) for v in vals) else False
    if not vals:
        return "" if kind == "choice" else 0
    if isinstance(vals[0], (int, float)):
        base = _median([float(v) for v in vals])
        # Shares and rates are already dimensionless, so they must not scale.
        if 0 < base <= 1 and all(0 <= float(v) <= 1 for v in vals):
            return base
        out = base * scale
        return round(out) if float(base).is_integer() else out
    return vals[0]


def _row_scale(row: dict, samples: list[dict], columns: dict) -> float:
    """How big this row is against the pack's typical one.

    Uses the largest evidenced numeric column the pack also publishes, which in
    practice is the money column: contract value, spend, AUM. Falls back to 1.0
    when nothing comparable was evidenced.
    """
    best = 1.0
    for column in columns:
        v = _num(row.get(column))
        if v is None or v <= 1:
            continue
        vals = [float(s[column]) for s in samples
                if isinstance(s.get(column), (int, float)) and not isinstance(s.get(column), bool)]
        vals = [x for x in vals if x > 1]
        if not vals:
            continue
        base = _median(vals)
        if base > 0:
            return max(0.1, min(10.0, v / base))
    return best


def build_prefill(industry: str, documents: list[dict], pack) -> dict:
    """Rows for each entity table the uploaded documents can actually evidence.

    Returns {question_id: {rows, unevidenced, label}} plus a note per table the
    documents could not speak to, so the panel can say why rather than silently
    showing nothing.
    """
    profile = get_profile(industry)
    # Every row of every table in every document. A sponsor revenue schedule is
    # six sponsors, not one, and reading only the first was why real operating
    # reports produced nothing at all.
    fields: list[dict] = []
    for d in documents:
        recs = d.get("records")
        fields.extend(r for r in recs if isinstance(r, dict)) if recs else fields.append(d.get("fields") or {})
    questions = {q.id: q for q in pack.questions if q.type == "entity_list"}

    filled: dict[str, dict] = {}
    skipped: dict[str, str] = {}

    for table in profile.tables:
        q = questions.get(table.question)
        if q is None:
            continue

        # Reports group the same business differently: one lists studies, another
        # lists the sponsors paying for them. Try the table's own key first and
        # fall back, so a schedule that never names a study still populates.
        groups: dict[str, list[dict]] = {}
        for key_field in (table.key, *table.alt_keys):
            for f in fields:
                key = f.get(key_field)
                if key is None or str(key).strip() == "":
                    continue
                groups.setdefault(str(key).strip(), []).append(f)
            if groups:
                break

        if not groups:
            skipped[table.question] = "nothing in these documents identifies one of these"
            continue

        samples = q.default if isinstance(q.default, list) else []
        schema = {f["name"]: f for f in (q.fields or [])}
        rows, unevidenced_cols = [], set()

        for key, entries in groups.items():
            # A row has to be evidenced by more than its own name.
            if not any(entries_have(entries, n) for n in table.needs):
                continue

            row, seen_cols = {}, set()
            for column, (source, how) in table.columns.items():
                if column not in schema:
                    continue
                value = _combine([e.get(source) for e in entries], how)
                if value is None or (how == ANY and value is False
                                     and not entries_have(entries, source)):
                    continue
                row[column] = value
                seen_cols.add(column)

            # Name the row when the key is not itself a name.
            name_col = next((c for c in ("name", "part") if c in schema), None)
            if name_col and not row.get(name_col):
                parts = [str(entries[0].get(f)) for f in table.label_from
                         if entries[0].get(f)]
                row[name_col] = " from ".join(parts) if parts else key
                seen_cols.add(name_col)

            scale = _row_scale(row, samples, table.columns)
            for f in q.fields or []:
                if f["name"] not in row:
                    row[f["name"]] = _pack_default(samples, f["name"], f["type"], scale)
                    unevidenced_cols.add(f["label"])
            rows.append(row)

        if rows:
            filled[table.question] = {
                "label": q.label,
                "rows": rows,
                "unevidenced": sorted(unevidenced_cols),
            }
        else:
            skipped[table.question] = "named in these documents but with no usable figures"

    for qid, q in questions.items():
        if qid not in filled and qid not in skipped:
            skipped[qid] = "these documents do not describe this"

    return {
        "prefill": filled,
        "skipped": skipped,
        "profile": profile.role,
        "note": (
            "Extraction is best-effort. Columns no document evidenced keep this "
            "industry's published default and are listed so you can check them."
        ),
    }


def entries_have(entries: list[dict], field: str) -> bool:
    return any(e.get(field) not in (None, "") for e in entries)
