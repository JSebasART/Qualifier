# Plan 4 — technical design (generic CRM export layer)

*2026-11-14. Implementation design for [`04-exportacion-a-crm.md`](04-exportacion-a-crm.md) under the owner
decisions of 2026-11-14 ([`04-PLAN-STATE.md`](04-PLAN-STATE.md)): **generic layer only** (CRM-1, CRM-2, CRM-3, the
parts of CRM-4 the generic layer needs, CRM-8). No native connectors, no mapping editor, no CRM-9/CRM-10.
Audience: implementation agents who have not read the plan. Goal: a **presentable demo** where every flow works
end to end; not production hardening. Where this file changes the plan it says so (**⚠ deviation**). Schema keys
English, UI Spanish, migrations append-only. Never open `qualifier-secrets.env.txt`. Never point a local process
at a Supabase project.*

Conventions (same as `02-design.md` / `03-design.md`): "admin" = `require_privacy_admin(tenant)` (tenant_admin of
the tenant or superadmin, **MFA gate included**). "staff" = `app_current_role() in (superadmin, tenant_admin,
underwriter, agent)`. "service-only" = `revoke all on function … from public, anon, authenticated; grant execute …
to service_role`. Every new SECURITY DEFINER function is `language plpgsql security definer set search_path =
public` (pure helpers: `set search_path = ''`), raises stable lower-case codes (`P0002` not found / other tenant,
`42501` not allowed, `22023` invalid), and every new table and function gets an explicit `revoke … from public,
anon` (Supabase **and** the replay's default privileges hand everything to `anon`). Random tokens use core
`gen_random_uuid()` and hashes core `sha256()` (pgcrypto lives in `extensions` on Supabase; see
`intake_new_token()` in `20261028000100`).

---

## 1. Decisions

| # | Open point (plan §) | Decision | Why |
| --- | --- | --- | --- |
| D1 | Destination kinds (§6) | **⚠** `kind in ('webhook','api_pull','file_export')` only. `hubspot/dynamics/odoo/salesforce` are catalog cards "vía webhook/API" with recipes, not kinds. | Owner: no native connectors. Adding a kind later is an `alter … check`. |
| D2 | Mapping editor, `integration_mapping_versions`, `mapping_version_id` (§6, §7) | **⚠ Dropped.** Webhooks and the API send the canonical model `tramiq.crm.v1`; file templates are fixed column maps in web TS (§6.6). | Owner decision. The iPaaS (Zapier/Make/n8n/Power Automate) does the mapping. |
| D3 | `CrmAdapter` interface (§7) | **⚠ Reduced** to `WebhookAdapter.deliver(req) → DeliveryResult` in `src/integrations/webhook.ts`; no `verify/describe/provision`. | Only one adapter exists; the seam stays for a future connector. |
| D4 | Where the work happens | **The database decides, the orchestrator only moves bytes.** Dispatch (event → deliveries), eligibility, payload, masking, backoff, circuit breaker, link and `data_transfers` writes are SQL functions. The orchestrator: claim → payload → sign → POST (SSRF-guarded) → finish. | One place to attack in pgTAP; replayable; the orchestrator holds no rules. `integration_payload()` is the **only** builder of what leaves. |
| D5 | Deliveries per destination+entity, "coalesced" (§6, §7) | One live row per `(destination_id, entity, entity_id)` (current state) + an append-only **`integration_delivery_attempts`** log (what the screen shows). | The plan's unique row cannot also be a log. |
| D6 | Outbox mechanics | Same pattern as `intake_notifications`: DB rows + `claim_*`/`finish_*` with `FOR UPDATE SKIP LOCKED` and a lease (`claim_token`, `lease_until` 5 min). pg-boss only schedules (`integration.dispatch`, `integration.deliver` every minute, `integration.reconcile` nightly). | No per-delivery pg-boss jobs to reconcile with DB state; backoff lives in `next_attempt_at`. |
| D7 | Order and idempotency (§2) | State sync: every send carries the **current** state; per-entity order is moot. `webhook-id = 'msg_' || delivery_id_without_dashes || '_' || left(payload_hash, 12)` — identical across retries of the same content, new for new content. Unchanged hash vs `integration_links.last_synced_hash` ⇒ not sent (`unchanged`) unless a manual resend (`force`). | Standard Webhooks dedupe by `webhook-id`. |
| D8 | Secrets (§6) | `secret_ref` + `secret_previous_ref` (+ `secret_previous_expires_at`, 24 h) on the destination; values in **Supabase Vault** when `vault.create_secret(text,text,text,uuid)` exists, else in `integration_private.secrets` (schema with no grant to any API role). Detection at call time, all Vault SQL is dynamic (`execute`). | Vault exists on dev/prod (conductor, 2026-11-14); PGlite and CI (plain PG 17) have none. Suites run the fallback path and assert the API roles cannot read either store. |
| D9 | Webhook secret format | Standard Webhooks: `whsec_` + base64 of 32 random bytes (from two `gen_random_uuid()` hex strings). Generated **in the DB**, returned **once** by `integration_rotate_secret()`, never readable again by `authenticated`. During the 24 h overlap the sender signs with **both** secrets (`webhook-signature: v1,<new> v1,<old>`), which is how "two valid secrets" works sender-side. | Spec-compatible; receivers with either secret verify. |
| D10 | `commercial_management` filter (§2) | **⚠ interpretation.** The purpose is seeded `requires_consent = false` ("Interés legítimo / contrato"). Eligible ⇔ purpose row active **and** (`requires_consent` ? `has_consent(c,'commercial_management')` : the latest `consent_records` decision for that purpose is not `refused`/`revoked`). A tenant who sets `requires_consent = true` gets strict consent. | Honest to Plan 2's legal-basis model; a refusal/revocation (opposition) always blocks. Flagged as Q1. |
| D11 | International (§2) | Destination `country` ≠ `privacy_settings.country` (default `SV`) ⇒ also `has_consent(c,'international_processing')`. | Plan 2 `LPD-12`. |
| D12 | Sensitivity cap (§6, §9) | Enforced in `integration_payload()` **and** at scope save: attributes with `client_attributes.sensitive` or category `health`/`biometric`, sensitive form fields (`form_schema.fields[].sensitive`), and condition `detail` texts never leave with `non_sensitive`. `sensitive_approved` only via `integration_approve_sensitive()` (superadmin, justification ≥ 20 chars, explicit attribute list); only listed sensitive keys pass. | DB, not screen. Condition details can name a health exclusion. |
| D13 | Never files or URLs (§2) | The payload builder never reads `documents`, Storage, or `extracted_data`; links are `links.tramiq_path` (**⚠** relative path `/clients/<id>`, not an absolute URL — the DB does not know the web origin). | Keeps the builder pure DB. Receivers prepend their Tramiq origin. |
| D14 | Score, narrative, signals (§9) | `scope.include_score` (default false) adds `{final_score, tier}` from the latest `scores` row; `ai_summary`, `rationale`, `rule_trace`, fraud signals never. Decision block (`decision, decided_at, conditions[{type,value}], reason_codes, sum_insured`) on by default (`scope.include_decision`), and for the API only with scope `read:decisions`; `case_decisions.note` never. | Plan §9. |
| D15 | Events (§5) | Catalog: `person.upserted, person.restricted, person.erased, consent.revoked, application.created, application.status_changed, application.decided, application.withdrawn` + `test.ping` (test sends only). Written by triggers **only when the tenant has a live webhook/api_pull destination** (`integration_events_enabled()`, partial index). Events hold ids and codes only. | Plan §5–6. |
| D16 | Propagation (§7.6, CRM-8) | Trigger-driven, **no Plan 2 wrapper replaced**: `clients.processing_state` changes carry `processing_state_dsr_id`; `consent_records` rows carry `dsr_id`; rectification is seen through `app.rectifying`. Dispatch turns `person.erased`/`consent.revoked` into `delete` and `person.restricted` into `restrict` deliveries **only for destinations holding a link**, with `due_on = add_business_days(privacy_local_date(), coalesce(privacy_settings.propagation_days,5), tenant, country)`. When the event has a `dsr_id`, one `dsr_propagations` row per such destination (`recipient_kind 'crm_destination'`); a delivered webhook completes it automatically (evidence text), api_pull/file_export ones stay for manual completion in the existing DSR screen. | `dsr_propagations.dsr_id` is NOT NULL, so revocations outside a DSR have the delivery's `due_on` as their only clock. |
| D17 | Plan 2 footprint/erasure hooks | All of `privacy_p3_*_{a,b,c}` are taken. Migration A **renames `privacy_p3_footprint_c` → `privacy_p3_footprint_c_base` and `privacy_p3_erase_c` → `privacy_p3_erase_c_base`** and creates new `privacy_p3_footprint_c`/`privacy_p3_erase_c` = `*_c_base(...) || privacy_p4_footprint(...)` / `|| privacy_p4_erase(...)`. The five Plan 2 wrappers are untouched. | Same late-binding trick Plan 3 used one level down; the wrappers resolve `privacy_p3_*_c` at call time. |
| D18 | `data_transfers` (§2) | One row per **disclosure**: each delivered webhook upsert, each person/application returned by `/api/v1`, each row of a file export (`recipient_kind 'crm_destination'`, `recipient_id = destination.id`, country, categories, `legal_basis = 'Gestión comercial — ' || purpose.legal_basis`, `consent_record_id` of the latest commercial grant if any, `reference` = `webhook:<webhook-id>` / `api:<key_prefix>` / `file:<export_id>`). Deletes, restricts and test pings are not disclosures. | Art. 8; already listed by the Plan 2 access report (footprint `data_transfers`). |
| D19 | API keys (§8.4) | `tq_live_` + 64 hex; only `sha256` hex stored + `key_prefix` (first 16 chars). **⚠** each key belongs to an `api_pull` destination (its scope, country and privacy rules apply). Scopes `read:persons, read:applications, read:decisions, read:events`. Web hashes the presented key; the DB derives tenant and destination from the hash in every `api_v1_*` call. | "Each response passes through `integration_payload()` with an `api_pull` destination" (plan §8.4). |
| D20 | `/events?after=` cursor | Cursor = `dispatch_seq`, assigned by the **serialized** dispatcher (`pg_try_advisory_xact_lock`), not the identity id. | An identity id becomes visible out of commit order; a consumer at 11 would miss 10. |
| D21 | XLSX (§8.4) | web has no spreadsheet dependency. **Dependency-free writer** `web/src/lib/xlsx.ts` (~150 lines): one sheet, inline strings, ZIP via `node:zlib` `deflateRawSync` + `zlib.crc32` (Node 22). Server route only. | No new package (the Windows lockfile trap in `CLAUDE.md`); SheetJS on npm is stale. Inline strings are never evaluated as formulas. |
| D22 | SSRF (§8.4) | Orchestrator resolves DNS (`dns.promises.lookup(host,{all:true,verbatim:true})`), rejects if **any** address is non-public, then connects with `https.request` and a `lookup` pinned to the checked address (no rebinding). https only, no userinfo, port 443 or ≥1024, **redirects never followed** (3xx = `validation`, "redirect_not_followed"). | Stricter than "reject redirects to private": following redirects buys nothing for webhooks. |
| D23 | Test receiver | **Built.** `POST /api/public/integrations/receiver/<destinationId>` in web: accepts only destinations with `config.test_receiver = true` whose `config.url` ends with that exact path, verifies the Standard Webhooks signature with the destination's secrets (service RPC, server-only), stores the last 20 receipts **masked**, answers `{"external_id":"rcv_<n>"}`. The URL is the public https origin of web, so it passes the SSRF guard **with no exception added**. | Demo end to end without an external service; SSRF rule untouched; a stranger can only make it record "firma inválida". |
| D24 | Retry/backoff (§7.3) | DB function `integration_backoff(attempt)`: 30 s, 2 m, 10 m, 30 m, 1 h, 3 h, 6 h, then 6 h; `dead` once `now() + delay > first_attempt_at + 24 h`. `Retry-After` (seconds or HTTP date) honored, clamped to [1 s, 6 h]. Circuit breaker: 5 consecutive `transient`/`rate_limited` outcomes on a destination ⇒ `circuit_open_until = now() + 10 min`; any success resets. | Plan §7 table. |
| D25 | Who exports files / initial sync | tenant_admin only (admin gate). | Disclosure decision; keeps one role in the attacker suite. |
| D26 | Reconciliation (§7.5) | Nightly: for every link of live webhook destinations (≤ 2000 per run) recompute the payload hash; differs ⇒ re-arm `upsert`; now ineligible ⇒ re-arm `restrict`/`delete` (see finish rules). Also prunes attempts > 30 d, dispatched events > 30 d. | Fixes lost events; demo-scale volumes. |
| D27 | Notice lists destinations (§2) | `integration_notice_recipients(tenant)` + `notice-generator.ts` adds them to «Destinatarios» and, when outside the country, to «Transferencias internacionales». The wizard tells the admin to publish a new notice version. | Plan 2's notice is versioned and published by a person; no auto-publish. |
| D28 | Out of scope | Native connectors, mapping editor, CRM-9, CRM-10, SFTP, application-level file templates (persons only), propagation of retention anonymizations (`privacy_anonymize_applications`), OAuth. | Owner decisions / presentation scope. |

---

## 2. Replay, CI and Vault

- PGlite replay (`…/scratchpad/db-replay/run.mjs`): pgcrypto, pg_trgm, unaccent; **no `vault`, no `vector`**. CI:
  plain PostgreSQL 17, same. Both run the fallback secret path (`integration_private.secrets`).
- `integration_vault_available()` = `to_regprocedure('vault.create_secret(text,text,text,uuid)') is not null and
  to_regclass('vault.decrypted_secrets') is not null`. Store: `execute 'select vault.create_secret($1,$2,$3)' into
  v_id using p_secret, p_name, 'tramiq integration secret'`. Read: `execute 'select decrypted_secret from
  vault.decrypted_secrets where id = $1' …`. Drop: `execute 'delete from vault.secrets where id = $1'`.
- Suites assert behaviour, not storage: `integration_rotate_secret()` returns a `whsec_` value once;
  `integration_delivery_secrets()` (service) returns it; tenant_admin gets `42501` on `secret_ref`, on
  `integration_private.secrets`, and (`has_function_privilege`) on every secret function. A guarded block
  `if integration_vault_available() then … end if` asserts nothing extra in replay/CI.
- No `CONCURRENTLY`, no pg_cron, no extension creation in either migration.

---

## 3. Database contract

Two migrations, each one transaction:

- **A** `db/supabase/migrations/20261114000000_integrations_core.sql` — CRM-1, CRM-2 data side, CRM-8, hooks.
- **B** `db/supabase/migrations/20261114000100_integrations_api_exports.sql` — CRM-3 (keys, `/api/v1` reads, events
  cursor), file export RPC.

### 3.1 Migration A — tables

```sql
create schema integration_private;
revoke all on schema integration_private from public, anon, authenticated, service_role;
create table integration_private.secrets (
  id uuid primary key default gen_random_uuid(), name text not null, secret text not null,
  created_at timestamptz not null default now());
revoke all on integration_private.secrets from public, anon, authenticated, service_role;

create table integration_destinations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  kind text not null check (kind in ('webhook','api_pull','file_export')),
  name text not null check (length(btrim(name)) between 2 and 80),
  status text not null default 'draft' check (status in ('draft','active','paused','error','disconnected')),
  status_reason text check (status_reason in ('auth_failed','endpoint_gone','url_not_allowed','disconnected_by_admin')),
  country char(2) not null default 'SV' check (country ~ '^[A-Z]{2}$'),
  config jsonb not null default '{}' check (jsonb_typeof(config) = 'object'),
    -- webhook {url, test_receiver:boolean} · file_export {template: hubspot|dynamics|odoo|salesforce|generic, format: csv|xlsx} · api_pull {}
  scope jsonb not null default '{}' check (jsonb_typeof(scope) = 'object'),   -- §3.3
  sensitivity_cap text not null default 'non_sensitive' check (sensitivity_cap in ('non_sensitive','sensitive_approved')),
  sensitive_approval jsonb,           -- {by, at, justification, attributes:[key]}
  dpa_attested_by uuid references auth.users (id) on delete set null, dpa_attested_at timestamptz,
  secret_ref uuid, secret_previous_ref uuid, secret_previous_expires_at timestamptz, secret_set_at timestamptz,
  consecutive_failures integer not null default 0, circuit_open_until timestamptz,
  activated_at timestamptz, disconnected_at timestamptz,
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (tenant_id, id),
  check (sensitivity_cap = 'non_sensitive' or sensitive_approval is not null));
create index integration_destinations_tenant on integration_destinations (tenant_id, created_at desc);
create index integration_destinations_live on integration_destinations (tenant_id)
  where status in ('active','paused','error');

create table integration_events (
  id bigint generated always as identity primary key,
  tenant_id uuid not null references tenants (id) on delete cascade,
  kind text not null check (kind in ('person.upserted','person.restricted','person.erased','consent.revoked',
    'application.created','application.status_changed','application.decided','application.withdrawn')),
  entity text not null check (entity in ('person','application')),
  entity_id uuid not null, client_id uuid,
  detail jsonb not null default '{}',     -- {dsr_id?, purpose?, from?, to?, rectification?:true}; ids and codes only
  occurred_at timestamptz not null default clock_timestamp(),
  dispatched_at timestamptz, dispatch_seq bigint unique);
create sequence integration_events_dispatch_seq;
create index integration_events_pending on integration_events (id) where dispatched_at is null;
create index integration_events_cursor on integration_events (tenant_id, dispatch_seq) where dispatch_seq is not null;

create table integration_deliveries (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null, destination_id uuid not null,
  entity text not null check (entity in ('person','application','test')),
  entity_id uuid not null, client_id uuid,
  action text not null default 'upsert' check (action in ('upsert','delete','restrict')),
  reason text check (reason in ('erasure','consent_revoked','restricted','rectification','disconnect','no_longer_eligible')),
  event_kind text not null,               -- the webhook `type`: last event that armed it, or 'test.ping'
  status text not null default 'pending' check (status in ('pending','in_flight','delivered','failed','dead','skipped')),
  skip_reason text,
  force boolean not null default false, rearm boolean not null default false,
  attempts integer not null default 0, first_attempt_at timestamptz,
  next_attempt_at timestamptz not null default now(),
  claim_token uuid, lease_until timestamptz,
  last_status_code integer, last_error text check (length(last_error) <= 300),
  payload_hash text, payload_masked jsonb, categories text[], webhook_id text,
  due_on date, dsr_id uuid, dsr_propagation_id uuid references dsr_propagations (id) on delete set null,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  delivered_at timestamptz,
  unique (destination_id, entity, entity_id),
  constraint integration_deliveries_destination_same_tenant foreign key (tenant_id, destination_id)
    references integration_destinations (tenant_id, id) on delete cascade,
  constraint integration_deliveries_client_same_tenant foreign key (tenant_id, client_id)
    references clients (tenant_id, id) on delete cascade);
create index integration_deliveries_due on integration_deliveries (next_attempt_at) where status in ('pending','failed');
create index integration_deliveries_lease on integration_deliveries (lease_until) where status = 'in_flight';
create index integration_deliveries_dest on integration_deliveries (destination_id, status, updated_at desc);
create index integration_deliveries_client on integration_deliveries (tenant_id, client_id);
create index integration_deliveries_deadline on integration_deliveries (due_on)
  where due_on is not null and status not in ('delivered','skipped');

create table integration_delivery_attempts (
  id bigint generated always as identity primary key,
  tenant_id uuid not null, destination_id uuid not null,
  delivery_id uuid not null references integration_deliveries (id) on delete cascade,
  client_id uuid, entity text not null, entity_id uuid not null, action text not null, event_type text not null,
  attempt integer not null,
  outcome text not null check (outcome in ('delivered','transient','rate_limited','auth','validation','blocked','skipped','unchanged')),
  http_status integer, duration_ms integer, error text check (length(error) <= 300),
  webhook_id text, payload_masked jsonb,
  attempted_at timestamptz not null default clock_timestamp());
create index integration_attempts_dest on integration_delivery_attempts (destination_id, attempted_at desc);
create index integration_attempts_delivery on integration_delivery_attempts (delivery_id, attempted_at desc);
create index integration_attempts_client on integration_delivery_attempts (tenant_id, client_id);

create table integration_links (
  tenant_id uuid not null, destination_id uuid not null,
  entity text not null check (entity in ('person','application')),
  entity_id uuid not null, client_id uuid not null,
  via text not null check (via in ('webhook','api','file')),
  external_id text check (length(external_id) <= 200),
  external_url text check (external_url ~ '^https://' and length(external_url) <= 500),
  last_synced_hash text, last_synced_at timestamptz not null default now(), restricted_at timestamptz,
  primary key (destination_id, entity, entity_id),
  constraint integration_links_destination_same_tenant foreign key (tenant_id, destination_id)
    references integration_destinations (tenant_id, id) on delete cascade,
  constraint integration_links_client_same_tenant foreign key (tenant_id, client_id)
    references clients (tenant_id, id) on delete cascade);
create index integration_links_client on integration_links (tenant_id, client_id);

create table integration_test_receipts (
  id bigint generated always as identity primary key,
  tenant_id uuid not null, destination_id uuid not null,
  client_id uuid, webhook_id text check (length(webhook_id) <= 120), event_type text check (length(event_type) <= 60),
  signature_valid boolean not null,
  failure text check (failure in ('missing_headers','stale_timestamp','invalid_signature','bad_json')),
  body_masked jsonb, external_id text, received_at timestamptz not null default clock_timestamp(),
  constraint integration_receipts_destination_same_tenant foreign key (tenant_id, destination_id)
    references integration_destinations (tenant_id, id) on delete cascade);
create index integration_receipts_dest on integration_test_receipts (destination_id, received_at desc);
```

**RLS and grants (A).** RLS enabled on all six public tables. One policy shape, `select to authenticated using
((tenant_id = current_tenant_id() and app_current_role() = 'tenant_admin') or app_current_role() = 'superadmin')`, on
`integration_destinations`, `integration_deliveries`, `integration_delivery_attempts`, `integration_links`,
`integration_test_receipts`. `integration_events`: **no policy, no grant** to authenticated. `revoke all on
<all six> from public, anon, authenticated`; `grant select, insert, update, delete … to service_role`.
`integration_destinations` gets a **column grant only**: `grant select (id, tenant_id, kind, name, status,
status_reason, country, config, scope, sensitivity_cap, sensitive_approval, dpa_attested_by, dpa_attested_at,
secret_set_at, secret_previous_expires_at, consecutive_failures, circuit_open_until, activated_at, disconnected_at,
created_by, created_at, updated_at) on integration_destinations to authenticated` (no `secret_ref`,
`secret_previous_ref`; web must list columns, `select *` fails). The other four: `grant select … to
authenticated`. No write grant to `authenticated` anywhere. `updated_at` triggers reuse the existing
`set_updated_at()`-style trigger function (DB-A: use whichever the repo already has, e.g. the one behind
`clients_set_updated_at`).

**`personal_data_stores` rows (A)** — `(table, description, subject_link, categories, holds_sensitive, access,
access_note, erase, retention_class)`:

| table | subject_link | categories | sens | access | erase | class | description / note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `integration_events` | `integration_events.client_id` | `{technical}` | f | include | retain_legal | audit_log | Eventos de integración (solo identificadores); se depuran a los 30 días |
| `integration_deliveries` | `integration_deliveries.client_id` | `{technical}` | f | include | redact_fields | audit_log | Estado de envío a cada destino; la supresión borra la carga enmascarada y el error |
| `integration_delivery_attempts` | `integration_delivery_attempts.client_id` | `{identity,contact,financial,employment}` | f | include_redacted | redact_fields | access_log | Bitácora de envíos con la carga enmascarada; 30 días |
| `integration_links` | `integration_links.client_id` | `{technical}` | f | include | retain_legal | audit_log | Qué destino tiene al titular; se conserva hasta confirmar la eliminación en el destino |
| `integration_test_receipts` | `integration_test_receipts.client_id` | `{identity,contact}` | f | include_redacted | delete | access_log | Receptor de prueba: últimos 20 envíos, enmascarados |

### 3.2 Canonical model — `integration_payload()` (the only builder of what leaves)

`integration_payload(p_destination_id uuid, p_entity text, p_id uuid, p_options jsonb default '{}') returns jsonb`
— stable definer, **service-only**. Options: `action` (`upsert`|`delete`|`restrict`, default `upsert`), `reason`,
`omit_decision` (bool). Returns **C-1**:

```json
{"status":"ok","payload":{…},"hash":"<sha256 hex of payload::text>","client_id":"uuid|null",
 "categories":["identity","contact"],"legal_basis":"Gestión comercial — Interés legítimo / contrato",
 "consent_record_id":"uuid|null"}
{"status":"skipped","reason":"processing_limited","client_id":"uuid"}
```

Order of checks for `upsert` (first failure wins; `reason` codes are the contract for web labels):
1. destination missing ⇒ `not_found`; entity row missing or `tenant_id` ≠ destination's ⇒ `not_found`.
2. `p_entity` (`application` → its client) not in `scope.entities` ⇒ `entity_not_in_scope`.
3. client `processing_state <> 'active'` ⇒ `processing_<state>` (limited|opposed|blocked|erased).
4. `integration_commercial_basis(client)` not ok (D10) ⇒ `no_commercial_basis`.
5. destination country ≠ tenant country and not `has_consent(client,'international_processing')` ⇒ `no_international_consent`.
6. application: `status = 'draft'` ⇒ `draft`; `scope.products` non-empty and product not in it ⇒ `product_not_in_scope`.
7. `scope.segment_id` set and client not matched by `segment_filter_sql(segment.definition, tenant)` (dynamic
   `execute format('select exists (select 1 from clients c left join lateral (select coalesce((select p.attributes
   from client_profiles p where p.client_id = c.id), ''{}''::jsonb) as attrs) a on true where c.id = $1 and %s)',
   flt)`) ⇒ `segment_mismatch`.

Entity `test` (any destination status): a synthetic person, `client_id` null, no checks.

**Person** (`schema tramiq.crm.v1/person`):
```json
{"schema":"tramiq.crm.v1/person","id":"<client uuid>","tenant_ref":"<clients.external_ref|null>",
 "updated_at":"<greatest(clients.updated_at, client_profiles.changed_at)>","profile_version":14,
 "attributes":{"identity.full_name":"Ana López","contact.email":"ana@example.com","income.band":"1000_1999"},
 "privacy":{"processing_state":"active","under_rectification":["income.monthly_gross"]},
 "links":{"tramiq_path":"/clients/<id>"}}
```
`attributes`: for each key in `scope.attributes` that `client_attribute_for(tenant,key)` knows and that passes the
cap (D12): `client_profiles.attributes -> key -> 'value'`; when the profile has no entry, the `clients` column named
by the attribute's `client_column` (record value). Null values omitted. `under_rectification`: attribute keys whose
`client_column` has an active `field_locks` row with reason `under_rectification`. `profile_version` 0 when no profile.

**Application** (`schema tramiq.crm.v1/application`):
```json
{"schema":"tramiq.crm.v1/application","id":"uuid","number":13,"person_id":"uuid",
 "product":{"id":"uuid","code":"VIDA-STD","name":"Vida estándar"},
 "status":"manual_review","channel":"staff","submitted_at":"ts","updated_at":"ts",
 "form":{"coverage_amount":50000},
 "score":null,
 "decision":{"decision":"approved","decided_at":"ts","conditions":[{"type":"extra_premium","value":15}],
             "reason_codes":["…"],"sum_insured":50000},
 "links":{"tramiq_path":"/applications/<id>"}}
```
`form`: keys in `scope.form_keys` that are fields of the product's `form_schema.fields[]` and not `sensitive` (unless
approved). `score`: only with `include_score` ⇒ `{final_score, tier}` of the latest `scores` row. `decision`: latest
`case_decisions` row, only when `include_decision` and not `omit_decision`; `conditions[].detail` only with
`sensitive_approved`.

**Delete / restrict** (no privacy checks — always allowed, no personal data):
`{"schema":"tramiq.crm.v1/person","id":"uuid","deleted":true,"reason":"erasure|consent_revoked|disconnect|no_longer_eligible"}`,
`{"schema":"tramiq.crm.v1/person","id":"uuid","restricted":true,"privacy":{"processing_state":"limited"}}`
(application entity: same with its schema; restrict is person-only).

`categories`: distinct `client_attributes.category` of included attributes; `+ 'application'` for applications;
`+ 'inferred'` when `score` included. `hash` = `encode(sha256(convert_to(payload::text,'UTF8')),'hex')`.

Helpers (A): `integration_commercial_basis(p_client_id uuid) returns jsonb {ok, consent_record_id, legal_basis}`
(stable, service-only); `integration_eligibility(p_destination_id uuid, p_entity text, p_id uuid) returns text`
(null = eligible; same checks, no payload; service-only); `integration_mask(p jsonb) returns jsonb` (immutable,
`search_path ''`, executable by authenticated+service): recursively, under `attributes` and `form`, strings ⇒
first char + `'•••'` (emails: first char + `'•••@'` + domain), numbers/booleans ⇒ `'•••'`; `decision.conditions`
values ⇒ `'•••'`; everything else (ids, schema, status, timestamps, product, codes) kept.

### 3.3 Scope

```json
{"entities":["person","application"], "events":[], "attributes":["identity.full_name","contact.email",
 "contact.phone","address.municipality","address.department","employment.employer_name","employment.job_title",
 "income.band"], "form_keys":[], "products":[], "segment_id":null, "include_decision":true, "include_score":false}
```
`events`/`products` empty = all. Defaults filled by `integration_destination_save` for missing keys (the list
above is `DEFAULT_ATTRIBUTES`, plan §9). `file_export` forces `entities = ["person"]`.
`integration_scope_validate(p_kind text, p_scope jsonb) returns jsonb` (stable definer, authenticated; tenant =
`current_tenant_id()`, admin gate) ⇒ `[{code, key}]` with codes `unknown_entity, unknown_event, unknown_attribute,
sensitive_attribute_not_allowed, unknown_form_key, sensitive_form_key, unknown_product, segment_not_found,
segment_purpose_not_commercial` (segment purpose must be `commercial_management`), `bad_scope`.

### 3.4 Event triggers (A)

`integration_events_enabled(p_tenant uuid) returns boolean` (stable definer, service-only): exists a destination
of the tenant with `kind in ('webhook','api_pull') and status in ('active','paused','error')`.
`integration_emit(p_tenant uuid, p_kind text, p_entity text, p_entity_id uuid, p_client_id uuid, p_detail jsonb
default '{}') returns void` (definer, service-only): no-op unless enabled; inserts one row. All trigger functions
are definer and call `integration_emit`:

| Trigger | When | Event |
| --- | --- | --- |
| `clients_integration_insert` AFTER INSERT on `clients` | always | `person.upserted` |
| `clients_integration_state` AFTER UPDATE OF processing_state on `clients` | `old.processing_state is distinct from new.processing_state` | `erased` ⇒ `person.erased`; `limited/opposed/blocked` ⇒ `person.restricted`; `active` ⇒ `person.upserted`; detail `{from, to, dsr_id: new.processing_state_dsr_id}` |
| `clients_integration_rectified` AFTER UPDATE on `clients` | `current_setting('app.rectifying', true) = 'on'` | `person.upserted`, detail `{rectification:true, dsr_id}` with `dsr_id` = first `field_sources -> col ->> 'dsr_id'` among columns whose value changed |
| `client_profiles_integration` AFTER INSERT OR UPDATE OF version on `client_profiles` | insert, or `old.version is distinct from new.version` | `person.upserted` |
| `applications_integration_status` AFTER INSERT OR UPDATE OF status on `applications` | `new.status <> 'draft'` and (insert or status changed) | from `draft` (or insert) ⇒ `application.created`; `withdrawn` ⇒ `application.withdrawn`; `approved/declined` ⇒ `application.decided`; else `application.status_changed` |
| `case_decisions_integration` AFTER INSERT on `case_decisions` | always | `application.decided` |
| `consent_records_integration` AFTER INSERT on `consent_records` | `purpose_code in ('commercial_management','international_processing')` | `granted` ⇒ `person.upserted`; `refused/revoked` ⇒ `consent.revoked`, detail `{purpose, dsr_id: new.dsr_id}` |

Duplicates (profile version + rectification in one transaction) are harmless: dispatch coalesces.

### 3.5 Dispatch, targets, enqueue (A)

`integration_targets(p_event_id bigint) returns table (destination_id uuid, entity text, entity_id uuid,
client_id uuid, action text, reason text, due_on date, dsr_id uuid)` — stable definer, service-only. For the
event's tenant, destinations with `kind = 'webhook'` and `status in ('active','paused','error')` whose
`scope.events` is empty or contains the kind and whose `scope.entities` contains the entity:

| Event | Rows |
| --- | --- |
| `person.upserted` | `upsert` of the person. If `detail.rectification` and a link exists: `reason 'rectification'`, `due_on`, `dsr_id`. |
| `application.*` | `upsert` of the application. |
| `person.restricted` | only if a person link exists: `restrict`, `reason 'restricted'`, `due_on`, `dsr_id`. |
| `person.erased` | for the person link and each application link of that client: `delete`, `reason 'erasure'`, `due_on`, `dsr_id`. |
| `consent.revoked` | same as erased with `reason 'consent_revoked'`; when `detail.purpose = 'international_processing'` only destinations whose country ≠ tenant country. |

`due_on` = `add_business_days(privacy_local_date(), coalesce(s.propagation_days,5), tenant, coalesce(s.country,'SV'))`.

`integration_enqueue(p_destination_id uuid, p_entity text, p_entity_id uuid, p_client_id uuid, p_action text,
p_event_kind text, p_reason text default null, p_due_on date default null, p_dsr_id uuid default null, p_force
boolean default false) returns uuid` — definer, service-only. The coalescing upsert on `(destination_id, entity,
entity_id)`:
- no row ⇒ insert `pending`, `next_attempt_at = now()`.
- `pending`/`failed` ⇒ update `event_kind`; `action`: `delete` > `restrict` > `upsert` (a stronger action is never
  downgraded by a later upsert while pending); keep `next_attempt_at` (backoff survives); keep the earliest non-null
  `due_on`, first non-null `dsr_id`/`reason`; `force := force or p_force`.
- `in_flight` ⇒ same field merge + `rearm = true`.
- `delivered`/`dead`/`skipped` ⇒ reset to `pending`, `attempts 0`, `first_attempt_at null`, `next_attempt_at now()`,
  new action/reason/due_on/dsr_id, `skip_reason null`.
- `delete` for an entity with **no link** and a pending `upsert` never delivered ⇒ the row becomes `skipped`,
  `skip_reason 'erased_before_send'` (nothing to propagate).

`integration_dispatch(p_limit integer default 500) returns jsonb` — definer, service-only.
`if not pg_try_advisory_xact_lock(hashtext('integration_dispatch')) then return {"busy":true}`. Claims up to
`p_limit` events `where dispatched_at is null order by id for update skip locked`; for each: rows of
`integration_targets` ⇒ `integration_enqueue`; for each row with a `dsr_id` (erasure, revocation, restriction or rectification), insert
`dsr_propagations (tenant_id, dsr_id, recipient_name = destination.name, recipient_kind 'crm_destination', action
= erase|revoke|limit|rectify, due_on)` and set `dsr_propagation_id`; plus, for `api_pull`/`file_export`
destinations holding a link and an event with `dsr_id` (erased/revoked/restricted/rectified), a manual
`dsr_propagations` row (no delivery) — and `update data_subject_requests set recipients_notified_at = null` like
`add_dsr_propagation`. Then `dispatched_at = now(), dispatch_seq = nextval('integration_events_dispatch_seq')` in id
order. Returns `{"events":n,"deliveries":n,"propagations":n}`.

### 3.6 Claim, payload, finish (A) — the orchestrator's contract

`claim_integration_deliveries(p_limit integer default 20) returns jsonb` — definer, service-only. Selects `for
update of d skip locked`, ordered by `next_attempt_at`: rows with (`status in ('pending','failed') and
next_attempt_at <= now()`) or (`status = 'in_flight' and lease_until < now()`), whose destination is
- `active` and (`circuit_open_until` null or past), or
- any of `draft/active/paused` when `entity = 'test'`, or
- `disconnected` when `action = 'delete'`.
Sets `status 'in_flight', claim_token = gen_random_uuid(), lease_until = now() + 5 min, attempts + 1,
first_attempt_at = coalesce(first_attempt_at, now())`. Returns **C-2**:
```json
[{"delivery_id":"uuid","claim_token":"uuid","destination_id":"uuid","url":"https://…","entity":"person",
  "entity_id":"uuid","action":"upsert","event_type":"person.upserted","attempt":1,"force":false}]
```

`integration_delivery_payload(p_delivery_id uuid, p_claim_token uuid) returns jsonb` — volatile definer,
service-only. Token mismatch ⇒ `22023 claim_lost`. Calls `integration_payload(dest, entity, entity_id,
{action, reason})`; on `ok` stores `payload_hash`, `payload_masked = integration_mask(payload)`, `categories`,
`webhook_id` (D7) on the delivery. Returns **C-3**:
```json
{"status":"ok","type":"person.upserted","webhook_id":"msg_…","payload":{…},"hash":"…","unchanged":false}
{"status":"skipped","reason":"no_commercial_basis"}
```
`unchanged` = action `upsert` and hash = the link's `last_synced_hash`.

`integration_delivery_secrets(p_destination_id uuid) returns jsonb` — service-only ⇒ `{"secrets":["whsec_…"]}`
(current, plus previous while `secret_previous_expires_at > now()`); no secret ⇒ `{"secrets":[]}`.

`finish_integration_delivery(p jsonb) returns jsonb` — definer, service-only. Input **C-4**:
```json
{"delivery_id":"uuid","claim_token":"uuid",
 "outcome":"delivered|transient|rate_limited|auth|validation|blocked|skipped|unchanged",
 "http_status":200,"duration_ms":143,"error":null,"retry_after_seconds":null,
 "skip_reason":null,"external_id":"rcv_12","external_url":null}
```
Always appends one `integration_delivery_attempts` row (with the delivery's `payload_masked`). Then:

| outcome | delivery | destination / side effects |
| --- | --- | --- |
| `delivered` | `delivered`, `delivered_at`, error cleared | `consecutive_failures 0`, circuit closed. `upsert`: upsert link (`via 'webhook'`, hash, external id/url) + `integration_record_transfer(...)` (D18; not for `test`). `restrict`: link `restricted_at = now()`. `delete`: delete the link. `dsr_propagation_id` set ⇒ `dsr_propagations.done_at = now(), evidence = 'Entregado a «<name>» por webhook (HTTP <s>, <webhook_id>) el <ts>'`; when none open for the DSR ⇒ `recipients_notified_at = now()` and `privacy_dsr_event(dsr, tenant, 'system', 'propagation.completed', {propagation_id})`. |
| `unchanged` | `skipped`, `skip_reason 'unchanged'` | — |
| `skipped` | `skipped`, `skip_reason` | If a link exists and reason ∈ `processing_limited/opposed/blocked` ⇒ re-arm `restrict` (`reason 'restricted'`, `due_on`); reason ∈ `no_commercial_basis, no_international_consent, segment_mismatch, product_not_in_scope, entity_not_in_scope` ⇒ re-arm `delete` (`reason 'no_longer_eligible'`, `due_on`). |
| `transient` / `rate_limited` | `failed`, `next_attempt_at = now() + coalesce(retry_after clamp, integration_backoff(attempts))`; `dead` if past `first_attempt_at + 24 h` | `consecutive_failures + 1`; reaching 5 ⇒ `circuit_open_until = now() + 10 min`. |
| `auth` | back to `pending` (`next_attempt_at now()`) | destination `status 'error'`, `status_reason 'auth_failed'` (410 ⇒ `'endpoint_gone'`). |
| `validation` | `dead` | — |
| `blocked` (SSRF / non-https) | `dead` | destination `status 'error'`, `status_reason 'url_not_allowed'`. |

`rearm` set and outcome ∈ (delivered, unchanged, skipped) ⇒ back to `pending` now, `rearm false`. Returns
`{"status":"…","next_attempt_at":"ts|null"}`. `integration_backoff(p_attempt integer) returns interval` immutable.
`integration_record_transfer(p_destination_id uuid, p_client_id uuid, p_categories text[], p_reference text,
p_dsr_id uuid default null) returns void` (definer, service-only; used by A's finish and by B).
`integration_touch_link(p_destination_id uuid, p_entity text, p_entity_id uuid, p_client_id uuid, p_via text,
p_hash text, p_external_id text default null, p_external_url text default null) returns void` (service-only).

### 3.7 Admin RPCs (A) — all definer, `authenticated`, admin gate on the destination's tenant, audited via `privacy_audit(tenant, role, action, 'integration_destination', id, meta-without-values)`

| Signature | Behaviour |
| --- | --- |
| `integration_destination_save(p jsonb) returns uuid` | `p = {id?, kind, name, country, config, scope, dpa_attested}`. Insert (`status 'draft'`) or update (kind immutable; not `disconnected`). Validates scope (§3.3; any error ⇒ `22023` with the first code). `config.url`: `^https://[^/@\s]+(:\d+)?(/\S*)?$`, ≤ 500 chars, host not `localhost`/IP literal (light check; the real guard is the orchestrator). `config.test_receiver = true` ⇒ url must end with `/api/public/integrations/receiver/<id>` (`receiver_url_mismatch`). `dpa_attested: true` stamps `dpa_attested_by/at`. Audit `integration.destination_saved`. |
| `integration_set_status(p_destination_id uuid, p_status text) returns void` | `draft→active` requires `dpa_attested_at`, valid scope, and for webhook `config.url` + `secret_ref` (`not_ready`); sets `activated_at`. `active→paused`, `paused→active`, `error→active` (clears `status_reason`, `consecutive_failures`, circuit). Else `invalid_transition`. Audit `integration.status_changed`. |
| `integration_rotate_secret(p_destination_id uuid) returns jsonb` | webhook only. Drops the old previous secret; current → previous with `secret_previous_expires_at = now() + 24 h` (none on first call); stores a new one (D8/D9). Returns **once** `{"secret":"whsec_…","previous_valid_until":"ts|null"}`. Audit `integration.secret_rotated` (no value). |
| `integration_send_test(p_destination_id uuid) returns uuid` | webhook with url+secret, not disconnected: `integration_enqueue(dest,'test',dest,null,'upsert','test.ping', p_force => true)`. |
| `integration_initial_sync(p_destination_id uuid) returns jsonb` | webhook, `active`: enqueue `upsert` for every client with `integration_eligibility(...) is null` (and, if applications in scope, their non-draft applications), ≤ 5000 ⇒ `{"queued":n,"capped":bool}`. Audit. |
| `integration_retry_delivery(p_delivery_id uuid) returns void` | `failed/dead` ⇒ `pending`, attempts 0, `first_attempt_at null`, `next_attempt_at now()`. |
| `integration_resend_delivery(p_delivery_id uuid) returns void` | `delivered/skipped` ⇒ re-arm with `force = true`. |
| `integration_resync_entity(p_entity text, p_id uuid) returns integer` | tenant_admin: enqueue `upsert` to every active webhook destination ⇒ count. |
| `integration_disconnect(p_destination_id uuid, p_request_deletion boolean) returns jsonb` | `true` and webhook ⇒ enqueue `delete` (`reason 'disconnect'`, no `due_on`) for every link; `false` ⇒ pending/failed deliveries `skipped 'disconnected'` and secrets dropped now. `status 'disconnected'`, `status_reason 'disconnected_by_admin'`, `disconnected_at`. ⇒ `{"deletions_queued":n}`. Reconcile drops secrets once no delete is pending. |
| `integration_approve_sensitive(p_destination_id uuid, p_attributes text[], p_justification text) returns void` | `privacy_require_superadmin()`; keys must be catalogued sensitive attributes; justification ≥ 20 chars ⇒ cap `sensitive_approved`, `sensitive_approval = {by, at, justification, attributes}`. Empty array ⇒ back to `non_sensitive`. |
| `integration_destination_metrics(p_destination_id uuid) returns jsonb` | **C-5** `{"pending":n,"in_flight":n,"failed":n,"dead":n,"delivered_24h":n,"failed_24h":n,"oldest_pending_seconds":n\|null,"last_delivered_at":"ts\|null","last_error":"…\|null","avg_duration_ms_24h":n\|null,"links":n,"propagations_open":n,"propagations_overdue":n}` |
| `integration_payload_preview(p_destination_id uuid, p_entity text, p_id uuid) returns jsonb` | `{"status":"ok","masked":{…}}` or `{"status":"skipped","reason":"…"}` — the browser never receives an unmasked payload. |
| `integration_entity_status(p_entity text, p_id uuid) returns jsonb` | **staff** of the tenant (hidden clients ⇒ `P0002` unless admin, as `client_profile_get`). **C-6** `[{"destination_id","name","kind","state":"synced\|pending\|failed\|not_sent\|restricted","reason":"code\|null","last_synced_at":"ts\|null","external_url":"…\|null"}]` over non-draft, non-disconnected destinations (`not_sent` + `reason` from `integration_eligibility`). |
| `integration_notice_recipients(p_tenant_id uuid) returns jsonb` | admin or superadmin ⇒ `[{"name","kind","country"}]` of `active/paused/error` destinations. |

### 3.8 Service RPCs for monitoring and the receiver (A)

| Signature | Returns |
| --- | --- |
| `integration_reconcile(p_limit integer default 2000) returns jsonb` | D26 ⇒ `{"checked":n,"rearmed":n,"pruned_attempts":n,"pruned_events":n,"secrets_dropped":n}` |
| `integration_propagation_alerts() returns table (tenant_name text, destination_name text, open integer, overdue integer, nearest_due_on date, days_left integer)` | deliveries with `due_on` not `delivered/skipped`, plus open `dsr_propagations` of `recipient_kind 'crm_destination'`; rows with `days_left <= 1` (`business_days_between`). |
| `integration_health() returns jsonb` | `{"destinations_active":n,"destinations_error":[{"tenant_name","name","status_reason"}],"due":n,"oldest_due_seconds":n\|null,"dead_24h":n,"events_undispatched":n}` |
| `integration_receiver_secrets(p_destination_id uuid) returns jsonb` | `{"tenant_id","secrets":[…]}` only when kind webhook, `config.test_receiver` true and not disconnected; else `null`. |
| `integration_receiver_record(p jsonb) returns jsonb` | `p = {destination_id, webhook_id, event_type, signature_valid, failure, body}`; `client_id` from `body.data.id` (person) / `body.data.person_id` (application) only if a client of that tenant; stores `integration_mask(body -> 'data')` (not stored when invalid); trims to the last 20 per destination ⇒ `{"external_id":"rcv_<id>"}`. |

### 3.9 Plan 2 hooks (A) — D17

```sql
alter function privacy_p3_footprint_c(uuid, uuid[], uuid[]) rename to privacy_p3_footprint_c_base;
alter function privacy_p3_erase_c(uuid, uuid[], uuid[], boolean) rename to privacy_p3_erase_c_base;
-- revoke all on both *_c_base from public, anon, authenticated; grant execute to service_role
```
- `privacy_p4_footprint(p_tenant uuid, p_client_ids uuid[], p_app_ids uuid[]) returns jsonb` ⇒
  `{"integrations":{"links":[{destination_name, kind, country, entity, last_synced_at, restricted_at}],
  "pending_propagations":[{destination_name, action, due_on, status}],"attempts":n,"test_receipts":n}}`.
- `privacy_p4_erase(p_tenant, p_client_ids, p_app_ids, p_simulate) returns jsonb` ⇒ counts; when not simulating:
  `payload_masked = null, error = null` on attempts, `payload_masked = null, last_error = null` on deliveries,
  delete receipts — for those clients and applications. **Links, deliveries and events stay** (they carry the
  propagation the `person.erased` event already queued). Rows: `[{table:'integration_delivery_attempts', rows,
  action:'redact_fields'}, {table:'integration_deliveries', …,'redact_fields'}, {table:'integration_test_receipts',
  …,'delete'}, {table:'integration_links', rows, action:'propagate'}]`.
- New `privacy_p3_footprint_c(...)` = `privacy_p3_footprint_c_base(...) || privacy_p4_footprint(...)`; new
  `privacy_p3_erase_c(...)` = `privacy_p3_erase_c_base(...) || privacy_p4_erase(...)`. Same grants as before
  (service-only). Comment in the migration: "Plan 4 extends Plan 3's `_c` stage by renaming it; a later plan does the
  same to `privacy_p4_*`. Never `create or replace` a Plan 2 wrapper."
- Access report: unchanged wrapper; each disclosure is already in its `data_transfers` section. Portability:
  nothing (copies, not subject-provided). Rectification: §3.4 trigger ⇒ re-send with `due_on` + `dsr_propagations`.

### 3.10 Migration B — API keys, reads, events cursor, file export

```sql
create table api_keys (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  destination_id uuid not null,
  name text not null check (length(btrim(name)) between 2 and 80),
  key_prefix text not null check (key_prefix ~ '^tq_live_[0-9a-f]{8}$'),
  key_hash text not null unique check (key_hash ~ '^[0-9a-f]{64}$'),
  scopes text[] not null check (scopes <@ array['read:persons','read:applications','read:decisions','read:events']
                                and cardinality(scopes) > 0),
  created_by uuid references auth.users (id) on delete set null, created_at timestamptz not null default now(),
  last_used_at timestamptz, revoked_at timestamptz, expires_at timestamptz,
  constraint api_keys_destination_same_tenant foreign key (tenant_id, destination_id)
    references integration_destinations (tenant_id, id) on delete cascade);
create index api_keys_tenant on api_keys (tenant_id, created_at desc);
```
RLS select admin-of-tenant (same predicate); `revoke all … from public, anon, authenticated`; `grant select (id,
tenant_id, destination_id, name, key_prefix, scopes, created_by, created_at, last_used_at, revoked_at, expires_at) to
authenticated` (**not `key_hash`**); service_role all. No personal data ⇒ no registry row.

| Signature | Kind | Behaviour / JSON |
| --- | --- | --- |
| `api_key_create(p_destination_id uuid, p_name text, p_scopes text[], p_expires_at timestamptz default null) returns jsonb` | admin | destination `api_pull`, not disconnected; key = `'tq_live_' || 64 hex`; stores prefix + sha256 ⇒ **once** `{"id","key":"tq_live_…","key_prefix"}`. Audit `integration.api_key_created` (prefix only). |
| `api_key_revoke(p_id uuid) returns void` | admin | `revoked_at = now()`; audit. |
| `api_v1_authenticate(p_key_hash text, p_scope text) returns jsonb` | service | key not found / revoked / expired ⇒ `42501 invalid_key`; scope missing ⇒ `42501 insufficient_scope`; destination not `active` ⇒ `42501 destination_inactive`. Touches `last_used_at` if older than 60 s ⇒ `{"key_id","key_prefix","tenant_id","destination_id","scopes"}`. |
| `api_v1_persons(p_key_hash text, p_after uuid default null, p_limit integer default 50) returns jsonb` | service | scope `read:persons`; clients of the tenant `id > p_after order by id`, scanning ≤ `3 × limit` (limit ≤ 100); keeps those with `integration_payload` ok ⇒ **C-7** `{"data":[payload…],"next_cursor":"uuid\|null"}` (`next_cursor` = last scanned id when more exist). Per returned row: `integration_touch_link(via 'api')` + `integration_record_transfer(reference 'api:<prefix>')`. |
| `api_v1_person(p_key_hash text, p_id uuid) returns jsonb` | service | payload or `P0002 not_found` (skipped is also `not_found`, never the reason). Link + transfer. |
| `api_v1_applications(p_key_hash text, p_after uuid default null, p_limit integer default 50, p_status text default null) returns jsonb` | service | scope `read:applications`; `omit_decision` unless key has `read:decisions`; same paging/side effects. |
| `api_v1_application(p_key_hash text, p_id uuid) returns jsonb` | service | as person. |
| `api_v1_events(p_key_hash text, p_after bigint default 0, p_limit integer default 100) returns jsonb` | service | scope `read:events`; tenant events with `dispatch_seq > p_after` filtered by destination `scope.entities/events` and key scopes (person events need `read:persons`, application events `read:applications`) ⇒ **C-8** `{"data":[{"id":"evt_<seq>","cursor":"<seq>","type","entity","entity_id","occurred_at"}],"next_cursor":"<seq>\|null"}`. Ids only: no transfer row. |
| `integration_file_export(p_destination_id uuid, p_source jsonb) returns jsonb` | admin | destination `file_export`, `active`. `p_source`: `{"kind":"clients","client_ids":[…≤5000]}` \| `{"kind":"segment","segment_id":"uuid"}` (segment of the tenant, purpose `commercial_management`) \| `{"kind":"all"}`. Builds person payloads (≤ 5000) ⇒ **C-9** `{"export_id":"uuid","template":"hubspot","format":"xlsx","rows":[payload…],"skipped":{"no_commercial_basis":3},"capped":false}`. Per row: link (`via 'file'`) + transfer (`reference 'file:<export_id>'`). `log_access('export.generated','export', null, null, {rows, view:'crm_export'})` and `privacy_audit(..., 'integration.file_exported', {rows, template})`. |

### 3.11 pgTAP suites (`db/supabase/tests/database/`, run by the replay and CI)

Fixture style as `plan3_attacker_test.sql`: two tenants, users per role, `set local role authenticated` + JWT claims.

- **`integration_core_test.sql`** (DB-A, ~35): payload with `non_sensitive` never contains `health.*` even if put in
  scope by service SQL; scope save refuses `health.bmi` (`sensitive_attribute_not_allowed`) and a sensitive form key;
  approved cap lets only the listed key through; `processing_limited/erased` ⇒ skipped; latest commercial
  `revoked` ⇒ `no_commercial_basis`; `requires_consent = true` without grant ⇒ same; US destination without
  `international_processing` ⇒ skipped, with it ⇒ ok; entity of tenant B via tenant A destination ⇒ `not_found`;
  segment mismatch; draft application ⇒ `draft`; score absent unless `include_score`; payload text never contains
  `ai_summary`, `rule_trace`, `storage`, `signed`, `extracted_data`, `note`; condition `detail` absent with
  `non_sensitive`; `integration_mask` keeps ids and masks attributes; hash stable for the same state.
- **`integration_attacker_test.sql`** (DB-A, ~40): agent and underwriter: 0 rows from destinations, deliveries,
  attempts, links, receipts; `42501` on every admin RPC; tenant_admin: `42501` selecting `secret_ref`,
  `secret_previous_ref`, from `integration_events`, from `integration_private.secrets`; `has_function_privilege
  ('authenticated', …)` false for `integration_payload, integration_eligibility, integration_dispatch,
  claim_integration_deliveries, integration_delivery_payload, integration_delivery_secrets,
  finish_integration_delivery, integration_secret_*, integration_receiver_*, integration_reconcile,
  integration_health, privacy_p4_*, privacy_p3_*_c_base`; insert/update/delete on every integration table as
  tenant_admin ⇒ permission denied; tenant A admin sees 0 rows of tenant B and gets `P0002` on B's destination in
  every RPC; `integration_approve_sensitive` as tenant_admin ⇒ `42501`; anon: `has_table_privilege` false on all
  six tables + `has_function_privilege` false on every new function; MFA-required tenant without aal2 ⇒ admin RPCs
  refused.
- **`integration_delivery_test.sql`** (DB-A, ~40): no live destination ⇒ no event rows; with one ⇒ events from each
  trigger; two events ⇒ one delivery (coalesced) and `dispatch_seq` increasing; claim sets lease, second claim
  gets nothing; finish `delivered` writes link + one `data_transfers` row (country, categories, legal_basis,
  `recipient_id`); same state again ⇒ `unchanged`; `transient` ⇒ `failed` with `next_attempt_at` ≈ +30 s; five
  transients ⇒ circuit open, claim skips; `auth` ⇒ destination `error`; `validation` ⇒ `dead`; attempts past 24 h ⇒
  `dead`; `execute_dsr_erasure` (not simulated) on a linked client ⇒ `person.erased` ⇒ `delete` deliveries for person
  and its applications with `due_on = add_business_days(…,5)` and one `dsr_propagations` row; delivering it ⇒
  `done_at` set, link gone; footprint has `integrations`; erasure nulls `payload_masked` of attempts and deletes
  receipts; consent `revoked` ⇒ `delete`; `set_processing_state('limited')` ⇒ `restrict`; unlinked erased client
  with pending upsert ⇒ `skipped 'erased_before_send'`; retry/resend re-arm; disconnect with deletion queues deletes;
  `integration_rotate_secret` returns `whsec_…` twice different, `integration_delivery_secrets` returns 2 values
  after rotation; `integration_receiver_record` trims to 20.
- **`integration_api_test.sql`** (DB-B, ~25): `api_key_create` returns the key once and stores `sha256(key)`;
  tenant_admin `42501` on `key_hash`; bad/revoked/expired hash ⇒ `invalid_key`; missing scope ⇒
  `insufficient_scope`; paused destination ⇒ `destination_inactive`; persons page excludes ineligible clients, other
  tenants and sensitive keys; each returned person adds one `data_transfers` row and a link `via 'api'`; decision
  omitted without `read:decisions`; events cursor monotonic, tenant-scoped, scope-filtered; `integration_file_export`
  skips ineligible with counts, refuses a `marketing` segment and a non-`file_export` destination, writes transfers;
  `has_function_privilege('authenticated','api_v1_persons(text,uuid,integer)','execute')` false.

---

## 4. ai-orchestrator — `src/integrations/` (package ORCH)

**Boundary:** nothing under `src/integrations/` imports from `src/agents/`, `src/applications/`, `src/documents/` or
`src/cases/` (vitest boundary test reading the files, like `__tests__/no-analyze.test.ts`).

| File | Content |
| --- | --- |
| `types.ts` | `ClaimedDelivery` (C-2), `PayloadResult` (C-3), `Outcome` union, `FinishInput` (C-4), `DeliveryResult {outcome, httpStatus?, durationMs, error?, retryAfterSeconds?, externalId?, externalUrl?}`. |
| `ssrf.ts` | `isPublicAddress(ip: string): boolean` — IPv4 rejects `0/8, 10/8, 100.64/10, 127/8, 169.254/16` (metadata `169.254.169.254`), `172.16/12, 192.0.0/24, 192.0.2/24, 192.168/16, 198.18/15, 198.51.100/24, 203.0.113/24, 224/4, 240/4, 255.255.255.255`; IPv6 rejects `::, ::1, fc00::/7, fe80::/10, ff00::/8, 2001:db8::/32, 64:ff9b::/96` with a private v4, and `::ffff:a.b.c.d` checked as v4. `checkUrl(url) ⇒ {ok:true, host, port} \| {ok:false, reason}` (https, no userinfo, port 443 or ≥ 1024). `resolvePublic(host, lookup = dns.promises.lookup) ⇒ {address, family}` — `{all:true, verbatim:true}`; any non-public ⇒ throws `SsrfError('private_address')`; IP-literal hosts checked directly. |
| `http.ts` | `postSigned({url, headers, body, timeoutMs, lookup})` — `https.request` with `servername = host` and `lookup: (_h, _o, cb) => cb(null, checked.address, checked.family)`; total timeout `INTEGRATION_HTTP_TIMEOUT_MS` (10 000) via `AbortSignal`; reads ≤ 64 KB of the response; never follows redirects; returns `{status, headers, bodyText}`. |
| `sign.ts` | Standard Webhooks: `signatureHeader(secrets: string[], msgId, timestampSeconds, body)` ⇒ `"v1,<b64> v1,<b64>"`; key = base64-decode of the part after `whsec_`; content = `${msgId}.${timestamp}.${body}`; HMAC-SHA256, base64. |
| `classify.ts` | `classify(status \| error) ⇒ Outcome`: 2xx delivered; 401/403 auth; 410 auth (endpoint gone); 3xx validation ("redirect_not_followed"); 400/404/405/413/415/422 validation; 408/425/429 rate_limited (429 with `parseRetryAfter`: seconds or HTTP date, clamp 1 s–6 h); 5xx, timeout, ECONNRESET/ECONNREFUSED/ENOTFOUND transient; `SsrfError`/non-https blocked. Error text ≤ 300 chars, response body excerpt **not** stored (it may echo personal data) — only `HTTP <status>` + code. |
| `webhook.ts` | `WebhookAdapter.deliver({url, msgId, type, payload, secrets}, deps)`: body = `JSON.stringify({type, timestamp: iso, data: payload})`; headers `content-type: application/json`, `user-agent: Tramiq-Webhooks/1`, `webhook-id`, `webhook-timestamp` (unix seconds), `webhook-signature`; parses a JSON response `{external_id?, external_url?}` (strings, ≤ 200 / https ≤ 500). |
| `deliver.ts` | `drainDeliveries(deps, {batch = INTEGRATION_DELIVER_BATCH (20), concurrency = INTEGRATION_DELIVER_CONCURRENCY (4), budgetMs = 50 000})`: loop claim (C-2) → per row `integration_delivery_payload` → `skipped` ⇒ finish `skipped`; `unchanged && !force` ⇒ finish `unchanged`; secrets cached per destination for the run (`integration_delivery_secrets`; empty ⇒ finish `auth` "no_secret"); deliver; finish. An RPC error on finish is logged and left to the lease. Returns counts. |
| `dispatch.ts` | `runDispatch()` = rpc `integration_dispatch(500)`; returns counts. |
| `reconcile.ts` | `runReconcile()` = rpc `integration_reconcile(2000)`. |
| `health.ts` | `integrationHealth()` = rpc `integration_health()`; failure ⇒ `{error:"unavailable"}` (never throws). |
| `routes.ts` | Fastify plugin: `POST /integrations/kick` (behind the existing bearer hook) ⇒ sends `integration.dispatch` then `integration.deliver` (stately; `null` = already queued) ⇒ 202 `{"queued":true}`. |
| `queues.ts` | `INTEGRATION_QUEUES` names; `registerIntegrationQueues(boss)`: `createQueue`+`updateQueue` with `SCHEDULED_POLICY`-equivalent `{policy:'stately', retryLimit:0, expireInMinutes:10, retentionDays:2}`; `work()` handlers (dispatch ⇒ then `send(deliver)`); `schedule('integration.dispatch','* * * * *')`, `schedule('integration.deliver','* * * * *')`, `schedule('integration.reconcile','53 5 * * *')`; boot: `send(dispatch)` and reconcile with the existing `CATCH_UP` options. `INTEGRATIONS_DISABLED=1` ⇒ `unschedule` all three and register no work. |

Edits outside the module (ORCH owns them): `src/queue/index.ts` (call `registerIntegrationQueues(boss)` from
`startWorker` after the existing schedules; export nothing else), `src/server.ts` (register `integrationRoutes`;
`/health/queue` response gains `"integrations": await integrationHealth()` — informational, does not change
`status`), `src/ops/watchdog.ts` (snapshot gains `integrations: {errors:[{tenant_name,name,status_reason}],
propagations:[…alerts rows], backlog_seconds}` read through injected deps that log and return empty on failure;
problems: `integration_error:<tenant>:<name>` «<tenant>: el destino «<name>» está en error (<motivo>).»,
`crm_propagation_overdue:<tenant>:<name>` «<tenant>: <n> eliminación(es)/limitación(es) para «<name>» vencieron
(plazo 5 días hábiles).», `crm_propagation_due_soon` (aggregate), `integration_backlog` when `oldest_due_seconds >
1800`), `.env.example` (`INTEGRATIONS_DISABLED`, `INTEGRATION_HTTP_TIMEOUT_MS`, `INTEGRATION_DELIVER_BATCH`,
`INTEGRATION_DELIVER_CONCURRENCY` — all optional, defaults in code; **no `render.yaml` change**).

Tests (vitest, `src/integrations/__tests__/`): `ssrf.test.ts` (every range above, mapped v6, mixed public+private
resolution rejected, literal IP host, http/userinfo/port refused); `sign.test.ts` — spec vector: secret
`whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw`, id `msg_p5jXN8AQM9LWM0D4loKWxJek`, timestamp `1614265330`, body
`{"test": 2432232314}` ⇒ `v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE=` (verified locally), and two secrets ⇒
two space-separated entries; `classify.test.ts` (table, Retry-After both forms); `deliver.test.ts` (fake rpc +
fake http: delivered, 429, 401, 400, timeout, skipped, unchanged, claim_lost); `boundary.test.ts`;
`src/queue/plan4.test.ts` (queue names registered, disabled flag unschedules).

---

## 5. web

### 5.1 Shared foundation — WEB-A step 1 (first commit; WEB-B imports, never edits)

| File | Content |
| --- | --- |
| `src/lib/integrations/types.ts` | `DestinationKind, DestinationStatus, Destination` (the granted columns), `DESTINATION_COLUMNS` string for `.select()`, `IntegrationScope`, `Delivery`, `DeliveryAttempt`, `DestinationMetrics` (C-5), `EntitySyncStatus` (C-6), `TestReceipt`, `ApiKey`, `CanonicalPerson`, `CanonicalApplication`, `FileTemplate = 'hubspot'\|'dynamics'\|'odoo'\|'salesforce'\|'generic'`, `EventType`. |
| `src/lib/integrations/labels.ts` | `KIND_LABELS` (webhook «Webhook», api_pull «API REST», file_export «Exportación de archivos»), `STATUS_LABELS` (Borrador, Activo, En pausa, Con error, Desconectado), `STATUS_REASON_LABELS`, `EVENT_LABELS` (person.upserted «Cliente creado o actualizado», person.restricted «Tratamiento limitado», person.erased «Cliente suprimido», consent.revoked «Consentimiento revocado», application.created «Solicitud enviada», application.status_changed «Cambio de estado de la solicitud», application.decided «Solicitud decidida», application.withdrawn «Solicitud retirada», test.ping «Prueba»), `OUTCOME_LABELS`, `SKIP_REASON_LABELS` (processing_limited «Tratamiento limitado», processing_opposed «El titular se opuso», processing_blocked «Bloqueado», processing_erased «Suprimido», no_commercial_basis «Sin base para gestión comercial», no_international_consent «Sin consentimiento para tratamiento fuera de El Salvador», product_not_in_scope «Producto fuera del alcance», segment_mismatch «Fuera del segmento del destino», entity_not_in_scope «Este destino no recibe este dato», draft «Solicitud en borrador», unchanged «Sin cambios desde el último envío», erased_before_send «Suprimido antes del envío», disconnected «Destino desconectado»), `SCOPE_LABELS` (read:persons «Leer clientes» …), `TEMPLATE_LABELS`. |
| `src/lib/integrations/errors.ts` | `integrationErrorMessage(code)` for every §3 code (`not_ready` «Falta completar el destino: país, declaración de contrato, URL y secreto.», `receiver_url_mismatch`, `invalid_transition`, `sensitive_attribute_not_allowed` «Ese dato es sensible y no puede salir de Tramiq.», `segment_purpose_not_commercial`, …). |

### 5.2 WEB-A — «Integraciones» (settings, tenant_admin)

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `app/(dashboard)/settings/page.tsx` (edit) | Add a `DATA_LINKS` entry «Integraciones» — «Enviar clientes y solicitudes al CRM de la empresa: webhooks, API y archivos.» (icon `Share2`). | — |
| `app/(dashboard)/settings/integrations/page.tsx` + `components/integrations/catalog.tsx` | Destinations list (name, kind, status badge, last delivery) and the catalog: three cards «Webhook», «API REST», «Exportación de archivos» («Configurar» ⇒ wizard), then «HubSpot», «Dynamics 365», «Odoo», «Salesforce, Zoho y otros» — each «Vía webhook/API» with a dialog showing its recipe. | `from('integration_destinations').select(DESTINATION_COLUMNS)` |
| `src/lib/integrations/recipes.ts` | Pure: per CRM, 4–6 Spanish steps for Zapier/Make/n8n/Power Automate (e.g. HubSpot: «En Zapier, cree un Zap con disparador *Webhooks by Zapier → Catch Raw Hook*; pegue la URL en Tramiq; agregue *HubSpot → Create or Update Contact* usando `data.attributes["contact.email"]`…»; Power Automate: «Cree un conector personalizado importando `/api/v1/openapi.json`»). | — |
| `app/(dashboard)/settings/integrations/new/page.tsx` + `components/integrations/destination-wizard.tsx`, `scope-editor.tsx`, `src/lib/integrations/wizard.ts` (pure step validation) | `?kind=`. **Webhook:** 1 «Destino» (name, country select, checkbox «La empresa tiene contrato de tratamiento de datos con el proveedor de este sistema») ⇒ `integration_destination_save` creates the draft; 2 «Qué enviar» (entities, events, products, segment of purpose Gestión comercial); 3 «Datos» (`scope-editor`: attributes grouped by category with sensitive ones disabled «Dato sensible: no sale de Tramiq», product form keys, toggles «Incluir decisión», «Incluir puntaje»; notice «Este destino aparecerá como destinatario en el aviso de privacidad. Publique una nueva versión del aviso.» with link to the notice editor; when country ≠ SV: «Solo se enviarán clientes con consentimiento de tratamiento internacional.»); 4 «Conexión» (URL, or checkbox «Usar el receptor de prueba de Tramiq» which fills `${origin}/api/public/integrations/receiver/${id}` and `test_receiver: true`; «Generar secreto de firma» ⇒ `secret-once-dialog`); 5 «Probar» (`integration_send_test` + kick; polls attempts every 2 s for 30 s; shows outcome, HTTP status, masked body); 6 «Activar» (`integration_set_status('active')`, optional «Enviar también los clientes existentes que cumplan» ⇒ `integration_initial_sync` + kick). **API REST:** 1, 2, 3, 4 «Llave» (`api_key_create` with scope checkboxes ⇒ show-once, OpenAPI link, `curl` example), 5 «Activar». **Archivos:** 1, 3 (persons only), 4 «Plantilla» (HubSpot/Dynamics 365/Odoo/Salesforce/Genérica; CSV/XLSX), 5 «Activar». | RPCs §3.7, B `api_key_create`, `POST /api/integrations/kick` |
| `app/(dashboard)/settings/integrations/[destinationId]/page.tsx` + `components/integrations/destination-detail.tsx`, `delivery-log.tsx`, `propagation-table.tsx`, `receiver-panel.tsx`, `sensitive-approval-dialog.tsx` | Header (name, kind, status, country) and actions: «Pausar»/«Reanudar», «Enviar ahora» (kick), «Rotar secreto» (show-once + «El secreto anterior sigue válido hasta …»), «Enviar prueba», «Desconectar» (dialog «¿Pedir al destino que elimine lo enviado?»), «Exportar» (file_export ⇒ WEB-B's button). Metrics cards (C-5). Delivery log: attempts newest first (fecha, evento, entidad, resultado, HTTP, duración, intento); row expands to the masked payload; «Reintentar» on failed/dead and «Reenviar» on delivered via the delivery. Propagations with due dates. Scope summary + «Editar alcance». Webhook: «Cómo verificar la firma» (Node snippet). `test_receiver`: last 20 receipts («Firma válida ✓» / «Firma inválida»). Superadmin only: «Aprobar datos sensibles». | table selects via RLS (`integration_delivery_attempts` paged 50, `integration_deliveries`, `integration_test_receipts`), `integration_destination_metrics`, `integration_payload_preview` |
| `app/(dashboard)/settings/integrations/api-keys/page.tsx` + `components/integrations/api-keys-manager.tsx`, `secret-once-dialog.tsx` | Keys (name, prefix `tq_live_ab12cd34…`, destination, scopes, last used, state); «Nueva llave» (choose api_pull destination) ⇒ show-once dialog «Copie la llave ahora: no se volverá a mostrar.»; «Revocar». | B `api_key_create/revoke`; `from('api_keys').select('id,…')` |
| `app/api/integrations/kick/route.ts` | `POST`: `requireStaff()`, role `tenant_admin`/`superadmin` else 403; `proxyToService(`${AI_ORCHESTRATOR_URL}/integrations/kick`, {method:'POST'}, "El orquestador")`. | orchestrator |
| Notice (edits) `src/lib/privacy/notice-generator.ts`, `components/privacy/notice-editor.tsx`, `src/lib/privacy/types.ts` | `buildNoticeSections(inv, settings, opts)` accepts `opts.crmRecipients?: {name,kind,country}[]`; recipients section adds «Sistemas de gestión de clientes de la aseguradora: «CRM Ventas» (US)…»; international section counts destinations outside `settings.country`. Editor loads `integration_notice_recipients` next to `processing_inventory`. | DB-A |

Tests: `test/unit/integrations-wizard.test.ts` (step validation, receiver URL builder), `integrations-labels.test.ts`
(every C-3 reason, outcome, event and §3 error code has a label), `notice-crm-recipients.test.ts`.

### 5.3 WEB-B — `/api/v1`, OpenAPI, files, badges, test receiver

| Route / file | Purpose |
| --- | --- |
| `src/lib/integrations/api-auth.ts` (server-only) | `apiKeyFromRequest(req)` (`Authorization: Bearer tq_live_…`, regex `^tq_live_[0-9a-f]{64}$`) ⇒ sha256 hex (`node:crypto`). Limits (`SlidingWindow`, per process): 120 requests/min per key hash; 20 failed authentications/10 min per `clientIp`. `apiRpc(fn, args)` = `publicRpc` from `lib/public/route.ts` with the mapping 42501 ⇒ 401 (`invalid_key`, `destination_inactive`) / 403 (`insufficient_scope`), P0002 ⇒ 404. |
| `src/lib/integrations/api-response.ts` | `apiJson(data, init)`, `apiError(code, status, retryAfter?)` ⇒ `{"error":{"code","message"}}` (Spanish message), `Cache-Control: no-store`, `RateLimit-Limit/Remaining` headers; `parseLimit`, `parseCursor` (uuid / integer). |
| `app/api/v1/persons/route.ts`, `persons/[id]/route.ts`, `applications/route.ts`, `applications/[id]/route.ts`, `events/route.ts` | `GET` only, `runtime = "nodejs"`, `dynamic = "force-dynamic"`. Query: `limit` (1–100), `cursor` (persons/applications), `status` (applications), `after` (events). Call `api_v1_*` with the hash. Response = C-7/C-8 with `next_cursor`. |
| `app/api/v1/openapi.json/route.ts` + `src/lib/integrations/openapi.ts` | Static OpenAPI **3.1.0** object: `servers: [{url: <origin>/api/v1}]`, bearer security scheme, the five paths, schemas `Person`, `Application`, `Event`, `Page`, `Error`, and a description of the webhook headers and event catalog. No auth. |
| `src/lib/integrations/file-templates.ts` (pure) | `rowsForTemplate(template, persons)` ⇒ `{headers, rows}`. Name split: first word = first name, rest = last name. HubSpot: First Name, Last Name, Email, Phone Number, City, State/Region, Company Name, Job Title, Tramiq ID. Dynamics 365: First Name, Last Name, Email, Mobile Phone, Address 1: City, Address 1: State/Province, Job Title, Tramiq ID. Odoo: Name, Email, Phone, City, Job Position, Company Name, Reference. Salesforce: First Name, Last Name, Email, Phone, Mailing City, Mailing State/Province, Title, Account Name, Tramiq ID. Generic: `id` + every canonical key present. City = `address.municipality`, State = `address.department`, Company = `employment.employer_name`, Title = `employment.job_title`. |
| `src/lib/xlsx.ts` (pure) | `toXlsx(headers, rows): Buffer` — `[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, `xl/_rels/workbook.xml.rels`, `xl/worksheets/sheet1.xml` (inline strings `t="inlineStr"`, numbers as `n`, XML-escaped, invalid XML chars stripped); ZIP local headers + central directory, deflate (`deflateRawSync`), `zlib.crc32`. |
| `app/api/integrations/destinations/[id]/export/route.ts` | `POST {source}` with the user's session (`lib/supabase/server`): `integration_file_export` ⇒ template rows ⇒ CSV (`toCsv` + BOM, formula-neutralized) or XLSX ⇒ attachment `tramiq-<template>-<yyyy-mm-dd>.csv|xlsx`. |
| `components/integrations/export-to-crm-button.tsx` + edits to `app/(dashboard)/clients/page.tsx` (selected/all rows) and `components/segments/segment-builder.tsx` (saved segment of purpose Gestión comercial) | «Exportar para CRM» menu listing active `file_export` destinations; tenant_admin only (hidden otherwise). |
| `components/integrations/sync-badges.tsx` + edits to `components/clients/client-detail.tsx` (Resumen header) and `components/applications/application-detail.tsx` | C-6: «Sincronizado con «CRM Ventas» ✓ · hace 5 min · Ver en el CRM» (external_url), «Pendiente de envío», «Envío fallido», «No se envía a «CRM Ventas»: tratamiento limitado» (reason label), «Restringido en «CRM Ventas»». tenant_admin: «Sincronizar ahora» ⇒ `integration_resync_entity` + kick. Nothing rendered when no destination. |
| `src/lib/integrations/webhook-verify.ts` (pure) + `app/api/public/integrations/receiver/[destinationId]/route.ts` | `verifyWebhook({secrets, id, timestamp, signatureHeader, body, now})` ⇒ `{ok} \| {ok:false, failure}` (timestamp within ±5 min, constant-time compare of any `v1,` entry against any secret). Route: `publicRoute`-style catch; `SlidingWindow` 120/min per IP; body ≤ 256 KB read as text; `integration_receiver_secrets` (null ⇒ 404 `not_found`); verify; `integration_receiver_record`; 200 `{"external_id"}` or 401 `{"error":"invalid_signature"}`. Never logs the body. |

Tests: `xlsx.test.ts` (unzip with a minimal reader written in the test via `inflateRawSync`; valid central
directory; escaping), `file-templates.test.ts` (each template's headers; name split; missing values empty),
`webhook-verify.test.ts` (the spec vector of §4, stale timestamp, second secret, tampered body),
`api-v1-helpers.test.ts` (bearer parsing, limit/cursor parsing, error mapping), `openapi.test.ts` (3.1.0, five
paths, every `$ref` resolves).

---

## 6. Cross-package contracts (summary)

| Contract | Producer → consumer | Shape |
| --- | --- | --- |
| C-1 `integration_payload` | DB-A → DB-A/B | §3.2 |
| C-2 `claim_integration_deliveries(p_limit)` | DB-A → ORCH | §3.6 |
| C-3 `integration_delivery_payload(p_delivery_id, p_claim_token)` | DB-A → ORCH | §3.6 |
| C-4 `finish_integration_delivery(p)` | ORCH → DB-A | §3.6 |
| `integration_delivery_secrets(p_destination_id)` | DB-A → ORCH | `{secrets:[…]}` |
| `integration_dispatch(p_limit)`, `integration_reconcile(p_limit)`, `integration_health()`, `integration_propagation_alerts()` | DB-A → ORCH | §3.5, §3.8 |
| C-5 metrics, C-6 entity status, admin RPCs | DB-A → WEB-A/B | §3.7 |
| C-7/C-8 `api_v1_*` | DB-B → WEB-B | §3.10 |
| C-9 `integration_file_export` | DB-B → WEB-B | §3.10 |
| `integration_receiver_secrets`, `integration_receiver_record` | DB-A → WEB-B | §3.8 |
| `POST /integrations/kick` (bearer) → 202 `{queued:true}` | ORCH → WEB-A (`/api/integrations/kick`) | §4 |
| Webhook wire format | ORCH → any receiver / WEB-B receiver | headers `webhook-id`, `webhook-timestamp`, `webhook-signature`; body `{"type","timestamp","data"}` |

---

## 7. Work packages

Everyone on `develop` of their repo. DB packages verify with the replay before handing over
(`node run.mjs integration` for the new suites, then `node run.mjs` for all; the runner reads the repo's
`db/supabase` directly).

| Package | Owns (creates, or is the only editor of) | Depends on | Notes |
| --- | --- | --- | --- |
| **DB-A** | `db/supabase/migrations/20261114000000_integrations_core.sql`; tests `integration_core_test.sql`, `integration_attacker_test.sql`, `integration_delivery_test.sql` | this design | Full replay must stay green (all existing suites, notably the `personal_data_stores` registry test and `plan3_attacker_test.sql`). |
| **DB-B** | `db/supabase/migrations/20261114000100_integrations_api_exports.sql`; test `integration_api_test.sql` | DB-A merged (uses `integration_payload`, `integration_touch_link`, `integration_record_transfer`) | Written in parallel from §3.10; tested after A. |
| **ORCH** | `ai-orchestrator/src/integrations/**` (+ `__tests__`), `src/queue/index.ts`, `src/queue/plan4.test.ts`, `src/server.ts`, `src/ops/watchdog.ts` (+ its test), `.env.example` | C-2…C-4, §3.8 names | All with fake rpc/http. Deploy after A+B are in the target DB (missing RPCs are logged by the jobs, not fatal). |
| **WEB-A** | §5.1 (first commit), §5.2 files incl. `settings/page.tsx` and the three notice files, `app/api/integrations/kick/**`, its tests | §3.7, B's `api_key_*` | All against the contract. |
| **WEB-B** | §5.3 files incl. edits to `clients/page.tsx`, `segment-builder.tsx`, `client-detail.tsx`, `application-detail.tsx`, its tests | WEB-A step 1 | |
| **DOCS** | `docs/integrations.md` (new), `docs/supabase-schema.md`, `docs/architecture.md`, `docs/roadmap.md`, `docs/deployment.md`, `RUNBOOK.md` § "Integrations", `CLAUDE.md` (§9), `STATUS.md`/`plans/04-PLAN-STATE.md` after verification | all merged | |

Apply/deploy order: DB-A → DB-B on dev (`vtcrbrajexbsberrqwvo`) with the four suites through the TAP shim →
production rehearsal in a rolled-back transaction → production `apply_migration` A, B → web → orchestrator →
`graphify update .` per package. Nothing leaves until a tenant admin activates a destination; no seed.

---

## 8. Docs and `CLAUDE.md` invariants (DOCS)

`docs/integrations.md`: the canonical model (C-1 shapes), event catalog, webhook headers and verification (with
the spec vector and a 10-line Node verifier), retry/backoff table and circuit breaker, `/api/v1` (auth, scopes,
cursors, limits, errors, OpenAPI URL), file templates (column tables), privacy rules (D10–D14, D16, D18), the test
receiver, recipes, and what is out of scope (D28). `docs/supabase-schema.md`: § "Integrations (Plan 4)" with the
seven tables, grants and functions. `docs/architecture.md`: the integrations module and its three jobs.
`docs/deployment.md`: optional envs (none required). `RUNBOOK.md`: checking `/health/queue` → `integrations`,
`integration_health()`, re-enabling a destination in `error`, and the demo receiver.

Invariants to add to `CLAUDE.md`:
- **What leaves for a third party is decided by one database function, `integration_payload()`.** Webhooks, the
  public API and file exports all go through it; it applies the destination's scope, the sensitivity cap (only a
  superadmin approval with a recorded justification lets a sensitive key out), `processing_state = 'active'`, the
  `commercial_management` basis and, outside the tenant's country, `international_processing` consent. Never build
  a payload in TypeScript. Every disclosure writes `data_transfers`.
- **Integration secrets are never readable by an API role.** Webhook secrets live in Vault (or
  `integration_private` where Vault is absent) and are shown once; API keys are stored as sha256 only;
  `secret_ref`/`key_hash` are closed by column grants.
- **An erasure, limitation or revocation reaches every destination that holds the subject within 5 business days.**
  It is trigger-driven (`processing_state`, `consent_records`, rectification), recorded in `dsr_propagations` when a
  DSR is involved, and watched by the watchdog. Plan 4 extended the Plan 3 `_c` hooks by renaming them
  (`privacy_p3_*_c_base`); extend `privacy_p4_*` the same way, never `create or replace` a Plan 2 wrapper.
- **Outbound HTTP to tenant URLs goes through `src/integrations/ssrf.ts`:** https only, DNS resolved and pinned,
  private/link-local/metadata addresses refused, redirects never followed.

---

## 9. Demo script (presentation, tenant `seguros`, deployed site)

0. Before: warm web and orchestrator (`RUNBOOK.md`); sign in as a tenant_admin with MFA.
1. Configuración → **Integraciones**: show the catalog; open «HubSpot — vía webhook/API» recipe.
2. «Webhook» → wizard: name «CRM Ventas (demo)», country SV, tick the DPA declaration ⇒ draft.
3. «Qué enviar»: clientes + solicitudes, all events. «Datos»: default attributes; show «Salud — IMC» disabled
   («Dato sensible: no sale de Tramiq»).
4. «Conexión»: tick «Usar el receptor de prueba de Tramiq», «Generar secreto de firma» ⇒ copy-once dialog.
5. «Probar» ⇒ within seconds «Entregado · HTTP 200»; the receiver panel shows «Firma válida ✓» and the masked
   synthetic client.
6. «Activar» + «Enviar también los clientes existentes que cumplan» ⇒ destination page: metrics climb, log fills.
7. Open a client: badge «Sincronizado con «CRM Ventas (demo)» ✓». Open one whose commercial basis was revoked (or
   set «Tratamiento limitado» from Privacidad) ⇒ «No se envía: tratamiento limitado», and the log shows a
   `person.restricted` delivery.
8. Decide an application (approve) ⇒ «Enviar ahora» ⇒ `application.decided` in the log and in the receiver.
9. Privacidad → a DSR for erasure of a synced client ⇒ execute ⇒ «Enviar ahora» ⇒ log shows `person.erased`
   (delete), the DSR shows the propagation «Entregado a «CRM Ventas (demo)»…» completed, and the access report of
   another client lists the transfers.
10. «Rotar secreto» ⇒ new secret shown once, «El anterior sigue válido hasta …»; «Enviar prueba» still verifies.
11. «API REST» wizard ⇒ key shown once ⇒ `curl -H "Authorization: Bearer tq_live_…" <origin>/api/v1/persons?limit=5`
    and `/api/v1/events?after=0`; open `/api/v1/openapi.json`.
12. «Exportación de archivos» (HubSpot, XLSX) ⇒ Clientes → segment «Gestión comercial» ⇒ «Exportar para CRM» ⇒ open
    the file in Excel: HubSpot columns.
13. Configuración → aviso de privacidad: the new draft lists «CRM Ventas (demo)» as a recipient.

---

## 10. Risks and deliberate simplifications

- **Free tier sleeps.** Schedules do not fire while the orchestrator sleeps; «Enviar ahora», the wizard test and
  «Sincronizar ahora» wake it through `/api/integrations/kick`. Real latency on free tier is "next wake".
- **Dispatch serialization** (`pg_try_advisory_xact_lock`) caps throughput at one dispatcher; fine at demo scale and
  required for a gap-free `/events` cursor.
- **Coalescing loses intermediate states** by design (state sync); a receiver that wants every transition uses
  `/events`.
- **`/api/v1` lists scan and filter** (≤ 3×limit per page); pages may be short. Each read writes `data_transfers`
  rows — volume grows with polling; acceptable for the demo, revisit with aggregation.
- **Legitimate-interest reading of `commercial_management`** (D10) is an interpretation the owner should confirm.
- **Per-process rate limits** in web (as today); one Render instance.
- **The receiver is a public endpoint**; it stores only masked bodies, verifies signatures, keeps 20 rows, and is
  rate-limited; invalid requests are recorded without body.
- **Masking is cosmetic, not anonymization**: the log still reveals first letters and domains to tenant_admins who
  can read the full client anyway.
- **Not built:** native connectors, mapping editor, OAuth, SFTP, inbound CRM-9, retention propagation, application
  file templates, per-destination rate limiter beyond the circuit breaker (`Retry-After` covers 429s).
- **Vault path is not exercised by CI/replay**; first run on dev is the test (Q2).

---

## 11. Questions for the conductor

1. Confirm D10 with the owner: `commercial_management` treated as legitimate interest unless the tenant sets
   `requires_consent = true`; a recorded refusal/revocation always blocks. (Alternative: always require a granted
   consent — then no seeded client is eligible until consents are recorded, which changes the demo.)
2. On dev and prod, as `postgres`: can it `select decrypted_secret from vault.decrypted_secrets` and `delete from
   vault.secrets`? (Creation was confirmed.) If not, DB-A keeps Vault for writes only and the conductor decides
   whether to fall back to `integration_private` everywhere.
3. Does the seeded demo data in `seguros` have clients with `commercial_management` refusals and with
   `international_processing` grants, so step 7 of the demo has both cases? If not, the conductor records them
   through the existing consent screens before the presentation.
4. Is the deployed web origin stable (custom domain vs `*.onrender.com`)? The test receiver URL stored in
   `config.url` embeds it; a domain change means editing the destination.
