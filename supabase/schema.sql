-- Avenoir v3 schema.
--
-- Apply it with `python supabase/apply.py`, which also round-trips the store
-- against the real project afterwards. Pasting it into the SQL editor
-- (Dashboard > SQL Editor > New query) works too; follow that with
-- `python supabase/apply.py --verify`, because tables existing proves nothing
-- about their columns agreeing with the code that reads them.
--
-- Safe to run more than once.
--
-- A note on what row-level security is actually doing here, because it is easy
-- to overstate. The backend authenticates with the SERVICE ROLE key, which
-- bypasses RLS by design, so today the enforcing check is `_auth()` in
-- backend/api_org.py. These policies matter for two other reasons: they are the
-- second layer if the application check is ever wrong, and they are what makes
-- it safe for the browser to talk to Supabase directly with the anon key later.
-- Defence in depth on tenant isolation is worth the duplication.

-- ---------------------------------------------------------------------------
-- Organisations
-- ---------------------------------------------------------------------------
create table if not exists organizations (
  id                 text primary key,
  name               text not null,
  industry_pack      text not null,
  reference_revenue  double precision not null default 0,
  created_at         timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Tokens. The plaintext is never stored, only a SHA-256 hash, so nothing here
-- can be replayed against us if this table leaks.
-- ---------------------------------------------------------------------------
create table if not exists tokens (
  id               text primary key,
  organization_id  text not null references organizations(id) on delete cascade,
  token_hash       text not null unique,
  label            text not null default '',
  scopes           text[] not null default array['read','ingest'],
  created_at       timestamptz not null default now(),
  last_used_at     timestamptz,
  revoked_at       timestamptz
);
create index if not exists tokens_hash_idx on tokens(token_hash) where revoked_at is null;
create index if not exists tokens_org_idx  on tokens(organization_id);

-- ---------------------------------------------------------------------------
-- Snapshots. Append-only: there is no update path in the application and none
-- is granted here. A correction arrives as a new dated row, which is what makes
-- a past assessment reproducible and "why did this change" a diff.
-- ---------------------------------------------------------------------------
create table if not exists snapshots (
  snapshot_id      text primary key,
  organization_id  text not null references organizations(id) on delete cascade,
  taken_at         timestamptz,
  stored_at        timestamptz not null default now(),
  source           text not null default '',
  window_start     date,
  window_end       date,
  record_counts    jsonb not null default '{}'::jsonb,
  completeness     jsonb not null default '{}'::jsonb,
  payload          jsonb not null
);
create index if not exists snapshots_org_stored_idx
  on snapshots(organization_id, stored_at desc);

-- ---------------------------------------------------------------------------
-- Audit log. Customer-visible: an audit log only we can read is a promise
-- rather than a control.
-- ---------------------------------------------------------------------------
create table if not exists audit_log (
  id               text primary key,
  organization_id  text not null references organizations(id) on delete cascade,
  at               timestamptz not null default now(),
  action           text not null,
  component        text not null default '',
  detail           text not null default '',
  record_counts    jsonb not null default '{}'::jsonb,
  token_id         text not null default ''
);
create index if not exists audit_org_at_idx on audit_log(organization_id, at desc);

-- ---------------------------------------------------------------------------
-- Decisions presented, for the eventual predicted-versus-realised record.
-- Worth capturing from the first decision even though the payoff is a year away:
-- a prediction cannot be scored honestly unless it was recorded when it was made.
-- ---------------------------------------------------------------------------
create table if not exists decisions (
  id                 text primary key,
  organization_id    text not null references organizations(id) on delete cascade,
  decision_id        text not null default '',
  title              text not null default '',
  kind               text not null default '',
  presented_at       timestamptz not null default now(),
  snapshot_id        text,
  status             text not null default 'presented',
  predicted_npv      double precision,
  predicted_npv_p10  double precision,
  predicted_npv_p90  double precision,
  prob_beneficial    double precision,
  cost_upfront       double precision default 0,
  cost_annual        double precision default 0,
  p95_reduction      double precision,
  p99_reduction      double precision,
  decided_at         timestamptz,
  realised_value     double precision,
  realised_at        timestamptz,
  notes              text not null default ''
);
create index if not exists decisions_org_idx on decisions(organization_id, presented_at desc);

-- ---------------------------------------------------------------------------
-- Row-level security. Enabled on every table, with no permissive default:
-- without a matching policy the anon key sees nothing at all, which is the
-- correct failure mode.
-- ---------------------------------------------------------------------------
alter table organizations enable row level security;
alter table tokens        enable row level security;
alter table snapshots     enable row level security;
alter table audit_log     enable row level security;
alter table decisions     enable row level security;

-- The organisation a request belongs to, taken from the JWT rather than from
-- anything the caller can set in a query. `request.jwt.claims` is set by
-- Supabase from the verified token, so this cannot be spoofed by the client.
create or replace function auth_org_id() returns text
language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claims', true)::json ->> 'org_id', ''),
    ''
  );
$$;

do $$
declare t text;
begin
  foreach t in array array['organizations','snapshots','audit_log','decisions'] loop
    execute format('drop policy if exists %I on %I', t || '_isolation', t);
  end loop;
end $$;

create policy organizations_isolation on organizations
  for select using (id = auth_org_id());

create policy snapshots_isolation on snapshots
  for select using (organization_id = auth_org_id());

create policy audit_log_isolation on audit_log
  for select using (organization_id = auth_org_id());

create policy decisions_isolation on decisions
  for select using (organization_id = auth_org_id());

-- Tokens deliberately get NO select policy. Even scoped to one organisation,
-- there is no reason for a browser to read token rows, and the hash is the one
-- thing in the schema worth never returning.

-- ---------------------------------------------------------------------------
-- Deletion. `on delete cascade` above means removing an organisation removes
-- its tokens, snapshots, audit rows and decisions. Deletion is deletion, not a
-- flag, which is the first thing a technical evaluator checks.
-- ---------------------------------------------------------------------------
