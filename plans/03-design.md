# Plan 3 — technical design (DAT-1 … DAT-9)

*2026-11-12. Implementation design for [`03-datos-del-cliente-y-enriquecimiento.md`](03-datos-del-cliente-y-enriquecimiento.md).
Audience: implementation agents who have not read the plan. Goal: a **presentable demo** in which every DAT
phase works end to end; not production hardening. Where this file changes the plan's SQL sketch it says so
(**⚠ deviation**). Schema keys English, UI Spanish, migrations append-only, Plan 2 rules everywhere. Never
open `qualifier-secrets.env.txt`. Never point a local process at a Supabase project.*

Conventions (same as `02-design.md`): "staff" = `profiles.role in (superadmin, tenant_admin, underwriter,
agent)`. "reviewer" = `underwriter | tenant_admin` of the tenant (superadmin passes where stated).
"sensitive reader" = role ≠ `agent` (the LPD-10 rule already used by `documents_select`). "hidden client" =
`client_processing_hidden(client_id)` (blocked/erased; visible only to tenant_admin/superadmin).
"service-only" = `revoke all on function … from public, anon, authenticated; grant execute … to service_role`.
Every new SECURITY DEFINER function is `language plpgsql security definer set search_path = public`,
raises stable lower-case codes (`P0002` not found / other tenant, `42501` not allowed, `22023` invalid),
and every new function and table gets an explicit `revoke … from public, anon` (Supabase **and** the
replay's default privileges hand everything to `anon`). Extension objects are always schema-qualified
(`extensions.similarity`, `extensions.gin_trgm_ops`, `operator(extensions.%)`, `extensions.vector`).

---

## 1. Decisions

| # | Open point in the plan | Decision | Why |
| --- | --- | --- | --- |
| D1 | How facts are written from a document | **SQL reads `documents.extracted_data` itself**: `record_document_facts(p_document_id)`. The orchestrator only calls it after the status is final. | One implementation serves the live path *and* the backfill (DAT-2, no model calls). Kinds are already normalized in TS (`normalize.ts`) before `extracted_data` is stored. |
| D2 | `client.profile_refresh` job with a singleton key per client | **⚠ deviation:** no job. Every `record_*` function ends with `rebuild_client_profile()` under `pg_advisory_xact_lock` per client. | Facts are also written by DB triggers (field reviews, rectification, form submit, staff edits, document status) where no queue is reachable. The advisory lock gives the same "one refresh per client at a time". |
| D3 | `client_profiles` read by `security invoker` RPCs | **⚠ deviation:** `client_profiles` is not selectable by `authenticated`; read via `client_profile_get()` (definer) which masks sensitive attributes for agents. | RLS cannot mask a key inside `attributes jsonb`, and column privileges cannot distinguish agent from underwriter (same DB role). `client_facts` stays RLS-readable (row-level sensitivity works there). |
| D4 | Survivorship rules 1–2 ("dsr wins over everything, then analyst") | **⚠ deviation:** a *human* fact (dsr, or analyst not tied to a document) wins over every evidence fact **not newer than itself**; newer evidence (evidence_date > human fact's date) wins. | Otherwise one rectification or one conflict choice freezes a salary forever and a constancia from next year never updates it. An analyst correction of a *document field* (field review) is evidence about that document and competes as evidence. |
| D5 | Rule 5 conflicts ("two current facts differing by more than tolerance") | Compared only inside `conflict_window_days` (default 60) of the winner's evidence date for `latest_evidence`; across all evidence for other rules. | Salaries change: last year's constancia is history, not a conflict. The form-vs-constancia disagreement of the same month is the useful one. |
| D6 | Plan 2 hooks (rectification, erasure, footprint, access, portability, retention) | **No copies of long Plan 2 bodies.** Rectification and staff edits via `AFTER UPDATE` triggers on `clients`/`applications`; `field_reviews` via `AFTER INSERT` trigger; the five report/erasure functions are **renamed to `*_base` and wrapped** (§3.4). Later migrations extend through stage hooks `privacy_p3_*_b/_c` created as stubs in migration A. | Copying 150–230-line bodies is where Plan 2 drifted. Wrapping is late-bound (plpgsql resolves names at call time) so `privacy_generate_response`, `retention_apply` etc. pick up the wrappers unchanged. Stubs let DB-B and DB-C be written in parallel. |
| D7 | Address normalization and phone E.164 as derived facts | Done at **write time** by a per-attribute `normalizer` (`raw_value` keeps what was read). Derived facts only for genuinely new attributes (age, DUI validity, email kind, annual income, income band, tenure, employer id, ID expiring). | A derived `address.department` would compete with the document's own value for the same attribute. |
| D8 | Occupation code (CIUO-08) | **Deferred** (catalog key `employment.occupation_code` exists, nothing fills it). | Plan marks it optional; no catalog to match against. |
| D9 | Income bands "configurable" | Fixed to `dashboard_metrics()` bands (`<500, 500-999, 1000-1999, 2000-2999, >=3000`, monthly) in `income_band(numeric)`. | Configurability adds a screen and nothing to the demo. |
| D10 | Transcription modes | Both. Requests live in `transcription_requests`; batch is the default (auto after extraction when the type has `extraction.transcribe = true`), immediate on an analyst's click. Model `MODEL_TRANSCRIPTION` (default `claude-haiku-5-5`), `thinking: {type:"disabled"}`, plain-text Markdown output. | Owner decision. Plain text, not a tool call: transcription is free text, and tool JSON escaping of 6 pages of text wastes output tokens. |
| D11 | Who authorizes a transcription | The DB: web calls `request_transcription()` with the user's JWT; the orchestrator only receives a request id and claims it with a service RPC. | The database is the security boundary; the orchestrator never trusts a document id from a browser. |
| D12 | Embeddings provider (DAT-8) | **Voyage AI `voyage-4`, 1024 dimensions, `POST https://api.voyageai.com/v1/embeddings`** (verified at docs.voyageai.com on 2026-11-12: multilingual 4-series, default 1024, 32k context, ≤1000 inputs and 320k tokens per request, US$0.06/M tokens, response `data[].embedding`/`data[].index`/`usage.total_tokens`). | Anthropic has no embeddings. Fails closed three ways: no `vector` extension, no `VOYAGE_API_KEY`, or the `Voyage AI` row in `subprocessors` inactive (it is seeded **inactive**: a superadmin activates it, which puts it in the generated privacy notice, *before* data flows). |
| D13 | Semantic search authorization | Orchestrator only embeds the **query**; the similarity search is `semantic_search_chunks()` **security invoker** called by web with the user's JWT, so RLS decides which chunks are visible. | Service role would bypass RLS. |
| D14 | DAT-9 replica | Schema `analytics` in the same Postgres, rebuilt nightly; pseudonym = first 32 hex of `sha256(key ‖ ':' ‖ uuid)` with the key in schema `analytics_private` (no grants to anon/authenticated/service_role; read only by the definer functions' owner). k = 5 over quasi-identifiers with two generalization levels then suppression. CSV export per dataset for tenant_admin. | No new infrastructure; core-only crypto (no pgcrypto/HMAC) so it replays in PGlite. Secret-prefix SHA-256 is not HMAC, but the threat is enumeration of client UUIDs, which needs the key. `supabase_vault` would be stronger but does not replay; noted as an upgrade. |
| D15 | Is pseudonymized data registered? | **Yes** (LPDP Art. 4 lit. q): `analytics.subjects` and `analytics.applications` in `personal_data_stores`, `access_handler = include_redacted` (the report says the subject is in the replica and shows the generalized row), `erase_handler = delete` (erasure computes the pseudonym and deletes immediately; the nightly rebuild only includes `active` clients). | The controller holds the key, so it can re-identify: still personal data. |
| D16 | Backfill "script" | A **SQL function** `backfill_client_facts()` the conductor runs with the Supabase connector, plus `backfill_regression_report()`. In backfill mode client columns are **never written** (only `field_sources.fact_id` is stamped where the legacy source points at the same document). | Runnable without a deployed orchestrator, idempotent, no model call, and makes the regression requirement provable (§3.6). |
| D17 | Staff edits of `clients` columns | Recorded as `analyst` facts (`method = 'record_edit'`) by a trigger, so the 360 and the column never disagree. | Today a staff edit leaves `field_sources` alone; without a fact, a refresh would show the old document value in the 360. |
| D18 | `processing_state` | Non-`active` clients: no new facts, no transcription/embedding, never in segments, exports or the replica; `blocked`/`erased` hidden from search (like `client_list`); `limited`/`opposed` still found by search with the badge (plan § 8). | Plan 2 invariant 4. |
| D19 | Segment purposes | `operations`, `commercial_management`, `marketing`, `profiling_offers`. Sensitive attributes only in `operations` and never for agents. `marketing`/`profiling_offers` require `has_consent()` of that code. | Plan § 4.5 and § 8. |
| D20 | Extras | Separate `extras` array in the tool schema; requested only when the type has fields and none is sensitive; also refused by the DB for sensitive types. Max 30 per document. Stored in `extracted_data.extras`. | Plan § 5.1. |

---

## 2. Extensions and the PGlite replay

Facts (conductor, 2026-11-12): production and dev have `pgcrypto`, `uuid-ossp`, `pg_stat_statements`,
`supabase_vault`; **not installed but available**: `pg_trgm`, `unaccent`, `vector`. Probed locally: the replay's
PGlite **0.5.15 is PostgreSQL 18.6** and ships `pg_trgm` and `unaccent` as contrib (both install into a
schema named `extensions`, `extensions.unaccent('extensions.unaccent'::regdictionary, …)`,
`to_tsvector('pg_catalog.spanish', …)`, `operator(extensions.%)` all work); **`vector` is not available**.

Migration A starts with:

```sql
create schema if not exists extensions;                 -- exists on Supabase; created in the replay
grant usage on schema extensions to authenticated, service_role;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists unaccent with schema extensions;

create or replace function unaccent_immutable(p text) returns text
language sql immutable parallel safe strict set search_path = '' as
$$ select extensions.unaccent('extensions.unaccent'::regdictionary, p) $$;
revoke all on function unaccent_immutable(text) from public, anon;
grant execute on function unaccent_immutable(text) to authenticated, service_role;
```

Migration C does `vector` defensively:

```sql
do $$ begin
  if exists (select 1 from pg_available_extensions where name = 'vector') then
    create extension if not exists vector with schema extensions;
  end if;
end $$;
-- every vector object is created inside `if to_regtype('extensions.vector') is not null then execute $ddl$…$ddl$`
```

**Replay runner change (conductor, `scratchpad/db-replay/run.mjs`, 3 lines):**

```js
import { pg_trgm } from "@electric-sql/pglite/contrib/pg_trgm";
import { unaccent } from "@electric-sql/pglite/contrib/unaccent";
const pg = new PGlite({ extensions: { pgcrypto, pg_trgm, unaccent } });
```

Suites that touch vectors assert `ok(case when not semantic_search_available() then true else <check> end, …)`
(the TAP shim has no `skip()`), so they pass in the replay and check for real on dev/prod rehearsals.

---

## 3. Database contract

Three migrations, each one transaction, replayable (no `CONCURRENTLY`, no pg_cron):

- **A** `db/supabase/migrations/20261113000000_client_data_core.sql` — DAT-1, DAT-2, DAT-3/4 data side, Plan 2 hooks.
- **B** `db/supabase/migrations/20261113000100_client_data_search_enrichment.sql` — DAT-5, DAT-6, DAT-7.
- **C** `db/supabase/migrations/20261113000200_client_data_vectors_analytics.sql` — DAT-8, DAT-9.

### 3.1 Migration A — tables

```sql
create table client_attributes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references tenants (id) on delete cascade,          -- null = platform
  key text not null check (key ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$'),
  label text not null check (length(btrim(label)) between 1 and 120),
  kind text not null check (kind in ('text','number','money','date','boolean','enum','id_number','phone','email','address')),
  options text[],                                                    -- enum values (English codes)
  category text not null check (category in ('identity','contact','demographic','financial','employment',
                                'health','biometric','vehicle','property','legal','other')),
  sensitive boolean not null default false,
  cardinality text not null default 'single' check (cardinality in ('single','multi','series')),  -- only 'single' is evaluated (multi/series shown as history)
  survivorship text not null default 'latest_evidence'
    check (survivorship in ('latest_evidence','highest_confidence','form_first','document_first','manual_only')),
  conflict_tolerance numeric check (conflict_tolerance is null or conflict_tolerance between 0 and 1),
  conflict_window_days integer not null default 60 check (conflict_window_days between 0 and 3650),
  protected boolean not null default false,       -- the plan's `identity`: never written to clients automatically
  normalizer text check (normalizer in ('title_case','sv_place','marital_status_es','phone_sv','email_lower','dui')),
  client_column text check (client_column in ('full_name','national_id','date_of_birth','email','phone',
                            'address_line1','district','region','marital_status','employer','occupation','annual_income')),
  client_column_transform text check (client_column_transform in ('monthly_to_annual')),
  client_column_priority integer not null default 0,
  expected boolean not null default false,        -- counts toward completeness
  derived boolean not null default false,         -- only record_derived_facts writes it
  status text not null default 'active' check (status in ('active','archived')),
  sort_order integer not null default 100,
  created_at timestamptz not null default now(),
  check (tenant_id is null or key like 'custom.%'),
  check (client_column is null or tenant_id is null));
create unique index client_attributes_key on client_attributes
  (coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), key);
-- RLS select authenticated: tenant_id is null or tenant_id = current_tenant_id() or superadmin. Writes: functions.
```
⚠ deviation: `identity` renamed `protected` (it also covers `contact.email`/`contact.phone`); added
`normalizer`, `conflict_window_days`, `client_column_priority`, `expected`, `derived`.

```sql
create table client_facts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null, client_id uuid not null,
  attribute_key text,                               -- null = not catalogued (schema field without canonical, or extra)
  field_key text,                                   -- document field key / form key / extra key
  extra boolean not null default false,
  label text,                                       -- Spanish label (type field label, form label, or model's label for extras)
  source_kind text not null check (source_kind in ('document','form','analyst','dsr','derived','import','crm')),
  document_id uuid references documents (id) on delete cascade,
  document_type_version_id uuid,
  application_id uuid,
  field_review_id uuid, dsr_id uuid,
  actor_id uuid references auth.users (id) on delete set null,
  method text,                                      -- document: prompt_version or 'legacy'; derived: 'age@1'; analyst: 'field_review'|'conflict_choice'|'manual'|'record_edit'; dsr: 'rectification'|'form_rectification'
  source_hash text,                                 -- md5(extracted_data::text) for document facts (idempotency)
  value_text text, value_number numeric, value_date date, value_bool boolean, value_json jsonb,
  raw_value text,
  confidence numeric check (confidence between 0 and 1),
  evidence_date date,
  category text not null, sensitive boolean not null,
  status text not null default 'current' check (status in ('current','superseded','excluded','retracted')),
  excluded_reason text check (excluded_reason in ('low_confidence','unparseable','document_flagged',
                              'document_rejected','document_unreadable','input_removed')),
  superseded_by uuid references client_facts (id) on delete set null,
  created_at timestamptz not null default clock_timestamp(),
  check (attribute_key is not null or field_key is not null),
  check (num_nonnulls(value_text, value_number, value_date, value_bool, value_json) = 1 or status = 'excluded'),
  check ((status = 'excluded') = (excluded_reason is not null) or status = 'retracted'),
  constraint client_facts_client_same_tenant foreign key (tenant_id, client_id) references clients (tenant_id, id) on delete cascade,
  constraint client_facts_application_same_tenant foreign key (tenant_id, application_id) references applications (tenant_id, id) on delete cascade);
create index client_facts_client_attr on client_facts (tenant_id, client_id, attribute_key) where status = 'current';
create index client_facts_attr_num on client_facts (tenant_id, attribute_key, value_number) where status = 'current';
create index client_facts_attr_text on client_facts using gin (value_text extensions.gin_trgm_ops) where status = 'current';
create index client_facts_document on client_facts (document_id);
create index client_facts_client_created on client_facts (client_id, created_at desc);

create table client_profiles (
  tenant_id uuid not null, client_id uuid not null,
  attributes jsonb not null default '{}' check (jsonb_typeof(attributes) = 'object'),
  completeness numeric(5,1) not null default 0, missing text[] not null default '{}',
  version integer not null default 1, refreshed_at timestamptz not null default now(), changed_at timestamptz not null default now(),
  primary key (tenant_id, client_id), unique (client_id),
  constraint client_profiles_client_same_tenant foreign key (tenant_id, client_id) references clients (tenant_id, id) on delete cascade);
create index client_profiles_attrs on client_profiles using gin (attributes jsonb_path_ops);

create table attribute_conflicts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null, client_id uuid not null, attribute_key text not null,
  sensitive boolean not null default false,
  fact_ids uuid[] not null, detail jsonb not null default '{}',   -- {values:[{value, fact_ids, sources:[source_kind]}], winner_fact_id, auto_resolved?}
  status text not null default 'open' check (status in ('open','resolved','dismissed')),
  opened_at timestamptz not null default now(),
  resolved_by uuid references auth.users (id) on delete set null, resolved_at timestamptz,
  resolution_fact_id uuid references client_facts (id) on delete set null, note text check (length(note) <= 500),
  constraint attribute_conflicts_client_same_tenant foreign key (tenant_id, client_id) references clients (tenant_id, id) on delete cascade);
create unique index attribute_conflicts_one_open on attribute_conflicts (client_id, attribute_key) where status = 'open';

create table sv_places (                              -- El Salvador geography, seeded from web/src/lib/sv-geography.ts
  id integer generated always as identity primary key,
  level text not null check (level in ('department','municipality','district')),
  name text not null, department text not null, municipality text,  -- parents (null for a department's municipality)
  match_key text not null);                           -- lower(unaccent_immutable(name)), spaces collapsed
create index sv_places_match on sv_places (match_key);
```
`sv_places`: 14 departments + 44 municipalities + 262 districts (DB-A generates the `insert` from
`web/src/lib/sv-geography.ts`; RLS select to authenticated `true`; platform data, no personal data).

**RLS and grants (A)**

| Table | authenticated | service_role |
| --- | --- | --- |
| `client_attributes` | select (policy above) | all |
| `client_facts` | select using `(tenant_id = current_tenant_id() or app_current_role() = 'superadmin') and (not sensitive or app_current_role() in ('underwriter','tenant_admin','superadmin')) and (not client_processing_hidden(client_id) or app_current_role() in ('tenant_admin','superadmin'))` | all |
| `client_profiles` | **none** (revoke all) | all |
| `attribute_conflicts` | select, same predicate as `client_facts` | all |
| `sv_places` | select `true` | all |

No insert/update/delete grant to `authenticated` on any of them.

**`personal_data_stores` rows (A)** — `(table, subject_link, categories, sensitive, access, erase, retention_class)`:
`client_facts (client_facts.client_id, {identity,contact,financial,health,inferred}, t, include, delete, extracted_data)` note "Cada valor con su fuente, fecha y confianza";
`client_profiles (client_profiles.client_id, {identity,contact,financial,health,inferred}, t, include, delete, approved_application)` note "Se reconstruye desde los hechos";
`attribute_conflicts (attribute_conflicts.client_id, {inferred}, f, include, delete, case_notes)`.

**Seed — platform catalog (A).** Columns: key · label · kind · category · flags. Defaults: `latest_evidence`,
tolerance null (= any difference), window 60, not protected, no column.

| key | label | kind | cat. | flags |
| --- | --- | --- | --- | --- |
| identity.full_name | Nombre completo | text | identity | protected, column full_name, expected |
| identity.national_id | Número de DUI | id_number | identity | protected, normalizer dui, column national_id, expected |
| identity.date_of_birth | Fecha de nacimiento | date | identity | protected, column date_of_birth, expected |
| identity.nationality | Nacionalidad | text | identity | |
| identity.passport_number | Número de pasaporte | id_number | identity | protected |
| identity.tax_id | NIT | id_number | identity | protected |
| identity.age | Edad | number | demographic | derived |
| identity.national_id_valid | DUI válido | boolean | identity | derived |
| contact.email | Correo electrónico | email | contact | protected, normalizer email_lower, column email, expected |
| contact.phone | Teléfono | phone | contact | protected, normalizer phone_sv, column phone, expected |
| contact.email_kind | Tipo de correo | enum {personal,corporate} | contact | derived |
| address.line1 | Dirección | address | contact | normalizer title_case, column address_line1, expected |
| address.district | Distrito | text | contact | normalizer sv_place |
| address.municipality | Municipio (como lo imprime el DUI) | text | contact | normalizer sv_place, column district |
| address.department | Departamento | text | contact | normalizer sv_place, column region, expected |
| address.country | País | text | contact | |
| family.marital_status | Estado familiar | enum {single,married,divorced,widowed} | demographic | normalizer marital_status_es, column marital_status, expected |
| family.dependents_count | Dependientes | number | demographic | |
| employment.status | Situación laboral | enum {employed,self_employed,unemployed,retired,student} | employment | |
| employment.employer_name | Patrono | text | employment | column employer, expected |
| employment.employer_id | Patrono (catálogo) | text | employment | derived |
| employment.job_title | Cargo | text | employment | column occupation, priority 1 |
| employment.occupation | Profesión u oficio (DUI) | text | employment | normalizer title_case, column occupation, priority 2 |
| employment.occupation_code | Código de ocupación | text | employment | (unused, D8) |
| employment.start_date | Fecha de ingreso | date | employment | |
| employment.tenure_years | Antigüedad (años) | number | employment | derived |
| income.monthly_gross | Ingreso mensual bruto | money | financial | tolerance 0.10, column annual_income transform monthly_to_annual, expected |
| income.annual_gross | Ingreso anual bruto | money | financial | derived |
| income.band | Banda de ingreso | enum {lt_500,500_999,1000_1999,2000_2999,gte_3000} | financial | derived |
| health.bmi · health.condition_count · health.glucose_mg_dl | IMC · Padecimientos declarados · Glucosa (mg/dL) | number | health | **sensitive** |
| health.smoker | Fumador | boolean | health | **sensitive** |
| vehicle.year · vehicle.plate | Año del vehículo · Placa | number · text | vehicle | |
| property.value | Valor del inmueble | money | property | tolerance 0.10 |
| credit.loan_amount · credit.term_months | Monto del préstamo · Plazo (meses) | money · number | financial | |
| document.national_id_expiry | Vencimiento del DUI | date | identity | |
| document.national_id_expires_soon | DUI por vencer | boolean | identity | derived |
| document.passport_expiry | Vencimiento del pasaporte | date | identity | |

The keys the seeded document types already declare as `canonical` (grep of 20261107000300/20261108000000)
are all present. The 7 columns `client-facts.ts` writes map exactly as today: `income.monthly_gross→annual_income
(×12, round 2)`, `employment.employer_name→employer`, `employment.job_title→occupation`,
`employment.occupation→occupation` (wins ties, priority 2 — today "applied last"), `address.line1→address_line1`,
`address.municipality→district`, `address.department→region`, `family.marital_status→marital_status`.

### 3.2 Migration A — functions

Pure/immutable helpers (`set search_path = ''`, execute to authenticated + service_role unless noted):

| Signature | Behaviour |
| --- | --- |
| `fact_text_key(p text) returns text` immutable | `lower(unaccent_immutable(regexp_replace(btrim(p), '\s+', ' ', 'g')))` with `[.,;:]` stripped — the text comparison key. |
| `title_case_es(p text) returns text` immutable | Exact port of `client-facts.ts titleCase`: lower (`es`), collapse spaces, split on ' ', capitalize first letter of each word except `de, del, y, e, en, a, para, por, con` when not first. Implement with `regexp_split_to_table … with ordinality` + `string_agg`. |
| `marital_status_code(p text) returns text` immutable | Port of `maritalStatusFrom`: unaccent lower prefix `solter→single, casad→married, divorciad→divorced, viud→widowed`; English codes pass through; else null. |
| `income_band(p_monthly numeric) returns text` immutable | D9 codes `lt_500 … gte_3000`; null in → null. |
| `normalize_fact_value(p_normalizer text, p_text text) returns text` stable definer | `title_case`→`title_case_es`; `sv_place`→ official `sv_places.name` whose `match_key = fact_text_key(p)` (first by level district, municipality, department) else `title_case_es`; `marital_status_es`→`marital_status_code`; `phone_sv`→`intake_phone(p)` else p; `email_lower`→lower(btrim); `dui`→`dui_digits` formatted `########-#` when 9 digits else p. Null in → null. |
| `client_column_value(p_transform text, p_value jsonb) returns jsonb` immutable | null transform → p_value; `monthly_to_annual` → `round(v*12, 2)` when number > 0 else null. |
| `fact_value(f client_facts) returns jsonb` immutable | The single non-null value as jsonb (date → 'YYYY-MM-DD' string). |
| `fact_values_differ(p_kind text, p_tolerance numeric, a jsonb, b jsonb) returns boolean` immutable | number/money: `abs(a-b) > coalesce(p_tolerance,0) * greatest(abs(a),abs(b))`; id_number: digits-only compare; text-like: `fact_text_key` compare; date/boolean: equality. |

Internal (service-only):

| Signature | Behaviour |
| --- | --- |
| `client_attribute_for(p_tenant_id uuid, p_key text) returns client_attributes` stable definer | Tenant row if any, else platform row; `status='active'`; null if unknown. |
| `insert_client_fact(p jsonb) returns uuid` definer | The one insert path: types `p->'value'` by the attribute (or field) kind into the right `value_*` column (number/money: jsonb number or `parse` of a numeric string with `,` thousands removed; date: `^\d{4}-\d{2}-\d{2}$`; boolean: jsonb bool or sí/si/yes/true/no/false; else text), applies the attribute `normalizer` (raw_value = original text when it differs), sets `status='excluded', excluded_reason='unparseable'` when typing fails. Copies `category`/`sensitive` from attribute (`sensitive = attr.sensitive or p.sensitive`). |
| `record_document_facts(p_document_id uuid, p_rebuild boolean default true) returns jsonb` definer | See algorithm below. |
| `record_form_facts(p_application_id uuid, p_source text default 'form') returns jsonb` definer | Application with client, client `active`. For each `products.form_schema.fields[]` object with `canonical` that `client_attribute_for` knows and a non-null `form_data[key]`: supersede the previous current fact of the same `(application_id, field_key, source_kind)`; insert `source_kind = p_source` (`form` or `dsr` with `method='form_rectification'`), `confidence = 1`, `evidence_date = coalesce(submitted_at, now())::date`, `category`/`sensitive` from field (`sensitive: true` on the field wins). Same value as the current one ⇒ no new row. Then `rebuild_client_profile`. Returns `{facts, superseded, client_id}`. |
| `record_analyst_fact(p_field_review_id uuid) returns uuid` definer | From the review row: its document's current fact with `field_key` (any status but superseded). No such fact or the field has no canonical ⇒ still insert a fact with `attribute_key = null`. Insert `source_kind='analyst', method='field_review', document_id, field_review_id, actor_id = reviewed_by, confidence = 1, evidence_date = the document fact's evidence_date`, value = `reviewed_value` (verdict confirmed ⇒ the reading). Old document fact → `superseded`, `superseded_by` = new. A correction to null ⇒ old fact `retracted` (`excluded_reason` null) and no new fact. Rebuild. |
| `sync_document_fact_status(p_document_id uuid) returns void` definer | Document `flagged`/`rejected` ⇒ its `current` facts → `excluded` with `document_flagged`/`document_rejected`; back to `extracted` ⇒ those two reasons → `current`. Rebuild. |
| `refresh_client_profile(p_client_id uuid, p_write_clients boolean default true) returns jsonb` definer | §3.3. |
| `record_derived_facts(p_client_id uuid) returns integer` definer | **Stub in A** (`return 0`); B replaces it. |
| `rebuild_client_profile(p_client_id uuid, p_write_clients boolean default true) returns jsonb` definer | `pg_advisory_xact_lock(hashtextextended('client_profile:' || p_client_id, 0))`; `r := refresh(...)`; `if record_derived_facts(id) > 0 then r := refresh(...)`; return r. No-op `{skipped:'processing_restricted'}` when the client is not `active` (existing profile kept). |
| `backfill_client_facts(p_tenant_id uuid default null, p_limit integer default 2000, p_write_clients boolean default false) returns jsonb` definer | §3.6. |
| `backfill_regression_report(p_tenant_id uuid default null) returns table (client_id uuid, client_column text, column_value text, profile_attribute text, profile_value text, field_source jsonb)` stable definer | §3.6. |

**`record_document_facts` algorithm** (all inside one call):

1. Load the document; `extracted_data` empty/`{}` or status in (`uploaded, classifying, classified, extracting`) ⇒ `{skipped:'not_read'}`. Application without `client_id` ⇒ `{skipped:'no_client'}`. Client `processing_state <> 'active'` ⇒ `{skipped:'processing_restricted'}`.
2. `hash := md5(extracted_data::text)`. If current/excluded document facts of this document all have `source_hash = hash` ⇒ `{skipped:'unchanged'}` (idempotent; still runs step 7's status sync).
3. Definition = version `documents.document_type_version_id`, else the tenant type's `current_version_id` for `doc_type`, else none (no schema: every field is uncatalogued). `sens := document_type_is_sensitive(tenant, doc_type)`.
4. Every previous `current`/`excluded` fact with `document_id = p_document_id and source_kind = 'document'` → `superseded` (`superseded_by` set when a new fact for the same `field_key` is inserted).
5. For each `extracted_data.fields[]` with non-null `value` (or with `excluded = 'unparseable'`): type field `tf` by key (may be null); `attr := client_attribute_for(tenant, tf.canonical)` (unknown canonical ⇒ null attribute, kept as uncatalogued); min = `greatest(0.6, coalesce((tf->>'min_confidence')::numeric, 0))`. Status: `unparseable` if marked so; `low_confidence` if confidence < min; `document_unreadable` if `legibility = 'unreadable'`; `document_flagged`/`document_rejected` from status; else current. Insert via `insert_client_fact` with `source_kind='document'`, `document_type_version_id`, `application_id`, `label = coalesce(tf.label, field.label)`, `category = coalesce(tf.category, attr.category, 'other')`, `sensitive = coalesce(tf.sensitive,false) or attr.sensitive`, `raw_value = field.raw_value`, `confidence`, `evidence_date = extracted_data.issue_date` when a valid date ≤ today else `uploaded_at::date`, `method = coalesce(extracted_data.meta.prompt_version, 'legacy')`, `source_hash = hash`.
6. Extras (`extracted_data.extras[]`, only when `not sens`): `attribute_key = null, extra = true, field_key = key, label`, category `other`, sensitive false, same status rules with min 0.6. Keys failing `^[a-z][a-z0-9_]{0,62}$` skipped.
7. `if p_rebuild then rebuild_client_profile(client_id)`.
Returns `{client_id, facts:int, extras:int, excluded:int, superseded:int, profile:{changed, version}|null}`.

**Staff RPCs (A)**

| Signature | Kind / grants | Behaviour / JSON |
| --- | --- | --- |
| `client_profile_get(p_client_id uuid) returns jsonb` | stable definer; authenticated | Staff of the client's tenant (superadmin any); hidden client ⇒ `P0002` unless admin; T2 ⇒ `P0002`. Shape **C-1** (§7). Agents: sensitive attributes `value: null, restricted: true`, sensitive conflicts omitted, sensitive other_facts omitted. No profile row yet (the function is `stable`, it cannot build one) ⇒ `{…, version: 0, groups: [record-only entries from the clients columns]}`. |
| `client_fact_history(p_client_id uuid, p_attribute text, p_field_key text default null) returns jsonb` | stable definer; authenticated | Same visibility; agent + sensitive attribute ⇒ `[]`. Shape **C-2**. `p_attribute` null + `p_field_key` given ⇒ history of an uncatalogued key. |
| `resolve_attribute_conflict(p_conflict_id uuid, p_fact_id uuid, p_note text default null) returns jsonb` | definer; authenticated | Reviewer of the tenant (+ `require_mfa_if_tenant_requires`); conflict open, fact ∈ `fact_ids` (`fact_not_in_conflict`); inserts analyst fact (`method='conflict_choice'`, document_id null, value of the chosen fact, confidence 1, evidence_date `current_date`, actor); conflict → `resolved`, `resolution_fact_id`; rebuild; audit `client.attribute_resolved {attribute_key}` (no value). Returns rebuild result. |
| `dismiss_attribute_conflict(p_conflict_id uuid, p_note text) returns void` | definer; authenticated | Reviewer; note ≥ 5 chars; → `dismissed` (the same `fact_ids` set is never reopened). |
| `set_attribute_value(p_client_id uuid, p_attribute_key text, p_value jsonb, p_note text default null) returns jsonb` | definer; authenticated | Reviewer; client active (`processing_restricted`); attribute catalogued, not `derived` except `employment.employer_id` (confirming a match); sensitive needs a sensitive reader (always true for reviewers); inserts analyst fact `method='manual'`; rebuild; audit `client.attribute_set {attribute_key}`. |
| `save_client_attribute(p jsonb) returns uuid` | definer; authenticated | `require_privacy_admin(current_tenant_id())` — tenant_admin only; key must start `custom.` (`custom_key_required`); fields `label, kind, options, category, sensitive, survivorship, conflict_tolerance, expected, status`; key immutable once facts exist. audit `client_attribute.saved`. |

Triggers (A), all functions `security definer`:

| Trigger | When | Calls |
| --- | --- | --- |
| `field_reviews_record_fact` AFTER INSERT on `field_reviews` | always | `record_analyst_fact(new.id)` |
| `documents_sync_fact_status` AFTER UPDATE OF status on `documents` | `old.status is distinct from new.status and new.status in ('extracted','flagged','rejected')` | `sync_document_fact_status(new.id)` |
| `applications_record_form_facts` AFTER UPDATE OF status on `applications` | `old.status = 'draft' and new.status = 'submitted'` | `record_form_facts(new.id)` |
| `applications_rectify_form_facts` AFTER UPDATE OF form_data on `applications` | `current_setting('app.rectifying', true) = 'on'` | `record_form_facts(new.id, 'dsr')` |
| `clients_rectify_facts` AFTER UPDATE on `clients` | `current_setting('app.rectifying', true) = 'on' and current_setting('app.profile_refreshing', true) is distinct from 'on'` | For each platform attribute with `client_column` whose column changed: insert `dsr` fact (`dsr_id = new.field_sources->col->>'dsr_id'`, method `rectification`, confidence 1, evidence_date `current_date`); `annual_income` ⇒ `income.monthly_gross = annual/12` (inverse of the transform); then rebuild. |
| `clients_record_staff_edits` AFTER UPDATE on `clients` | `current_user = 'authenticated' and current_setting('app.rectifying', true) is distinct from 'on'` | Same column scan ⇒ `analyst` facts `method='record_edit'`, `actor_id = auth.uid()`; rebuild. (Nested updates from definer functions run as the owner, so they never re-fire it.) |

### 3.3 Survivorship — `refresh_client_profile(p_client_id, p_write_clients)`

Runs as owner, sets `set_config('app.profile_refreshing','on',true)` before any `clients` update and `'off'` after.

**Inputs:** client row `c`; catalog `A` = active attributes visible to the tenant (tenant rows override platform
rows with the same key); `F` = facts of the client with `status = 'current'` and `attribute_key is not null`;
`L` = active `field_locks` with `field_path = 'clients.' || attr.client_column`; old profile `P`.

**Per attribute `a`** with any fact in `F`, or with `client_column` and a non-null column value:

1. Partition `F_a`: **H** (human) = `dsr` facts and `analyst` facts with `document_id is null`;
   **E** (evidence) = `document, form, import, crm` facts and `analyst` facts with `document_id is not null`;
   **D** = `derived`. `date(f) = coalesce(f.evidence_date, f.created_at::date)`; for H facts `date = created_at::date`.
2. `h` = latest H by `created_at` (dsr before analyst on a tie).
3. `e` = best E by `a.survivorship`:
   `latest_evidence`: max `date`, then max `confidence` (null = 0), then max `created_at`;
   `highest_confidence`: max confidence, then latest_evidence order;
   `form_first`: best `form` fact by latest_evidence else best other E; `document_first`: same with `document`;
   `manual_only`: `e := null`.
4. Winner `w`: if `h` and (`e` is null or `date(e) <= date(h)`) ⇒ `h`; elsif `e` ⇒ `e`; elsif `h` ⇒ `h`; else latest D
   (D facts only win when nothing else exists; derived attributes have only D).
5. **Protected** (`a.protected`): the profile value is `h` if present, else the record value (`c.<client_column>`,
   source `record`, no fact), else `e`. Columns are never written.
6. **Lock**: if `a.client_column` has an active lock ⇒ keep `P[a]` unchanged (if `P[a]` missing, compute as usual),
   set `locked: true`, skip conflicts for `a`.
7. **Conflicts:** comparison set `S` = E facts with (`h` null or `date > date(h)`) plus `h` (if any) plus, for
   protected attributes, the record value. For `latest_evidence`, keep only E facts with
   `abs(date - date(w)) <= a.conflict_window_days`. Group `S` by value using `fact_values_differ(kind, tolerance)`
   (greedy: a fact joins the first group whose representative it does not differ from). ≥ 2 groups ⇒ conflict:
   if an open conflict for `(client, a)` exists, update `fact_ids`/`detail`; else unless a `dismissed` conflict has
   exactly the same sorted `fact_ids`, insert. 1 group and an open conflict ⇒ `resolved`, `detail.auto_resolved = true`.
8. **Entry** `P'[a] = {value, kind, fact_id, source, source_ref:{document_id, application_id, dsr_id, field_review_id, actor_id}, method, evidence_date, confidence, sensitive, category, conflict, locked, fact_count}`; `source = 'record'` with `fact_id: null` for step-5 record values. `pending_confirmation = (a.key = 'employment.employer_id' and confidence < 0.8 and source = 'derived')`.
9. `completeness = round(100 * |{a expected with entry}| / |{a expected}|, 1)`; `missing` = expected keys without entry.
10. Upsert `client_profiles`: if `attributes`, `completeness` and `missing` all equal the stored ones ⇒ only
    `refreshed_at`; else `version + 1`, `changed_at = now()` (insert ⇒ version 1).
11. **Client columns** (`p_write_clients`, non-protected, unlocked attributes with a fact winner): group attributes by
    `client_column`; per column choose the attribute whose winner has the latest `date(w)`, tie ⇒ higher
    `client_column_priority`. `fs := c.field_sources -> column`.
    - `fs->>'fact_id' = w.id` ⇒ nothing.
    - Legacy `fs` (no `fact_id`) with `fs->>'document_id' = w.document_id` ⇒ stamp `fact_id`/`attribute` only, value untouched.
    - `fs` exists, `fs->>'date' > date(w)` and `w` is not H ⇒ skip (older evidence never overwrites a newer source — `newerFacts()`).
    - else write `client_column_value(transform, value(w))` (null ⇒ skip; **never nulls a column**) and
      `field_sources[column] = {source: w.source_kind, document_id, doc_type, application_id, dsr_id, field_review_id, date: date(w), fact_id: w.id, attribute: a.key}` (nulls stripped; `doc_type` from the document).
    - With `p_write_clients = false` only the legacy stamp runs.
12. Return `{client_id, changed:boolean, version, conflicts_opened:int, conflicts_resolved:int, columns_written:[text]}`.

**Regression requirement:** after the backfill the 7 columns hold the same values, and for every column whose
legacy `field_sources` names a document, the profile winner of the mapped attribute is a fact of that same
document (proved by `backfill_regression_report()` returning no row, §3.6).

### 3.4 Plan 2 wrappers and stage hooks (A)

```sql
alter function data_subject_footprint(uuid, uuid[]) rename to data_subject_footprint_base;
alter function dsr_access_report(uuid) rename to dsr_access_report_base;
alter function dsr_portability_export(uuid) rename to dsr_portability_export_base;
alter function execute_dsr_erasure(uuid, boolean) rename to execute_dsr_erasure_base;
alter function privacy_anonymize_applications(uuid, uuid[], text) rename to privacy_anonymize_applications_base;
-- revoke all on each *_base from public, anon, authenticated (wrappers are definer and owner-executed)
```

| Wrapper (same signature, same grants as the original) | Body |
| --- | --- |
| `data_subject_footprint(t, ids)` | `fp := data_subject_footprint_base(t, ids)` (it runs `require_privacy_admin`); `app_ids` as base; return `fp \|\| privacy_p3_footprint_a(t, ids, app_ids) \|\| privacy_p3_footprint_b(…) \|\| privacy_p3_footprint_c(…)`. |
| `dsr_access_report(p_dsr_id)` | `r := base`; ids = `privacy_linked_clients`; adds `sections.profile = [{key, label, value, source_label, evidence_date, derived:boolean}]` (all current profile entries incl. sensitive — it is the subject's own data; `derived` marked "inferido"), `sections.conflicts_open:int`; if footprint has `document_texts` ⇒ `sections.document_texts = [{doc_type_label, pages, transcribed_at}]` (summary, D-access modality); if `analytics` ⇒ `sections.analytics = {rows, generalized:[…]}`; appends glossary terms `Dato inferido`, `Transcripción`, `Réplica analítica seudonimizada`. |
| `dsr_portability_export(p_dsr_id)` | `base \|\| {profile_provided: {<attribute_key>: value}}` from **form** facts and DSR facts only (data the subject provided; derived/document-read values excluded, plan § 8). Schema id stays `tramiq.subject-export/v1` (additive key). |
| `execute_dsr_erasure(p_dsr_id, p_simulate)` | `r := base(...)`; `anon := ids of r.subjects with action 'anonymize'`; `apps := applications of anon`; `extra := privacy_p3_erase_a(tenant, anon, apps, sim) \|\| _b(…) \|\| _c(…)` (arrays of `{table, rows, action}`; when not simulating they also delete); return `r` with `per_store = r.per_store \|\| extra`. |
| `privacy_anonymize_applications(t, app_ids, placeholder)` | `res := base(...)`; `x := privacy_p3_erase_a(t, '{}', app_ids, false) \|\| _b \|\| _c`; then `rebuild_client_profile(cid, true)` for each distinct client of `app_ids` whose state is not `erased`; return `res \|\| {plan3: x}`. (Covers retention of withdrawn/declined applications.) |

Stage hooks (definer, service-only), A implements `_a`, creates `_b`/`_c` as stubs returning `'{}'`/`'[]'`:

- `privacy_p3_footprint_X(p_tenant uuid, p_client_ids uuid[], p_app_ids uuid[]) returns jsonb` — A: `{client_facts:[…all statuses, value as jsonb, source_kind, attribute_key, field_key, evidence_date, status], client_profile:[profile rows], attribute_conflicts:[…]}`.
- `privacy_p3_erase_X(p_tenant uuid, p_client_ids uuid[], p_app_ids uuid[], p_simulate boolean) returns jsonb` — A: counts then (not simulating) `delete from client_facts where tenant and (client_id = any(client_ids) or application_id = any(app_ids) or document_id in docs of app_ids)`; `delete from attribute_conflicts / client_profiles where client_id = any(client_ids)`. Rows: `[{table:'client_facts', rows, action:'delete'}, {table:'client_profiles', …}, {table:'attribute_conflicts', …}]`.

`delete_client()` needs nothing: the composite FKs cascade.

### 3.5 Migration A — data changes and seed

- Insert catalog, `sv_places`, the three `personal_data_stores` rows.
- `db/supabase/seed.sql` (DB-A edits, at the end): `select backfill_client_facts(null, 2000, false);` so the
  replay and a fresh dev database start with facts and profiles (idempotent, re-runnable).

### 3.6 Backfill and regression

`backfill_client_facts(p_tenant_id, p_limit, p_write_clients)` (service-only):
1. Documents of the tenant(s) with `extracted_data` non-empty, status in (`extracted, flagged, rejected`), and **no
   `document` fact yet**, oldest `uploaded_at` first, up to `p_limit`: `record_document_facts(id, false)`.
2. Applications with status ≠ `draft` and no `form` facts: `record_form_facts(id)` with rebuild suppressed (internal
   flag `p_rebuild` — add `p_rebuild boolean default true` to `record_form_facts` too).
3. Every touched client (and every client without a profile): `rebuild_client_profile(id, p_write_clients)`.
4. Returns `{documents:int, forms:int, clients:int, facts:int, skipped:{no_client, processing_restricted, not_read}, remaining:int}`. A second call returns zeros (idempotent). `remaining > 0` ⇒ call again.

`backfill_regression_report()` returns a row per (client, column ∈ the 7) where **either** the column value differs
from `client_column_value(transform, profile winner)` compared with `fact_text_key` (numeric equality for
`annual_income`) **and** the column's `field_sources` names a document (legacy or new); **or** the legacy
`document_id` is not the document of the winner fact. Expected empty on production after `p_write_clients = false`.

**Where it is proven:** the pgTAP fixture in `client_profile_test.sql` (seed clients carry no `field_sources`, so the
seed alone proves nothing) and **production data** (41 documents, all with `extracted_data`): the conductor runs,
after A and B are applied, `select backfill_client_facts(); select * from backfill_regression_report();` and then a
`select count(*)` sanity pair (§10). Dev has no documents.

### 3.7 Migration B — tables

```sql
create table employers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  name text not null check (length(btrim(name)) between 2 and 200),
  aliases text[] not null default '{}', sector text, nit text,
  match_keys text[] not null default '{}',     -- fact_text_key of name and aliases, kept by trigger
  status text not null default 'active' check (status in ('active','archived')),
  created_by uuid references auth.users (id) on delete set null, created_at timestamptz not null default now(),
  unique (tenant_id, id));
create unique index employers_name on employers (tenant_id, lower(name));
create index employers_match on employers using gin (match_keys);
-- RLS select tenant staff. Writes: save_employer(). Not personal data (companies): not registered.

create table document_texts (
  document_id uuid primary key references documents (id) on delete cascade,
  tenant_id uuid not null, application_id uuid not null, client_id uuid,
  pages integer, text text not null, truncated boolean not null default false,
  tsv tsvector generated always as (to_tsvector('pg_catalog.spanish'::regconfig, unaccent_immutable(text))) stored,
  model text not null, prompt_version text not null, request_id uuid,
  created_at timestamptz not null default now());
create index document_texts_tsv on document_texts using gin (tsv);
create index document_texts_client on document_texts (client_id);

create table transcription_batches (
  id uuid primary key default gen_random_uuid(),
  anthropic_batch_id text not null unique, model text not null,
  status text not null default 'submitted' check (status in ('submitted','ended','failed')),
  request_count integer not null, submitted_at timestamptz not null default now(),
  ended_at timestamptz, processed_at timestamptz, error text);
-- platform table: RLS on, no authenticated grant.

create table transcription_requests (
  id uuid primary key default gen_random_uuid(),                -- also the batch custom_id
  tenant_id uuid not null references tenants (id) on delete cascade,
  document_id uuid not null references documents (id) on delete cascade,
  application_id uuid not null,
  mode text not null check (mode in ('immediate','batch')),
  status text not null default 'queued' check (status in ('queued','claimed','submitted','succeeded',
          'blocked','errored','expired','refused','discarded','skipped')),
  reason text,                                 -- gate reason, spend_cap_reached, stop_reason, api error class
  batch_id uuid references transcription_batches (id) on delete set null,
  attempts integer not null default 0, requested_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(), claimed_at timestamptz, completed_at timestamptz);
create unique index transcription_requests_open on transcription_requests (document_id)
  where status in ('queued','claimed','submitted','blocked');

create table client_segments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  name text not null check (length(btrim(name)) between 2 and 120),
  purpose text not null check (purpose in ('operations','commercial_management','marketing','profiling_offers')),
  definition jsonb not null, description text check (length(description) <= 500),
  owner_id uuid references auth.users (id) on delete set null, shared boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now());
```

RLS: `document_texts` select using `exists (select 1 from documents d where d.id = document_texts.document_id)`
(inherits `documents_select`, i.e. tenant + agent/sensitive-type rule) `and (client_id is null or not
client_processing_hidden(client_id) or app_current_role() in ('tenant_admin','superadmin'))`;
`transcription_requests` select using the same `exists(documents)` predicate; `client_segments` select tenant
staff and (`shared or owner_id = auth.uid() or app_current_role() = 'tenant_admin'`). No write grants.

Registry rows (B): `document_texts (document_texts.client_id, {identity,financial,health}, t, include_redacted
'Se informa qué documentos tienen transcripción; el texto se entrega con el documento', delete, document_file)`;
`transcription_requests (…document_id→applications.client_id, {technical}, f, exclude 'sin datos personales', delete,
audit_log)`; `client_segments (client_segments.owner_id, {staff}, f, exclude 'definiciones sin datos de titulares',
not_applicable, audit_log)`.

### 3.8 Migration B — functions

**Enrichment (DAT-5)** — replaces the stub:

`record_derived_facts(p_client_id uuid) returns integer` definer, service-only + internal. Reads the client row and
the current profile. For each method below computes `(attribute, value, confidence)` or "no input"; compares with the
current derived fact of that `(attribute, method)`: equal ⇒ nothing; different ⇒ supersede + insert
(`source_kind='derived'`, `method`, `evidence_date = current_date`, `confidence` default 1); no input but a current
derived fact ⇒ `retracted`, `excluded_reason = 'input_removed'`. Returns number of inserted/retracted facts.

| method | attribute | rule |
| --- | --- | --- |
| `age@1` | identity.age | whole years from profile `identity.date_of_birth` (record or fact) to `current_date` |
| `dui_check@1` | identity.national_id_valid | `dui_valid(national_id)` when 9 digits, else no input |
| `email_kind@1` | contact.email_kind | domain ∈ {gmail.com, hotmail.com, outlook.com, live.com, msn.com, yahoo.com, yahoo.es, icloud.com, proton.me, protonmail.com} ⇒ `personal`, else `corporate` |
| `income_annual@1` | income.annual_gross | `round(monthly*12,2)` from profile `income.monthly_gross` |
| `income_band@1` | income.band | `income_band(monthly)` |
| `tenure@1` | employment.tenure_years | `round(days/365.25, 1)` from `employment.start_date` |
| `employer_match@1` | employment.employer_id | profile `employment.employer_name`: exact `fact_text_key ∈ match_keys` ⇒ confidence 1; else best `extensions.similarity(key, mk)` over active employers ≥ 0.45 ⇒ confidence = similarity (< 0.8 shows "por confirmar"); else no input. A human `employment.employer_id` fact wins anyway (§3.3). |
| `id_expiry@1` | document.national_id_expires_soon | expiry from profile `document.national_id_expiry` ≤ `current_date + 60` |

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `enrich_due_clients(p_limit integer default 500) returns integer` | definer; service-only | Active clients whose profile `refreshed_at::date < current_date` (age/expiry move with the calendar): `rebuild_client_profile`. Daily job. |
| `save_employer(p jsonb) returns uuid` / `archive_employer(p_id uuid) returns void` | definer; authenticated | Reviewer of `current_tenant_id()`; upsert by id; duplicates `employer_exists`; audit. Re-derives nothing (daily job / next rebuild picks it up). |
| `employer_candidates(p_name text) returns jsonb` | stable definer; authenticated | Tenant staff; `[{id, name, similarity}]` top 5 (for "confirmar patrono"). |

**Transcription (DAT-6)**

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `document_type_transcribes(p_tenant_id uuid, p_doc_type text) returns boolean` | stable definer; authenticated, service_role | Current version `definition->'extraction'->>'transcribe' = 'true'`. |
| `request_transcription(p_document_id uuid, p_mode text default 'batch') returns jsonb` | definer; authenticated | Caller reviewer (`underwriter`/`tenant_admin`) of the document's tenant (`tenant_id = current_tenant_id()`; agents are refused, so the sensitive-type rule needs no re-check). Refusals: `P0002` (other tenant/missing), `transcription_not_enabled`, `document_not_read` (status not extracted/flagged), `processing_restricted` (client not active). If an open request exists: immediate asked on a batch request still `queued`/`blocked` ⇒ switch `mode='immediate'`; else return it. Already has `document_texts` and `p_mode='batch'` ⇒ `{status:'succeeded', existing:true}`. Returns `{request_id, mode, status, existing}`. audit `document.transcription_requested {mode}`. |
| `request_transcription_system(p_document_id uuid) returns jsonb` | definer; service-only | Called by the orchestrator after extraction: if `document_type_transcribes` and no text and no open request ⇒ insert `batch` request. `{queued:boolean, reason}`. |
| `queue_transcriptions(p_tenant_id uuid default null) returns integer` | definer; service-only | Historical fill: batch requests for every read document of a transcribing type without text/open request. |
| `claim_transcription_requests(p_mode text, p_limit integer default 20) returns jsonb` | definer; service-only | First reverts `claimed` older than 30 min to `queued`; marks `skipped` (`reason='stale'`) `blocked` requests older than 7 days; then claims `queued` + `blocked` of `p_mode` (`for update skip locked`) → `claimed`, `attempts+1`. Returns `[{request_id, tenant_id, document_id, application_id, storage_path, doc_type, mode}]`. |
| `claim_transcription_request(p_request_id uuid) returns jsonb` | definer; service-only | Immediate path: only `queued`/`blocked` with `mode='immediate'` ⇒ `claimed`; returns the same object or null. |
| `mark_transcription_requests(p_updates jsonb) returns integer` | definer; service-only | `[{request_id, status, reason?, batch_id?}]`; terminal statuses set `completed_at`. |
| `record_transcription_batch(p_anthropic_batch_id text, p_model text, p_request_ids uuid[]) returns uuid` | definer; service-only | Inserts batch; requests → `submitted`, `batch_id`. |
| `transcription_batches_pending() returns jsonb` / `finish_transcription_batch(p_batch_id uuid, p_status text, p_error text default null) returns void` | definer; service-only | `[{id, anthropic_batch_id, submitted_at}]` of `submitted`; finish sets `ended_at`/`processed_at`. |
| `transcription_request_context(p_request_ids uuid[]) returns jsonb` | stable definer; service-only | `[{request_id, tenant_id, document_id, application_id, status}]` (to map batch results by `custom_id`). |
| `record_document_text(p_request_id uuid, p_text text, p_pages integer, p_model text, p_prompt_version text, p_truncated boolean) returns jsonb` | definer; service-only | Upserts `document_texts` (client_id from the application), request `succeeded`. Returns `{document_id, application_id, tenant_id}`. |

**Search (DAT-6)** — `search_clients(p_query text, p_filters jsonb default '{}', p_limit integer default 20) returns jsonb`,
**security invoker**, stable, authenticated. `q := btrim(p_query)`; length < 2 ⇒ `query_too_short` (22023); `p_limit`
clamped 1–50. Sources (each limited to `p_limit`, all under the caller's RLS):
- clients: `client_list` rows (it already hides blocked/erased from non-admins) where `search_text ilike '%'||unaccent-free q||'%'` or `unaccent_immutable(search_text) operator(extensions.%) unaccent_immutable(lower(q))` or `dui_digits(national_id) = dui_digits(q)`; order by `extensions.similarity` desc; `match` = which matched.
- facts: `client_facts` current with `value_text` trigram/ilike match (sensitive filtered by RLS) joined to `client_list` ⇒ clients with `match:'fact'`, `match_label` = attribute or fact label.
- applications: `application_list` where `search_text ilike` or `number::text = q`.
- documents (`p_filters->>'documents'` default true): `document_texts` where `tsv @@ websearch_to_tsquery('pg_catalog.spanish', unaccent_immutable(q))`, ranked by `ts_rank`, `snippet = ts_headline('pg_catalog.spanish', text, query, 'StartSel=«,StopSel=»,MaxWords=25,MinWords=8,MaxFragments=1')`, page = count of `=== Página` markers before the first hit (computed with `position` on the lowered text; null if none).
- `p_filters`: `{documents:boolean, client_id:uuid}`.
Shape **C-3** (§7). Web logs `search.performed` itself (the function is stable).

**Segments (DAT-7)** — definition grammar `{"match":"all"|"any","conditions":[{"attr":"<catalog key>","op":"…","value":…}]}`,
1–20 conditions. Ops by kind: number/money `eq neq gt gte lt lte between`; text/address/id_number/phone/email
`eq neq contains starts_with`; enum `in not_in`; boolean `is_true is_false`; date `before after between within_last_days`;
every kind `is_set is_not_set`. Evaluated over `client_profiles.attributes -> attr ->> 'value'` with typed casts;
SQL built with `format('%L')` only (never `%s` with user text).

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `segment_validate(p_definition jsonb, p_purpose text) returns jsonb` | stable definer; authenticated | Errors list `[{index, code}]`: `unknown_attribute`, `bad_operator`, `bad_value`, `sensitive_attribute_not_allowed` (sensitive attr with purpose ≠ operations, or caller agent). |
| `segment_preview(p_definition jsonb, p_purpose text) returns jsonb` | stable definer; authenticated | Staff; validation errors ⇒ raise first code (22023). Population: clients of `current_tenant_id()` with `processing_state = 'active'`; `marketing`/`profiling_offers` ⇒ `has_consent(client, purpose)`. `{count, sample:[{client_id, full_name}] (≤10, by name), excluded:{not_active:int, without_consent:int}}`. |
| `segment_save(p jsonb) returns uuid` | definer; authenticated | `{id?, name, purpose, definition, description, shared}`; validation; owner or tenant_admin edits; audit `segment.saved {purpose}`. |
| `segment_delete(p_id uuid) returns void` | definer; authenticated | owner or tenant_admin. |
| `segment_members(p_segment_id uuid, p_after uuid default null, p_limit integer default 200) returns jsonb` | stable definer; authenticated | Reviewers only (`not_allowed` for agent); re-evaluates with the stored purpose; shape **C-4**; keyset by `client_id`. |

**Data quality and portfolio analytics (DAT-7)**

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `data_quality_summary(p_days integer default 30) returns jsonb` | stable definer; authenticated | Tenant staff of `current_tenant_id()` (superadmin: `p_tenant` not supported — uses their tenant-less view ⇒ empty). Shape **C-5**. Coverage from `document` facts by `(doc_type, field_key)` over documents uploaded in the window; accuracy = `field_reviews` latest per field joined to the document's `document_type_version_id` (version number) and `extracted_data->'meta'->>'prompt_version'` ("legacy" when absent); conflicts from `attribute_conflicts`; extras from `extra = true` facts (keys and counts only, **never values**); completeness from `client_profiles` by product of the client's latest application; confidence drops = avg confidence last 7 days vs previous 7 per `(doc_type, field_key)` with n ≥ 5 each and drop > 10 points. |
| `data_quality_alerts() returns jsonb` | stable definer; service-only | Same drop computation across tenants: `[{tenant_id, tenant_name, doc_type, field_key, last_7d, prior_7d, drop_points}]`. |
| `uncatalogued_extras(p_doc_type text default null) returns jsonb` | stable definer; authenticated | tenant_admin; `[{doc_type, key, label, occurrences, documents, last_seen}]` (label = most frequent), sorted by documents desc. No values. |
| `portfolio_analytics() returns jsonb` | stable definer; authenticated | Tenant staff; active clients only; never sensitive attributes. `{min_group:5, income_bands:[{band, clients}], employment_status:[…], departments:[…], occupations:[{name, clients}] (top 10 of profile occupation/job title by fact_text_key), completeness_by_product:[{product_name, clients, average}], suppressed_groups:int}`; any group with < 5 clients is folded into `{"band"/"name": "otros", …}`; a list whose "otros" is itself < 5 drops it and counts it in `suppressed_groups`. |

Stage hooks replaced in B: `privacy_p3_footprint_b` ⇒ `{document_texts:[{document_id, doc_type, pages, created_at, chars}]}` (no text); `privacy_p3_erase_b` ⇒ `document_texts` (documents of app_ids or client_ids) and `transcription_requests` of those documents, delete.

### 3.9 Migration C — DAT-8 vectors

```sql
create table document_chunks (
  id bigint generated always as identity primary key,
  tenant_id uuid not null, document_id uuid not null references documents (id) on delete cascade,
  application_id uuid not null, client_id uuid,
  ord integer not null, page integer, content text not null, model text not null,
  created_at timestamptz not null default now(), unique (document_id, ord));
-- if to_regtype('extensions.vector') is not null:
--   alter table document_chunks add column embedding extensions.vector(1024) not null;
--   create index document_chunks_embedding on document_chunks using hnsw (embedding extensions.vector_cosine_ops);
-- RLS select: same predicate as document_texts. No write grants.
insert into subprocessors (name, service, country, data_categories, receives_sensitive, purpose, safeguards, active)
values ('Voyage AI', 'Vectores para búsqueda por significado', 'US', '{identity,financial,health}', true,
        'Convertir fragmentos de documentos y consultas en vectores para la búsqueda semántica',
        'Pendiente (L3) — sin cuenta configurada', false);
```

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `semantic_search_available() returns boolean` | stable; authenticated, service_role | `to_regtype('extensions.vector') is not null`. |
| `semantic_search_status() returns jsonb` | stable definer; authenticated, service_role | `{vector_extension:boolean, subprocessor_active:boolean, dimensions:1024, model:'voyage-4', chunks:int (caller's tenant; all for service)}`. The orchestrator adds `api_key`. |
| `document_text_for_embedding(p_document_id uuid) returns jsonb` | stable definer; service-only | `{tenant_id, application_id, client_id, text, has_chunks}` or null. |
| `record_document_chunks(p_document_id uuid, p_model text, p_chunks jsonb) returns integer` | definer; service-only | Unavailable ⇒ `semantic_search_unavailable` (22023). Deletes existing chunks of the document, inserts `[{ord, page, content, embedding:[1024 floats]}]` with `execute … ($1::text)::extensions.vector` (dimension mismatch ⇒ `bad_dimension`). |
| `embedding_candidates(p_limit integer default 50) returns jsonb` | stable definer; service-only | `[document_id]` with text, no chunks, client active. |
| `semantic_search_chunks(p_embedding text, p_limit integer default 10) returns jsonb` | **security invoker**, stable; authenticated | Unavailable ⇒ raise `semantic_search_unavailable`. Dynamic SQL: `select … from document_chunks c join documents d on d.id = c.document_id … order by c.embedding operator(extensions.<=>) $1::extensions.vector limit $2` (RLS applies to both tables); hidden clients excluded like `document_texts`. Shape **C-6**. |

Hook `_c`: footprint adds `document_chunks:{count}`; erase deletes chunks of app_ids/client_ids.

### 3.10 Migration C — DAT-9 analytics replica

```sql
create schema analytics;
create schema analytics_private;
revoke all on schema analytics, analytics_private from public, anon, authenticated, service_role;

create table analytics_private.pseudonym_key (
  id smallint primary key check (id = 1), key text not null, created_at timestamptz not null default now());
insert into analytics_private.pseudonym_key (id, key) values (1, intake_new_token());   -- 64 hex, core-only
revoke all on analytics_private.pseudonym_key from public, anon, authenticated, service_role;

create table analytics.subjects (
  tenant_id uuid not null, pseudonym text not null,
  age_band text, department text, marital_status text, employment_status text, income_band text,
  has_employer boolean, completeness_band text, application_count integer not null,
  generalization smallint not null,                 -- 0 none, 1 department+marital dropped, 2 all QIs dropped
  refreshed_at timestamptz not null, primary key (tenant_id, pseudonym));
create table analytics.applications (
  tenant_id uuid not null, pseudonym text not null, application_ref text not null,
  product_type text, product_name text, status text, created_month date, decided_month date,
  decision text, tier text, score_band text, refreshed_at timestamptz not null,
  primary key (tenant_id, application_ref));
create table analytics.refresh_runs (
  id bigint generated always as identity primary key, tenant_id uuid not null, at timestamptz not null default now(),
  subjects integer not null, suppressed integer not null, generalized integer not null, applications integer not null);
-- all: revoke all from public, anon, authenticated, service_role; read only via the definer functions below.
```

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `analytics_pseudonym(p_id uuid) returns text` | stable definer; **no grants** (owner only) | `left(encode(sha256(convert_to(k.key \|\| ':' \|\| p_id::text, 'UTF8')), 'hex'), 32)`. |
| `analytics_refresh(p_tenant_id uuid default null) returns jsonb` | definer; service-only | Per tenant: delete its rows; temp rows for clients `processing_state = 'active'`: `age_band` (`18-29,30-39,40-49,50-59,60+`), `department` (profile `address.department`), `marital_status`, `employment_status` (column), `income_band`, `has_employer`, `completeness_band` (`0-49,50-79,80-100`), `application_count`. **k = 5**: QI = (age_band, department, marital_status, employment_status, income_band); classes < 5 ⇒ level 1 (department, marital_status := null); recompute; still < 5 ⇒ level 2 (all QI null); still < 5 ⇒ dropped (`suppressed`). Applications of retained pseudonyms: `application_ref = analytics_pseudonym(application id)`, months truncated, `score_band` = 10-point band. Never health or any sensitive attribute. Inserts `refresh_runs`. Returns `{tenants:[{tenant_id, subjects, suppressed, generalized, applications}]}`. |
| `analytics_refresh_tenant() returns jsonb` | definer; authenticated | tenant_admin of `current_tenant_id()`: `analytics_refresh(current_tenant_id())`. |
| `analytics_status() returns jsonb` | stable definer; authenticated | tenant_admin: `{last_refresh_at, subjects, applications, suppressed, generalized, k:5}`. |
| `analytics_dataset(p_dataset text) returns jsonb` | stable definer; authenticated | tenant_admin; `p_dataset in ('subjects','applications')` (`unknown_dataset`); rows of `current_tenant_id()` only, without `tenant_id`; array of objects. |

Hook `_c` additionally: footprint `analytics:{rows, generalized:[subjects row without pseudonym]}` (computing the
pseudonym per client); erase deletes `analytics.subjects`/`analytics.applications` rows of the clients' pseudonyms.
Trigger `clients_delete_analytics` AFTER DELETE on `clients` (definer) deletes the same rows.

Registry rows (C): `document_chunks (document_chunks.client_id, {identity,financial,health}, t, include_redacted
'Se informa la cantidad de fragmentos', delete, document_file)`; `analytics.subjects (seudónimo = hash con clave de
clients.id; la clave está en analytics_private, {financial,inferred}, f, include_redacted 'Datos seudonimizados y
generalizados', delete, approved_application)`; `analytics.applications` (same, `{inferred}`).

---

## 4. pgTAP suites (`db/supabase/tests/database/`)

All written from the attacker's side; fixtures create their own tenants `c3…`, staff via
`request.jwt.claims`, as the Plan 2 suites do. Each ends `select * from finish(); rollback;`.

**`client_facts_test.sql` (DB-A)**
- authenticated (agent, underwriter, tenant_admin) `insert/update/delete` on `client_facts`, `attribute_conflicts`, `client_attributes`, `sv_places` ⇒ 42501; `select * from client_profiles` ⇒ 42501.
- `has_function_privilege('anon', …)` false for every new function; `authenticated` false for `record_document_facts`, `record_form_facts`, `refresh_client_profile`, `rebuild_client_profile`, `backfill_client_facts`, `insert_client_fact`, `privacy_p3_*`, every `*_base`.
- agent selects 0 rows with `sensitive`; underwriter sees them; `client_profile_get` as agent ⇒ `health.bmi` `value` null, `restricted` true.
- T2 staff: 0 T1 facts/conflicts; `client_profile_get(T1)` and `client_fact_history(T1, …)` ⇒ P0002.
- flagged document ⇒ facts `excluded/document_flagged`, not the profile value; status back to `extracted` ⇒ current.
- second `record_document_facts` with same data ⇒ `skipped:'unchanged'`; changed `extracted_data` ⇒ old `superseded`.
- sensitive type with `extras` in `extracted_data` ⇒ 0 extra facts.
- limited client ⇒ `skipped:'processing_restricted'`, no facts.
- blocked client ⇒ underwriter 0 facts, tenant_admin sees them.
- `save_client_attribute` as underwriter ⇒ 42501; tenant_admin with key `income.x` ⇒ `custom_key_required`; T2's `custom.*` invisible to T1.
- `review_document_field(…,'corrected', '1500')` ⇒ analyst fact current, document fact superseded, profile value 1500.
- `rectify_subject_data` on `annual_income` ⇒ `dsr` fact for `income.monthly_gross = annual/12`, profile winner dsr, `field_sources.annual_income.fact_id` set on next rebuild.
- staff `update clients set employer = 'X'` ⇒ analyst fact `record_edit`.
- `execute_dsr_erasure(…, true)` lists `client_facts` in `per_store` and deletes nothing; `false` on a declined-only client ⇒ 0 facts/profile/conflicts; T2 client with same DUI untouched.
- `data_subject_footprint(T1, ids)` has `client_facts`; `dsr_access_report` has `sections.profile` and no T2 id (`not (report::text like '%<t2 id>%')`); `dsr_portability_export` `profile_provided` has only form/dsr facts.
- `retention_apply` on a declined application (approved policy) ⇒ its facts gone, client profile rebuilt.
- `privacy_consent_test.sql`'s invariant still green (re-run is part of the replay).

**`client_profile_test.sql` (DB-A)** — survivorship
- two constancias, older with higher confidence ⇒ newer wins; reading the older one *after* ⇒ `annual_income` unchanged (field_sources date rule).
- DUI with a different name ⇒ open conflict on `identity.full_name`, `clients.full_name` unchanged.
- salaries 1000/1050 same month (5% < 10%) ⇒ no conflict; 1000/1200 ⇒ conflict; 800 a year earlier vs 1200 ⇒ no conflict (window).
- `resolve_attribute_conflict` ⇒ analyst winner; then a document with `issue_date` tomorrow-relative-newer ⇒ document wins again.
- `lock_field(client, 'clients.annual_income', …)` ⇒ new constancia does not change the column, entry `locked:true`.
- rebuild twice ⇒ same `version`; a column is never set to null when facts disappear.
- same DUI-side document with `job_title` and `occupation` ⇒ `occupation` column = title-cased DUI occupation.
- `manual_only` custom attribute ⇒ document fact does not win; `set_attribute_value` does.
- `title_case_es('LICENCIADA EN ADMINISTRACIÓN') = 'Licenciada en Administración'`; `marital_status_code('CASADA') = 'married'`.
- **regression fixture:** client with 7 columns + legacy `field_sources` exactly as `client-facts.ts` writes (`{document_id, doc_type, date}`), two documents; `backfill_client_facts(T, 100, false)` ⇒ the 7 columns byte-identical, `backfill_regression_report(T)` empty, each `field_sources` entry gained `fact_id`; second backfill ⇒ zero counts.

**`client_enrichment_test.sql` (DB-B)** — derived age/DUI/email kind/income band/annual; employer exact (1.0) and typo (`'Banco Agricola'` vs alias `'BANCO AGRÍCOLA S.A.'`, 0.45 ≤ c < 1); input removed ⇒ `retracted`; idempotent second rebuild; agent `save_employer` ⇒ 42501; T2 employers invisible.

**`client_search_test.sql` (DB-B)** — accent-insensitive name, DUI digits, employer typo, document text (`'constancias'` finds `'constancia'`), snippet has `«`; agent gets no hit from a sensitive document's text and 0 rows of its `document_texts`; T2 none; blocked client absent for underwriter, present for tenant_admin; `query_too_short`; authenticated cannot write `document_texts`, `transcription_requests`, `transcription_batches` (and cannot select batches); `request_transcription` by agent ⇒ 42501, on a non-transcribing type ⇒ `transcription_not_enabled`, T2 doc ⇒ P0002; claim/mark/record functions not executable by authenticated; `uncatalogued_extras` output contains no value; `data_quality_summary` for T2 never counts T1.

**`client_segments_test.sql` (DB-B)** — marketing definition with `health.bmi` ⇒ `sensitive_attribute_not_allowed`; agent operations with sensitive ⇒ same; marketing preview excludes a client without `marketing` consent and counts it in `without_consent`; limited/opposed/blocked never counted for any purpose; T2 preview never counts T1; `segment_members(T1 seg)` by T2 ⇒ P0002; agent `segment_members` ⇒ 42501; direct insert into `client_segments` ⇒ 42501; `%L` injection probe (`value: "x'); drop table clients; --"`) returns 0 and clients still exist.

**`semantic_search_test.sql` (DB-C)** — `Voyage AI` subprocessor row exists and is inactive; authenticated cannot write `document_chunks`; `record_document_chunks` not executable by authenticated; guarded assertions (`semantic_search_available()`): T2 0 chunks, agent 0 chunks of sensitive types, `semantic_search_chunks` returns only own tenant; when unavailable `semantic_search_chunks('[0]')` throws `semantic_search_unavailable`.

**`analytics_replica_test.sql` (DB-C)** — authenticated `select` on `analytics.subjects` / `analytics_private.pseudonym_key` ⇒ 42501 (schema usage); `set role service_role; select key from analytics_private.pseudonym_key` ⇒ 42501; after refresh with 12 fixture clients: every QI class ≥ 5 (`select min(n) from (select count(*) n from analytics.subjects group by tenant_id, age_band, department, marital_status, employment_status, income_band) x` ≥ 5, run as the owner before any `set role`); no `pseudonym` equals any `clients.id::text` or `md5(id)`; limited client absent; erasure removes its row; `analytics_dataset` as underwriter ⇒ 42501; T2 admin gets only T2 rows; `personal_data_stores` has both analytics rows.

---

## 5. ai-orchestrator

### 5.1 ORCH-A — extraction extras, facts, case Q&A

| File | Change |
| --- | --- |
| `src/agents/types.ts` | `ExtraFieldSchema = z.object({ key: z.string(), label: z.string().nullable().optional(), value: z.union([z.string(), z.number(), z.boolean(), z.null()]), confidence: z.number().min(0).max(1) })`; `ExtractionResultSchema` gains `extras: z.array(ExtraFieldSchema).optional()` and `meta: z.object({ model: z.string().nullable(), prompt_version: z.string() }).optional()`. `ExtractionAnswerSchema` unchanged. |
| `src/agents/extraction-agent.ts` | `export function wantsExtras(spec?: ExtractionSpec): boolean` — spec with ≥ 1 field and none `sensitive`. `export function keepExtras(value: unknown, reserved: ReadonlySet<string>): ExtraField[]` (pure: objects only, key `^[a-z][a-z0-9_]{0,62}$`, not in `reserved` (type keys + playbook expected keys), scalar value non-null, dedupe by key keeping the first, max 30). `extractionToolSchema(checkIds, options: { extras: boolean; reserved: string[] } = { extras: false, reserved: [] })` — extras ⇒ `.extend({ extras: z.preprocess((v) => keepExtras(v, set), z.array(ExtraFieldSchema)).describe("Otros datos que el documento imprime y que no están en la lista de llaves.") })`. `export function extrasBlock(): string` — "Además de las llaves de arriba, anota en `extras` cada otro dato que el documento imprima: `key` en inglés snake_case (p. ej. `afp_name`), `label` en español, `value` como lo imprime, `confidence`. No repitas en `extras` una llave de la lista. Si no hay más datos, deja `extras` vacío." Appended to the blocks only when `options.extras`. `runExtractionAgent` options gain `extras?: boolean`. The system prompt does **not** change (PROMPT_VERSION stays). |
| `src/documents/extract.ts` | Compute `const extras = wantsExtras(spec)`; pass `{ spec, extras }` to both readings; after `anchoredToRow`, set `result.meta = { model: <onModel value or modelFor('default')>, prompt_version: PROMPT_VERSION }`. **Remove** `refreshClientFromDocument` and call, after the audit insert: `await recordDocumentFacts(doc.id); await requestSystemTranscription(doc.id);`. |
| `src/documents/facts.ts` (new) | `export async function recordDocumentFacts(documentId: string): Promise<RecordFactsOutcome \| null>` — rpc `record_document_facts {p_document_id}`; never throws (log warn; `null`). `export async function requestSystemTranscription(documentId: string): Promise<void>` — rpc `request_transcription_system`; never throws. `RecordFactsOutcome` = contract C-7. |
| `src/documents/client-facts.ts` + `__tests__/client-facts.test.ts` | **Deleted** (logic now in SQL §3.3; `titleCase`/`maritalStatusFrom` live on as `title_case_es`/`marital_status_code`). |
| `src/documents/normalize.ts` | Keep `extras`/`meta` (it already spreads `...result`); add a test. |
| `src/privacy/minimize.ts` | `export function redactKnownIdentifiers(text: string, who: { full_name?: string \| null; national_id?: string \| null; email?: string \| null; phone?: string \| null }): string` — case- and accent-insensitive replacement of the full name (and each name token ≥ 4 letters) by `[titular]`, DUI digits in any `########-#`/9-digit form by `[DUI]`, the email by `[correo]`, the phone digits (last 8) by `[teléfono]`. Pure. |
| `src/cases/bundle.ts` | `CaseQaBundle` gains `facts: QaFact[]` (`{key, label, value, source_kind, evidence_date}` from `client_profiles.attributes` of the application's client; excluded: categories `contact`, keys `identity.full_name`, `identity.national_id`, `identity.passport_number`, `identity.tax_id`, `identity.date_of_birth` — age stays) and `texts: QaText[]` (`{document_id, doc_type, pages:[{page, text}]}` from `document_texts` of the application's non-rejected documents, each document ≤ 4 000 chars, ≤ 6 documents, `redactKnownIdentifiers` with the client row). `CITATION_KINDS` += `"fact"`, `"page"`; `citableRefs` adds `fact:<key>` ("Ingreso mensual bruto = 2400 (document, 2026-09-28)") and `page:<document_id>#<n>` ("<doc_type>, página n"). `splitPages(text)` (pure) on `=== Página N ===` markers (no marker ⇒ one page 1). |
| `src/cases/ask.ts` | System prompt adds "los datos consolidados del cliente (`facts`) y la transcripción de los documentos (`texts`, por página)"; the untrusted block includes `facts` and `texts`. |

Tests (vitest): `src/agents/__tests__/extras.test.ts` (schema only with extras option; `keepExtras` drops reserved,
invalid, non-scalar, >30, duplicates; `wantsExtras` false for a type with a sensitive field and for no spec);
`src/documents/__tests__/facts.test.ts` (rpc called with the id; error ⇒ null, no throw; extract.ts calls
`recordDocumentFacts` after the audit row — extend `extract-acceptance.test.ts` mocks); `src/privacy/__tests__/redact.test.ts`;
`src/cases/__tests__/case-qa.test.ts` (fact/page citations accepted, unknown page refused, no contact facts in bundle,
identifiers redacted in texts).

### 5.2 ORCH-B — new jobs, routes, providers

**Env** (`render.yaml` service envVars + `.env.example`): `MODEL_TRANSCRIPTION` value `claude-haiku-5-5`;
`TRANSCRIPTION_MAX_TOKENS` `"8192"`; `TRANSCRIPTION_BATCH_SIZE` `"20"`; `VOYAGE_API_KEY` `sync: false` (comment: "unset ⇒
semantic search disabled, fails closed"); `EMBEDDING_MODEL` `voyage-4` (the DB column is 1024-d; changing the model
family needs a migration). No change to `MODEL_DEFAULT`/`MODEL_ESCALATION` (on `develop` the file already says
`MODEL_DEFAULT=claude-sonnet-5-5`, not `-4-5`).

| File | Content |
| --- | --- |
| `src/lib/pricing.ts` | Add `"claude-haiku-5-5": { input: 0.1, output: 0.5, cacheWrite: 0.125, cacheRead: 0.01 }` and `"voyage-4": { input: 0.06, output: 0, cacheWrite: 0, cacheRead: 0 }` (comment: Voyage per docs.voyageai.com/docs/pricing 2026-11-12; 200M free tokens per account not modelled — overstates, like the Sonnet 5 note). `export const BATCH_DISCOUNT = 0.5`. |
| `src/lib/usage.ts` | `AgentName` += `"transcription" \| "embedding"`; `recordUsage(..., latencyMs?, options?: { batch?: boolean })` — batch ⇒ `cost * BATCH_DISCOUNT`. |
| `src/transcription/prompt.ts` | `TRANSCRIPTION_SYSTEM_PROMPT` (Spanish: transcribe every printed word in reading order as Markdown, tables as Markdown tables, `=== Página N ===` before each page, no summary, no commentary, illegible = `[ilegible]`, + `UNTRUSTED_CONTENT_RULE`); `TRANSCRIPTION_PROMPT_VERSION = promptVersion([TRANSCRIPTION_SYSTEM_PROMPT])`; `transcriptionParams(media, documentId): Anthropic.MessageCreateParamsNonStreaming` = `{ model: modelTranscription(), max_tokens: Number(TRANSCRIPTION_MAX_TOKENS ?? 8192), thinking: { type: "disabled" }, system, messages: [{ role: "user", content: [ {type:"text", text: DOCUMENT_PREAMBLE}, buildDocumentBlock(…), {type:"text", text:"Transcribe el documento completo."} ] }] }` — **no** `temperature`, no assistant prefill. |
| `src/transcription/result.ts` | Pure `readTranscription(message): { ok: true; text; pages; truncated } \| { ok: false; reason: "refusal" \| "empty" }` — checks `stop_reason` **before** reading content: `refusal` ⇒ refused; `max_tokens` ⇒ ok with `truncated: true`; text = concatenated `text` blocks; `pages` = count of markers (≥ 1). |
| `src/transcription/run.ts` | `export async function runImmediate(requestId: string)`: rpc `claim_transcription_request`; null ⇒ return. `processingGate(application_id)` refused ⇒ mark `blocked` with reason. `spendStatus(tenant).over` ⇒ `blocked`/`spend_cap_reached`. Download from bucket `documents`, `resolveMimeType`, `messages.create(transcriptionParams)`, `recordUsage({tenant_id, application_id, document_id}, "transcription", model, usage, latency)`. `readTranscription`: refused ⇒ `refused`; ok ⇒ **gate again** (consent could have been revoked meanwhile; refused ⇒ `discarded`) then rpc `record_document_text` and `enqueueEmbedding(document_id)`. API 400/413/422 ⇒ `errored` (no retry); other errors rethrow (pg-boss retries; dead letter marks `errored`). |
| `src/transcription/batch.ts` | `submitBatch()`: rpc `claim_transcription_requests('batch', TRANSCRIPTION_BATCH_SIZE)`; per request: gate (refused ⇒ `blocked`), spend cap per tenant (over ⇒ back to `queued` via mark), download; stop adding when base64 bytes sum > 100 MB; `client.messages.batches.create({ requests: [{ custom_id: request_id, params }] })`; rpc `record_transcription_batch(batch.id, model, ids)`. Create failure ⇒ mark all `queued`. `pollBatches()`: rpc `transcription_batches_pending`; for each `client.messages.batches.retrieve(id)`; `processing_status !== "ended"` ⇒ skip (older than 25 h ⇒ `finish_transcription_batch(…,'failed')` + requests `expired`); ended ⇒ `transcription_request_context(ids)`; `for await (const r of await client.messages.batches.results(id))` keyed by **`r.custom_id`**: `succeeded` ⇒ `recordUsage(…, { batch: true })`, `readTranscription`, gate again, `record_document_text`, enqueue embedding; `errored` ⇒ `errored` (reason = error type); `canceled` ⇒ `errored`; `expired` ⇒ `queued` again when `attempts < 2` else `expired`. Then `finish_transcription_batch(id,'ended')`. Never keyed by position. |
| `src/embeddings/voyage.ts` | `embeddingConfig(): { apiKey: string; model: string } \| null` (null without `VOYAGE_API_KEY`). `export async function embed(texts: string[], inputType: "document" \| "query", cfg)`: `fetch("https://api.voyageai.com/v1/embeddings", { method:"POST", headers:{ Authorization:`Bearer ${key}`, "content-type":"application/json" }, body: JSON.stringify({ input: texts, model, input_type: inputType, output_dimension: 1024, truncation: true }) })`; ≤ 128 inputs per call; returns vectors ordered by `data[].index`; `usage.total_tokens`. Non-2xx ⇒ throw with status. Pure `parseVoyageResponse(json)` validated with zod (each vector length 1024). |
| `src/embeddings/chunk.ts` | Pure `chunkText(text): { ord; page; content }[]` — split by page markers, then windows of 1 200 chars with 200 overlap on whitespace boundaries, max 200 chunks; empty pages skipped. |
| `src/embeddings/run.ts` | `semanticStatus()`: rpc `semantic_search_status` + `api_key: embeddingConfig() !== null` ⇒ `{ enabled, reason: null \| "no_vector_extension" \| "no_api_key" \| "subprocessor_inactive" }`. `embedDocument(documentId)`: not enabled ⇒ return (logged once at info). rpc `document_text_for_embedding`; `processingGate(application_id)` refused ⇒ return; spend cap ⇒ return; chunk, embed (`document`), `recordUsage(ctx, "embedding", model, { input_tokens: total, output_tokens: 0 })`, rpc `record_document_chunks`. `embedQuery(text)`: not enabled ⇒ throw `SemanticDisabled(reason)`; text 2–300 chars. |
| `src/embeddings/routes.ts` | `GET /search/semantic/status` ⇒ `semanticStatus()`. `POST /search/embed-query` body `{ tenant_id, query }` ⇒ 503 `{error:"semantic_disabled", reason}` or `{ embedding: number[] }`; records usage to `tenant_id` (agent `embedding`). Both behind the existing bearer hook. |
| `src/transcription/routes.ts` | `POST /transcriptions/run` body `{ request_id }` (uuid) ⇒ `boss.send(QUEUE_DOCUMENT_TRANSCRIBE, { requestId }, { singletonKey: requestId })` ⇒ 202 `{ queued: true }`. |
| `src/clients/jobs.ts` | `runEnrichment()` ⇒ rpc `enrich_due_clients(500)`; `runAnalyticsRefresh()` ⇒ rpc `analytics_refresh`; both log counts, never throw. |
| `src/server.ts` | Register the two route modules. |
| `src/queue/index.ts` | Constants and declarations: `QUEUE_DOCUMENT_TRANSCRIBE = "document.transcribe"` (JOB_POLICY, payload `{requestId}`, handler `runImmediate`); `QUEUE_DOCUMENT_EMBED = "document.embed"` (JOB_POLICY with `retryLimit: 3`, payload `{documentId}`, singletonKey documentId); scheduled (SCHEDULED_POLICY): `transcription.submit` `*/10 * * * *`, `transcription.poll` `*/5 * * * *`, `embedding.sweep` `*/30 * * * *` (rpc `embedding_candidates(50)` ⇒ enqueue), `client.enrich` `17 5 * * *`, `analytics.refresh` `41 5 * * *`. Boot catch-up `send` (CATCH_UP) for `transcription.poll`, `client.enrich`, `analytics.refresh`. Dead letter: payload with `requestId` ⇒ `mark_transcription_requests([{status:'errored', reason:'retries_exhausted'}])`. `export async function enqueueEmbedding(documentId)`. |
| `src/ops/watchdog.ts` | Snapshot `quality_drops` from rpc `data_quality_alerts`; one problem per row `kind: 'field_confidence_drop'` ("Confianza de `<field>` en `<doc_type>` bajó N puntos"). |

Tests (vitest): `src/transcription/__tests__/result.test.ts` (refusal checked before content; max_tokens ⇒ truncated;
page count), `prompt.test.ts` (params carry `thinking: {type:"disabled"}`, no `temperature`, model from env, document
block before text), `batch.test.ts` (fake SDK: results mapped by `custom_id` when returned out of order; usage recorded
with batch flag; expired re-queued once; gate refusal at result time ⇒ `discarded`, nothing stored),
`src/embeddings/__tests__/voyage.test.ts` (request body exactly `{input, model, input_type, output_dimension:1024,
truncation:true}`, ordering by index, wrong dimension throws), `chunk.test.ts`, `run.test.ts` (no key ⇒ no fetch and
`reason:"no_api_key"`; inactive subprocessor ⇒ disabled; gate refused ⇒ no fetch), `src/lib/__tests__/pricing.test.ts`
(haiku 5.5 priced; batch discount), `src/ops/__tests__/watchdog.test.ts` (quality drop ⇒ problem).

**Cost note** (plan § 5.3 updated to Haiku 5.5): a 4-page document ≈ 6 400 input + 3 000 output tokens ⇒ US$0.0021
immediate, US$0.0011 batch. Embedding a 4-page document ≈ 2 000 tokens ⇒ US$0.00012.

---

## 6. web

Patterns: as `02-design.md` § 4.1 (client components with `createClient()`, `.rpc()`, `failure()`, `useToast`,
`PageHeader`, `useUrlState`, `toCsv/downloadCsv`, hand-written types, Node test runner). Orchestrator calls only from
route handlers through `fetchService` after an RLS probe with the user's session (copy
`app/api/cases/[caseId]/ask/route.ts`).

### 6.1 Shared foundation — WEB-A step 1 (others import, never edit)

| File | Content |
| --- | --- |
| `src/lib/client-data/types.ts` | Types for contracts C-1…C-8 (§7) and rows: `ClientAttribute, ClientFact, FactSourceKind, ProfileEntry, ClientProfileView, AttributeConflict, FactHistoryRow, SearchResults, SegmentDefinition, SegmentCondition, SegmentOperator, SegmentPurpose, SegmentPreview, SegmentMembers, DataQualitySummary, PortfolioAnalytics, TranscriptionRequest, DocumentText, SemanticHit, SemanticStatus, AnalyticsStatus`. |
| `src/lib/client-data/labels.ts` | `GROUP_LABELS` (by key prefix: identity Identidad, contact Contacto, address Domicilio, family Familia, employment Empleo, income Ingresos, health Salud, vehicle Vehículo, property Inmueble, credit Crédito, document Documentos, custom Propios), `SOURCE_LABELS` (document Documento, form Formulario, analyst Analista, dsr Solicitud ARCO-POL, derived Calculado, record Registrado en la ficha, import Importado, crm CRM), `EXCLUDED_REASON_LABELS`, `STATUS_LABELS` (Vigente, Sustituido, Excluido, Retirado), `PURPOSE_LABELS` (Operación, Gestión comercial, Mercadeo, Perfiles y ofertas), `OPERATOR_LABELS`, `INCOME_BAND_LABELS`, `TRANSCRIPTION_STATUS_LABELS`, `SEMANTIC_REASON_LABELS` (no_api_key "Falta configurar el proveedor de vectores (Voyage AI).", no_vector_extension "La base de datos no tiene la extensión de vectores.", subprocessor_inactive "Voyage AI no está activado como subencargado en Privacidad."). |
| `src/lib/client-data/format.ts` | Pure: `formatFactValue(kind, value, options?)` (money `US$2,400.00`, dates `28-sep-2026`, enum via labels, booleans Sí/No), `sourceLabel(entry): string` ("Constancia del 28-sep-2026", "Formulario de la solicitud N.º 13", "Corregido por Ana López", "Rectificación (solicitud N.º 4)", "Calculado (edad@1)", "Registrado en la ficha"), `groupOf(key)`. |
| `src/lib/client-data/errors.ts` | `clientDataErrorMessage(code)`: Spanish for `fact_not_in_conflict, custom_key_required, processing_restricted, transcription_not_enabled, document_not_read, query_too_short, sensitive_attribute_not_allowed, unknown_attribute, bad_operator, bad_value, employer_exists, unknown_dataset, semantic_search_unavailable, semantic_disabled`. |
| `src/lib/clients.ts` (edit) | `FieldSource` union adds `{ source: "document" \| "form" \| "analyst" \| "dsr"; fact_id?: string; attribute?: string; application_id?: string; field_review_id?: string; … }` keeping the two existing shapes valid. |

### 6.2 Screens by package

**WEB-A — ficha 360 (DAT-3)**

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `components/clients/client-detail.tsx` (edit) | Tab bar «Resumen» / «Datos del cliente» (`?tab=datos` via `useUrlState`); existing content under Resumen unchanged; `client.viewed` already logged | — |
| `components/client-data/client-data-tab.tsx` | Completeness bar ("Perfil completo al 73 %" + chips of missing), open-conflicts banner, groups (collapsible cards) of `<AttributeRow>`, Plan 2 badges ("En revisión por rectificación" for `locked`, "Tratamiento limitado"), "Otros datos de documentos" (`other_facts`, extras marked "no catalogado") | `client_profile_get` |
| `components/client-data/attribute-row.tsx` | value, source label, confidence (%), date; "acceso restringido" for `restricted`; "por confirmar" + "Confirmar patrono" for `pending_confirmation`; click ⇒ history drawer | — |
| `components/client-data/fact-history-drawer.tsx` | every fact (status, motivo, fuente, valor leído vs normalizado) | `client_fact_history` |
| `components/client-data/conflict-card.tsx` | values with sources; "Elegir este valor" (reviewer) / "Descartar" with note | `resolve_attribute_conflict`, `dismiss_attribute_conflict` |
| `components/client-data/set-value-dialog.tsx` | manual value per kind; employer picker | `set_attribute_value`, `employer_candidates` |
| Tests | `test/unit/client-data-format.test.ts` (every source/kind; restricted never renders a value), `test/unit/client-data-labels.test.ts` (every catalog group prefix, source kind, excluded reason, purpose has a label) | |

**WEB-B — search, segments, quality, analytics (DAT-6 search UI, DAT-7, DAT-8 UI, DAT-9 UI)**

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `components/dashboard/dashboard-shell.tsx` (edit) | `<GlobalSearch>` in the sidebar header and the mobile bar; NAV unchanged | — |
| `src/proxy.ts` (edit) | `/search` in `PROTECTED_PREFIXES` | — |
| `components/search/global-search.tsx` | input "Buscar clientes, DUI, teléfono, documentos…", `Ctrl+K`/`/` focus, Enter ⇒ `/search?q=` | — |
| `app/(dashboard)/search/page.tsx` + `components/search/search-results.tsx` | Tabs «Texto» and «Por significado»; Texto: grouped Clientes / Solicitudes / Documentos, snippet with `«…»` rendered as `<mark>` (escape first, then replace); limited/opposed badge; `logSearch('global')` once per term | `search_clients` |
| `components/search/semantic-results.tsx` + `app/api/search/semantic/route.ts` | Notice "La consulta se envía a un proveedor externo (Voyage AI); no escriba nombres ni números de documento." Disabled state with `SEMANTIC_REASON_LABELS`. Route: `requireStaff` → user client `semantic_search_status` → `fetchService POST /search/embed-query {tenant_id: caller.tenantId, query}` → 503 passthrough → user client `semantic_search_chunks(JSON.stringify(embedding), 10)`; `logSearch('semantic')` | as stated |
| `app/(dashboard)/clients/segments/page.tsx`, `new/page.tsx`, `[id]/page.tsx` + `components/segments/segment-builder.tsx`, `condition-row.tsx` | List (name, purpose, owner, shared); builder: purpose first (explains consent rule per purpose), conditions by kind with catalog attributes (sensitive hidden unless operations and not agent), live count (debounced 500 ms) with excluded counts, sample, save; members table + "Exportar CSV" (reviewers) ⇒ `logExport('segment', rows)` | `client_attributes`, `segment_validate`, `segment_preview`, `segment_save`, `segment_delete`, `segment_members` |
| `app/(dashboard)/clients/page.tsx` (edit) | Button "Filtros avanzados y segmentos" ⇒ `/clients/segments/new?purpose=operations` | — |
| `lib/segments.ts` | Pure: `OPERATORS_BY_KIND`, `emptyCondition(attr)`, `toDefinition(rows)`, `validateLocally(def, catalog, purpose, role)`, `membersToCsv(members)` | — |
| `app/(dashboard)/dashboard/page.tsx` (edit) + `components/dashboard/data-quality.tsx`, `portfolio-analytics.tsx` | "Calidad de datos": coverage table (lowest 10), accuracy by version, conflict rate, top extras with link to "Campos no catalogados", drops in red; "Cartera": bars (`BarList`) of income bands, departments, occupations, completeness by product, note "Grupos de menos de 5 titulares se agrupan en «otros»". Hidden for agents. | `data_quality_summary`, `portfolio_analytics` |
| `app/(dashboard)/settings/analytics/page.tsx` + `components/admin/analytics-replica.tsx` | tenant_admin: explanation (seudonimizada, k = 5, se reconstruye cada noche), status, "Actualizar ahora", "Descargar CSV" per dataset (`logExport('analytics', rows)`), DuckDB snippet `select * from read_csv_auto('sujetos.csv')` | `analytics_status`, `analytics_refresh_tenant`, `analytics_dataset` |
| Tests | `test/unit/segments.test.ts` (operators per kind, sensitive refused for marketing and for agent, CSV columns), `test/unit/search-highlight.test.ts` (HTML in snippet escaped, «» ⇒ mark), `test/unit/analytics-csv.test.ts` | |

**WEB-C — document viewer, transcription, catalogs (DAT-4, DAT-5 UI, DAT-6 UI)**

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `components/documents/extracted-fields.tsx` (edit) | Required fields first; section "Otros datos que imprime el documento" for `extracted_data.extras` (label, value, confidence, "no catalogado") | — |
| `components/documents/document-preview.tsx` (edit) + `components/documents/document-transcription.tsx` | Panel "Transcripción": pages, in-text search with highlight, `truncated` notice; status of the open request ("En cola por lotes — puede tardar hasta 24 h", "Transcribiendo…", "Bloqueada: sin consentimiento para IA"); "Transcribir ahora" (reviewers, type transcribes) ⇒ route; polls request status every 5 s while immediate | `document_texts`, `transcription_requests`, `document_type_transcribes` |
| `app/api/documents/[id]/transcribe/route.ts` | POST `{mode}`: `requireStaff` → user client `request_transcription(id, mode)` → immediate ⇒ `fetchService POST /transcriptions/run {request_id}` (failure: request stays queued, 202 with `{queued:true, warning}`) | — |
| `components/admin/document-types/fields-tab.tsx` (edit) | Checkbox "Transcribir el texto completo de estos documentos (búsqueda en el contenido; costo aprox. US$0.001 por documento con lotes)" ⇒ `extraction.transcribe`; field `canonical` becomes a select of catalog keys (+ "ninguno") | `client_attributes` |
| `app/(dashboard)/settings/document-types/uncatalogued/page.tsx` + `components/admin/document-types/uncatalogued-extras.tsx` | grouped extras ("`afp_name` apareció en 37 constancias"); "Agregar al esquema" ⇒ choose label/kind/category/canonical ⇒ appends a field to the type's definition and `save_document_type_draft` (opens the editor on the draft) | `uncatalogued_extras`, `document_type_for_admin`, `save_document_type_draft` |
| `components/admin/form-schema-editor.tsx` + `lib/form-schema.ts` (edit) | `FieldDef.canonical: string \| null` normalized/serialized; select "Atributo del cliente" | `client_attributes` |
| `app/(dashboard)/settings/attributes/page.tsx` + `components/admin/attribute-catalog.tsx` | Platform attributes read-only (key, label, kind, sensitive, regla); tenant `custom.*` create/edit/archive | `client_attributes`, `save_client_attribute` |
| `app/(dashboard)/settings/employers/page.tsx` + `components/admin/employers-manager.tsx` | list, add/edit with aliases (chips), sector, NIT, archive | `employers`, `save_employer`, `archive_employer` |
| `app/(dashboard)/settings/page.tsx` (edit) | link cards: Atributos del cliente, Patronos, Campos no catalogados, Réplica analítica (the last → WEB-B's route) | — |
| Tests | `test/unit/transcription-pages.test.ts` (marker split, no-marker ⇒ one page, search highlight), `test/unit/form-schema-canonical.test.ts` (canonical round-trips, invalid dropped) | |

Spanish copy guidance: plain, second person "usted" in client-facing text, "tú"-free staff text matching existing
screens; numbers with `es-SV` formatting; never show a sensitive value to an agent, show "Acceso restringido".

---

## 7. Cross-package contracts (exact JSON)

**C-1 `client_profile_get(p_client_id uuid)`**
```json
{"client_id":"uuid","version":3,"refreshed_at":"ts","completeness":72.7,
 "missing":[{"key":"contact.email","label":"Correo electrónico"}],
 "processing_state":"active",
 "groups":[{"group":"income","attributes":[{"key":"income.monthly_gross","label":"Ingreso mensual bruto","kind":"money",
   "value":2400,"restricted":false,"sensitive":false,"conflict":false,"locked":false,"pending_confirmation":false,
   "evidence_date":"2026-09-28","confidence":0.97,"fact_count":3,
   "source":{"kind":"document","fact_id":"uuid","method":"a1b2c3","document_id":"uuid","doc_type":"proof_of_income",
             "doc_type_label":"Constancia de salario","application_id":"uuid","application_number":13,
             "actor_name":null,"dsr_number":null}}]}],
 "conflicts":[{"id":"uuid","attribute_key":"income.monthly_gross","label":"…","opened_at":"ts","winner_fact_id":"uuid",
   "values":[{"value":2400,"fact_ids":["uuid"],"sources":[{"kind":"document","doc_type_label":"…","evidence_date":"…"}]}]}],
 "other_facts":[{"fact_id":"uuid","field_key":"afp_name","label":"AFP","value":"Crecer","extra":true,
   "document_id":"uuid","doc_type":"proof_of_income","doc_type_label":"…","evidence_date":"…","confidence":0.9}]}
```
`source.kind = "record"` has only `kind`. Restricted entries: `value:null, source:{kind}` only.

**C-2 `client_fact_history`** → `[{fact_id, value, raw_value, status, excluded_reason, superseded_by, confidence, evidence_date, created_at, method, source:{…as C-1}}]` newest first.

**C-3 `search_clients`** → `{"clients":[{client_id, full_name, national_id, processing_state, match:"name"|"national_id"|"phone"|"email"|"employer"|"fact", match_label}], "applications":[{application_id, number, client_id, client_name, product_name, status}], "documents":[{document_id, application_id, client_id, client_name, doc_type, page, snippet, rank}], "truncated":false}`.

**C-4 `segment_members`** → `{"segment":{id,name,purpose},"columns":["income.monthly_gross"],"rows":[{"client_id","full_name","email","phone","values":{"income.monthly_gross":2400}}],"next_after":"uuid|null"}`.

**C-5 `data_quality_summary`** → `{window_days, coverage:[{doc_type, doc_type_label, field_key, attribute_key, documents, read, coverage_pct, avg_confidence}], accuracy:[{doc_type, version, prompt_version, field_key, reviewed, confirmed, accuracy_pct}], conflicts:[{attribute_key, label, open, resolved, dismissed, clients_with_facts, rate_pct}], extras:[{doc_type, key, label, occurrences, documents}], completeness:{average, by_product:[{product_name, clients, average}]}, confidence_drops:[{doc_type, field_key, last_7d, prior_7d, drop_points}]}`.

**C-6 `semantic_search_chunks`** → `[{document_id, application_id, client_id, client_name, doc_type, page, snippet, distance}]` (snippet = first 300 chars of the chunk).

**C-7 `record_document_facts`** → `{client_id, facts, extras, excluded, superseded, profile:{changed, version}|null}` or `{skipped:"not_read"|"no_client"|"processing_restricted"|"unchanged"}`.

**C-8 `request_transcription`** → `{request_id, mode, status, existing}`; orchestrator `POST /transcriptions/run {request_id}` → 202 `{queued:true}`; `POST /search/embed-query {tenant_id, query}` → `{embedding:number[1024]}` or 503 `{error:"semantic_disabled", reason}`; `GET /search/semantic/status` → `{enabled, reason}`.

---

## 8. Work packages

Everyone on `develop` of their repo. DB packages verify with the replay (§10) before handing over.

| Package | Owns (creates, or is the only editor of) | Depends on | Before migrations exist |
| --- | --- | --- | --- |
| **DB-A** | `…/20261113000000_client_data_core.sql`; tests `client_facts_test.sql`, `client_profile_test.sql`; `db/supabase/seed.sql` (append backfill call) | design | all (replay) |
| **DB-B** | `…/20261113000100_client_data_search_enrichment.sql`; tests `client_enrichment_test.sql`, `client_search_test.sql`, `client_segments_test.sql` | DB-A merged (replaces its stubs) | write in parallel with DB-A from this contract; test after A |
| **DB-C** | `…/20261113000200_client_data_vectors_analytics.sql`; tests `semantic_search_test.sql`, `analytics_replica_test.sql` | DB-A merged (DB-B's tables `document_texts` needed at apply time ⇒ apply order A→B→C) | same |
| **ORCH-A** | `src/agents/{types,extraction-agent}.ts`, `src/documents/{extract,facts,normalize}.ts`, deletes `src/documents/client-facts.ts` + its test, `src/privacy/minimize.ts`, `src/cases/{bundle,ask}.ts`, their tests | contracts C-7 | all with mocked rpc; **deploy only after A+B are in the target DB** (rpc `record_document_facts` missing ⇒ logged, not fatal) |
| **ORCH-B** | `src/transcription/**`, `src/embeddings/**`, `src/clients/jobs.ts`, `src/queue/index.ts`, `src/server.ts`, `src/lib/{pricing,usage}.ts`, `src/ops/watchdog.ts`, `render.yaml`, `.env.example`, their tests | C-8, §3.8/§3.9 RPC names | all with fake SDK/fetch; deploy after A+B+C |
| **WEB-A** | §6.1 foundation (step 1, first commit), `lib/clients.ts`, `components/clients/client-detail.tsx`, `components/client-data/**`, its tests | C-1, C-2 | all |
| **WEB-B** | `components/dashboard/dashboard-shell.tsx`, `src/proxy.ts`, `components/search/**`, `app/(dashboard)/search/**`, `app/api/search/**`, `app/(dashboard)/clients/segments/**`, `components/segments/**`, `lib/segments.ts`, `app/(dashboard)/clients/page.tsx`, `app/(dashboard)/dashboard/page.tsx`, `components/dashboard/{data-quality,portfolio-analytics}.tsx`, `app/(dashboard)/settings/analytics/**`, `components/admin/analytics-replica.tsx`, its tests | WEB-A step 1 | all |
| **WEB-C** | `components/documents/{extracted-fields,document-preview,document-transcription}.tsx`, `app/api/documents/[id]/transcribe/**`, `components/admin/document-types/{fields-tab,uncatalogued-extras}.tsx`, `app/(dashboard)/settings/document-types/uncatalogued/**`, `components/admin/form-schema-editor.tsx`, `lib/form-schema.ts`, `app/(dashboard)/settings/{attributes,employers}/**`, `components/admin/{attribute-catalog,employers-manager}.tsx`, `app/(dashboard)/settings/page.tsx`, its tests | WEB-A step 1 | all |
| **DOCS** | `docs/supabase-schema.md` (§ "Client data: facts, profiles, search, segments, analytics" + § "Subject export `tramiq.subject-export/v1`" incl. `profile_provided`), `docs/architecture.md` (data section with the §3 diagram of the plan, transcription batch lifecycle, embeddings fail-closed, replica), `CLAUDE.md` (invariants §9), `STATUS.md`/`plans/03-PLAN-STATE.md` after verification | all merged | — |

**WEB-A step 1** = `lib/client-data/{types,labels,format,errors}.ts` + `lib/clients.ts` edit (half a day). Afterwards a
package needing a new shared type keeps it local; WEB-A folds them in at the end.

Merge/apply order: DB-A → DB-B → DB-C applied to dev (`vtcrbrajexbsberrqwvo`) with suites through the TAP shim →
production rehearsal in a rolled-back transaction → production `apply_migration` A, B, C → `backfill_client_facts`
+ regression report on production → web (A, then B/C any order) → ORCH-A → ORCH-B → `graphify update .` per package.

---

## 9. CLAUDE.md invariants to add (DOCS)

- **Facts are the source of truth for client data; the profile and the `clients` columns are derived.** Every value
  enters `client_facts` through a `record_*` function or a trigger, with source, date and confidence; nothing writes a
  mapped `clients` column except `refresh_client_profile()`, rectification and staff edits (which become facts). An
  older piece of evidence never overwrites a newer source, and a column is never nulled by a refresh.
- **Sensitive client data never reaches an agent, a commercial segment or the analytics replica.** RLS on
  `client_facts`, masking in `client_profile_get()`, `segment_validate()` and `analytics_refresh()` each enforce it.
- **A new external processor fails closed until it is a registered, active subprocessor.** Semantic search requires
  the `vector` extension, `VOYAGE_API_KEY` and the active `Voyage AI` row in `subprocessors`; missing any ⇒ disabled
  with a stated reason, never a silent call.
- **Pseudonymized data is personal data.** `analytics.*` is registered in `personal_data_stores`, rebuilt only from
  `active` clients, and erased with the subject; its key lives in `analytics_private`, unreadable by every API role.
- **Plan 2 report and erasure functions are wrapped, not copied.** `data_subject_footprint`, `dsr_access_report`,
  `dsr_portability_export`, `execute_dsr_erasure`, `privacy_anonymize_applications` are wrappers over `*_base`;
  extend through `privacy_p3_*` hooks. Replacing a `*_base` body means re-checking the wrapper.

---

## 10. Verification

```bash
# db (after the run.mjs extension change in §2)
node C:/Users/Sebas/AppData/Local/Temp/claude/170f4bc0089f9df9/83ca3cad-1521-429e-8771-899dcc964eff/scratchpad/db-replay/run.mjs client_ semantic analytics privacy
node C:/Users/Sebas/AppData/Local/Temp/claude/170f4bc0089f9df9/83ca3cad-1521-429e-8771-899dcc964eff/scratchpad/db-replay/run.mjs   # every suite
cd ai-orchestrator && npm test && npx tsc --noEmit
cd web && npm run typecheck && npm run lint && npm test && npm run build
```

Production sanity after backfill (conductor, read-only except the two function calls):
`select backfill_client_facts();` (repeat until `remaining = 0`), `select * from backfill_regression_report();` (expect
0 rows), `select count(*) from client_facts; select count(*) from client_profiles;` (expect ≈ 17 profiles),
`select analytics_refresh();`.

**Demo script** (tenant `seguros`; warm both services):
1. Configuración → Tipos de documento → Constancia de salario: tick "Transcribir el texto completo", publish.
2. New application with DUI + constancia (client with AI consent). After extraction: client → «Datos del cliente»:
   salary, employer ("por confirmar" against the catalog), address with official spelling, age, income band,
   completeness; a form-declared salary 20 % off ⇒ conflict card → "Elegir este valor".
3. Document viewer: extras ("AFP: Crecer — no catalogado"); "Transcribir ahora" ⇒ text by page within ~30 s.
4. Top bar: search "constansia crecer" ⇒ client, application and the document page with the highlighted hit.
5. Settings → Campos no catalogados ⇒ "Agregar al esquema" `afp_name` as `custom.afp_name`.
6. Clientes → Segmentos: marketing, income ≥ 1 500 ⇒ count excludes clients without marketing consent; adding
   `health.bmi` is refused; export CSV (access log shows `export.generated`).
7. Panel: Calidad de datos and Cartera.
8. Búsqueda por significado: shows "Falta configurar el proveedor de vectores (Voyage AI)" (owner has no account);
   with a key + subprocessor activated it answers "¿quién trabaja en un banco?".
9. Réplica analítica: Actualizar ahora ⇒ counts, suppressed; download CSV; open in DuckDB.
10. Privacidad → solicitud de acceso: the report shows "Datos del cliente" with sources; erasure simulation lists
    `client_facts`, `document_texts`, `analytics.subjects`.
11. Log in as agent: 360 shows health values "Acceso restringido"; no transcription of the lab results.
12. Batch: queue the rest with `select queue_transcriptions();` (conductor) and show the requests "En cola por lotes".

---

## 11. Risks and deliberate simplifications

- **Wrapping by rename** (D6): a future migration that `create or replace`s a Plan 2 original name would silently
  replace the wrapper. Mitigated by the invariant in §9 and the pgTAP checks of the wrapped outputs.
- **Refresh inline in triggers** (D2): a slow refresh slows the triggering statement (field review, submit). At demo
  volume it is milliseconds; at scale move to a job keyed by client (the plan's original design).
- **Survivorship deviation D4/D5** changes the plan's rule wording; worth showing the owner.
- **Batch spend cap** is checked at submit time; cost is recorded when results arrive, so a tenant can overshoot by
  one batch. Free-tier sleep: polls run only while the service is awake (boot catch-up runs one).
- **k-anonymity covers `analytics.subjects` only**; joining `analytics.applications` (product, month) can narrow a
  class. Accepted for the demo, stated on the replica page.
- **Secret-prefix SHA-256, key in a table** (not Vault, not HMAC). Upgrade path: key in `supabase_vault`.
- **Query text to Voyage** is staff-typed and may contain personal data; mitigated by the UI notice only.
- **Identity facts never written** to `clients`; a wrong typed DUI stays until a person fixes it (as today).
- **Not built:** occupation codes (D8), configurable income bands (D9), events table for Plan 4 (the
  `client_profiles.version` bump is the hook), external enrichment (bureau, registry, geocoding — plan § 5.4),
  multi-valued attributes (`cardinality` stored, only `single` evaluated), re-extraction of old documents.
- **Database size:** facts ≈ 30 per document; fine on the free plan at demo volume (24 MB today); the plan's paid-plan
  warning stands.

---

## 12. Questions for the conductor

1. Is `claude-haiku-5-5` enabled on the organization's API key, and are Message Batches allowed for it? (Not
   verifiable locally; ORCH-B's first dev run will show a 404/403.)
2. Before applying A to production, run read-only:
   `select distinct f->>'canonical' from document_type_versions v, jsonb_array_elements(v.definition->'fields') f where f->>'canonical' is not null;`
   — any value not in the §3.1 catalog stays an uncatalogued fact; tell DB-A if a tenant typed custom canonicals
   worth seeding.
3. Also read-only: `select count(*) from clients where field_sources <> '{}'::jsonb;` — if 0, the production
   regression check is vacuous and only the pgTAP fixture proves it.
4. Which document type should demo transcription (suggested: `proof_of_income` in `seguros`), and should the
   historical fill (`queue_transcriptions()`) run on production (≈ 41 documents ≈ US$0.05 in batch)?
5. The brief says `MODEL_DEFAULT=claude-sonnet-4-5`; `ai-orchestrator/render.yaml` on `develop` already declares
   `claude-sonnet-5-5`. Confirm which is deployed (out of scope here; affects nothing in this design).
