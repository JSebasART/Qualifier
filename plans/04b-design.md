# Plan 4b — technical design (native CRM connectors, mapping versions, the remaining gaps)

*2026-11-15. Implementation design for the parts of [`04-exportacion-a-crm.md`](04-exportacion-a-crm.md) left out of
the first round ([`04-design.md`](04-design.md), in production since 2026-11-15), under the owner decision of
2026-11-15 ([`04-PLAN-STATE.md`](04-PLAN-STATE.md) row 23): **CRM-5 HubSpot, CRM-6 Dynamics 365 (Dataverse), CRM-7
Odoo** on a common adapter interface, the **mapping editor with immutable mapping versions**, **application-level
file templates**, **propagation of retention anonymizations**, and the **segment-builder premature error**. Out of
scope: CRM-9 inbound, OAuth apps / marketplace, a native Salesforce adapter, Nango. Audience: sonnet implementation
agents who have not read the plan; nothing below is to be re-decided. Where this file changes the plan it says
**⚠ deviation**. Schema keys English, UI Spanish, migrations append-only. Never open `qualifier-secrets.env.txt`;
never point a local process at a Supabase project. Run `graphify query "<question>"` before the first grep or
source read of a codebase question, and put that rule in every subagent prompt.*

Conventions are those of `04-design.md` (header): "admin" = `require_privacy_admin(tenant)` (MFA gate included)
reached through `integration_destination_admin(id)`; "service-only" = revoked from `public, anon, authenticated`,
granted to `service_role`; every new definer function is `language plpgsql security definer set search_path =
public` (pure helpers `set search_path = ''`); error codes `P0002` / `42501` / `22023` with stable lower-case
messages; every new table and function revoked from `public, anon` explicitly. "Push kinds" = `webhook, hubspot,
dynamics, odoo` (the engine delivers to them); "native kinds" = `hubspot, dynamics, odoo`.

**API facts were checked on 2026-11-15** against: HubSpot contacts/deals/properties guides (date-versioned
`/crm/objects/2026-09/…`, batch upsert with per-input `idProperty`, 100 records per batch), HubSpot usage guidelines
(private apps 100 req/10 s Free/Starter, 190 Pro/Enterprise; 250 000–1 000 000/day; 429 body
`{status, message, errorType:"RATE_LIMIT", policyName, correlationId}`, no `Retry-After` documented), HubSpot
`POST /oauth/v2/private-apps/get/access-token-info`, the contacts GDPR delete reference
(`POST /crm/v3/objects/contacts/gdpr-delete`); Dataverse "Update and delete table rows" (upsert = `PATCH
set(key='v')`, `Prefer: return=representation` ⇒ 201 created / 200 updated, key values not in the body), "Perform
conditional operations" (`If-Match: *` prevents create ⇒ 404 when absent), "Service protection API limits" (6 000
requests / 1 200 s execution / 52 concurrent per user per web server in a 300 s window; 429 with `Retry-After`
seconds; hex codes `0x80072322`, `0x80072321`, `0x80072326`); Odoo 19 External JSON-2 API (`POST
/json/2/<model>/<method>`, `Authorization: bearer <key>`, optional `X-Odoo-Database`, named arguments + `ids` +
`context`, error JSON `{name, message, arguments, context, debug}`, one transaction per call, `/xmlrpc`, `/xmlrpc/2`,
`/jsonrpc` removed in Odoo 22 and Odoo Online 21.1). Facts **not** confirmed by a fetched page are marked
**(pin by fixture)**: the implementer records them in the fixture's `source` and keeps them configurable.

---

## 1. Decisions

| # | Point | Decision | Why |
| --- | --- | --- | --- |
| E1 | Kinds | `integration_destinations.kind` gains `hubspot`, `dynamics`, `odoo`. `salesforce` stays a file template + recipe. | Owner scope. |
| E2 | Where CRM calls run | **Only the orchestrator talks to a CRM**, for deliveries *and* for the wizard's `verify/describe/provision`. web asks the DB for a **connector op** (admin + MFA gate there), then asks the orchestrator to run it by id. The orchestrator reads credentials through a service RPC and writes the result back through another. | The DB stays the authorization boundary; credentials never reach web; one SSRF-guarded transport. |
| E3 | Payload | Adapters receive C-3's canonical `tramiq.crm.v1` payload and the published mapping; they **project** it (rename, transform, constants), never add client data. The DB adds *link context* (CRM ids already known) and `tenant_country`, no client data. `integration_payload()` is **not** replaced. | Single builder invariant. |
| E4 | Credentials | One JSON secret per destination in Vault (fallback `integration_private.secrets`) via the existing `integration_secret_store/read/drop`, referenced by the existing `secret_ref`. Non-secret parts (org URL, Entra tenant and client id, Odoo URL/database/login) in `config`. `credential_hint` (last 4 chars) is the only thing shown again. Replacing credentials drops the old secret at once (no overlap: the CRM, not Tramiq, issues them). | Reuses Plan 4's store and its suites' guarantees. |
| E5 | Mapping | `integration_mapping_versions` (draft → published → archived), JSON definition §3.4, **immutable once published** (trigger + functions), one published per destination (`integration_destinations.mapping_version_id`), validated in SQL against scope **and** the latest `describe` result. Every delivery, attempt and link records the mapping version. Publishing re-arms every link (state sync under the new mapping). | Playbook pattern; "every decision records the version" extended to disclosures. |
| E6 | Default mappings | Suggestions are web TS (`mapping-defaults.ts`), filled with ids from `describe()`; only what the admin publishes is data. | They are formats of other people's software, as file templates are. |
| E7 | Upsert keys | HubSpot: batch upsert (1 input per call) by unique custom property `tramiq_client_id` / `tramiq_application_id`. Dataverse: `PATCH contacts(tramiq_clientid='<uuid>')` by alternate key. Odoo: link id → `write`; else `search_read` on `x_tramiq_*_id` → `write` or `create`. | Plan §8; no duplicates by construction. |
| E8 | Batching | **⚠ deviation:** one record per request (HubSpot batch endpoint with one input, no Dataverse `$batch`). | Per-delivery finish/lease semantics stay exact; demo volumes (≤ 5 000) fit the limits. |
| E9 | Ordering of person → application | An application whose person is not yet in the CRM ends with new outcome **`deferred`** (retry in 60 s, no circuit-breaker count, dead after 24 h). HubSpot/Odoo look the person up by key before deferring. | Coalesced deliveries have no order. |
| E10 | Decision note | When `mapping.application.decision_note = true` and the canonical `decision` changed (hash in `link.external_refs.note_decision_hash`): HubSpot note on the deal, Dataverse `annotation`, Odoo `message_post` (internal note). Text built from `decision` fields only, Spanish labels, never `case_decisions.note` (not in the payload). | Plan §8; idempotent. |
| E11 | Erasure | HubSpot contact: `gdpr-delete` (permanent); deal: archive (`DELETE`, recycle bin — the API offers no purge; documented). Dataverse: `DELETE`. Odoo: `unlink`; if refused (`ValidationError`/`UserError`, linked accounting) ⇒ anonymize + archive (`active=false`, name «Suprimido», contact fields cleared), `external_refs.erasure_mode = 'anonymized'`. 404 on delete ⇒ `delivered` (already gone). | Plan §8; a partner with invoices cannot be unlinked in Odoo. |
| E12 | Restriction | Marker property set true (HubSpot `tramiq_restricted`, Dataverse `tramiq_restricted`, Odoo `x_tramiq_restricted`) with "update only" semantics; every upsert writes it `false`. Restrict of a missing record ⇒ `delivered`. | Plan §8 `restrict?`. |
| E13 | Provisioning | HubSpot: property group `tramiq` + properties via the properties API. Dataverse: **⚠ deviation:** Web API metadata calls (publisher `tramiq`, solution `TramiqConnector`, columns, alternate keys, `PublishXml`) instead of shipping a solution package; when the application user lacks customization privileges, verify says so and the screen lists the columns to create by hand. Odoo: `ir.model.fields` create (needs Settings/Administration); otherwise manual Studio instructions. The `tramiq_connector` Odoo module is out of scope. | Testable with recorded responses; no hand-built solution zip. |
| E14 | Limits | Orchestrator token bucket per destination (HubSpot 80/10 s, concurrency 4; Dataverse 150/10 s, concurrency 4; Odoo 20/10 s, concurrency 1) + an **in-run gate**: after a `rate_limited` or `auth` answer the rest of that destination's claimed rows finish the same way without a call. The persistent breaker stays the DB's (5 consecutive ⇒ 10 min). `deferred` never counts. | Plan §8 limits; DB keeps the durable state. |
| E15 | SSRF | Every outbound request (CRM, Entra) goes through one transport: `checkUrl` + `resolvePublic` + pinned lookup + no redirects (Plan 4 D22), generalized to GET/POST/PATCH/PUT/DELETE and a per-call response cap. HubSpot host fixed `api.hubapi.com`; Entra fixed `login.microsoftonline.com`; Dataverse `config.org_url` must match `^https://[a-z0-9][a-z0-9-]{0,62}\.crm[0-9]{0,2}\.dynamics\.com$` (DB on save **and** adapter); Odoo URL arbitrary, light check in DB, full guard at send. Non-https Odoo is refused. | Task rule. |
| E16 | Errors to the DB | `error` text = stable code + `HTTP <s>` + at most CRM *property names* (never values, never bodies). New finish field `auth_reason` (`auth_failed` \| `permission_missing`) ⇒ `status_reason`. | Bodies echo personal data. |
| E17 | Entra tokens | Cached in orchestrator memory per `destination_id:credentials_set_at`, refreshed 5 min before expiry, single-flight; one forced refresh on a Dataverse 401 before classifying `auth`. Never persisted, never logged. | Credentials-change invalidates by key. |
| E18 | Demo without CRM accounts | **⚠ addition (Q1):** `config.sandbox = true` (any native kind) swaps the network transport for an in-process **simulated CRM** that implements exactly the endpoints the adapter calls, with the response shapes of the fixtures; no socket is opened; state in orchestrator memory (ids only + masked values). Everything else (DB contract, mapping, links, transfers, propagation) is the real path. Locked after draft like `country`. Labelled «CRM simulado» everywhere. | No real accounts exist; the presentation needs flows that work end to end. Contract tests remain the verification of the real APIs. |
| E19 | Retention propagation | **No wrapper replaced:** `privacy_p4_erase` (a Plan 4 hook, not a Plan 2 wrapper) is renamed `privacy_p4_erase_base` and re-created as `base || privacy_p4_erase_retention(...)`. The retention path is recognized by its arguments (`p_simulate = false`, no client ids, ≥ 1 application id — the only call shape `privacy_anonymize_applications` makes outside an erasure). Push destinations holding the application get `delete` or `restrict` (`config.retention_action`, default `delete`) with `reason 'retention'` and `due_on`; API/file destinations get an `integration_manual_tasks` row with the same deadline; no `dsr_propagations` (no DSR). Retired applications are recorded and never sent again (`retention_expired`). | Task 3b; `dsr_propagations.dsr_id` is NOT NULL. |
| E20 | Application file export | New RPC `integration_file_export_applications` (the persons RPC is untouched); file destinations may now scope `application`; web templates for HubSpot deals, Dynamics opportunity/lead, Odoo opportunity, Salesforce opportunity/lead. | Task 3a. |
| E21 | Core function changes | **22 functions of the Plan 4 migrations are `create or replace`d** in the new migrations (list §3.6), each a verbatim copy with the listed edits only. None is a Plan 2/3 wrapper or Plan 4's `privacy_p3_*_c` wrapper. | The `kind = 'webhook'` predicates are spread through them; one helper `integration_kind_pushes()` replaces them. |
| E22 | Webhook retention payload | A retention `delete` reaches webhooks as `{"deleted":true,"reason":"erasure"}` (the builder maps unknown reasons to `erasure`); the delivery row and the log say `retention`. | Keeps `integration_payload()` unreplaced (Q4). |
| E23 | Segment builder | Value errors (`bad_value`) show only after the row's value was touched or a save was attempted; every other code shows at once. | Task 3c. |

---

## 2. Replay, CI, Vault

Unchanged from Plan 4 §2: PGlite replay and CI have no Vault and no `vector`; credentials go to the fallback store
there; suites assert behaviour (an admin cannot read either store, `integration_connector_credentials` returns what
was set), and guard Vault-specific checks with `if integration_vault_available()`. No `CONCURRENTLY`, no pg_cron,
no extension creation. A credential JSON is stored as text (`p_credentials::text`, ≤ 20 000 chars).

---

## 3. Database (package DB-4B)

Two migrations, each one transaction, applied in order:

- **A** `db/supabase/migrations/20261115000100_crm_connectors.sql` — kinds, credentials, connector ops, mapping
  versions, the delivery-contract extensions, 19 replaced functions.
- **B** `db/supabase/migrations/20261115000200_crm_retention_files.sql` — retired applications, manual tasks, the
  retention hook, application file export, 3 replaced functions.

### 3.1 A — schema changes

```sql
-- Constraint swaps: inline checks are auto-named; drop by column, not by guessed name.
-- do-block: for each (table, column) in (integration_destinations.kind, integration_destinations.status_reason,
-- integration_deliveries.reason, integration_delivery_attempts.outcome, integration_links.via) drop the CHECK whose
-- conkey is that single column, then add the named one below.
alter table integration_destinations add constraint integration_destinations_kind_check
  check (kind in ('webhook','api_pull','file_export','hubspot','dynamics','odoo'));
alter table integration_destinations add constraint integration_destinations_status_reason_check
  check (status_reason in ('auth_failed','endpoint_gone','url_not_allowed','disconnected_by_admin','permission_missing'));
alter table integration_deliveries add constraint integration_deliveries_reason_check
  check (reason in ('erasure','consent_revoked','restricted','rectification','disconnect','no_longer_eligible','retention'));
alter table integration_delivery_attempts add constraint integration_delivery_attempts_outcome_check
  check (outcome in ('delivered','transient','rate_limited','auth','validation','blocked','skipped','unchanged','deferred'));
alter table integration_links add constraint integration_links_via_check check (via in ('webhook','api','file','crm'));

alter table integration_destinations
  add column credential_hint text check (credential_hint ~ '^••••.{1,4}$'),
  add column verified_at timestamptz,
  add column verify_status text check (verify_status in ('ok','missing_permissions','failed')),
  add column connector_meta jsonb not null default '{}' check (jsonb_typeof(connector_meta) = 'object'),
  add column mapping_version_id uuid;            -- FK added after the versions table
alter table integration_deliveries add column mapping_version_id uuid;
alter table integration_delivery_attempts add column mapping_version_id uuid,
  add column external_url text check (external_url ~ '^https://' and length(external_url) <= 500);
alter table integration_links add column external_refs jsonb not null default '{}' check (jsonb_typeof(external_refs) = 'object'),
  add column mapping_version_id uuid;

create table integration_mapping_versions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  destination_id uuid not null,
  version integer not null check (version >= 1),
  status text not null default 'draft' check (status in ('draft','published','archived')),
  definition jsonb not null check (jsonb_typeof(definition) = 'object' and pg_column_size(definition) <= 65536),
  issues jsonb not null default '[]',          -- last validation, [{code,path,detail}]
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  published_by uuid references auth.users (id) on delete set null, published_at timestamptz,
  unique (destination_id, version), unique (tenant_id, id),
  constraint integration_mapping_versions_destination_same_tenant foreign key (tenant_id, destination_id)
    references integration_destinations (tenant_id, id) on delete cascade,
  check ((status = 'draft') = (published_at is null)));
create unique index integration_mapping_one_published on integration_mapping_versions (destination_id) where status = 'published';
create unique index integration_mapping_one_draft on integration_mapping_versions (destination_id) where status = 'draft';
alter table integration_destinations add constraint integration_destinations_mapping_fk
  foreign key (mapping_version_id) references integration_mapping_versions (id) on delete set null;

create table integration_connector_ops (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null, destination_id uuid not null,
  op text not null check (op in ('verify','describe','provision')),
  status text not null default 'pending' check (status in ('pending','running','done','failed')),
  requested_by uuid references auth.users (id) on delete set null,
  requested_at timestamptz not null default clock_timestamp(),
  credentials_set_at timestamptz,               -- destination.secret_set_at when requested
  claim_token uuid, started_at timestamptz, finished_at timestamptz,
  result jsonb check (result is null or (jsonb_typeof(result) = 'object' and pg_column_size(result) <= 1048576)),
  error text check (length(error) <= 300),
  constraint integration_connector_ops_destination_same_tenant foreign key (tenant_id, destination_id)
    references integration_destinations (tenant_id, id) on delete cascade);
create index integration_connector_ops_dest on integration_connector_ops (destination_id, op, requested_at desc);
```

Triggers: `set_updated_at` on mapping versions. **`integration_mapping_versions_guard()`** (invoker, `search_path
''`) BEFORE UPDATE: `old.status = 'draft'` ⇒ allow (except `tenant_id/destination_id/version` changes ⇒ raise);
`old.status = 'published'` ⇒ only `status → 'archived'` with every other column equal (`updated_at` excepted);
`old.status = 'archived'` ⇒ raise `mapping_version_immutable`. Same message for any `definition` change of a
non-draft. DELETE is not blocked (cascade from the destination; no role but `service_role` can delete).

RLS (A): enabled on both new tables; policy shape of Plan 4 (`tenant_admin` of the tenant, or superadmin) for
`select`. `revoke all … from public, anon, authenticated`; `grant select on integration_mapping_versions to
authenticated`; `grant select (id, tenant_id, destination_id, op, status, requested_by, requested_at, started_at,
finished_at, result, error) on integration_connector_ops to authenticated` (no `claim_token`);
`grant select (credential_hint, verified_at, verify_status, connector_meta, mapping_version_id) on
integration_destinations to authenticated`; `grant select (mapping_version_id) on integration_deliveries to
authenticated`; service_role all. No new table has a `client_id/email/phone/national_id/full_name/form_data/
extracted_data` column ⇒ no `personal_data_stores` row (registry test stays green). Connector results never hold
personal data: adapters strip user names/e-mails from verify answers (§4.5).

### 3.2 Config and credential shapes (validated in `integration_destination_save` / `integration_set_credentials`)

| kind | `config` keys (others ⇒ `invalid_config`) | `credentials` JSON (secret) | hint |
| --- | --- | --- | --- |
| webhook | `url`, `test_receiver`, **`retention_action`** | — (rotate_secret as today) | — |
| api_pull | — | — | — |
| file_export | `template`, `format`, **`application_object`** (`opportunity`\|`lead`, default `opportunity`) | — | — |
| hubspot | `api_version` (`^20[0-9]{2}-(03|09)$`, default `'2026-09'`), `sandbox` (bool), `retention_action` | `{"token": "^pat-[a-z0-9]+-[A-Za-z0-9-]{20,200}$"}` | last 4 of token |
| dynamics | `org_url` (E15 regex, no trailing slash), `entra_tenant_id` (uuid or `^[a-z0-9-]+(\.[a-z0-9-]+)+$`), `client_id` (uuid), `auth` (`secret`\|`certificate`), `application_object` (`opportunities`\|`leads`, default `opportunities`), `sandbox`, `retention_action` | `{"client_secret": 8–512 chars}` or `{"certificate_pem": "-----BEGIN CERTIFICATE-----…", "private_key_pem": "-----BEGIN (RSA )?PRIVATE KEY-----…"}` (each ≤ 8 000) — must match `config.auth` | last 4 of secret / of the cert's base64 body |
| odoo | `url` (same FQDN light check as webhook URLs, https), `database` (`^[A-Za-z0-9_.-]{1,63}$`), `login` (1–120, required when `protocol = 'xmlrpc'`), `protocol` (`auto`\|`json2`\|`xmlrpc`, default `auto`), `sandbox`, `retention_action` | `{"api_key": 20–200 chars}` | last 4 |

`retention_action` ∈ (`delete`, `restrict`), default `delete`. `sandbox` and `country` are locked once the
destination leaves draft (`sandbox_locked`, `country_locked`). Sandbox credentials only need to match the format.

### 3.3 A — new functions

| Signature | Kind | Behaviour / JSON |
| --- | --- | --- |
| `integration_kind_pushes(p_kind text) returns boolean` | immutable, `search_path ''`, authenticated+service | `p_kind in ('webhook','hubspot','dynamics','odoo')` |
| `integration_set_credentials(p_destination_id uuid, p_credentials jsonb) returns jsonb` | admin | native kind, not disconnected; shape per §3.2 (`invalid_credentials` with `detail` = field name, never the value); `v_ref := integration_secret_store('integration:'||id, p_credentials::text)`; drop old `secret_ref`; set `secret_ref, secret_set_at = now(), credential_hint, verified_at = null, verify_status = null`. Audit `integration.credentials_set` `{kind}`. ⇒ `{"set_at":"ts","hint":"••••a1b2"}` |
| `integration_connector_request(p_destination_id uuid, p_op text) returns uuid` | admin | native kind, not disconnected, `secret_ref` set (`no_credentials`). Reuses a `pending`/`running` op of the same kind younger than 2 min; > 30 ops per destination in the last hour ⇒ `too_many_requests` (22023). Inserts `pending` with `credentials_set_at = secret_set_at`. Audit `integration.connector_op_requested` `{op}`. |
| `integration_connector_op_get(p_op_id uuid) returns jsonb` | admin (via the op's destination) | `{"id","op","status","result","error","requested_at","finished_at"}` |
| `claim_integration_connector_op(p_op_id uuid) returns jsonb` | service | `pending` and `requested_at > now() - 10 min` ⇒ `running`, `claim_token`, `started_at`; else `null`. ⇒ **C-10** `{"op_id","claim_token","op","destination_id","kind","config","connector_meta","credentials":{…},"credentials_set_at","sandbox":bool}` |
| `finish_integration_connector_op(p jsonb) returns jsonb` | service | `p = {op_id, claim_token, status: done|failed, result?, error?, connector_meta?}`; token mismatch ⇒ `22023 claim_lost`. Stores result/error, `finished_at`. `verify` done ⇒ destination `verified_at = now()`, `verify_status = result.ok ? 'ok' : (result.missing ≠ [] ? 'missing_permissions' : 'failed')`, `connector_meta = connector_meta || <allowed keys of p.connector_meta>` (§4.5 list; other keys dropped). `verify` failed ⇒ `verify_status 'failed'`. Audit `integration.connector_op_finished` `{op, status}`. ⇒ `{"status"}` |
| `integration_connector_credentials(p_destination_id uuid) returns jsonb` | service | **C-11** `{"kind","config","connector_meta","credentials":{…}\|null,"credentials_set_at","sandbox"}` — `credentials` = `integration_secret_read(secret_ref)::jsonb` |
| `integration_describe_cache(p_destination_id uuid) returns jsonb` | stable, service (internal) | `result` of the latest `done` describe op, plus `"stale": finished_at < secret_set_at`; `null` if none |
| `integration_mapping_sources(p_kind text, p_entity text, p_scope jsonb) returns text[]` | immutable, authenticated+service | §3.4 source list for the scope |
| `integration_mapping_validate(p_destination_id uuid, p_definition jsonb) returns jsonb` | admin | `[{"code","path","detail"}]` per §3.4 (empty = valid) |
| `integration_mapping_save_draft(p_destination_id uuid, p_definition jsonb) returns jsonb` | admin | native kind, not disconnected; upserts the single draft (`version = coalesce(max,0)+1` on insert), stores `issues` (a draft may be invalid). Audit `integration.mapping_saved`. ⇒ `{"id","version","issues":[…]}` |
| `integration_mapping_publish(p_version_id uuid) returns jsonb` | admin | draft only; revalidates — any issue ⇒ `22023` message = first code, `detail` = issues JSON. In one transaction: published → archived; draft → published (`published_by/at`); destination `mapping_version_id`. If the destination is `active`: `integration_enqueue(…,'upsert', 'person.upserted' \| 'application.status_changed')` for every link (≤ 5 000). Audit `integration.mapping_published` `{version, resync}`. ⇒ `{"version":n,"resync_queued":n}` |
| `integration_mapping_discard(p_version_id uuid) returns void` | admin | drafts only (else `mapping_version_immutable`); deletes it. |

### 3.4 Mapping definition (contract M-1; DB validates, ORCH applies, WEB-B edits)

```json
{"version": 1,
 "objects": {
   "person": {"target": "contacts", "id_property": "tramiq_client_id", "restricted_property": "tramiq_restricted",
     "fields": [
       {"from": "attributes.identity.full_name", "to": ["firstname", "lastname"], "transform": "split_name"},
       {"from": "attributes.contact.email", "to": "email"},
       {"from": "attributes.contact.phone", "to": "phone", "transform": "phone_e164"},
       {"to": "lifecyclestage", "transform": "constant", "value": "lead"}]},
   "application": {"target": "deals", "id_property": "tramiq_application_id", "restricted_property": "tramiq_restricted",
     "associate_to": "person", "decision_note": true,
     "fields": [
       {"to": "dealname", "transform": "template", "template": "Solicitud N.º {number} — {product.name}"},
       {"to": "pipeline", "transform": "constant", "value": "default"},
       {"from": "status", "to": "dealstage", "transform": "enum_map",
        "map": {"submitted": "appointmentscheduled", "manual_review": "qualifiedtobuy", "approved": "closedwon",
                "declined": "closedlost", "withdrawn": "closedlost"}},
       {"from": "decision.sum_insured", "to": "amount", "transform": "money_number"}]}}}
```

- **`from` grammar** (**⚠ deviation:** attribute sources are prefixed `attributes.`, form keys `form.`, so dotted
  attribute keys are unambiguous): person `id, tenant_ref, updated_at, profile_version, privacy.processing_state,
  privacy.under_rectification, links.tramiq_path, attributes.<k ∈ scope.attributes>`; application `id, number,
  person_id, product.id, product.code, product.name, status, channel, submitted_at, updated_at, links.tramiq_path,
  form.<k ∈ scope.form_keys>`, `score.final_score, score.tier` (only `include_score`), `decision.decision,
  decision.decided_at, decision.sum_insured, decision.reason_codes` (only `include_decision`). Template placeholders
  `{path}` use the same grammar.
- **Targets** per kind: hubspot person `contacts`, application `deals`; dynamics person `contacts`, application
  `opportunities` \| `leads` (must equal `config.application_object`); odoo person `res.partner`, application
  `crm.lead`. `id_property` / `restricted_property` defaults: hubspot `tramiq_client_id` / `tramiq_application_id`,
  `tramiq_restricted`; dynamics `tramiq_clientid` / `tramiq_applicationid`, `tramiq_restricted`; odoo
  `x_tramiq_client_id` / `x_tramiq_application_id`, `x_tramiq_restricted`.
- **Transforms** (ORCH semantics, §4.3): `none` (default), `split_name` (`to` = 2-element array), `phone_e164`
  (`default_country_code?` digits), `date_iso`, `date_epoch_ms` (`midnight?` bool), `enum_map` (`map` ≤ 50 entries,
  values string or integer; `default?`), `template` (`template` ≤ 300 chars), `money_number`, `uppercase`, `constant`
  (`value` string/number/boolean ≤ 200, no `from`). `to` is a string except for `split_name`.
- **Limits:** ≤ 60 fields per object; `to` names `^[A-Za-z_][A-Za-z0-9_.@]{0,99}$`.
- **Validation codes** (`integration_mapping_validate`, in this order per object): `bad_definition`,
  `object_not_in_scope` (object for an entity not in `scope.entities`), `object_missing` (entity in scope without
  object), `target_not_allowed`, `describe_missing` (no done describe), `id_property_missing` (not in describe),
  `id_property_not_unique` (HubSpot `hasUniqueValue` false), `id_property_not_ready` (Dataverse key status ≠
  `Active`), `restricted_property_missing`, `transform_unknown`, `transform_params`, `unknown_source`,
  `source_not_in_scope`, `unknown_target_field`, `target_read_only`, `reserved_target` (id/restricted property or
  `@odata.bind` written by a field), `duplicate_target`, `transform_type_mismatch` (`date_*` ⇒ date/datetime;
  `money_number` ⇒ number; `enum_map` ⇒ enum/number/string), `enum_value_unknown` (enum target whose describe
  options lack a mapped value), `required_target_missing` (describe `required` writable fields not produced,
  excluding system-filled ones listed in the describe result's `auto_filled`). `path` = `objects.person.fields[3].to`
  style; `detail` = the offending name. Warnings are not issued: everything listed blocks publication.

`integration_destination_save` (replaced, §3.6) refuses `mapping_object_missing` when a native destination with a
published mapping adds an entity the mapping has no object for.

### 3.5 A — delivery-contract extensions (C-2/C-3/C-4 v2; the webhook path is unchanged byte for byte)

**C-2** `claim_integration_deliveries` rows gain `"kind"`; `url` is `null` for native kinds.

**C-3** `integration_delivery_payload` (replaced) — for push kinds other than webhook:
```json
{"status":"ok","type":"application.decided","webhook_id":"msg_…","payload":{…},"hash":"…","unchanged":false,
 "kind":"hubspot","mapping_version_id":"uuid","mapping":{…objects.<entity> of the published definition…},
 "link":{"external_id":"512","external_refs":{"note_decision_hash":"…"}},
 "person_link":{"external_id":"901"},          // application entity only: the person's link at this destination, or null
 "tenant_country":"SV","sandbox":false}
{"status":"skipped","reason":"no_mapping"}      // native destination without a published mapping object for the entity
```
`entity = 'test'` uses `objects.person`. The delivery row stores `mapping_version_id`. `unchanged` =
`upsert` and `link.last_synced_hash = hash` **and** `link.mapping_version_id is not distinct from` the current
version and `restricted_at is null`.

**C-4** `finish_integration_delivery` (replaced) input gains `"auth_reason": "auth_failed|permission_missing|null"`
and `"external_refs": {…}` (keys `associated_person, note_id, note_decision_hash, erasure_mode, crm_object` only;
string values ≤ 200; others dropped). Changes to the outcome table of Plan 4 §3.6:

| outcome | change |
| --- | --- |
| `delivered` | link `via = case kind when 'webhook' then 'webhook' else 'crm' end`; after `integration_touch_link`: `external_refs = external_refs || p.external_refs`, `mapping_version_id = delivery.mapping_version_id`. Transfer reference: webhook unchanged; native `'crm:'||kind||':'||coalesce(external_id, entity_id)` (`'crm:'||kind||':sandbox:'||…` in sandbox). DSR evidence for native kinds: delete `Eliminado en «<name>» (<HubSpot\|Dynamics 365\|Odoo>, HTTP <s>, id <ext>) el <ts>`, restrict `Marcado como limitado en «<name>» …`, rectification `Actualizado en «<name>» …`; `erasure_mode = 'anonymized'` ⇒ `Anonimizado y archivado en «<name>» …`. `test` entity: attempt `external_url` = p.external_url. |
| `deferred` (new) | delivery `failed`, `next_attempt_at = now() + coalesce(retry_after clamp, 60 s)`; `dead` past `first_attempt_at + 24 h`; **no** `consecutive_failures` change. |
| `auth` | `status_reason = case when http 410 then 'endpoint_gone' when auth_reason = 'permission_missing' then 'permission_missing' else 'auth_failed' end`. |
| `skipped` | re-arm list for `delete` gains `retention_expired` (or `restrict` when `config.retention_action = 'restrict'` and the link is not restricted). |

Every attempt row gets the delivery's `mapping_version_id`.

### 3.6 Replaced functions (verbatim copies with exactly these edits; ⇒ E21)

| Function (source migration) | Edit |
| --- | --- |
| `integration_scope_normalize` (core) | file_export keeps `entities` as given (default `["person"]`), no forcing. |
| `integration_scope_check` (core) | drop `(p_kind = 'file_export' and v <> 'person')`. |
| `integration_scope_validate` (core) | kind list = 6 kinds. |
| `integration_events_enabled` (core) | `d.kind in ('webhook','api_pull','hubspot','dynamics','odoo')`. |
| `clients_integration_deleting`, `applications_integration_deleting` (core) | `d.kind = 'webhook'` ⇒ `integration_kind_pushes(d.kind)`. |
| `integration_targets` (core) | all five `d.kind = 'webhook'` ⇒ `integration_kind_pushes(d.kind)`. |
| `integration_dispatch` (core) | manual branch: `(d.kind in ('api_pull','file_export') or (integration_kind_pushes(d.kind) and d.status = 'disconnected'))`. |
| `integration_touch_link` (core) | `p_via` accepts `crm`. |
| `claim_integration_deliveries` (core) | + `'kind', x.kind`; `url` only for webhook. |
| `integration_delivery_payload` (core) | §3.5 C-3. |
| `finish_integration_delivery` (core) | §3.5 C-4. |
| `integration_destination_save` (core) | 6 kinds; §3.2 config validation; `sandbox_locked`; Dataverse regex; `mapping_object_missing`. |
| `integration_set_status` (core) | `draft→active` for native: `dpa_attested_at`, scope ok, `secret_ref`, `verify_status = 'ok' and verified_at >= secret_set_at`, `mapping_version_id`; `not_ready` with `detail` = JSON array of missing items among `dpa, scope, credentials, verify, mapping, url, secret, template`. `error→active` unchanged. |
| `integration_send_test` (core) | native: `secret_ref`, verify ok, published mapping (else `not_ready` + detail). |
| `integration_initial_sync`, `integration_resync_entity` (core) | `d.kind = 'webhook'` ⇒ `integration_kind_pushes(d.kind)`. |
| `integration_disconnect` (core) | deletion request for any push kind; credentials (secret_ref) dropped as the webhook secret is. |
| `integration_reconcile` (core) | push kinds; re-arm `upsert` also when `link.mapping_version_id is distinct from d.mapping_version_id` (native); `retention_expired` ⇒ `delete`/`restrict` per `retention_action`; mark `pending/running` connector ops older than 10 min `failed` (`expired`); prune connector ops older than 7 days except the latest done of each `(destination, op)`. Return adds `ops_expired`, `ops_pruned`. |
| `integration_eligibility` (**B**) | after the `not_found` checks: application in `integration_retired_applications` ⇒ `retention_expired`. |
| `integration_destination_metrics` (**B**) | `propagations_open/overdue` add open `integration_manual_tasks`; + `"manual_tasks_open":n`. Manual DSR branch uses the push-kind predicate. |
| `integration_propagation_alerts` (**B**) | union open manual tasks (`due_on`). |

Grant block (A and B): the Plan 4 `do $$ … $$` pattern (revoke from all four roles, grant by list, fail on a missing
name) over every function each migration creates or replaces. Authenticated: `integration_set_credentials,
integration_connector_request, integration_connector_op_get, integration_mapping_validate,
integration_mapping_save_draft, integration_mapping_publish, integration_mapping_discard` (+ B:
`integration_manual_task_done, integration_file_export_applications`) plus the replaced admin RPCs; both:
`integration_kind_pushes, integration_mapping_sources` and the replaced pure helpers; service: the rest; trigger
functions: none.

### 3.7 B — retention propagation, manual tasks, application files

```sql
create table integration_retired_applications (
  tenant_id uuid not null references tenants (id) on delete cascade,
  application_id uuid primary key,              -- no FK: the row outlives a later hard delete
  reason text not null default 'retention' check (reason in ('retention')),
  retired_at timestamptz not null default now());
create table integration_manual_tasks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null, destination_id uuid not null,
  entity text not null check (entity in ('person','application')), entity_id uuid not null,
  action text not null check (action in ('delete','restrict')),
  reason text not null check (reason in ('retention')),
  due_on date not null, created_at timestamptz not null default now(),
  done_at timestamptz, done_by uuid references auth.users (id) on delete set null,
  evidence text check (length(evidence) between 5 and 500),
  constraint integration_manual_tasks_destination_same_tenant foreign key (tenant_id, destination_id)
    references integration_destinations (tenant_id, id) on delete cascade);
create unique index integration_manual_tasks_open on integration_manual_tasks (destination_id, entity, entity_id, reason)
  where done_at is null;
```
RLS: manual tasks select for admins (Plan 4 shape); retired applications **no policy, no grant** to authenticated.
`revoke all … from public, anon, authenticated`; service all; `grant select on integration_manual_tasks to
authenticated`.

Hook (comment in the migration: "Plan 4b extends `privacy_p4_erase` by renaming it; a later plan does the same to
`privacy_p4b_*`. Never `create or replace` a Plan 2 wrapper."):
```sql
alter function privacy_p4_erase(uuid, uuid[], uuid[], boolean) rename to privacy_p4_erase_base;
-- privacy_p4_erase_retention(p_tenant uuid, p_client_ids uuid[], p_app_ids uuid[], p_simulate boolean) returns jsonb
-- privacy_p4_erase(...) = privacy_p4_erase_base(...) || privacy_p4_erase_retention(...)   (service-only, as before)
```
`privacy_p4_erase_retention`: returns `'[]'` unless `not coalesce(p_simulate,true) and cardinality(coalesce(p_client_ids,'{}')) = 0
and cardinality(coalesce(p_app_ids,'{}')) > 0`. Otherwise: insert retired rows (`on conflict do nothing`); `v_due :=
integration_due_on(p_tenant)`; for every application link of those ids whose destination is not `draft`:
push kind ⇒ `integration_enqueue(d.id, 'application', id, l.client_id, v_action, case v_action when 'delete' then
'application.withdrawn' else 'application.status_changed' end, 'retention', v_due)` with `v_action = 'restrict'`
only when `config.retention_action = 'restrict'` and status ≠ `disconnected`; `api_pull`/`file_export` ⇒
manual task `(action 'delete', reason 'retention', due_on v_due)` `on conflict do nothing`. Pending never-delivered
upserts of those applications at push destinations ⇒ `integration_enqueue(…,'delete',…)` (becomes
`skipped 'erased_before_send'`). Returns `[{"table":"integration_links","rows":n,"action":"propagate_retention"},
{"table":"integration_manual_tasks","rows":m,"action":"create"}]`. Audit nothing per subject (retention already
audits counts).

| Signature | Kind | Behaviour |
| --- | --- | --- |
| `integration_manual_task_done(p_task_id uuid, p_evidence text) returns void` | admin (task's destination) | open task only (`invalid_transition`); evidence 5–500 chars; sets `done_at/by`; deletes the link it refers to when `action = 'delete'`. Audit `integration.manual_task_done`. |
| `integration_file_export_applications(p_destination_id uuid, p_source jsonb) returns jsonb` | admin | as `integration_file_export` (same gates, codes, 5 000 cap, `log_access('export.generated', …, {view:'crm_export_applications'})`, audit `integration.file_exported` `{entity:'application'}`), plus `entity_not_in_scope` when `scope.entities` lacks `application`. Sources: `{"kind":"applications","application_ids":[…]}` \| `{"kind":"clients","client_ids":[…]}` (their non-draft applications) \| `{"kind":"segment","segment_id"}` (commercial purpose) \| `{"kind":"all","statuses":[…]?}`. Per application: `integration_payload(d,'application',id)`; ok ⇒ person payload too when `scope.entities ? 'person'` (else `null`); application link (`via 'file'`), person link when included, one `integration_record_transfer` per row with the union of categories, reference `'file:'||export_id`. ⇒ **C-12** `{"export_id","template","format","application_object","rows":[{"application":{…},"person":{…}\|null}],"skipped":{"draft":2},"capped":false}` |

### 3.8 pgTAP suites (`db/supabase/tests/database/`, attacker side first)

Fixture style of `plan4_attacker_test.sql` (two tenants, every role, `set local role authenticated` + JWT claims,
`pg_temp.code()` / `sqlstate_of()` helpers). Describe results are inserted by service SQL as done ops (the shapes of
§4.5).

- **`crm_connectors_attacker_test.sql`** (~70): agent/underwriter get 0 rows from mapping versions, connector ops,
  manual tasks and `42501` on every new admin RPC; tenant_admin: `42501` selecting `secret_ref`, `claim_token`
  from connector ops, from `integration_retired_applications`, from `integration_private.secrets`;
  `has_function_privilege('authenticated', …)` false for `claim_integration_connector_op,
  finish_integration_connector_op, integration_connector_credentials, integration_describe_cache,
  privacy_p4_erase_base, privacy_p4_erase_retention`; tenant A admin gets `P0002` on B's destination/op/version/task
  in every RPC; insert/update/delete on every new table as tenant_admin ⇒ permission denied; a published version:
  `update … set definition` as **service_role** raises `mapping_version_immutable`, archived → published raises,
  `integration_mapping_discard` of a published one raises; `integration_set_credentials` never returns or audits the
  value (`audit_log.metadata::text` has no token substring); `integration_connector_op_get` result has no credential
  substring; anon: no privilege on the new tables, no execute on any new function; MFA-required tenant without aal2 ⇒
  new admin RPCs refused; `integration_destination_save` refuses `org_url` `https://evil.com`, `https://x.crm.dynamics.com.evil.io`,
  `http://x.crm.dynamics.com`, Odoo `https://127.1`, `https://localhost.` (`invalid_url`); sandbox flip on an active
  destination ⇒ `sandbox_locked`; `finish_integration_connector_op` drops `connector_meta` keys outside the list.
- **`crm_connectors_test.sql`** (~80): the 6-kind check; credentials set ⇒ hint, `verified_at` reset; replace drops
  the old secret (fallback store row gone); C-10/C-11 shapes; op reuse within 2 min, 31st op ⇒ `too_many_requests`;
  verify finish sets `verify_status` per result; every validation code of §3.4 with a minimal failing definition;
  publish archives the previous, sets `mapping_version_id`, re-arms links of an active destination; claim row has
  `kind`; C-3 carries mapping + `link` + `person_link`; changed mapping version ⇒ `unchanged = false`; finish
  `delivered` writes link `via 'crm'`, `external_refs` (unknown key dropped), `mapping_version_id`, transfer
  reference `crm:hubspot:<id>`; `deferred` ⇒ `failed` +60 s, `consecutive_failures` unchanged; `auth` +
  `permission_missing` ⇒ that status_reason; set_status `not_ready` detail lists `verify` and `mapping`; erasure of a
  linked client at a HubSpot destination ⇒ `delete` + `dsr_propagations`, evidence text «Eliminado en «…» (HubSpot…»;
  webhook suites unchanged (run them).
- **`crm_retention_files_test.sql`** (~45): approved automated `withdrawn_application` policy +
  `retention_apply()` on a linked application ⇒ `delete` with `reason 'retention'`, `due_on`, **no**
  `dsr_propagations` row; `retention_action 'restrict'` ⇒ `restrict`; file destination holding it ⇒ one manual task;
  the application is then `retention_expired` (payload skipped, `api_v1_application` ⇒ `not_found`, initial sync
  skips it); `execute_dsr_erasure` (real) produces **no** retention rows; simulated retention changes nothing;
  `integration_manual_task_done` removes the link, second call ⇒ `invalid_transition`; metrics count manual tasks;
  application export: refuses without `application` in scope, skips drafts with counts, rows carry the person
  payload only with `person` in scope, one transfer per row, `log_access` row.
- **Edits to existing suites (DB-4B owns them):** `plan4_attacker_test.sql` lines 271–280 — the exact allowlist of
  authenticated Plan 4 functions gains the new authenticated names (keep it exact); `integration_core_test.sql`
  line 357 — becomes "a file export keeps `["person","application"]` when asked; defaults to persons".

Verification: `node run.mjs crm` then `node run.mjs` (all suites, incl. `plan3_attacker`, `plan4_attacker`, the
registry test) — replay path in `CLAUDE.md` / Plan 4 §7.

---

## 4. ai-orchestrator (package ORCH-4B; split ORCH-4B-1 core, then 2a/2b/2c adapters in parallel)

Boundary unchanged: nothing under `src/integrations/` imports `src/agents|applications|documents|cases`; adapters
import only `src/integrations/**` and `src/lib/logger.js`. Logs: ids, kinds, outcome classes, error codes. Never a
URL path with ids beyond the host, a credential, a token, a property value, a body. Add a test that runs every
contract fixture with a capturing logger and asserts no credential/token/payload string appears.

### 4.1 Core files (ORCH-4B-1)

| File | Content |
| --- | --- |
| `http.ts` (edit) | `export interface HttpRequest {method:'GET'\|'POST'\|'PATCH'\|'PUT'\|'DELETE'; url; headers; body?; timeoutMs; maxBytes?}`; `HttpResponse {status, headers, bodyText, truncated}`; `export type HttpTransport = (r: HttpRequest) => Promise<HttpResponse>`; `guardedRequest(req, deps)` = today's logic generalized (checkUrl, resolvePublic, pinned lookup, `agent:false`, no redirects, `maxBytes` default 64 KB, describe passes 2 MB). `postSigned` becomes a wrapper (webhook tests unchanged). |
| `adapters/types.ts` | `NativeKind`, `CanonicalPerson/Application` (opaque records), `MappingObject` (M-1), `ConnectorContext {destinationId, kind, config, meta, credentials, credentialsSetAt, transport, now, timeoutMs, sandbox}`, `VerifyResult`, `DescribeResult`, `ProvisionResult` (§4.5), `UpsertRequest {entity:'person'\|'application'\|'test'; payload; mapping; link:{externalId, externalRefs}; personLink:{externalId}\|null; tenantCountry}`, `RemoveRequest {entity; entityId; link; reason}`, `RestrictRequest {entity; entityId; link; mapping}`, `AdapterResult = DeliveryResult & {externalRefs?: Record<string,string>; authReason?: 'auth_failed'\|'permission_missing'}`, `interface CrmAdapter {kind; limits:{perTenSeconds; concurrency}; verify(ctx); describe(ctx); provision(ctx, d: DescribeResult); upsert(ctx, r); remove(ctx, r); restrict(ctx, r)}` (`provision`/`restrict` mandatory for all three). |
| `adapters/errors.ts` | `class ConnectorError {outcome; code; httpStatus?; retryAfterSeconds?; authReason?}`; `toResult(err, durationMs): AdapterResult` (SsrfError ⇒ blocked; DeliveryTimeoutError ⇒ transient `timeout`). |
| `adapters/transforms.ts` + `adapters/mapping.ts` | pure: `resolvePath(payload, from)`; `applyMapping(obj: MappingObject, payload, ctx:{tenantCountry}) ⇒ {properties, idValue, warnings}` (§4.3). |
| `adapters/limiter.ts` | `DestinationLimiter` (token bucket per destination, `acquire(id, limits, maxWaitMs = 20 000)` ⇒ `true` or `{waitMs}`), `RunGate` (`close(id, outcome, retryAfterSeconds?, authReason?)`, `closed(id)`). One instance per drain run. |
| `adapters/registry.ts` | `adapterFor(kind)`; `transportFor(ctx)` = sandbox ? `sandboxTransport(kind, destinationId)` : `guardedRequest`. |
| `adapters/sandbox-store.ts` | in-memory `Map<destinationId, Map<object, Map<key, {id, props (masked via the same rule as integration_mask), restricted, deleted}>>>`, id counters; `listSandbox(destinationId)` for §4.6. |
| `deliver.ts` (edit) | rows with `kind === 'webhook'` exactly as today. Native rows: payload (C-3) → `skipped`/`unchanged` as today → `integration_connector_credentials` cached per destination per run (C-11; `null` ⇒ `transient secrets_unavailable`; `credentials null` ⇒ `auth no_credentials`) → `RunGate`/limiter → `adapter.upsert|remove|restrict` by `row.action` → finish with `auth_reason`, `external_refs`. Per-destination concurrency = `adapter.limits.concurrency` (mapPool partitions by destination). `test` entity ⇒ `upsert` with `entity 'test'`. |
| `connector-ops.ts` | `runConnectorOp(opId, deps)`: `claim_integration_connector_op` (null ⇒ `{status:'gone'}`) → ctx → `verify` / `describe` / `provision` (provision first runs `describe`, then runs `describe` again and returns `{…provision, describe}`; DB stores the provision result; web then requests a fresh describe op) → `finish_integration_connector_op` (`connector_meta` from verify) → `{status, result, error}`. Budget 40 s; on timeout finish `failed` `timeout`. |
| `routes.ts` (edit) | `POST /integrations/connector-ops/:opId/run` (bearer, uuid check) ⇒ 200 `{status, result?, error?}` \| 404 `{status:'gone'}`; `GET /integrations/sandbox/:destinationId` (bearer) ⇒ `{records:[{object, key, id, props, restricted, deleted}]}` (masked, sandbox only; 404 otherwise). |
| `server.ts`, `.env.example` (edit) | register the new route options; optional `INTEGRATION_CONNECTOR_OP_TIMEOUT_MS` (40 000). No `render.yaml` change. |
| watchdog (edit) | if it maps `status_reason` to Spanish, add `permission_missing` «faltan permisos en el CRM». |

### 4.2 Fixtures and contract tests

`src/integrations/__tests__/fixtures/<hubspot|dataverse|entra|odoo>/<case>.json`:
```json
{"source": "https://developers.hubspot.com/docs/... (fetched 2026-11-15) | pin by fixture",
 "exchanges": [{"request": {"method": "POST", "url": "https://api.hubapi.com/crm/objects/2026-09/contacts/batch/upsert",
                            "headers": {"authorization": "Bearer pat-na1-fixture"}, "bodySubset": {"inputs": [{"idProperty": "tramiq_client_id"}]}},
                "response": {"status": 200, "headers": {"x-hubspot-ratelimit-remaining": "99"}, "body": {…}}}]}
```
`__tests__/replay.ts`: `replayTransport(fixture)` asserts method, URL (exact), header subset, deep body subset, in
order, and fails on an extra call. Contract tests `__tests__/contract/<crm>.test.ts`, one `it` per fixture, each
asserting the `AdapterResult` (outcome, error code, retryAfter, externalId/Url, externalRefs). Idempotency test per
CRM: the same upsert twice ⇒ identical request (same key) and the same external id. Sandbox tests
`__tests__/sandbox.test.ts`: upsert/upsert/restrict/delete round-trip per kind through the real adapter.

### 4.3 Transform semantics (`transforms.ts`; WEB-B shows the same names)

`none`: string/number/boolean as is; array ⇒ `join(', ')`; object ⇒ omitted. `split_name`: trim, split on
whitespace, `to[0]` = first word, `to[1]` = rest (omitted when empty) — same rule as web `splitName`. `phone_e164`:
keep `+` and digits; `+` + 8–15 digits ⇒ as is; else 8 digits ⇒ `+<cc><digits>` with `cc = default_country_code ??
{SV:503, GT:502, HN:504, NI:505, CR:506, PA:507, MX:52, US:1}[tenantCountry]`; else digits that start with the
`cc` and are 9–15 long ⇒ `+digits`; else the trimmed original. `date_iso`: `Date.parse` ⇒ `YYYY-MM-DD` (UTC);
unparsable ⇒ omitted. `date_epoch_ms`: ms number; `midnight: true` ⇒ UTC midnight of that date. `enum_map`:
`String(value)` lookup, else `default`, else omitted. `template`: replace `{path}` (missing ⇒ ''), collapse spaces,
trim, ≤ 1 000 chars, empty ⇒ omitted. `money_number`: finite number or numeric string ⇒ rounded to 2 decimals.
`uppercase`: `toLocaleUpperCase('es')`. `constant`: `value`. Empty strings and `undefined` are never sent (a CRM
value is not cleared when Tramiq's becomes empty — documented). The adapter always adds `id_property = payload.id`
(HubSpot/Odoo body; Dataverse URL key) and `restricted_property = false`.

### 4.4 Adapters (ORCH-4B-2a/b/c; one folder each: `client.ts`, `adapter.ts`, `classify.ts`, `describe.ts`, `provision.ts`, `sandbox.ts`)

**HubSpot** (`adapters/hubspot/`). Base `https://api.hubapi.com`, `v = config.api_version ?? '2026-09'`, header
`authorization: Bearer <token>`, `content-type: application/json`.
- `verify`: `POST /oauth/v2/private-apps/get/access-token-info` `{"tokenKey": token}` ⇒ `hubId`, `scopes` (keep
  those two + `appId`; drop user). Required scopes: `crm.objects.contacts.read/.write`, `crm.objects.deals.read/.write`,
  `crm.schemas.contacts.read`, `crm.schemas.deals.read`; provisioning also `crm.schemas.contacts.write`,
  `crm.schemas.deals.write` (pin by fixture). Then `GET /crm/associations/{v}/deals/contacts/labels` and
  `…/notes/deals/labels` ⇒ store the HUBSPOT_DEFINED type ids (defaults 3 and 214 if absent). `ui_host` from the
  token prefix (`pat-na1` ⇒ `app.hubspot.com`, `pat-eu1` ⇒ `app-eu1.hubspot.com`, `pat-<r>` ⇒ `app-<r>.hubspot.com`).
- `describe`: `GET /crm/properties/{v}/contacts` and `/deals` (2 MB cap) ⇒ fields `{name, label, type:
  string|number|date|datetime|enum|bool, writable: !modificationMetadata.readOnlyValue && !calculated, required:
  false, unique: hasUniqueValue, options:[{value,label}]}`; `GET /crm/v3/pipelines/deals` ⇒ `pipelines[{id,label,
  stages[{id,label}]}]` (pin by fixture). `auto_filled: []`.
- `provision`: `POST /crm/properties/{v}/{contacts|deals}/groups` `{"name":"tramiq","label":"Tramiq"}` (409 ⇒
  existing); `POST /crm/properties/{v}/{object}` per missing property (409 ⇒ existing): contacts `tramiq_client_id`
  (string/text, `hasUniqueValue:true`), `tramiq_restricted` (bool/booleancheckbox), `tramiq_income_band`,
  `tramiq_under_rectification` (string/text); deals `tramiq_application_id` (unique), `tramiq_application_number`
  (number/number), `tramiq_status`, `tramiq_decision` (string/text), `tramiq_restricted` (bool).
- `upsert` person/test: `POST /crm/objects/{v}/contacts/batch/upsert` `{"inputs":[{"idProperty":"tramiq_client_id",
  "id":"<uuid>","properties":{…, "tramiq_client_id":"<uuid>","tramiq_restricted":"false"}}]}` ⇒ 200/201
  `{status:"COMPLETE", results:[{id, new}]}` ⇒ externalId, URL `https://<ui_host>/contacts/<hubId>/record/0-1/<id>`.
  Booleans sent as `"true"/"false"`. **409 / CONFLICT** "Existing ID: <n>" (an e-mail already used): `GET
  /crm/objects/{v}/contacts/<n>?properties=tramiq_client_id`; empty ⇒ `PATCH …/contacts/<n>` with the same properties
  (adoption, `externalRefs.adopted = 'email'`); a different Tramiq id ⇒ `validation email_conflict`.
- `upsert` application: deal `…/deals/batch/upsert` by `tramiq_application_id`; person id = `personLink.externalId`
  ?? `POST /crm/objects/{v}/contacts/batch/read` `{"idProperty":"tramiq_client_id","inputs":[{"id":person_id}],
  "properties":["tramiq_client_id"]}` ?? ⇒ `deferred person_not_synced`; when `externalRefs.associated_person ≠
  contactId`: `PUT /crm/objects/{v}/deals/<deal>/associations/contacts/<contact>/<deal_contact_type_id>`; decision
  note when `decision_note` and `sha256(JSON(decision))[0:16] ≠ note_decision_hash`: `POST /crm/objects/{v}/notes`
  `{"properties":{"hs_timestamp":<decided_at ms>,"hs_note_body":"<texto>"},"associations":[{"to":{"id":deal},
  "types":[{"associationCategory":"HUBSPOT_DEFINED","associationTypeId":<note_deal_type_id>}]}]}`.
- `remove` person: `POST /crm/v3/objects/contacts/gdpr-delete` `{"objectId":"<hubspot id>"}` (no link id ⇒
  `{"objectId":"<uuid>","idProperty":"tramiq_client_id"}`) ⇒ 204; application: `DELETE /crm/objects/{v}/deals/<id>`
  (no link id ⇒ batch read by key first; not found ⇒ delivered). `restrict`: `PATCH …/<object>/<id>` (or
  `?idProperty=<key>` with the uuid) `{"properties":{"tramiq_restricted":"true"}}`; 404 ⇒ delivered.
- `classify`: 2xx ⇒ delivered; **207** or body `errors[]` ⇒ by first error `category`: `VALIDATION_ERROR` ⇒
  validation `<code>: <propertyName…>` (e.g. `PROPERTY_DOESNT_EXIST: tramiq_income_band`, `INVALID_OPTION: dealstage`,
  `INVALID_EMAIL: email`), `OBJECT_NOT_FOUND` ⇒ validation, `CONFLICT` ⇒ conflict path, `MISSING_SCOPES` ⇒ auth
  `permission_missing` (`missing_scopes`), `RATE_LIMITS` ⇒ rate_limited; 400 ⇒ same parsing; 401 ⇒ auth
  `auth_failed`; 403 ⇒ `MISSING_SCOPES` ⇒ `permission_missing` else `auth_failed`; 404 on objects ⇒ validation
  (on delete/restrict ⇒ delivered); 409 ⇒ conflict path; 429 ⇒ rate_limited, `retryAfter` = `Retry-After` if
  present, else `policyName = 'DAILY'` ⇒ seconds to next UTC midnight (clamped 6 h; the DB clamps too), else
  `ceil(X-HubSpot-RateLimit-Interval-Milliseconds / 1000)` (default 10); 5xx ⇒ transient. Header
  `X-HubSpot-RateLimit-Remaining < 3` ⇒ limiter waits until the interval ends.
- limits `{perTenSeconds: 80, concurrency: 4}`. Fixtures (≥ 16): verify ok, verify missing scopes, labels,
  describe contacts/deals/pipelines, provision created/409, upsert created/updated, conflict adoption, conflict
  other id, deal + association + note, deal deferred, gdpr-delete 204/404, deal archive, restrict, 400
  PROPERTY_DOESNT_EXIST, 401, 403 MISSING_SCOPES, 429 TEN_SECONDLY_ROLLING, 429 DAILY, 502.

**Dataverse** (`adapters/dataverse/`, + `entra.ts`). Base `<org_url>/api/data/v9.2/`; headers `authorization: Bearer`,
`accept: application/json`, `odata-version: 4.0`, `odata-maxversion: 4.0`, `content-type: application/json; charset=utf-8`.
- `entra.ts`: `POST https://login.microsoftonline.com/<entra_tenant_id>/oauth2/v2.0/token`, form
  `client_id, scope=<org_url>/.default, grant_type=client_credentials` + `client_secret`, or
  `client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer, client_assertion=<JWT>`: header
  `{alg:"RS256", typ:"JWT", "x5t#S256": b64url(sha256(DER)), x5t: b64url(sha1(DER))}`, claims `{aud: <token URL>,
  iss: client_id, sub: client_id, jti: uuid, nbf, iat: now, exp: now+600}`, signed with `node:crypto`. Errors: 400/401
  `invalid_client` (AADSTS7000215 bad secret, AADSTS700027 bad assertion), `unauthorized_client` (AADSTS700016 app
  not found), `invalid_request` (AADSTS90002 tenant not found) ⇒ auth `auth_failed` with code `aadsts_<n>` (never
  `error_description`); 5xx ⇒ transient. Cache E17.
- `verify`: token; `GET WhoAmI` ⇒ `UserId, BusinessUnitId, OrganizationId`; `GET systemusers(<UserId>)/
  Microsoft.Dynamics.CRM.RetrieveUserPrivileges()` ⇒ `RolePrivileges[].PrivilegeName`. Required (pin by fixture):
  `prvCreate/Read/Write/Delete/Append/AppendToContact`, the same for `Opportunity` or `Lead` per config,
  `prvCreateNote`, `prvAppendToOpportunity|Lead`; `can_customize` = `prvCreateAttribute`, `prvCreateEntityKey`,
  `prvCreatePublisher`, `prvCreateSolution`, `prvPublishCustomizations` all present.
- `describe`: `GET EntityDefinitions(LogicalName='contact')/Attributes?$select=LogicalName,AttributeType,
  DisplayName,IsValidForCreate,IsValidForUpdate,RequiredLevel` (same for `opportunity`/`lead`) ⇒ fields (`writable =
  IsValidForCreate && IsValidForUpdate`; `required = RequiredLevel.Value in (ApplicationRequired, SystemRequired)`;
  `type` from `AttributeType`: String/Memo ⇒ string, Integer/Decimal/Double/Money ⇒ number, DateTime ⇒ datetime,
  Boolean ⇒ bool, Picklist/State/Status ⇒ enum, Lookup/Customer ⇒ reference); `…/Keys?$select=SchemaName,
  LogicalName,KeyAttributes,EntityKeyIndexStatus` ⇒ `keys[{name, attributes, status}]`; picklist options of
  `salesstage` (opportunity) via `…/Attributes(LogicalName='salesstage')/Microsoft.Dynamics.CRM.PicklistAttributeMetadata?
  $select=LogicalName&$expand=OptionSet($select=Options)`. `auto_filled: ["lastname"]` is **not** set (contacts need
  `lastname`; `split_name` provides it).
- `provision` (only `can_customize`; else `{failed:[{code:'no_customize_privilege'}]}`): `GET publishers?$filter=
  customizationprefix eq 'tramiq'` ⇒ else `POST publishers` `{uniquename:"tramiq", friendlyname:"Tramiq",
  customizationprefix:"tramiq", customizationoptionvalueprefix:72431}`; `GET solutions?$filter=uniquename eq
  'TramiqConnector'` ⇒ else `POST solutions` `{uniquename, friendlyname, version:"1.0.0.0",
  "publisherid@odata.bind":"/publishers(<id>)"}`; per missing column `POST EntityDefinitions(LogicalName='<t>')/
  Attributes` with header `MSCRM.SolutionUniqueName: TramiqConnector` and `{"@odata.type":
  "Microsoft.Dynamics.CRM.StringAttributeMetadata", SchemaName:"tramiq_ClientId", MaxLength:100, RequiredLevel:
  {Value:"None"}, DisplayName:{LocalizedLabels:[{Label:"Tramiq: ID de cliente", LanguageCode:3082}]}}` (Boolean
  columns: `BooleanAttributeMetadata` with `OptionSet` true/false labels) — contact `tramiq_clientid`,
  `tramiq_restricted`, `tramiq_incomeband`; opportunity/lead `tramiq_applicationid`, `tramiq_applicationstatus`,
  `tramiq_restricted`; keys `POST EntityDefinitions(LogicalName='<t>')/Keys` `{SchemaName:"tramiq_clientid_key",
  DisplayName:{…}, KeyAttributes:["tramiq_clientid"]}`; then `POST PublishXml` `{ParameterXml:"<importexportxml>
  <entities><entity>contact</entity><entity>opportunity</entity></entities></importexportxml>"}`. Keys build
  asynchronously: provision returns `pending:[{name, status}]`; the mapping cannot publish until a describe shows
  `Active` (§3.4). (Bodies pin by fixture against "Create and update column definitions using the Web API".)
- `upsert`: `PATCH contacts(tramiq_clientid='<uuid>')?$select=contactid` with `Prefer: return=representation`, body =
  mapped properties **without** the key, `tramiq_restricted:false` ⇒ 201/200 `{contactid}`; URL
  `<org_url>/main.aspx?pagetype=entityrecord&etn=contact&id=<guid>`. Application: `PATCH <opportunities|leads>
  (tramiq_applicationid='<uuid>')?$select=<opportunityid|leadid>` with `"parentcontactid@odata.bind":
  "/contacts(tramiq_clientid='<person_id>')"` (opportunities also `"customerid_contact@odata.bind"`, same value);
  404 whose message names the contact ⇒ `deferred person_not_synced`. Note: `POST annotations` `{"subject":
  "Decisión de Tramiq","notetext":"…","objectid_<opportunity|lead>@odata.bind":"/<set>(<guid>)"}` ⇒ `note_id` from
  `OData-EntityId`.
- `remove`: `DELETE contacts(<guid>)` (no link ⇒ `contacts(tramiq_clientid='<uuid>')`); 404 ⇒ delivered.
  `restrict`: `PATCH …` with `If-Match: *` `{"tramiq_restricted":true}`; 404 ⇒ delivered.
- `classify` (body `{"error":{"code":"0x…","message":…}}`; message never stored): 401 ⇒ one token refresh and retry,
  then auth `auth_failed`; 403 or code `0x80040220` ⇒ auth `permission_missing`; 429 / `0x80072322|0x80072321|
  0x80072326` ⇒ rate_limited with `Retry-After` seconds; 400 `0x8006088a` (resource not found for the segment: bad
  set/column) ⇒ validation `dataverse_resource_not_found`; other 400 ⇒ validation `dataverse_<code>`; 404 on PATCH
  without `If-Match` (bind target) ⇒ deferred; 412 ⇒ validation; 5xx ⇒ transient. limits `{perTenSeconds: 150,
  concurrency: 4}`. Fixtures (≥ 16): token secret ok, token certificate ok (assertion shape), AADSTS7000215,
  AADSTS90002, WhoAmI+privileges ok/missing, describe ×3, key Pending/Active, provision (publisher exists, column
  created, key created, PublishXml), upsert 201/200, opportunity bind 404 ⇒ deferred, annotation, delete 204/404,
  restrict 204/404, 401→refresh→204, 403 0x80040220, 429 0x80072322 Retry-After 37, 400 0x8006088a, 503.

**Odoo** (`adapters/odoo/`: + `json2.ts`, `xmlrpc.ts` codec). Base `config.url`; protocol `auto` resolved at verify
and stored in `meta.protocol`.
- JSON-2: `POST <url>/json/2/<model>/<method>`, headers `authorization: bearer <api_key>`, `x-odoo-database:
  <database>`, `content-type: application/json; charset=utf-8`, `user-agent: Tramiq-CRM/1`; body = named arguments
  (+ `ids`, `context:{lang:"es_ES", active_test:false}`). Calls: `res.users/context_get {}` ⇒ `uid`;
  `res.users/has_group {"ids":[uid],"group_ext_id":"…"}` (pin by fixture); `<m>/fields_get {"attributes":["string",
  "type","readonly","required","selection","relation"]}`; `<m>/search_read {"domain":[["x_tramiq_client_id","=",
  "<uuid>"]],"fields":["id"],"limit":1}`; `<m>/create {"vals_list":[{…}]}` ⇒ `[id]`; `<m>/write {"ids":[id],"vals":
  {…}}`; `<m>/unlink {"ids":[id]}`; `crm.lead/message_post {"ids":[id],"body":"<p>…</p>","message_type":"comment",
  "subtype_xmlid":"mail.mt_note"}`; stages `crm.stage/search_read {"domain":[],"fields":["id","name","sequence"]}`.
- XML-RPC (Odoo 17–18; `xmlrpc.ts` encodes string/int/double/boolean/array/struct/nil and parses
  `methodResponse`/`fault`, ≤ 200 lines, no dependency): `POST /xmlrpc/2/common` `version()` (protocol probe),
  `authenticate(db, login, key, {})` ⇒ uid (`false` ⇒ auth); `POST /xmlrpc/2/object` `execute_kw(db, uid, key,
  model, method, args, kwargs)` with positional `args` (`search_read [domain]` + `{fields, limit}`, `create [vals]`,
  `write [[id], vals]`, `unlink [[id]]`, `fields_get []` + `{attributes}`, `message_post [[id]]` + `{body, …}`).
  uid cached per `destination:credentials_set_at`.
- `auto`: JSON-2 `context_get`; HTTP 404 ⇒ XML-RPC (`login` required, else verify fails `login_required`).
- `verify`: uid; groups `base.group_partner_manager` (contacts), `sales_team.group_sale_salesman` (CRM),
  `base.group_system` (provisioning ⇒ `can_customize`); `crm.lead/fields_get` ⇒ `crm_installed`; `version` from
  `/xmlrpc/2/common version()` or JSON-2 `ir.module.module/search_read [["name","=","base"]]` field
  `latest_version` (pin by fixture).
- `describe`: `fields_get` on `res.partner` and `crm.lead` (types char/text/html ⇒ string, integer/float/monetary ⇒
  number, date ⇒ date, datetime ⇒ datetime, boolean ⇒ bool, selection ⇒ enum with options, many2one ⇒ reference);
  `stages[{id,name}]` (enum targets on `stage_id` validate against stage ids). `auto_filled: []`.
- `provision` (`can_customize`): `ir.model/search_read [["model","in",["res.partner","crm.lead"]]]` ⇒ ids;
  `ir.model.fields/create` for missing `x_tramiq_client_id` (char, `index:true`, `copied:false`),
  `x_tramiq_restricted` (boolean), `x_tramiq_income_band` (char) on res.partner; `x_tramiq_application_id`,
  `x_tramiq_status`, `x_tramiq_restricted` on crm.lead; `field_description` in Spanish.
- `upsert`: link id ⇒ `write`; `MissingError` ⇒ search; else `search_read` by key ⇒ `write` or `create` (with the key
  field). Lead: `vals` + `type:"opportunity"`, `partner_id` = `personLink.externalId` ?? search partner by key ??
  `deferred`. URL `<url>/web#id=<id>&model=<model>&view_type=form`. Note via `message_post`.
- `remove`: `unlink`; `ValidationError`/`UserError` ⇒ `write {"active":false,"name":"Suprimido","email":false,
  "phone":false,"mobile":false,"street":false,"city":false,"function":false,"x_tramiq_restricted":true}` ⇒ delivered
  `erasure_mode 'anonymized'`; `MissingError` ⇒ delivered. `restrict`: `write {"x_tramiq_restricted": true}`.
- `classify` (JSON-2 error `name`; XML-RPC `faultString` first line): `odoo.exceptions.AccessDenied` or HTTP 401 ⇒
  auth `auth_failed`; `odoo.exceptions.AccessError` / 403 ⇒ auth `permission_missing`; `odoo.exceptions.MissingError`
  ⇒ handled as above; `ValidationError`/`UserError` ⇒ validation `odoo_validation`; HTTP 404 /
  `werkzeug.exceptions.NotFound` ⇒ validation `odoo_model_or_method_missing` (or protocol fallback in verify); 429 ⇒
  rate_limited (Retry-After if present, else 60 s); 502/503/504 ⇒ transient; other 5xx with `name` ⇒ validation
  `odoo_<last segment>` (a server-side exception does not heal by retrying), without `name` ⇒ transient. limits
  `{perTenSeconds: 20, concurrency: 1}`. Fixtures (≥ 14): JSON-2 verify, XML-RPC fallback verify, bad key 401,
  AccessError, fields_get ×2, stages, provision, create, write, MissingError → create, lead deferred, message_post,
  unlink ok, unlink ValidationError → anonymize, XML-RPC fault parsing.

### 4.5 Op result shapes (stored by the DB; read by web; contract C-13)

```json
// verify
{"ok": true, "account_label": "HubSpot 1234567", "missing": [],
 "permissions": [{"code": "crm.objects.contacts.write", "granted": true, "needed_for": "deliver|provision"}],
 "can_customize": true, "notes": ["alternate_key_pending"]}
// connector_meta keys accepted by finish_integration_connector_op:
//   hubspot  portal_id, ui_host, deal_contact_type_id, note_deal_type_id, scopes
//   dynamics organization_id, user_id, business_unit_id, can_customize, org_host
//   odoo     version, protocol, uid, crm_installed, can_customize
//   all      account_label, sandbox
// describe
{"objects": {"person": {"target": "contacts", "fields": [{"name","label","type","writable","required","unique","options":[{"value","label"}]}],
                        "keys": [{"name","attributes":["…"],"status":"Active"}]},
             "application": {…}},
 "pipelines": [{"id":"default","label":"Sales Pipeline","stages":[{"id":"closedwon","label":"Closed Won"}]}],
 "stages": [{"id": 1, "name": "New"}], "auto_filled": [], "fetched_at": "ts"}
// provision
{"created": [{"object":"person","name":"tramiq_client_id"}], "existing": [...], "pending": [{"name":"tramiq_clientid_key","status":"Pending"}],
 "failed": [{"name":"…","code":"no_customize_privilege"}]}
```
≤ 1 000 fields per object; labels ≤ 120 chars; no descriptions, no user names or e-mails.

### 4.6 Sandbox transports (`<crm>/sandbox.ts`, E18)

Each implements the same URLs as its fixtures against `sandbox-store.ts`: verify ⇒ all permissions granted (a
credential ending in `-limited` ⇒ the deal/opportunity/lead write permission is missing, for the demo),
`account_label` «HubSpot (simulado)» etc.; describe ⇒ a fixed field list (fixture `describe` bodies) + provisioned
`tramiq` fields; provision ⇒ created then existing; keys become `Active` on the next describe; upsert by key
creates/updates ids `sbx-<n>`; association/note recorded in refs; gdpr-delete/DELETE/unlink mark deleted; Entra
token served locally. Never opens a socket (asserted by a test that injects a throwing `guardedRequest`).

### 4.7 Tests (vitest)

`transforms.test.ts` (each transform, edge cases above), `mapping.test.ts` (path grammar, id/restricted always set,
split_name two targets, omitted empties), `limiter.test.ts`, `deliver-native.test.ts` (fake rpc + fake adapter:
routing by kind, unchanged, skipped `no_mapping`, gate after 429/auth, deferred, external_refs and auth_reason passed
to finish, webhook rows untouched), `connector-ops.test.ts` (claim null ⇒ gone, verify meta forwarded, timeout ⇒
failed), `http.test.ts` (generalized methods, maxBytes, no redirect), contract tests §4.2, `sandbox.test.ts`,
`no-secrets-in-logs.test.ts`, `boundary.test.ts` (covers `adapters/**`). `npm test`, `npm run typecheck`.

---

## 5. web

### 5.1 WEB-4B-A step 1 — foundation (first commit; WEB-4B-B imports, never edits)

| File | Change |
| --- | --- |
| `src/lib/integrations/types.ts` | `DestinationKind` + `hubspot|dynamics|odoo`; `NativeKind`; `Destination` + `credential_hint, verified_at, verify_status, connector_meta, mapping_version_id` (and `DESTINATION_COLUMNS`); `DELIVERY_COLUMNS` + `mapping_version_id`; `DeliveryAttempt` + `mapping_version_id, external_url`; `ConnectorOp`, `VerifyResult`, `DescribeResult`, `DescribeField`, `ProvisionResult` (C-13); `MappingVersion {id, version, status, definition, issues, published_at, published_by}`; `ManualTask`; `CanonicalApplicationExportRow {application, person}`. (The mapping definition types live in WEB-B's `mapping.ts`.) |
| `src/lib/integrations/labels.ts` | `KIND_LABELS` hubspot «HubSpot», dynamics «Dynamics 365», odoo «Odoo»; `OUTCOME_LABELS.deferred` «En espera: el cliente aún no está en el CRM»; `SKIP_REASON_LABELS.retention_expired` «Plazo de conservación vencido», `no_mapping` «Falta publicar el mapeo»; `REASON_LABELS.retention` «Conservación»; `STATUS_REASON_LABELS.permission_missing` «Faltan permisos en el CRM»; `PERMISSION_LABELS` (every HubSpot scope, Dataverse privilege and Odoo group of §4.4 ⇒ Spanish); `VERIFY_STATUS_LABELS`; `SANDBOX_LABEL` «CRM simulado (demostración)». |
| `src/lib/integrations/errors.ts` | messages for `invalid_credentials` «Las credenciales no tienen el formato esperado (<campo>).», `no_credentials`, `too_many_requests`, `sandbox_locked`, `mapping_version_immutable`, `mapping_object_missing`, every §3.4 validation code, `not_ready` with detail items («Falta: verificar la conexión, publicar el mapeo»), `entity_not_in_scope`. |

### 5.2 WEB-4B-A — connectors in the wizard and on the destination page

| File | Purpose |
| --- | --- |
| `src/lib/integrations/connectors.ts` (pure) | per kind: config fields (label, placeholder, help, regex mirroring §3.2), credential fields (password inputs), `credentialProblems()`, `configProblems()`, help text per CRM (HubSpot: «Configuración → Integraciones → Apps privadas → Crear app privada; permisos: …»; Dynamics: «Registre una aplicación en Microsoft Entra, cree un usuario de aplicación en el entorno con un rol de seguridad mínimo…»; Odoo: «Preferencias del usuario técnico → Seguridad de la cuenta → Nueva llave de API…»), `readiness(destination)` ⇒ missing items. |
| `src/lib/integrations/wizard.ts` (edit) | steps for native kinds: `destination, connect, what, data, mapping, test, activate`; edit steps `what, data, mapping`; labels «Conectar», «Mapeo». |
| `src/lib/integrations/connector-client.ts` (browser) | `runConnectorOp(destinationId, op)` ⇒ `POST /api/integrations/destinations/<id>/connector/<op>`; on `{status:'pending', op_id}` polls `integration_connector_op_get` every 2 s for 60 s. |
| `app/api/integrations/destinations/[id]/connector/[op]/route.ts` | `POST`, `requireStaff()`, role `tenant_admin`/`superadmin`; uuid + op check; user-session RPC `integration_connector_request` (errors mapped like the export route); `fetchService` to `${AI_ORCHESTRATOR_URL}/integrations/connector-ops/<opId>/run` (POST, bearer added server-side, 50 s); upstream 200 ⇒ pass through; timeout/502/503 ⇒ 202 `{status:'pending', op_id}`. A second route `…/connector/sandbox/route.ts` (`GET`, sandbox destinations only, admin) proxies `GET /integrations/sandbox/<id>`. |
| `components/integrations/connector-connect-step.tsx` | config form (saved through `integration_destination_save`); «Modo de demostración: usar un CRM simulado» checkbox (draft only); credential inputs (`type=password`, `autoComplete="off"`), «Guardar credenciales» ⇒ `integration_set_credentials`, inputs cleared, then only «Configurado ✓ · termina en ••••a1b2 · <fecha>» and «Reemplazar credenciales» (**show-never-again**); «Verificar conexión» ⇒ verify op ⇒ `connector-verify-result.tsx`. Next is enabled only when `verify_status = 'ok'`. |
| `components/integrations/connector-verify-result.tsx` | account label; permissions table ✓/✗ with `PERMISSION_LABELS`; «Faltan permisos: …» + how to grant them (per CRM); `can_customize = false` ⇒ «Tramiq no puede crear los campos; créelos a mano:» list. |
| `components/integrations/connector-provision-panel.tsx` | «Crear propiedades en el CRM» ⇒ provision op ⇒ created/existing/pending/failed lists; then a describe op («Actualizar campos del CRM» also manual); pending keys ⇒ «La clave alternativa se está creando en Dataverse; vuelva a actualizar en unos minutos.» |
| `components/integrations/destination-wizard.tsx` (edit) | branch steps by kind; `connect` ⇒ connect step; `mapping` ⇒ provision panel + WEB-B `<MappingEditor>`; `test` for native ⇒ `integration_send_test` + kick + poll attempts (existing code) showing outcome, HTTP, masked payload, mapping version and «Ver en <CRM>» (`attempt.external_url`); `activate` shows `not_ready` items. |
| `components/integrations/catalog.tsx` (edit) | HubSpot, Dynamics 365, Odoo cards: primary «Conectar» (wizard `?kind=`), secondary «Vía webhook/API» (existing recipe). Salesforce/Zoho stays recipe-only. Icons per kind. |
| `components/integrations/destination-detail.tsx` (edit) + `connector-panel.tsx`, `manual-tasks-table.tsx`, `sandbox-records.tsx` | native: connector panel (credential status, «Reemplazar credenciales», «Verificar de nuevo», last verify result, `status_reason permission_missing` banner), provision panel, WEB-B `<MappingVersions>`; all kinds: manual tasks table («Pendientes manuales»: entity, motivo «Conservación», vence, «Marcar como hecho» ⇒ evidence dialog ⇒ `integration_manual_task_done`); `config.retention_action` select (push kinds) via edit; sandbox: «Registros en el CRM simulado» (masked; «se borran al reiniciar el servicio»). |
| `components/integrations/delivery-log.tsx` (edit) | columns «Mapeo v<n>», outcome `deferred`, external link on test rows. |

Tests: `test/unit/integrations-connectors.test.ts` (config/credential checks mirror §3.2 regexes incl. the
Dataverse attack strings of §3.8, readiness, steps per kind), updates to `integrations-wizard.test.ts` and
`integrations-labels.test.ts` (every new outcome/reason/status_reason/permission/error code has a label).

### 5.3 WEB-4B-B — mapping editor, application files, segment fix

| File | Purpose |
| --- | --- |
| `src/lib/integrations/mapping.ts` (pure) | M-1 types (`MappingDefinition`, `MappingObject`, `MappingField`, `Transform`); `mappingSources(entity, scope)` (mirror of `integration_mapping_sources`, with Spanish labels from the attribute catalog); `compatibleTargets(transform, fields)`; `localMappingIssues(def, describe, scope)` (subset of §3.4 for instant feedback; the DB stays authoritative); `TRANSFORM_LABELS`, `MAPPING_ISSUE_LABELS`. |
| `src/lib/integrations/mapping-defaults.ts` (pure) | `defaultMapping(kind, describe, scope, config)`: HubSpot §3.4 example plus contacts `city←address.municipality`, `state←address.department`, `company←employment.employer_name`, `jobtitle←employment.job_title`, `tramiq_income_band←income.band`, `tramiq_under_rectification←privacy.under_rectification`; deals `closedate←decision.decided_at (date_iso)`, `tramiq_status←status`, `tramiq_application_number←number`, stage ids taken from the `default` pipeline when its stages exist, else the first pipeline by label match (Spanish/English). Dataverse contacts `firstname/lastname (split_name)`, `emailaddress1`, `mobilephone (phone_e164)`, `address1_city`, `address1_stateorprovince`, `jobtitle`, `tramiq_incomeband`; opportunities `name (template)`, `estimatedvalue (money_number ← decision.sum_insured)`, `estimatedclosedate (date_iso)`, `salesstage enum_map {submitted:0, processing:0, manual_review:1, approved:3, declined:3, withdrawn:3}` (only if describe options contain them), `tramiq_applicationstatus ← status`, `description (template)`; leads `subject (template)`, `tramiq_applicationstatus`. Odoo res.partner `name ← full_name`, `email`, `phone (phone_e164)`, `city`, `function ← job_title`, `company_name ← employer_name`, `x_tramiq_income_band`; crm.lead `name (template)`, `type constant "opportunity"`, `expected_revenue (money_number)`, `x_tramiq_status`, `stage_id enum_map` by stage-name match (New/Nuevo ⇒ submitted+processing, Qualified/Calificado ⇒ manual_review, Won/Ganado ⇒ approved). Fields whose source is not in scope or whose target is not in describe are dropped. `decision_note: true`. |
| `components/integrations/mapping-editor.tsx` | props `{destination: Destination; describe: DescribeResult \| null; scope: IntegrationScope; onPublished(version: number): void}`. Loads the draft (or seeds `defaultMapping`); per object: target (fixed), rows `fuente → transformación → campo del CRM`, «Agregar campo», row params (template text, constant value, phone country code, `enum-map-editor.tsx` listing application statuses with a select of describe options/stages/pipeline stages); `mapping-field-picker.tsx` (searchable, writable-only, type badge, «Tramiq» group first, incompatible ones disabled with reason); toggles «Agregar nota con la decisión», shows id/restriction properties read-only. Debounced (600 ms) `integration_mapping_validate`; issues inline (`MAPPING_ISSUE_LABELS`); «Guardar borrador» ⇒ `integration_mapping_save_draft`; «Publicar versión N» (disabled with issues) ⇒ confirm «Los próximos envíos usarán este mapeo y se reenviarán los <links> registros ya sincronizados.» ⇒ `integration_mapping_publish`. `describe = null` ⇒ «Primero cree las propiedades o actualice los campos del CRM.» |
| `components/integrations/mapping-versions.tsx` | props `{destination: Destination; canManage: boolean}`; list of versions (versión, estado, publicada por/el, problemas), view a version read-only, «Nueva versión» (draft from the published one), «Descartar borrador». |
| `src/lib/integrations/file-templates.ts` (edit) | `rowsForApplicationTemplate(template, object, rows: CanonicalApplicationExportRow[])`: HubSpot deals «Deal Name, Pipeline, Deal Stage, Amount, Close Date, Email, Tramiq Application ID, Tramiq Client ID» (stage labels Appointment Scheduled / Qualified To Buy / Closed Won / Closed Lost); Dynamics opportunity «Topic, Potential Customer, Est. Revenue, Est. Close Date, Sales Stage, Description, Tramiq Application ID», lead «Topic, First Name, Last Name, Email, Mobile Phone, Description, Tramiq Application ID»; Odoo «Opportunity, Customer, Email, Phone, Expected Revenue, Stage, Type, Reference»; Salesforce opportunity «Opportunity Name, Account Name, Stage, Close Date, Amount, Tramiq Application ID» (Prospecting / Qualification / Closed Won / Closed Lost), lead «First Name, Last Name, Email, Phone, Company, Lead Status, Description, Tramiq Application ID» (Company = employer or full name); generic = flattened canonical keys with `application.` / `person.` prefixes. Amount = `decision.sum_insured ?? form.coverage_amount`; Close Date = `decided_at ?? submitted_at` (yyyy-mm-dd). `exportFileName(template, format, entity, object)`. |
| `app/api/integrations/destinations/[id]/export/route.ts` (edit) | body `{entity?: 'person'\|'application', source}`; `application` ⇒ `integration_file_export_applications` + `rowsForApplicationTemplate`; persons path unchanged. |
| `components/integrations/export-to-crm-button.tsx` (edit) + `app/(dashboard)/applications/page.tsx` (edit) | prop `entity`; applications list: «Exportar para CRM» with the selected (or all non-draft) applications, tenant_admin only; destination page «Exportar solicitudes» for file destinations whose scope includes applications. The data step for file destinations may now tick «Solicitudes» (WEB-A's scope editor already offers entities; only remove the file_export lock there — WEB-B owns that one-line edit in `scope-editor.tsx` and `wizard.ts defaultScope` stays persons). |
| `src/lib/segments.ts` (edit) + `components/segments/segment-builder.tsx` (edit) | `visibleIssues(issues, touched: Set<string>, submitted: boolean, rows)` (pure): `bad_value` kept only when its row id ∈ `touched` or `submitted`; other codes always. Builder: `touched` set (add the row id on value change/blur, on operator change after a value exists), `submitted` set on «Guardar»; `messageFor` and the summary use visible issues; the preview still waits for *all* local issues to clear; when only hidden issues exist the summary reads «Complete la condición para ver cuántos clientes entran.»; a new row starts untouched. |

Tests: `test/unit/integrations-mapping.test.ts` (sources follow scope, compatible targets, local issues,
defaults per kind drop unknown fields and pick stage ids), `file-templates.test.ts` (each application template's
headers, stage labels, amount/close-date fallbacks), `segments.test.ts` (`visibleIssues`: fresh row hides
`bad_value`, touched shows it, save shows it, `unknown_attribute` always shown).

Contract between A and B: WEB-B delivers `MappingEditor` and `MappingVersions` with exactly the props above; WEB-A
mounts them in its last commit (after WEB-B lands). WEB-A owns `destination-wizard.tsx`, `destination-detail.tsx`,
`catalog.tsx`, `delivery-log.tsx`; WEB-B owns `scope-editor.tsx` (one-line change), `file-templates.ts`, export
route/button, applications page, segments files.

---

## 6. Cross-package contracts

| Contract | Producer → consumer | Shape |
| --- | --- | --- |
| C-2 v2 claim (+`kind`) | DB-4B → ORCH | §3.5 |
| C-3 v2 delivery payload (+`kind, mapping_version_id, mapping, link, person_link, tenant_country, sandbox`; `skipped no_mapping`) | DB-4B → ORCH | §3.5 |
| C-4 v2 finish (+`deferred`, `auth_reason`, `external_refs`) | ORCH → DB-4B | §3.5 |
| C-10 `claim_integration_connector_op` / `finish_integration_connector_op` | DB ↔ ORCH | §3.3 |
| C-11 `integration_connector_credentials` | DB → ORCH | §3.3 |
| C-12 `integration_file_export_applications` | DB → WEB-B | §3.7 |
| C-13 verify/describe/provision results, `connector_meta` keys | ORCH → DB → WEB-A/B | §4.5 |
| M-1 mapping definition + validation codes | DB ↔ ORCH ↔ WEB-B | §3.4, §4.3 |
| `POST /integrations/connector-ops/:id/run` ⇒ `{status, result?, error?}`; `GET /integrations/sandbox/:id` | ORCH → WEB-A | §4.1 |
| Admin RPCs §3.3, §3.7 | DB → WEB-A/B | signatures above |
| `MappingEditor`, `MappingVersions` props | WEB-B → WEB-A | §5.3 |

---

## 7. Work packages

Everyone on `develop` of their repo; the umbrella records pins on `main` (memory: umbrella works on main).

| Package | Owns (creates or is the only editor of) | Depends on | Model / effort |
| --- | --- | --- | --- |
| **DB-4B** | the two migrations; `crm_connectors_test.sql`, `crm_connectors_attacker_test.sql`, `crm_retention_files_test.sql`; the two edits in `plan4_attacker_test.sql` and `integration_core_test.sql` | this design | sonnet / high (A and B may be two agents; B after A compiles) |
| **ORCH-4B-1** | `http.ts`, `adapters/{types,errors,transforms,mapping,limiter,registry,sandbox-store}.ts`, `deliver.ts`, `connector-ops.ts`, `routes.ts`, `server.ts`, watchdog edit, `.env.example`, `__tests__/replay.ts`, core tests | C-2…C-4 v2, C-10, C-11, M-1 | sonnet / high |
| **ORCH-4B-2a/b/c** | `adapters/hubspot/**`, `adapters/dataverse/**` (+ `entra.ts`), `adapters/odoo/**` (+ `xmlrpc.ts`), their fixtures, contract and sandbox tests | ORCH-4B-1's `adapters/types.ts` + `replay.ts` (first commit of 4B-1) | sonnet / high, parallel; each WebFetches its §4.4 "pin by fixture" items first |
| **WEB-4B-A** | §5.1 (first commit), §5.2 files, its tests | C-13, §3.3 RPCs; WEB-B components for the last commit | sonnet / medium |
| **WEB-4B-B** | §5.3 files, its tests | WEB-4B-A step 1; C-12; M-1 | sonnet / medium |
| **DOCS** | `docs/integrations.md` (sections «Conectores nativos», «Mapeos», «Conservación», «Modo de demostración»; update «Destination kinds», «File exports», «Not built»), `docs/supabase-schema.md` (Plan 4b tables, columns, functions, replaced list), `docs/architecture.md` (adapters, connector ops), `docs/roadmap.md`, `RUNBOOK.md` § Integrations (verify/replace credentials, Entra secret expiry, `permission_missing`, rate limits, Dataverse key pending, sandbox, retention tasks), `CLAUDE.md` invariants (§8), `STATUS.md` / `plans/04-PLAN-STATE.md` after verification | all merged | sonnet / medium |

Order: DB-4B A ∥ ORCH-4B-1 ∥ WEB-4B-A step 1 → DB-4B B ∥ ORCH-4B-2a/b/c ∥ WEB-4B-B ∥ WEB-4B-A → WEB-4B-A final
commit → review (opus; security: credentials, SSRF, payload projection, grants) + independent attacker suite
(sonnet) → replay (`node run.mjs`) → dev rehearsal/apply → production rehearsal (rolled back) → production apply →
deploy web, then orchestrator (a missing RPC is logged, not fatal) → DOCS → `graphify update .` per repo →
promote. Nothing new leaves until an admin activates a native destination.

---

## 8. Invariants for `CLAUDE.md` (DOCS)

- **Adapters project, they never enrich.** HubSpot, Dataverse and Odoo receive the canonical payload from
  `integration_delivery_payload()` and a published mapping; what they send is a renaming and formatting of it.
  CRM ids the DB already knows are the only extra input.
- **A CRM is called only from the orchestrator, through the SSRF-guarded transport,** including the wizard's
  verify/describe/provision (connector ops authorized by the DB). web never sees credentials; they live in Vault as
  one JSON per destination and are shown once.
- **A published mapping version is immutable** (trigger) and every delivery, attempt and link records the version
  that produced it.
- **Plan 4b extended `privacy_p4_erase` by renaming it** (`privacy_p4_erase_base`); a later plan does the same to
  the newest hook. Retention anonymizations reach every destination holding the application within the
  propagation deadline (delete/restrict, or a manual task for API/file destinations).
- **Sandbox destinations open no socket**; they exist for demonstrations and are labelled as simulated.

---

## 9. Demo script (tenant `seguros`, deployed site, warm services)

1. Integraciones: catalog shows «HubSpot — Conectar» beside «Vía webhook/API».
2. HubSpot wizard: «HubSpot Ventas (demo)», SV, DPA ✓, **CRM simulado ✓** (or a real developer test portal, Q1);
   paste a token ⇒ «Configurado ✓ · termina en ••••…»; «Verificar conexión» ⇒ permissions all ✓ (a second
   destination with a restricted token — sandbox token ending `-limited` — shows «Faltan permisos: escribir negocios»).
3. Qué enviar / Datos as Plan 4. Mapeo: «Crear propiedades en el CRM» ⇒ created list; editor opens with the
   suggested mapping; show the field picker, the `dealstage` enum map, an inline error by mapping a source out of
   scope; «Publicar versión 1».
4. Probar ⇒ «Entregado · HTTP 200 · Mapeo v1 · Ver en HubSpot».
5. Activar + clientes existentes ⇒ log fills; a client badge «Sincronizado con «HubSpot Ventas (demo)» ✓».
6. Decide an application ⇒ «Enviar ahora» ⇒ deal upsert, association, note; sandbox records panel shows contact,
   deal and note (masked).
7. Edit the mapping ⇒ version 2 published ⇒ «se reenviaron N registros»; log shows «Mapeo v2».
8. Privacidad: erasure DSR of a synced client ⇒ the DSR propagation «Eliminado en «HubSpot Ventas (demo)»
   (HubSpot, HTTP 204, id sbx-…)».
9. Retention: run the approved `withdrawn_application` policy on a synced withdrawn application ⇒ log `delete`
   motivo «Conservación» with its due date; a file destination shows «Pendientes manuales» ⇒ «Marcar como hecho».
10. Dynamics 365 (simulado): certificate auth, provision shows «clave alternativa en creación», then «Actualizar
    campos» ⇒ Active ⇒ publish. Odoo (simulado) quickly, protocol «JSON-2».
11. Archivos: «Exportar solicitudes» (HubSpot, XLSX) ⇒ deals columns in Excel.
12. Segmentos: new condition shows no error until a value is typed.

---

## 10. Risks and simplifications

- **No live verification of the three APIs** (no accounts): contract fixtures follow the docs fetched 2026-11-15
  and the "pin by fixture" list; the first real tenant needs a live smoke test per CRM (developer portals are free).
- **22 replaced functions** can drift from the originals: verbatim copies, the full replay and every existing Plan 4
  suite must stay green; the review diffs each replaced body against its source.
- **HubSpot versions** (`2026-09`) are dated; `config.api_version` and a semestral review. Deals are archived, not
  purged (90-day recycle bin) — told to the admin and in the docs.
- **Dataverse provisioning** needs customization privileges most customers will not grant; the manual list is the
  fallback. Alternate keys build asynchronously.
- **Odoo**: `has_group`/`context_get` argument names and Odoo 17 XML-RPC differences are pinned by fixture only;
  non-https instances unsupported; `unlink` fallback anonymizes (lawyer to confirm, plan §8.3).
- **E-mail adoption on HubSpot 409** links a pre-existing contact; it never overwrites one holding another Tramiq id.
- **One record per call** and in-memory limiter/token caches (one Render instance, free tier sleeps: syncs wait for
  a wake; kicks wake it).
- **Sandbox state is lost on restart** and is not a CRM; it exercises the adapters' real code paths only.
- **CRM values are never cleared** when Tramiq's value disappears (omitted, not nulled).
- **Retention to webhooks says `reason: "erasure"`** in the body (E22).

---

## 11. Questions for the conductor

1. **Sandbox (E18):** approve the simulated-CRM mode for the presentation? Alternatively, can the owner create free
   developer accounts (HubSpot developer test portal, Power Apps Developer Plan environment + Entra app registration,
   Odoo 19 trial or Docker) so one leg of the demo is live? The design supports both.
2. **E21:** approve replacing the 22 Plan 4 functions in new migrations (none is a Plan 2/3 wrapper), or require a
   narrower approach (e.g. only `integration_kind_pushes()` injected by renaming each original to `*_v1`)?
3. **E19 default:** retention reaches CRMs as `delete` by default (`restrict` opt-in per destination) — confirm.
4. **E22:** accept the webhook body saying `erasure` for retention, or allow one more replaced function
   (`integration_payload`, to pass `retention`)?
5. **E13:** confirm Dataverse provisioning by metadata API instead of a solution package.
6. **HubSpot e-mail adoption** (plan CRM-0 question 10): adopt an existing contact with the same e-mail when it has
   no Tramiq id — confirm.
7. Read-only facts to check on production before the demo (do not query from agents): is any retention policy of
   class `withdrawn_application` or `declined_application` approved and `automated` in `seguros`; is there a withdrawn
   or declined application old enough to be due; still 0 integration destinations; Vault accepts a ~16 KB secret
   (certificate + key) on dev.
8. Should a sandbox destination write `data_transfers` rows (current design: yes, reference `crm:<kind>:sandbox:…`,
   consistent with the test receiver) or skip them as not a real disclosure?
