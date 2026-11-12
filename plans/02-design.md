# Plan 2 — technical design (LPD-1 … LPD-13)

*2026-11-11. Implementation design for [`02-cumplimiento-lpdp-arco-pol.md`](02-cumplimiento-lpdp-arco-pol.md).
Audience: engineers who have not read the plan. Goal is a **presentable demo**: every LPD component has
a working end-to-end flow. Where the plan's SQL sketch conflicts with the existing schema, this file
follows the schema and says so (marked **⚠ deviation**). Schema keys English, UI Spanish, migrations
append-only. Never open `qualifier-secrets.env.txt`.*

Conventions used below: "staff" = a `profiles` row with role in `superadmin | tenant_admin | underwriter | agent`.
"admin of T" = `app_current_role() = 'superadmin'` or (`'tenant_admin'` and `current_tenant_id() = T`).
"MFA gate" = `perform require_mfa_if_tenant_requires(T)` (20261107000200). "service-only" = `revoke all … from
public, anon, authenticated; grant execute … to service_role`. Every SECURITY DEFINER function here is
`language plpgsql security definer set search_path = public` and raises stable lower-case codes
(`raise exception 'not_found' using errcode = 'P0002'`; `'42501'` = not allowed, `'22023'` = invalid
state/input), the convention `web/src/lib/public/server.ts` (`PublicError`) and `lib/db-errors.ts` parse.

---

## 1. Scope

| LPD | Status | What is built / how it is simplified / why deferred |
| --- | --- | --- |
| 0 | Checklist only | §7. No code. MFA stays optional (owner decision). |
| 1 Inventory, RAT | **Built** | `personal_data_stores` (+ invariant test), `subprocessors`, `processing_inventory()`, `data_subject_footprint()`. RAT = screen + CSV + printable HTML (no XLSX/PDF). Form questions get optional `category`/`sensitive` keys, read by the inventory; `form_schema_valid()` is **not** changed (it already tolerates unknown keys) — unclassified questions are counted on the dashboard instead of blocking publication. |
| 2 Privacy notice | **Built** | `privacy_settings`; `consent_texts` gains `kind`, `sections`, `requires_reconsent`. Generator in TS (web) from `processing_inventory()`. Public page `/privacidad/<slug>` + permanent version page. Copy to subject on consent = outbox `consent_copy` with a permanent link (no PDF). Notice change ⇒ flag `requires_reconsent` + banner on client panels (no campaign). Tramiq's own notice (L12): deferred, legal text. |
| 3 Purposes, consent | **Built** | `processing_purposes` (seeded 12), `consent_records` append-only, `client_consent_state` view, `has_consent()`. Channels: **consent link** (`/consentimiento/<token>`) and **staff signed paper form** (`consent_form` document). Self-service channel **dropped** (intake removed). Per-tenant switch `consent_enforced_since`, ON for `seguros`/`medico`, applied per application through a stamped column (§2.2). Revocation by staff and via DSR. |
| 4 Processing state | **Built** | `clients.processing_state` + `field_locks`; `processing_gate()`; control points in `submit_application`, `pipeline_sweep_candidates`, `auto_decide_case`, `application_list`, `client_list`, `clients_select`, orchestrator. Plan 3/4 hooks: only the functions. |
| 5 DSR engine | **Built** | `data_subject_requests`, `dsr_subjects`, `dsr_events`, `dsr_attachments`, `business_holidays` (SV 2026–2028), `add_business_days()`, staff functions, deadlines in watchdog + daily job. `privacy_officer` role **deferred**: tenant_admin (and superadmin) only. "Recibidas por Tramiq" = superadmin registers a DSR into any tenant with `channel = 'forwarded_by_processor'` (no separate screen). |
| 6 Portal | **Built** | `/privacidad/<slug>/solicitud` + `/privacidad/<slug>/seguimiento/<token>`; Turnstile + rate limit + OTP; never reveals whether data exists; report download needs staff identity verification + fresh OTP; link valid 15 days. ACE model forms: deferred (not published). |
| 7 Access report, portability | **Built** | `dsr_access_report()` JSON → printable HTML + JSON download; portability JSON `tramiq.subject-export/v1` + CSV. Third-party form keys excluded; fraud signals withheld as partial denial (configurable, L8). ZIP of originals: **deferred** (optional per owner). |
| 8 Rectify, erase, propagate | **Built** | `rectify_subject_data()`, `execute_dsr_erasure(p_simulate)` (simulation first), `redact_audit_metadata()`, block-instead-of-erase when a legal retention applies, `dsr_propagations` (manual recipients). `delete_client()` also redacts the audit log. Re-score after rectification = existing "Volver a puntuar" button, not automatic. |
| 9 Retention | **Built (partial classes)** | `retention_policies` (13 classes seeded as unapproved proposals), `legal_holds`, `retention_candidates()`, `retention_apply()`, orchestrator `privacy.retention` daily. The job only acts on **approved** policies and only on `staff_draft`, `withdrawn_application`, `declined_application`, `access_log`; other classes are configuration shown as "sin ejecución automática". |
| 10 Security, minimization | **Built (simplified)** | `access_log` (not partitioned) + `log_access()`; document rows of sensitive types hidden from `agent` by RLS + placeholder list; sensitive form answers masked for `agent` by `application_form_for_viewer()` (UI-level — base column still readable, **documented gap**); `minimizeForModel()`; staff confidentiality acknowledgement gate. MFA: status only. Column encryption: not proposed (plan). |
| 11 Incidents | **Built** | `security_incidents`, `incident_tenants`, `incident_events`; superadmin screen with 72 h clock and notification checkboxes + Spanish templates; subject notice through outbox. Watchdog-opened draft incidents: **deferred**. |
| 12 Transfers | **Built** | `data_transfers` append-only + manual registration screen; portability-to-controller writes one. ACE communication: process, not code. |
| 13 Accountability | **Built** | `compliance_summary()`, Privacidad → Resumen dashboard, printable evidence package + JSON. Tenant exit (DPA return/purge): **deferred**. |

---

## 2. Database contract

Three migrations, applied in order, each in one transaction, PGlite-replayable (no `CONCURRENTLY`, no
pg_cron, no extensions beyond `pgcrypto`; `auth.mfa_factors` is read only through `to_regclass` +
`EXECUTE`, the pattern `session_aal()` uses). Files:

- **A** `db/supabase/migrations/20261111000000_privacy_inventory_consent.sql` — LPD-1/2/3
- **B** `db/supabase/migrations/20261111000100_privacy_state_requests.sql` — LPD-4/5/6
- **C** `db/supabase/migrations/20261111000200_privacy_execution_security.sql` — LPD-7…13

### 2.0 Shared helpers (in A, used by B and C)

```sql
-- Append-only guard. UPDATE always refused. DELETE refused unless it runs inside a
-- cascade (an FK action is itself a trigger, so our trigger sees depth > 1) or the
-- transaction set app.privacy_purge = 'on' (retention_apply, execute_dsr_erasure).
create function prevent_append_only_change() returns trigger language plpgsql set search_path = '' as $$
begin
  if tg_op = 'DELETE' and (pg_trigger_depth() > 1 or current_setting('app.privacy_purge', true) = 'on') then
    return old;
  end if;
  raise exception '% is append-only', tg_table_name using errcode = '42501';
end $$;

-- Admin of the tenant (+ MFA gate). Returns the caller role for audit rows.
create function require_privacy_admin(p_tenant uuid) returns text  -- stable, security definer
  -- superadmin, or tenant_admin of p_tenant; else raise 'privacy_admin_only' (42501); then MFA gate.
-- Any staff of the tenant (superadmin included). Returns the role. Raise 'not_allowed' (42501).
create function require_tenant_staff(p_tenant uuid) returns text
-- Outbox insert for privacy kinds (internal, service-only).
create function privacy_notify(p_tenant_id uuid, p_kind text, p_email text, p_phone text,
                               p_client_id uuid, p_dsr_id uuid, p_payload jsonb) returns void
  -- inserts intake_notifications(tenant_id, kind, recipient, recipient_phone, client_id, dsr_id, payload)
  -- payload always gets tenant_name (branding.display_name or name) and tenant_slug.
  -- No-op when both p_email and p_phone are null. Never put a token or code in p_payload.
```

Reused unchanged (generic, not intake-specific): `intake_new_token()` (64-hex token), `intake_hash(text)`
(SHA-256 hex), `dui_digits()`, `dui_valid()`, `intake_phone()` (E.164 for SV). Calling them from new
SECURITY DEFINER functions is fine (they are owner-executable). No `intake_*` *flow* function is called.

`audit_log.actor_type` has no `subject` value; portal/consent-link actions are recorded with
`actor_type = 'applicant'`, `actor_id = null` (⚠ deviation: no constraint change).

### 2.1 Migration A — inventory, settings, notice, purposes, consent

**Tables**

```sql
create table personal_data_stores (           -- platform registry; written by migrations only
  table_name text primary key,
  description text not null,
  subject_link text not null,                  -- 'clients.id', 'applications.client_id', 'documents.application_id→applications.client_id', 'profiles.id', …
  categories text[] not null,                  -- identity, contact, financial, health, inferred, technical, staff
  holds_sensitive boolean not null,
  access_handler text not null check (access_handler in ('include','include_redacted','exclude')),
  access_note text,
  erase_handler text not null check (erase_handler in ('delete','anonymize','redact_fields','retain_legal','not_applicable')),
  retention_class text not null);
-- RLS on; select to authenticated (true); no write grants. service_role all.

create table subprocessors (                    -- platform; superadmin writes via save_subprocessor()
  id uuid primary key default gen_random_uuid(),
  name text not null, service text not null, country char(2) not null, region text,
  data_categories text[] not null, receives_sensitive boolean not null, purpose text not null,
  safeguards text, dpa_signed_at date, dpa_url text, active boolean not null default true,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now());
-- RLS: select to authenticated using (true). Writes: function only.

create table privacy_settings (                  -- one row per tenant, seeded by trigger
  tenant_id uuid primary key references tenants (id) on delete cascade,
  legal_name text, address text, privacy_email text, privacy_phone text,
  responsible_person text,                      -- optional (former Delegado; D.L. 659)
  changes_medium text,                          -- Art. 24 g
  portal_enabled boolean not null default true,
  consent_enforced_since timestamptz,           -- null = enforcement off
  third_party_form_keys text[] not null default '{beneficiaries,dependents,beneficiarios,dependientes}',
  withhold_fraud_signals boolean not null default true,   -- [abogado L8]
  country char(2) not null default 'SV',
  dsr_response_days int not null default 20 check (dsr_response_days between 1 and 60),
  dsr_extension_days int not null default 20, dsr_prevention_days int not null default 10,
  dsr_incompetent_days int not null default 5, dsr_denial_notice_days int not null default 3,
  propagation_days int not null default 5, revocation_days int not null default 5,
  updated_at timestamptz not null default now(), updated_by uuid references auth.users (id) on delete set null);
-- RLS: select to authenticated using (tenant_id = current_tenant_id() or superadmin). Writes: functions.

alter table consent_texts
  add column kind text not null default 'privacy_notice'
    check (kind in ('privacy_notice','consent','bureau_authorization','staff_confidentiality')),
  add column sections jsonb not null default '[]' check (jsonb_typeof(sections) = 'array'),
  add column requires_reconsent boolean not null default false;
alter table consent_texts drop constraint consent_texts_tenant_id_version_key;   -- verify the name with \d first
alter table consent_texts add constraint consent_texts_tenant_kind_version_key unique (tenant_id, kind, version);
drop index consent_texts_one_published_per_tenant;
create unique index consent_texts_one_published_per_kind on consent_texts (tenant_id, kind) where status = 'published';
-- prevent_published_consent_edits(): re-create so sections/kind/requires_reconsent are also frozen once not draft.
grant select (kind, sections, requires_reconsent) on consent_texts to authenticated;  -- table grant already covers it; keep explicit

create table processing_purposes (
  tenant_id uuid not null references tenants (id) on delete cascade,
  code text not null check (code ~ '^[a-z][a-z0-9_]{1,40}$'),
  label text not null, description text not null, legal_basis text not null,
  requires_consent boolean not null,            -- false = informed only (no checkbox)
  optional boolean not null,                    -- true = can refuse and keep the service
  written_required boolean not null default false,  -- typed name + drawn signature
  applies_to text not null default 'all' check (applies_to in ('all','sensitive_products')),
  core boolean not null default false,          -- ai_processing, international_processing, sensitive_health: cannot be deactivated
  active boolean not null default true, sort_order int not null default 100,
  primary key (tenant_id, code));
-- RLS: select tenant staff. Writes: save_processing_purpose().

create table consent_requests (                 -- the consent link
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  client_id uuid not null, application_id uuid,
  token_hash text not null unique,
  status text not null default 'pending'
    check (status in ('pending','completed','expired','revoked','locked')),
  channel text not null check (channel in ('email','whatsapp')),
  contact_email text, contact_phone text,       -- snapshot of the contact ON FILE at creation
  requires_written boolean not null,            -- product handles sensitive data
  purposes text[] not null,                     -- codes shown, frozen at creation
  failed_attempts int not null default 0,       -- DOB/DUI misses; 5 => locked
  identity_method text check (identity_method in ('date_of_birth','national_id')),
  identity_verified_at timestamptz,
  otp_hash text, otp_expires_at timestamptz, otp_attempts int not null default 0,
  otp_sent_count int not null default 0, otp_sent_at timestamptz, otp_channel text,
  contact_verified_at timestamptz, completed_at timestamptz,
  expires_at timestamptz not null,              -- now() + 7 days
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  unique (tenant_id, id),
  constraint consent_requests_client_same_tenant foreign key (tenant_id, client_id) references clients (tenant_id, id) on delete cascade,
  constraint consent_requests_application_same_tenant foreign key (tenant_id, application_id)
    references applications (tenant_id, id) on delete set null (application_id));
-- RLS select tenant staff. Column grant to authenticated: every column EXCEPT token_hash, otp_hash,
-- otp_expires_at, otp_attempts. No write grants.

create table consent_records (                  -- append-only
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  client_id uuid not null,                      -- ⚠ deviation: NOT NULL and no FK (self-service channel gone;
                                                -- no FK so delete_client and erasure never touch proof rows)
  application_id uuid, consent_request_id uuid,
  purpose_code text not null,
  consent_text_id uuid not null, consent_version int not null, text_sha256 text not null,
  decision text not null check (decision in ('granted','refused','revoked')),
  channel text not null check (channel in ('consent_link','staff_signed_form','portal','staff_recorded','imported')),
  identity_basis text not null check (identity_basis in
    ('link_dob_otp','link_dui_otp','signed_form_checked','in_person_id_check','dsr_verified','staff_recorded')),
  signature_kind text check (signature_kind in ('checkbox','typed_name','drawn','scanned_autograph','certified_e_signature')),
  signature_path text,                          -- privacy bucket: <tenant_id>/signatures/<consent_request_id>.png
  evidence_document_id uuid,                    -- consent_form document (paper channel)
  evidence jsonb not null default '{}',         -- {typed_name, otp_channel, contact_hint, signed_on}
  dsr_id uuid, actor_id uuid references auth.users (id) on delete set null,
  ip inet, user_agent text,
  created_at timestamptz not null default clock_timestamp());
create index consent_records_client_idx on consent_records (client_id, purpose_code, created_at desc);
create trigger consent_records_append_only before update or delete on consent_records
  for each row execute function prevent_append_only_change();
-- RLS select tenant staff. Column grant to authenticated: all columns except ip, user_agent.

create view client_consent_state with (security_invoker = true) as
  select distinct on (r.client_id, r.purpose_code)
         r.tenant_id, r.client_id, r.purpose_code, r.decision, r.created_at as decided_at, r.channel,
         r.consent_text_id, r.consent_version, r.id as consent_record_id,
         (r.consent_version < coalesce((select max(t.version) from consent_texts t
             where t.tenant_id = r.tenant_id and t.kind = 'privacy_notice' and t.status = 'published'
               and t.requires_reconsent), 0)) as reconsent_needed
    from consent_records r order by r.client_id, r.purpose_code, r.created_at desc;
grant select on client_consent_state to authenticated;

alter table applications add column consent_enforced boolean not null default false;
-- Stamped at insert by trigger applications_stamp_consent_enforcement (BEFORE INSERT):
--   new.consent_enforced := exists (select 1 from privacy_settings ps where ps.tenant_id = new.tenant_id
--                                    and ps.consent_enforced_since is not null and ps.consent_enforced_since <= now());
-- and kept by the same trigger on UPDATE (new.consent_enforced := old.consent_enforced).

alter table intake_notifications
  add column client_id uuid, add column dsr_id uuid;     -- no FKs (outbox, dormant intake columns stay)
alter table intake_notifications drop constraint intake_notifications_kind_check;  -- verify name
alter table intake_notifications add constraint intake_notifications_kind_check check (kind in (
  'submitted','info_requested','decided',
  'consent_copy','dsr_received','dsr_prevention','dsr_extended','dsr_resolved','dsr_returned',
  'dsr_response_ready','privacy_deadline','incident_notice'));
```

**⚠ Why `applications.consent_enforced` and not `created_at >= consent_enforced_since`:** `refresh_demo_dates()`
(20261107000200) shifts `applications.created_at` forward in demo tenants, so seeded applications would
silently cross the threshold and lose their AI pipeline. A column stamped at insert is immune.

Storage: `insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types) values
('privacy','privacy',false,10485760, array['image/png','image/jpeg','image/webp','application/pdf'])
on conflict (id) do nothing;` — no storage policies (service role only; staff read through web routes).

**Functions (A)**

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `seed_tenant_privacy(p_tenant_id uuid) returns void` | definer, service-only | Idempotent (`on conflict do nothing`): `privacy_settings` row; 12 purposes (table below); `copy_document_type_template(p_tenant_id,'consent_form')`. Called by trigger `tenants_seed_privacy` (AFTER INSERT on tenants — runs after `tenants_seed_document_types` alphabetically) and once for every existing tenant at the end of A. Migration C extends the seed with retention policies and a staff confidentiality text by re-creating this function. |
| `copy_document_type_template(p_tenant_id uuid, p_key text) returns uuid` | definer, service-only | If the tenant lacks `p_key`, copy template (tenant_id null) row + its current version exactly as `seed_tenant_document_types` lines 2351–2360 of 20261108000000 do, including setting `current_version_id`. Returns the tenant type id. |
| `product_handles_sensitive(p_product_id uuid) returns boolean` | stable definer; authenticated, service_role | True if any `products.form_schema.fields[]` object has `"sensitive": true`, or the product's published playbook `required_documents[].doc_type` names a tenant document type whose current version has any field with `sensitive = true`. Derived, never configured (plan). |
| `has_consent(p_client_id uuid, p_purpose text) returns boolean` | stable definer; authenticated, service_role | Latest `consent_records` row for (client, purpose) has `decision = 'granted'`. Under a user JWT returns false when the client is not in `current_tenant_id()` (superadmin: any). |
| `save_privacy_settings(p jsonb) returns void` | definer; authenticated | `require_privacy_admin(current_tenant_id())` (superadmin passes `p->>'tenant_id'`). Updates the editable columns present in `p` (all but `tenant_id`, `consent_enforced_since`). audit `privacy.settings_saved` (entity `tenant`). |
| `set_consent_enforcement(p_tenant_id uuid, p_on boolean) returns timestamptz` | definer; authenticated | admin; sets `consent_enforced_since = case when p_on then coalesce(existing, now()) else null end`; audit `privacy.consent_enforcement_changed {from,to}`. |
| `save_processing_purpose(p jsonb) returns void` | definer; authenticated | admin of `current_tenant_id()`; upsert by `code`; a `core` purpose cannot get `active=false` (`core_purpose`, 22023); `code` immutable once it has consent records. audit `privacy.purpose_saved`. |
| `save_privacy_text(p_id uuid, p_kind text, p_title text, p_body text, p_sections jsonb, p_requires_reconsent boolean default false) returns uuid` | definer; authenticated | Same contract as `save_consent_text` (20261028000100:1609) plus kind; new draft version = `max(version)+1` **per (tenant, kind)**; at most one draft per kind (update it). `sections`: `[{key, title, body}]`, keys from `responsible, data, legal_basis_purposes, recipients, international, retention, security, rights, revocation, changes, cookies`. |
| `publish_privacy_text(p_id uuid) returns void` | definer; authenticated | admin + MFA gate; archives the published row **of the same kind** only; audit `consent_text.published {version, kind}`. |
| `publish_consent_text(p_id uuid)` | **re-created** | Body of 20261028000100:1641 but the archive statement adds `and kind = target.kind`. `save_consent_text` re-created to compute version per `(tenant, 'privacy_notice')` and insert `kind = 'privacy_notice'`. Kept for the old `ConsentTextsManager` until WEB-1 removes it. |
| `save_subprocessor(p jsonb) returns uuid` | definer; authenticated | superadmin only; upsert by `p->>'id'`; audit with tenant = none → write to `audit_log` is impossible (tenant_id not null); record nothing (platform table), set `updated_at`. |
| `processing_inventory(p_tenant_id uuid) returns jsonb` | stable definer; authenticated, service_role | `require_tenant_staff(p_tenant_id)`. Returns `{settings, notice:{id,version,published_at}|null, activities:[{product_id, product_name, product_type, sensitive, purposes:[code], data_categories:[text], form_fields:[{key,label,category,sensitive}], document_types:[{key,label,categories:[text],sensitive}], retention_class:'approved_application'}], fixed_activities:[{key:'staff_accounts'|'notifications'|'fraud_prevention', …same keys}], purposes:[…rows], subprocessors:[…active rows], stores:[…personal_data_stores], unclassified:{form_fields:int, document_fields:int}}`. A form field without `category` is reported as `'unclassified'`. |
| `data_subject_footprint(p_tenant_id uuid, p_client_ids uuid[]) returns jsonb` | stable definer; **service_role + authenticated admin** | `require_privacy_admin(p_tenant_id)` when `auth.uid()` is not null. Every query filters `tenant_id = p_tenant_id` **and** `client_id = any(p_client_ids)` (a foreign client id yields nothing). Returns `{clients:[row minus nothing], applications:[{id, number, product_name, status, created_at, submitted_at, form_data}], documents:[{id, application_id, doc_type, status, uploaded_at, extracted_data, storage_path}], scores:[{application_id, final_score, tier, decision, rule_trace, rationale, ai_summary, created_at, playbook_version}], decisions:[case_decisions rows], comments:[{case_id, body, created_at}], field_reviews:[…], consents:[client_consent_state rows + history], intake_sessions:[contact columns], notifications:[{kind, recipient, created_at}], counts:{audit_log:int}}`. B and C re-create it adding `field_locks`, `access_log`, `data_transfers`, `dsr`. |
| `create_consent_request(p_client_id uuid, p_application_id uuid default null, p_channel text default null) returns jsonb` | definer; authenticated | Caller role in `tenant_admin, agent, underwriter` of the client's tenant (or superadmin). Refuse: `notice_not_published` (no published `privacy_notice`), `no_contact_on_file` (client has neither email nor phone; whatsapp needs phone), `client_not_active` (B adds: processing_state ≠ active). Revokes earlier `pending` requests for the client (`status='revoked'`). `purposes` = active purposes with `requires_consent` (+ `applies_to='sensitive_products'` only if `requires_written`); `requires_written = product_handles_sensitive(app.product_id)` (false without application). Returns `{id, token, expires_at, channel, email, phone, tenant_name, tenant_slug}` — the **only** time the token exists in clear. audit `consent_request.created` (entity `client`, metadata `{application_id, channel}`). |
| `revoke_consent_request(p_id uuid) returns void` | definer; authenticated | same roles; pending → revoked; audit. |
| `consent_link_get(p_token text) returns jsonb` | stable definer; service-only | `P0002 link_invalid` for unknown hash. Computes stage: `unavailable` (status ≠ pending or expired — sets nothing in a stable fn; reason in `reason`), `identify`, `code`, `review`, `done`. Returns `{stage, reason, tenant:{display_name, color, slug}, client_first_name (only after identity), contact_hint:{email:'a***@x.com', phone:'****1234'}, channels:['email','whatsapp'], notice:{id, version, title, sections, body}, purposes:[{code,label,description,legal_basis,optional,written_required}], requires_written, expires_at, request_id, signature_path}` — **web strips `request_id` and `signature_path` before replying to a browser** (they carry tenant id). |
| `consent_link_verify_identity(p_token text, p_date_of_birth date, p_national_id text) returns jsonb` | definer; service-only | Stage must be `identify`. Match `clients.date_of_birth = p_date_of_birth` or `dui_digits(clients.national_id) = dui_digits(p_national_id)`; miss ⇒ `failed_attempts+1`, at 5 `status='locked'`, raise `identity_mismatch` (22023) / `link_locked`. Hit ⇒ `identity_verified_at`, `identity_method`. Returns `{stage:'code'}`. audit `consent_link.identity_verified` / `.identity_failed`. |
| `consent_link_issue_code(p_token text, p_channel text default null) returns jsonb` | definer; service-only | Stage `code`; `intake_issue_code` limits verbatim: ≤5 sends, ≥30 s apart (`code_too_soon`, `too_many_codes`), 6 digits, `otp_hash = intake_hash(id::text || ':' || code)`, 10 min. Channel must be one on file. Returns `{code, email, phone, channel}` (web sends it; never stored in clear). |
| `consent_link_verify_code(p_token text, p_code text) returns jsonb` | definer; service-only | ≤5 attempts per code (`code_invalid`, `code_expired`, `too_many_attempts`); sets `contact_verified_at`. Returns `{stage:'review'}`. |
| `consent_link_sign(p_token text, p_decisions jsonb, p_typed_name text, p_signature_path text, p_ip text, p_user_agent text) returns jsonb` | definer; service-only | Stage `review`. `p_decisions = [{"purpose":"ai_processing","decision":"granted"\|"refused"}]` must cover exactly `request.purposes` (`decisions_incomplete`). If `requires_written`: `p_typed_name` 2–200 chars and `p_signature_path = tenant_id || '/signatures/' || id || '.png'` (`signature_required`). Inserts one `consent_records` row per decision: channel `consent_link`, `identity_basis = 'link_dob_otp'|'link_dui_otp'`, `signature_kind = 'drawn'` (written) else `'checkbox'`, `consent_text_id/version` = published notice, `text_sha256 = intake_hash(body)`, `evidence = {typed_name, otp_channel, contact_hint}`, `ip = nullif(p_ip,'')::inet` (bad value ⇒ null), `user_agent` ≤ 500 chars. `status='completed'`. Then `privacy_after_consent(client_id)`. Enqueues `consent_copy` (payload `{notice_title, notice_version, notice_path:'/privacidad/<slug>/aviso/<version>', decisions:[{label, decision}], signed_at}`) to the verified contact. audit `consent.recorded {channel, purposes:n}`. Returns `{stage:'done', rescore_applications: uuid[]}` (the ids `privacy_after_consent` flagged). |
| `record_staff_consent(p_document_id uuid, p_decisions jsonb, p_signed_on date) returns jsonb` | definer; authenticated | Roles `tenant_admin, agent, underwriter` of the document's tenant. Document must have `doc_type='consent_form'`, `received_at is not null`, `status <> 'rejected'`, and an application with a client (`no_client`). Decisions validated against active `requires_consent` purposes. Rows: channel `staff_signed_form`, identity_basis `signed_form_checked`, signature_kind `scanned_autograph`, `evidence_document_id`, `actor_id = auth.uid()`, `evidence = {signed_on}`. `privacy_after_consent()`. audit `consent.recorded`. **Does not depend on AI acceptance of the form** (the form cannot be read by the model before consent exists). |
| `revoke_consent(p_client_id uuid, p_purpose text, p_dsr_id uuid default null, p_note text default null) returns void` | definer; authenticated | `require_privacy_admin(client.tenant_id)`; inserts `decision='revoked'`, channel `staff_recorded` (or `portal` when `p_dsr_id` is given and the DSR channel is portal), identity_basis `dsr_verified` / `staff_recorded`, consent_text = current published notice. Effect is immediate (`has_consent` false). audit `consent.revoked`. |
| `privacy_after_consent(p_client_id uuid) returns uuid[]` | internal (service-only) | For applications of the client in `manual_review` whose latest score has `rationale->>'blocked_reason' = 'ai_processing_not_consented'` and that now pass consent: `rescore_requested_at = now()`. Returns their ids. The sweep (5 min) or web's explicit enqueue picks them up. |

**Purpose seed** (`processing_purposes`, per tenant; labels Spanish, codes English; `core` marked *):

| code | requires_consent | optional | written | applies_to | legal_basis (seed text) |
| --- | --- | --- | --- | --- | --- |
| underwriting | f | f | f | all | Medidas precontractuales (Art. 5 lit. g num. 2) |
| sensitive_health* | t | f | **t** | sensitive_products | Consentimiento escrito (Art. 26 ¶4) [abogado] |
| ai_processing* | t | **t** | f | all | Consentimiento [abogado] |
| international_processing* | t | f | f | all | Consentimiento previo (Art. 44) [abogado L7] |
| identity_verification | f | f | f | all | Contrato / interés legítimo |
| fraud_prevention | f | f | f | all | Interés legítimo (num. 6) |
| notifications | f | f | f | all | Contrato |
| commercial_management | f | f | f | all | Interés legítimo / contrato [abogado] |
| marketing | t | t | f | all | Consentimiento (Art. 32) |
| profiling_offers | t | t | f | all | Consentimiento |
| retain_after_decline | t | t | f | all | Consentimiento |
| bureau_inquiry | t | t | f | all | Autorización especial (D.L. 695) |

`bureau_inquiry` seeded `active = false` (no bureau integration yet).

**Inventory seed** (`personal_data_stores`) — one row per table; columns abbreviated `(table, subject_link, categories, sensitive, access, erase, retention_class)`:
`clients (clients.id, {identity,contact,financial}, f, include, anonymize, approved_application)`;
`applications (applications.client_id, {identity,financial,health}, t, include_redacted /*third-party keys*/, anonymize, approved_application)`;
`documents (documents.application_id→applications.client_id, {identity,financial,health}, t, include, anonymize /*+Storage object*/, document_file)`;
`scores (…application_id, {inferred}, f, include_redacted /*fraud signals L8*/, redact_fields, approved_application)`;
`cases (…application_id, {technical}, f, include, not_applicable, approved_application)`;
`case_comments (cases.application_id, {inferred}, f, include, redact_fields, case_notes)`;
`case_decisions (…application_id, {inferred}, f, include, redact_fields, approved_application)`;
`field_reviews (…application_id, {identity,financial,health}, t, exclude 'QA de lectura', delete, case_notes)`;
`intake_links (client_id, {technical}, f, exclude 'canal desactivado', delete, unconverted_intake_contact)`;
`intake_sessions (client_id, {contact}, f, include, anonymize, unconverted_intake_contact)`;
`intake_info_requests (…application_id, {inferred}, f, include, redact_fields, case_notes)`;
`intake_notifications (client_id|application_id, {contact}, f, include, delete, unconverted_intake_contact)`;
`audit_log (entity_id, {technical}, f, include_redacted, redact_fields, audit_log)`;
`profiles (profiles.id, {staff,contact}, f, exclude 'personal del responsable: ARCO-POL propio', retain_legal, audit_log)`;
`ai_usage (application_id, {technical}, f, exclude 'sin datos personales', not_applicable, audit_log)`;
`consent_requests (client_id, {contact}, f, include, anonymize, consent_record)`;
`consent_records (client_id, {technical}, f, include, retain_legal, consent_record)`.
B adds `field_locks, data_subject_requests, dsr_subjects, dsr_events, dsr_attachments`; C adds
`dsr_responses, dsr_propagations, access_log, legal_holds, data_transfers, staff_acknowledgements`
(`staff_acknowledgements`: subject `profiles.id`, exclude). Every row's `retention_class` must be a
`retention_policies.data_class` value (C's test checks it).

**Subprocessor seed:** Supabase (US, us-east-1, BD/Auth/Storage, sensitive t), Render (US, ohio, API y
procesos), Anthropic (US, lectura y análisis con IA, sensitive t), Resend (US, correo), Cloudflare
(US, captcha Turnstile), Meta (US, WhatsApp). All `dpa_signed_at = null`, `safeguards = 'Pendiente (L3)'`.

**Data changes in A:** `perform seed_tenant_privacy(id) from tenants`; then
`update privacy_settings set consent_enforced_since = now() where tenant_id in (select id from tenants where slug in ('seguros','medico'))`.
In the local PGlite replay the seed tenants arrive after migrations, so enforcement stays off there
(expected; tests make their own tenants).

**pgTAP suite A:** `db/supabase/tests/database/privacy_consent_test.sql`. Key assertions:
- invariant: `select array_agg(distinct c.table_name) from information_schema.columns c join pg_class k on k.relname = c.table_name and k.relkind = 'r' join pg_namespace n on n.oid = k.relnamespace and n.nspname = 'public' where c.table_schema = 'public' and c.column_name in ('client_id','email','phone','national_id','full_name','form_data','extracted_data','contact_email','contact_phone','subject_full_name','recipient') and c.table_name not in (select table_name from personal_data_stores)` is null (B and C must keep it green);
- authenticated cannot `insert/update/delete` `consent_records`, `consent_requests`, `privacy_settings`, `processing_purposes`, `personal_data_stores`, `subprocessors` (`throws_ok … '42501'`);
- authenticated cannot select `consent_records.ip`, `.user_agent`, `consent_requests.token_hash`, `.otp_hash`;
- service_role `update consent_records` throws; `delete` throws;
- anon and authenticated cannot execute `consent_link_get|verify_identity|issue_code|verify_code|sign` (`has_function_privilege` false);
- staff of T2 cannot `create_consent_request` for a T1 client (P0002/42501); `record_staff_consent` refuses a non-`consent_form` document and a T2 document;
- link flow: wrong DOB ×5 ⇒ `locked`; sign before code ⇒ refused; sign with missing purpose ⇒ `decisions_incomplete`; written product without signature ⇒ `signature_required`; success ⇒ `has_consent` true and `consent_copy` outbox row without code/token in payload;
- `revoke_consent` ⇒ `has_consent` false immediately; T2 admin's `has_consent` on T1 client is false;
- `applications.consent_enforced` stamped true only when tenant switch on; an UPDATE cannot change it;
- `data_subject_footprint(T1, array[T2 client])` returns empty arrays;
- `publish_privacy_text` keeps one published per kind (publishing `consent` leaves `privacy_notice` published).
`anon_surface_test.sql` must still pass (no new function executable by anon).

### 2.2 Migration B — processing state, gate, DSR engine, portal

**Tables / columns**

```sql
alter table clients
  add column processing_state text not null default 'active'
    check (processing_state in ('active','limited','opposed','blocked','erased')),
  add column processing_state_reason text,
  add column processing_state_dsr_id uuid,
  add column processing_state_since timestamptz;
-- clients_keep_provenance() re-created (20261103000000 body) adding, under authenticated/anon:
--   INSERT: processing_state := 'active', reason/dsr_id/since := null
--   UPDATE: the four columns keep old values.

create table field_locks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  client_id uuid not null,
  field_path text not null check (field_path ~ '^(clients\.[a-z_]+|applications\.[0-9a-f-]{36}\.form_data\.[a-z][a-z0-9_]*)$'),
  reason text not null check (reason in ('under_rectification','disputed_accuracy')),
  dsr_id uuid, locked_by uuid references auth.users (id) on delete set null,
  locked_at timestamptz not null default now(), lifted_at timestamptz,
  constraint field_locks_client_same_tenant foreign key (tenant_id, client_id) references clients (tenant_id, id) on delete cascade);
create unique index field_locks_one_active on field_locks (client_id, field_path) where lifted_at is null;
-- trigger clients_respect_field_locks BEFORE UPDATE on clients: for each active lock 'clients.<col>' raise
-- 'field_locked: <col>' (22023) if to_jsonb(new)-><col> is distinct from to_jsonb(old)-><col>, unless
-- current_setting('app.rectifying', true) = 'on'. Same check for applications.form_data keys in
-- trigger applications_respect_field_locks (BEFORE UPDATE OF form_data).

create table business_holidays (
  id bigint generated always as identity primary key,
  country char(2) not null, day date not null, name text not null,
  tenant_id uuid references tenants (id) on delete cascade);   -- null = national
create unique index business_holidays_unique on business_holidays
  (country, day, coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid));
-- RLS: select authenticated where tenant_id is null or tenant_id = current_tenant_id() or superadmin.

create table data_subject_requests (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  number integer,                               -- null while 'unverified'
  "right" text not null check ("right" in ('access','rectification','cancellation','opposition',
                                          'portability','forgetting','limitation','consent_revocation')),
  status text not null default 'received' check (status in ('unverified','received','identity_pending',
     'prevention_sent','in_review','extended','resolved','returned_incompetent','archived_unanswered')),
  resolution text check (resolution in ('granted','partially_granted','denied')),
  denial_reasons text[] not null default '{}' check (denial_reasons <@ array['art22_a','art22_b','art22_c',
     'art22_d','art22_e','art22_f','art22_g','art22_h']),
  resolution_note text,
  channel text not null check (channel in ('portal','email','in_person','letter','forwarded_by_processor')),
  requester_kind text not null check (requester_kind in ('subject','representative','heir')),
  subject_full_name text not null, subject_national_id text, subject_birth_date date,
  contact_email text, contact_phone text,
  notification_medium text not null default 'email' check (notification_medium in ('email','whatsapp','letter','in_person')),
  delivery_modality text check (delivery_modality in ('electronic','simple_copy','certified_copy','consultation')),
  description text check (length(description) <= 4000), requested_changes jsonb,
  revoke_purposes text[],                       -- for consent_revocation
  identity_verified_at timestamptz, identity_verified_by uuid references auth.users (id) on delete set null,
  identity_method text check (identity_method in ('contact_on_file','id_document','in_person','representative_document')),
  received_at timestamptz not null default now(),
  complete_at timestamptz,                      -- = received_at (conservative: L11 assumed "no suspension")
  due_on date, extended_due_on date, extension_reason text,
  prevention_sent_at timestamptz, prevention_message text, prevention_due_on date, prevention_answered_at timestamptz,
  prevention_answer text,
  decided_at timestamptz, decided_by uuid references auth.users (id) on delete set null,
  decision_notified_at timestamptz, recipients_notified_at timestamptz,
  assigned_to uuid references profiles (id) on delete set null,
  -- portal credentials (never selectable by staff)
  portal_token_hash text unique, otp_hash text, otp_expires_at timestamptz, otp_attempts int not null default 0,
  otp_sent_count int not null default 0, otp_sent_at timestamptz, otp_channel text,
  contact_verified_at timestamptz, download_verified_until timestamptz,
  created_by uuid references auth.users (id) on delete set null,
  unique (tenant_id, number), unique (tenant_id, id));
-- ⚠ deviation: column is "right" (quoted; RIGHT is a keyword). Plan's 'unverified' status, revoke_purposes,
-- prevention_message/answer and download_verified_until are additions.
-- Column grant to authenticated: all except portal_token_hash, otp_*, download_verified_until.

create table dsr_subjects (
  dsr_id uuid not null, tenant_id uuid not null references tenants (id) on delete cascade,
  client_id uuid not null,                      -- no FK (survives erasure/deletion)
  matched_by text[] not null, linked_by uuid references auth.users (id) on delete set null,
  linked_at timestamptz not null default now(), primary key (dsr_id, client_id),
  constraint dsr_subjects_dsr_same_tenant foreign key (tenant_id, dsr_id) references data_subject_requests (tenant_id, id) on delete cascade);

create table dsr_events (                        -- append-only
  id bigint generated always as identity primary key,
  tenant_id uuid not null references tenants (id) on delete cascade, dsr_id uuid not null,
  at timestamptz not null default clock_timestamp(),
  actor_id uuid, actor_type text not null check (actor_type in ('staff','subject','system')),
  event text not null, detail jsonb not null default '{}');
create trigger dsr_events_append_only before update or delete on dsr_events for each row execute function prevent_append_only_change();

create table dsr_attachments (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade, dsr_id uuid not null,
  kind text not null check (kind in ('identity','power_of_attorney','heir_proof','supporting','response')),
  storage_path text not null unique,            -- privacy bucket: <tenant_id>/dsr/<dsr_id>/<uuid>.<ext>
  file_name text not null, uploaded_by_subject boolean not null,
  uploaded_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  constraint dsr_attachments_dsr_same_tenant foreign key (tenant_id, dsr_id) references data_subject_requests (tenant_id, id) on delete cascade);
-- ⚠ deviation: identity documents of a DSR are NOT `documents` rows (documents.application_id is NOT NULL and
-- would push them through extraction, a model call). Staff verify them by eye in the DSR detail.
```

RLS for all of the above: select only for `tenant_admin`/`superadmin` of the tenant (an `agent` or
`underwriter` sees no DSR rows) — `using ((tenant_id = current_tenant_id() and app_current_role() = 'tenant_admin') or app_current_role() = 'superadmin')`.
`field_locks` select for all tenant staff (screens show "En revisión por rectificación"). No write grants.

Views: `dsr_list` (security_invoker) = `data_subject_requests` safe columns + `coalesce(extended_due_on, due_on) as effective_due_on`,
`business_days_between(current_date, coalesce(extended_due_on, due_on), tenant_id) as business_days_left`,
`(select count(*) from dsr_subjects s where s.dsr_id = d.id) as subject_count`, `assigned_name`. Filter `status <> 'unverified'`.

Re-created views (they expand `c.*`, see 20261103000000:116):
- `drop view client_list; create view client_list with (security_invoker = true) as select c.*, …same two columns… from clients c where c.processing_state not in ('blocked','erased') or app_current_role() in ('tenant_admin','superadmin');`
- `create or replace view application_list … ` = 20261102000000:299 body, appending column `c.processing_state as client_processing_state` at the end and the same `where coalesce(c.processing_state,'active') not in ('blocked','erased') or app_current_role() in ('tenant_admin','superadmin')`.

`clients_select` policy re-created: existing predicate `(tenant_id = current_tenant_id() or app_current_role() = 'superadmin')`
**and** `(processing_state <> 'blocked' or app_current_role() in ('tenant_admin','superadmin'))`, `to authenticated`.
(Applications of a blocked client stay readable by their RLS — documented gap.)

**Seed:** national SV holidays 2026–2028 (`tenant_id null`, 33 rows): 01-01 Año Nuevo; Jueves/Viernes/Sábado
Santo — 2026-04-02/03/04, 2027-03-25/26/27, 2028-04-13/14/15; 05-01 Día del Trabajo; 05-10 Día de la Madre;
06-17 Día del Padre; 08-06 Fiesta del Divino Salvador del Mundo; 09-15 Independencia; 11-02 Día de los
Difuntos; 12-25 Navidad. San Salvador's 08-03…08-05 are tenant-local (admin adds). [abogado L10]

**Functions (B)**

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `add_business_days(p_from date, p_days int, p_tenant uuid, p_country char(2) default 'SV') returns date` | stable, invoker; authenticated, service_role | Loop: advance one day, skip Sat/Sun (`extract(isodow) in (6,7)`) and holidays where `country = p_country and (tenant_id is null or tenant_id = p_tenant)`, until `p_days` counted. `p_days = 0` returns `p_from`. |
| `business_days_between(p_from date, p_to date, p_tenant uuid) returns int` | stable; same grants | Business days in `(p_from, p_to]`; negative when `p_to < p_from` (overdue). |
| `processing_gate(p_application_id uuid) returns jsonb` | stable definer; **service-only** | `{allowed, reason, client_id, processing_state, enforced, consent:{ai_processing, international_processing}}`. Order: client `processing_state ≠ 'active'` ⇒ `reason = 'processing_' || state`; else if `applications.consent_enforced` and not (`has_consent(client,'ai_processing')` and `has_consent(client,'international_processing')`) ⇒ `'ai_processing_not_consented'`; a null `client_id` with enforcement ⇒ not consented. Unknown application ⇒ `{allowed:false, reason:'not_found'}`. |
| `set_processing_state(p_client_id uuid, p_state text, p_reason text, p_dsr_id uuid default null) returns void` | definer; authenticated | `require_privacy_admin`; allowed targets `active, limited, opposed, blocked` (`erased` only via `execute_dsr_erasure`; from `erased` nothing); reason required (≥ 5 chars) for anything but `active`; sets the four columns (runs as owner, so `clients_keep_provenance` does not reset them). dsr_event when `p_dsr_id`. audit `client.processing_state_changed {from,to}`. |
| `lock_field(p_client_id uuid, p_field_path text, p_reason text, p_dsr_id uuid default null) returns uuid` / `unlock_field(p_lock_id uuid) returns void` | definer; authenticated | privacy admin; path must exist (client column or application of that client); audit. |
| `register_dsr(p jsonb) returns jsonb` | definer; authenticated | Tenant from `current_tenant_id()`; superadmin must pass `p->>'tenant_id'` and channel `forwarded_by_processor` is superadmin-only. Required: `right, channel ∈ (email,in_person,letter,forwarded_by_processor), requester_kind, subject_full_name`. Assigns number under `select … from privacy_settings where tenant_id = T for update` then `coalesce(max(number),0)+1`. `complete_at = received_at`, `due_on = add_business_days(received_at::date, dsr_response_days, T, country)`. status `identity_pending`. dsr_event `received`; outbox `dsr_received` to the contact given. Runs `dsr_auto_match()`. Returns `{id, number, due_on}`. |
| `dsr_auto_match(p_dsr_id uuid) returns int` | internal | Inserts `dsr_subjects` for clients **of the same tenant** matching `dui_digits(national_id)`, `lower(email)`, `intake_phone(phone)`, or `(lower(full_name), date_of_birth)`; `matched_by` lists which. Never exposed to the portal. |
| `match_dsr_subject(p_dsr_id uuid) returns jsonb` | stable definer; authenticated | privacy admin; candidate clients of the DSR's tenant with `matched_by` and whether linked: `[{client_id, full_name, national_id, email, phone, matched_by:[], linked}]`. |
| `link_dsr_subject(p_dsr_id uuid, p_client_id uuid) / unlink_dsr_subject(p_dsr_id uuid, p_client_id uuid) returns void` | definer; authenticated | privacy admin; client must be in the DSR's tenant (`P0002` otherwise); dsr_event. |
| `verify_dsr_identity(p_dsr_id uuid, p_method text, p_note text) returns void` | definer; authenticated | status `received|identity_pending` → `in_review`; requires ≥1 linked subject **or** p_method in (`id_document`,`in_person`) with note; dsr_event. |
| `send_dsr_prevention(p_dsr_id uuid, p_message text) returns void` | definer; authenticated | once only (`prevention_already_sent`); → `prevention_sent`, `prevention_due_on = add_business_days(today, dsr_prevention_days)`; outbox `dsr_prevention` with message. |
| `answer_dsr_prevention(p_dsr_id uuid, p_answer text) returns void` | definer; authenticated | staff records an answer received off-portal → `in_review`. |
| `extend_dsr(p_dsr_id uuid, p_reason text) returns date` | definer; authenticated | once (`already_extended`); not after due; `extended_due_on = add_business_days(due_on, dsr_extension_days)`; → `extended`; outbox `dsr_extended`. |
| `assign_dsr(p_dsr_id uuid, p_user_id uuid) returns void` | definer; authenticated | assignee must be tenant_admin of the tenant. |
| `resolve_dsr(p_dsr_id uuid, p_resolution text, p_denial_reasons text[], p_note text) returns void` | definer; authenticated | status in (`in_review`,`extended`); note ≥ 20 chars always (`motivation_required`); `denied`/`partially_granted` need ≥1 reason (`denial_reason_required`); identity must be verified for `granted`/`partially_granted`. → `resolved`, `decided_at/by`, `decision_notified_at = now()` with outbox `dsr_resolved` (`{number, right, resolution, note, follow_up:'portal'}`). |
| `return_dsr_incompetent(p_dsr_id uuid, p_note text) returns void` | definer; authenticated | → `returned_incompetent`; outbox `dsr_returned`. |
| `add_dsr_note(p_dsr_id uuid, p_note text) returns void` | definer; authenticated | dsr_event `note`. |
| `add_dsr_attachment(p_dsr_id uuid, p_kind text, p_file_name text) returns jsonb` | definer; authenticated | privacy admin; inserts row with `uploaded_by_subject=false`; returns `{id, path}` (web signs the upload). |
| `execute_dsr_revocation(p_dsr_id uuid, p_purposes text[]) returns int` | definer; authenticated | right `consent_revocation`, identity verified; `revoke_consent()` per linked subject × purpose with `p_dsr_id`; dsr_event. |
| `execute_dsr_state(p_dsr_id uuid) returns void` | definer; authenticated | right `opposition` ⇒ `set_processing_state(subject,'opposed',…)`; `limitation` ⇒ `'limited'`; for each linked subject. |
| `privacy_portal_info(p_slug text) returns jsonb` | stable definer; service-only | Null when slug unknown or `portal_enabled=false`. `{tenant:{display_name,color,slug}, contact:{privacy_email, privacy_phone, legal_name, address, responsible_person}, notice:{version,title,sections,body,published_at}|null, rights:[…8 codes]}`. |
| `privacy_notice_version(p_slug text, p_version int) returns jsonb` | stable definer; service-only | A published or archived `privacy_notice` of that tenant (permanent link from the consent copy). |
| `privacy_open_request(p_slug text, p jsonb) returns jsonb` | definer; service-only | Portal filing. Validates `right`, `requester_kind`, name 2–200, at least email or phone, `dui_valid` when a DUI is given. Inserts `status='unverified'`, `channel='portal'`, `portal_token_hash = intake_hash(token)`. Returns `{token}`. ≤ 20 unverified requests per tenant per hour (`rate_limited`). |
| `privacy_issue_code(p_token text) returns jsonb` | definer; service-only | Same limits as `consent_link_issue_code`; to the contact the requester typed (proves the contact, not identity). `{code,email,phone,channel}`. |
| `privacy_verify_code(p_token text, p_code text) returns jsonb` | definer; service-only | First success on an `unverified` request: assign number, `received_at = complete_at = now()`, `due_on`, status `identity_pending`, `dsr_auto_match()`, outbox `dsr_received`, dsr_event `received` (actor subject). Later successes (download step): `download_verified_until = now() + 15 min`. Returns `{number, due_on, status}`. **Same response whether or not any client matched.** |
| `privacy_status(p_token text) returns jsonb` | stable definer; service-only | Requires `contact_verified_at`. `{number, right, status, received_at, due_on, extended_due_on, prevention:{message, due_on}|null, resolution, resolution_note, response_available:boolean}`. Never subject matches, never staff names. |
| `privacy_add_attachment(p_token text, p_kind text, p_file_name text) returns jsonb` | definer; service-only | Verified requests only; ≤ 5 per request; `{path}`. |
| `privacy_answer_prevention(p_token text, p_answer text) returns void` | definer; service-only | status `prevention_sent` and not past `prevention_due_on` → `in_review`; dsr_event. |
| `privacy_daily(p_today date default current_date) returns jsonb` | definer; service-only | (1) `prevention_sent` past `prevention_due_on` ⇒ `archived_unanswered`; (2) delete `unverified` older than 24 h; (3) for DSRs open with `business_days_left ≤ 3` (or overdue) not yet alerted today (dsr_events `deadline.alerted` with `detail->>'day'`), outbox `privacy_deadline` to every active tenant_admin email; (4) same for revocations? no. Returns `{archived, purged, alerted}`. |
| `privacy_deadline_alerts() returns table (tenant_id uuid, tenant_name text, dsr_id uuid, number int, due_on date, days_left int)` | stable definer; service-only | For the watchdog snapshot. |

**Existing functions changed in B** (copy the latest body, add only what is listed):

| Function (latest file) | Change |
| --- | --- |
| `submit_application(uuid)` (20261107000000:366) | After the authorisation block and before the documents check: `if exists(select 1 from clients where id = app.client_id and processing_state <> 'active') then raise exception 'processing_restricted' using errcode = '22023'; end if;` and `if app.consent_enforced and product_handles_sensitive(app.product_id) and not has_consent(app.client_id, 'sensitive_health') then raise exception 'consent_missing: sensitive_health' using errcode = '22023'; end if;`. `ai_processing` is **not** required (refusing it routes to manual review). |
| `pipeline_sweep_candidates(int)` (20261108000000:764) | `extract` branch adds `and coalesce((processing_gate(d.application_id) ->> 'allowed')::boolean, false)`. ⚠ deviation from plan: `process`/`rescore` still return non-active subjects, because the orchestrator gate must close them to manual review (fail closed) or they sit in `submitted` forever. |
| `auto_decide_case(uuid, uuid)` (20261108000000:660) | **Whole ~95-line body copied**; add first branch `if not coalesce((processing_gate(a.id) ->> 'allowed')::boolean, false) then reason := 'processing_restricted'; elsif not p.auto_approve_enabled …`. Must be re-copied from 20261108000000 verbatim — easy place to drift. |
| `create_consent_request` (A) | add `client_not_active` refusal. |
| `data_subject_footprint` (A) | add `field_locks:[…]`, `dsr:[{number,right,status,received_at}]`. |
| `clients_keep_provenance()` | see above. |

**pgTAP suite B:** `db/supabase/tests/database/privacy_requests_test.sql`:
- `agent` and `underwriter` select 0 rows from `data_subject_requests`, `dsr_events`, `dsr_subjects`, `dsr_attachments`; calling `resolve_dsr`, `register_dsr`, `verify_dsr_identity` throws 42501;
- T2 admin sees no T1 DSR; `link_dsr_subject(T1 dsr, T2 client)` throws P0002; `match_dsr_subject` never returns a T2 client even with identical DUI/email;
- `portal_token_hash`, `otp_hash` not selectable by authenticated; anon/authenticated cannot execute any `privacy_*`;
- `dsr_events` update/delete throws (service_role too);
- `add_business_days('2026-03-31', 3, T)` = `'2026-04-07'` (skips 2–4 Apr + weekend); `add_business_days('2026-12-24', 1, T)` = `'2026-12-28'`; a tenant holiday shifts only that tenant;
- `resolve_dsr(…,'denied','{}', …)` throws `denial_reason_required`; short note throws `motivation_required`; second `extend_dsr` throws;
- portal: open → verify ⇒ number assigned and `due_on` 20 business days later; `privacy_status` identical shape for matched and unmatched subjects;
- `processing_gate`: limited client ⇒ `processing_limited`; enforced app without consent ⇒ `ai_processing_not_consented`; with both consents ⇒ allowed;
- `submit_application` on a limited client throws `processing_restricted`; on an enforced sensitive product without `sensitive_health` throws `consent_missing: sensitive_health`; unenforced app passes as before;
- `auto_decide_case` returns `processing_restricted` for an opposed client with a perfect score;
- `underwriter` cannot see a `blocked` client in `clients` or `client_list`; `tenant_admin` can;
- direct `update clients set annual_income = …` by an agent on a locked field throws `field_locked: annual_income`; a JWT update cannot change `processing_state`.

### 2.3 Migration C — execution, retention, access, security, transfers, summary

**Tables**

```sql
create table dsr_responses (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade, dsr_id uuid not null,
  kind text not null check (kind in ('access','portability')),
  content jsonb not null, created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(), released_at timestamptz, expires_at timestamptz,
  constraint dsr_responses_dsr_same_tenant foreign key (tenant_id, dsr_id) references data_subject_requests (tenant_id, id) on delete cascade);

create table dsr_propagations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade, dsr_id uuid not null,
  recipient_name text not null, recipient_kind text not null check (recipient_kind in
    ('crm_destination','reinsurer','bureau','other_controller','authority','processor')),
  action text not null check (action in ('rectify','erase','revoke','limit')),
  due_on date not null, done_at timestamptz, evidence text,
  created_by uuid references auth.users (id) on delete set null, created_at timestamptz not null default now(),
  constraint dsr_propagations_dsr_same_tenant foreign key (tenant_id, dsr_id) references data_subject_requests (tenant_id, id) on delete cascade);

create table retention_policies (
  tenant_id uuid not null references tenants (id) on delete cascade,
  data_class text not null check (data_class in ('intake_draft','staff_draft','withdrawn_application',
    'declined_application','approved_application','document_file','extracted_data','case_notes',
    'access_log','consent_record','dsr_record','unconverted_intake_contact','audit_log')),
  retain_days int not null check (retain_days between 1 and 36500),
  starts_from text not null check (starts_from in ('last_activity','decision','policy_end','created')),
  action text not null check (action in ('delete','anonymize','block_then_anonymize')),
  legal_basis text not null, automated boolean not null default false,  -- true only for the 4 classes the job runs
  approved_by uuid references auth.users (id) on delete set null, approved_at timestamptz,
  primary key (tenant_id, data_class));

create table legal_holds (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  client_id uuid, application_id uuid, reason text not null, until date,
  created_by uuid references auth.users (id) on delete set null, created_at timestamptz not null default now(),
  released_at timestamptz, released_by uuid references auth.users (id) on delete set null,
  check (client_id is not null or application_id is not null));

create table access_log (                        -- append-only, NOT partitioned (owner decision)
  id bigint generated always as identity primary key,
  tenant_id uuid not null references tenants (id) on delete cascade,
  actor_id uuid references auth.users (id) on delete set null, actor_role text not null,
  client_id uuid,                               -- derived; null for export/search
  entity_type text not null check (entity_type in ('client','application','case','document','export','search','dsr')),
  entity_id uuid,
  action text not null check (action in ('client.viewed','application.viewed','case.viewed','document.viewed',
    'export.generated','search.performed','dsr.viewed','report.generated')),
  purpose text not null default 'underwriting_review' check (purpose in
    ('underwriting_review','customer_service','dsr_response','audit','other')),
  purpose_note text check (length(purpose_note) <= 300), detail jsonb not null default '{}',
  created_at timestamptz not null default now());
create index access_log_client_idx on access_log (client_id, created_at desc);
create index access_log_tenant_idx on access_log (tenant_id, created_at desc);
-- append-only trigger; RLS select tenant_admin/superadmin; no grants but select.

create table staff_acknowledgements (           -- append-only
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  consent_text_id uuid not null, version int not null, accepted_at timestamptz not null default now(),
  unique (user_id, consent_text_id));
-- RLS select: own rows, or tenant_admin/superadmin of the tenant.

create table security_incidents (               -- platform
  id uuid primary key default gen_random_uuid(), title text not null,
  detected_at timestamptz not null, known_at timestamptz not null,     -- 72 h runs from known_at
  nature text not null, data_categories text[] not null, includes_sensitive boolean not null,
  affected_subjects_estimate int, immediate_actions text, recommendations text,
  root_cause text, corrective_actions text,
  status text not null default 'open' check (status in ('draft','open','contained','closed')),
  notifiable boolean not null default true, not_notifiable_reason text,
  created_by uuid references auth.users (id) on delete set null, created_at timestamptz not null default now(),
  closed_at timestamptz);
create table incident_tenants (
  incident_id uuid not null references security_incidents (id) on delete cascade,
  tenant_id uuid not null references tenants (id) on delete cascade,
  responsible_notified_at timestamptz, ace_notified_at timestamptz, fgr_notified_at timestamptz,
  subjects_notified_at timestamptz, subjects_notified_count int, primary key (incident_id, tenant_id));
create table incident_events (                   -- append-only
  id bigint generated always as identity primary key,
  incident_id uuid not null references security_incidents (id) on delete cascade,
  at timestamptz not null default clock_timestamp(), actor_id uuid, event text not null, detail jsonb not null default '{}');
-- RLS: superadmin all select; tenant_admin selects incident_tenants of own tenant and the incidents they
-- name (exists subquery). Writes: functions.

create table data_transfers (                    -- append-only
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id) on delete cascade,
  client_id uuid not null, recipient_kind text not null check (recipient_kind in
    ('crm_destination','reinsurer','bureau','other_controller','authority')),
  recipient_id uuid, recipient_name text not null, country char(2) not null,
  categories text[] not null, legal_basis text not null, consent_record_id uuid, dsr_id uuid,
  occurred_at timestamptz not null default now(), reference text,
  created_by uuid references auth.users (id) on delete set null);
-- RLS select tenant_admin/superadmin.
```

Every table above gets RLS enabled, `revoke all … from anon, authenticated`, the select grant stated, and
`grant select, insert, update, delete … to service_role`. `personal_data_stores` gains their rows.

**Seed in C:** `seed_tenant_privacy()` re-created to also insert the 13 retention proposals and a
published `staff_confidentiality` text (version 1, Spanish, ~8 lines: confidentiality, use only for the
stated purposes, no copies, report incidents) — then run for every tenant. Retention proposals
(`legal_basis = 'Propuesta pendiente de validación legal (L6)'`, `approved_at null`):

| data_class | days | starts_from | action | automated |
| --- | --- | --- | --- | --- |
| intake_draft | 30 | last_activity | delete | f (intake dormant) |
| staff_draft | 90 | last_activity | delete | **t** |
| withdrawn_application | 730 | decision | anonymize | **t** |
| declined_application | 730 | decision | anonymize | **t** |
| approved_application | 3650 | policy_end | block_then_anonymize | f |
| document_file / extracted_data | 3650 | decision | delete / anonymize | f |
| case_notes | 3650 | decision | anonymize | f |
| access_log | 730 | created | delete | **t** |
| consent_record / dsr_record | 1825 | created | delete | f |
| unconverted_intake_contact | 30 | created | delete | f |
| audit_log | 3650 | created | anonymize | f |

**Functions (C)**

| Signature | Kind / grants | Behaviour |
| --- | --- | --- |
| `dsr_access_report(p_dsr_id uuid) returns jsonb` | stable definer; authenticated (privacy admin), service_role | Built from `data_subject_footprint(tenant, linked client ids)`. Shape `{schema:'tramiq.access-report/v1', generated_at, dsr:{number,right,received_at}, tenant:{legal_name,display_name,privacy_email}, glossary:[{term,definition}], sections:{identity:{fields:[{key,label,value,source}]}, applications:[{number, product, status, answers:[{key,label,value}], third_party_omitted:boolean}], documents:[{doc_type_label, uploaded_at, status, extracted:[{label,value}]}], inferred:[{application_number, final_score, tier, recommendation, rules:[{rule_id, label, result}], narrative}], decisions:[{application_number, decision, decided_at, conditions, reasons}], accesses:[{at, who, role, action, purpose}], transfers:[{recipient_name, country, categories, occurred_at}], subprocessors:[{name,service,country}], consents:[{purpose_label, decision, at, channel, version}], processing_state:{state, reason, locks:[…]}}, withheld:[{section:'fraud_signals', reason:'art22_c'}]}`. Third-party keys (`privacy_settings.third_party_form_keys`) dropped from answers with `third_party_omitted=true`; fraud signals and identity mismatches dropped from `inferred` when `withhold_fraud_signals` (and listed in `withheld`). `accesses` = `access_log` rows of the subject's entities + `audit_log` decision rows, staff named by `profiles.full_name`. No other client's data can enter: every lookup keyed by linked `client_id` and tenant. |
| `dsr_portability_export(p_dsr_id uuid) returns jsonb` | same | `{schema:'tramiq.subject-export/v1', exported_at, subject:{full_name,email,phone,national_id,date_of_birth,address…}, applications:[{number, product, submitted_at, answers:{key:value}}], documents:[{doc_type, file_name, uploaded_at}], consents:[…]}` — only data the subject **provided** (no scores, no narratives). |
| `execute_dsr_access(p_dsr_id uuid) returns uuid` / `execute_dsr_portability(p_dsr_id uuid) returns uuid` | definer; authenticated | privacy admin; identity verified; inserts `dsr_responses` with the JSON; access_log `report.generated` (purpose `dsr_response`); returns response id. |
| `release_dsr_response(p_response_id uuid) returns void` | definer; authenticated | `released_at = now()`, `expires_at = now() + 15 days`; outbox `dsr_response_ready`; dsr_event. |
| `privacy_response(p_token text) returns jsonb` | definer; service-only | Requires `identity_verified_at` (staff) **and** `download_verified_until > now()`; latest released, unexpired response(s) `{kind, content}[]`; dsr_event `response.downloaded`. |
| `rectify_subject_data(p_dsr_id uuid, p_changes jsonb) returns jsonb` | definer; authenticated | privacy admin; right `rectification`; identity verified. `p_changes = [{"target":"client","field":"annual_income","value":…}, {"target":"application","application_id":"…","key":"monthly_income","value":…}]`. Client fields whitelist: `full_name,email,phone,national_id,date_of_birth,address_line1,address_line2,city,region,district,postal_code,employer,occupation,annual_income,marital_status`. `set local app.rectifying = 'on'`; client: update column, `field_sources[field] = {"source":"dsr","dsr_id":…,"date":current_date}`; application: `form_data = jsonb_set(...)` — **documents are never edited** (evidence of what was presented); dsr_event `annotation` per document of the application listing the corrected keys. Lifts matching `field_locks`. Returns `{changed:int, rescore_suggested:boolean}` (true when an application with a score had a key changed). audit `client.rectified` (field names only). |
| `execute_dsr_erasure(p_dsr_id uuid, p_simulate boolean default true) returns jsonb` | definer; authenticated | privacy admin; right `cancellation|forgetting`; resolution `granted|partially_granted`. Per linked subject: **retain** if active legal hold, or any application `approved`, or an open case ⇒ `processing_state='blocked'` (Art. 11). Else **anonymize**: clients → `full_name='Titular eliminado'`, every other personal column null, `tags='{}'`, `field_sources='{}'`, `processing_state='erased'`; applications → `form_data='{}'`; documents → `extracted_data='{}'`, `content_sha256=null`, `validation = validation || '{"erased":true}'`; scores → `ai_summary=null`, `inputs=null`, `rationale = jsonb_build_object('erased',true,'blocked',rationale->'blocked')`; case_comments/case_decisions.note/intake_info_requests.response_note → `'[eliminado por solicitud N.º <n>]'`; field_reviews of those applications deleted; intake_sessions contacts null; intake_notifications of the client deleted; consent_requests contact null; then `redact_audit_metadata(client)`. With `p_simulate` nothing is written: returns the plan. Returns `{simulate, subjects:[{client_id, action:'anonymize'|'block', reasons:[]}], per_store:[{table, rows, action}], storage_paths:[text]}`. Not simulating: dsr_event `erasure.executed` with counts; audit `client.erased`. Web deletes `storage_paths` from bucket `documents` afterwards and calls `record_dsr_files_removed`. |
| `record_dsr_files_removed(p_dsr_id uuid, p_count int, p_failed int) returns void` | definer; authenticated | dsr_event. |
| `redact_audit_metadata(p_client_id uuid) returns int` | definer; service-only (called internally) | `set local app.privacy_purge`; `update audit_log set metadata = jsonb_build_object('redacted', true, 'redacted_at', now()) where entity_id = p_client_id or entity_id in (applications/cases/documents of the client)`; inserts one `audit.redacted` row (counts only). |
| `add_dsr_propagation(p_dsr_id uuid, p_recipient_name text, p_recipient_kind text, p_action text) returns uuid` / `complete_dsr_propagation(p_id uuid, p_evidence text) returns void` | definer; authenticated | `due_on = add_business_days(today, propagation_days)`; completing the last one sets `recipients_notified_at`. |
| `save_retention_policy(p_data_class text, p_retain_days int, p_starts_from text, p_action text, p_legal_basis text) returns void` / `approve_retention_policy(p_data_class text) returns void` | definer; authenticated | admin of `current_tenant_id()`; saving clears approval; approve sets `approved_by/at`; audit. |
| `place_legal_hold(p_client_id uuid, p_application_id uuid, p_reason text, p_until date) returns uuid` / `release_legal_hold(p_id uuid) returns void` | definer; authenticated | admin; audit. |
| `retention_candidates(p_limit int default 200) returns table (tenant_id uuid, data_class text, entity_type text, entity_id uuid, action text, due_since timestamptz, storage_paths text[])` | stable definer; service-only | Only `approved_at is not null and automated`. `staff_draft`: applications `status='draft'` and `greatest(updated_at, created_at) + retain_days < now()`; `withdrawn_application`/`declined_application`: status withdrawn/declined, decision time = `case_decisions.decided_at` else `updated_at`, client not `blocked`, no active legal hold on client/application, and **not** `has_consent(client,'retain_after_decline')`, and form_data ≠ `'{}'` (not already done); `access_log`: one row per tenant (`entity_type='access_log'`, `entity_id = tenant_id`). Paths via `application_storage_paths(array[id])`. |
| `retention_preview(p_tenant_id uuid) returns jsonb` | stable definer; authenticated | admin; the same predicates **ignoring approval**: `[{data_class, approved, automated, count, sample:[application numbers ≤ 10]}]`. This is the "simulation" screen. |
| `retention_apply(p_data_class text, p_entity_id uuid) returns jsonb` | definer; service-only | Re-checks the predicate (row may have changed); `set local app.privacy_purge = 'on'`; `staff_draft` ⇒ `delete from applications`; withdrawn/declined ⇒ anonymize the application the way `execute_dsr_erasure` does for one application (client row untouched); `access_log` ⇒ delete rows older than retain_days. Returns `{applied:boolean, rows:int}`. |
| `record_retention_run(p_summary jsonb) returns void` | definer; service-only | One `audit_log` row per tenant: action `retention.applied`, entity `tenant`, metadata = counts only. |
| `log_access(p_action text, p_entity_type text, p_entity_id uuid default null, p_purpose text default null, p_note text default null, p_detail jsonb default '{}') returns void` | definer; authenticated | Actor = `auth.uid()`, role = `app_current_role()`. For client/application/case/document/dsr: resolve tenant and client **through tables the caller could read** (same tenant or superadmin); invisible ⇒ silently return (no oracle). export/search: tenant = `current_tenant_id()`, entity null, `detail` limited to `{rows:int, view:text}` (never the search text). Purpose default by entity: dsr ⇒ `dsr_response`, else `underwriting_review`. Never raises (an access log must not break a screen); returns void. |
| `document_type_is_sensitive(p_tenant_id uuid, p_doc_type text) returns boolean` | stable definer; authenticated, service_role | Tenant type's current version has any `fields[].sensitive = true`. |
| `restricted_documents(p_application_id uuid) returns table (id uuid, doc_type text, label text, status text, uploaded_at timestamptz)` | stable definer; authenticated | Caller `agent` of the application's tenant: the sensitive rows hidden from them. Anyone else: empty. |
| `application_form_for_viewer(p_application_id uuid) returns jsonb` | stable definer; authenticated | Visible application only; for role `agent` removes keys whose product `form_schema.fields[]` has `sensitive: true` and returns `{form_data, masked_keys:[…]}`; others get the full `form_data`. |
| `pending_acknowledgement() returns jsonb` | stable definer; authenticated | Null for superadmin or when the caller accepted the published `staff_confidentiality` text of their tenant; else `{id, version, title, body}`. |
| `acknowledge_confidentiality(p_text_id uuid) returns void` | definer; authenticated | Must be the published one of the caller's tenant; idempotent; audit `staff.confidentiality_accepted`. |
| `open_incident(p jsonb) returns uuid` / `update_incident(p_id uuid, p jsonb) returns void` / `close_incident(p_id uuid, p_note text) returns void` | definer; authenticated | superadmin only (+ MFA gate with null tenant ⇒ skipped). `p.tenant_ids uuid[]` creates `incident_tenants`. Each write → `incident_events`. |
| `mark_incident_notified(p_incident_id uuid, p_tenant_id uuid, p_target text) returns void` | definer; authenticated | superadmin, or tenant_admin of that tenant for targets `ace, fgr, subjects`; target `responsible` superadmin only. Sets the `*_notified_at` column; event. |
| `notify_incident_subjects(p_incident_id uuid, p_tenant_id uuid, p_client_ids uuid[], p_message text) returns int` | definer; authenticated | same roles; clients must be in the tenant; one `incident_notice` outbox row each; sets `subjects_notified_at`/count. |
| `record_data_transfer(p jsonb) returns uuid` | definer; authenticated | admin; client in tenant; append-only insert; audit. |
| `compliance_summary(p_tenant_id uuid) returns jsonb` | stable definer; authenticated | `require_tenant_staff` + role tenant_admin/superadmin. `{notice:{published_version, published_at, requires_reconsent}, consent:{enforced:boolean, enforced_since, applications_enforced:int, applications_with_ai_consent:int, by_channel:{consent_link:int, staff_signed_form:int, staff_recorded:int, portal:int}, pending_links:int}, dsr:{open:int, due_soon:int, overdue:int, resolved_90d:int, avg_business_days:numeric}, retention:{policies_approved:int, policies_total:int, pending_candidates:int}, mfa:{required:boolean, staff_total:int, staff_with_factor:int|null}, acknowledgements:{staff_total:int, accepted_current:int}, incidents:{open:int, overdue_72h:int}, subprocessors:{total:int, without_dpa:int}, classification:{form_fields_unclassified:int, document_fields_unclassified:int}, processing:{limited:int, opposed:int, blocked:int, erased:int}}`. `staff_with_factor` via `to_regclass('auth.mfa_factors')` + `execute` (verified factors), null when absent (PGlite). |

**Existing objects changed in C**

| Object | Change |
| --- | --- |
| `documents_select` policy (20260911000000:193) | Re-create: existing predicate **and** `(app_current_role() is distinct from 'agent' or not document_type_is_sensitive(tenant_id, doc_type))`, `to authenticated`. |
| storage policy `"tenant_read_documents"` (20260730000100:38) | Re-create with the same predicate **and** `not (app_current_role() = 'agent' and exists (select 1 from documents d where d.storage_path = name and document_type_is_sensitive(d.tenant_id, d.doc_type)))`. |
| `delete_client(uuid, boolean)` (20261103000000:263) | Copy; after `delete from clients`, `perform redact_audit_metadata(cl.id)` (before the `client.deleted` insert, which keeps counts only). |
| `data_subject_footprint` | add `access_log`, `data_transfers`, `legal_holds`. |
| `seed_tenant_privacy` | retention + staff text (above). |

Existing suites to re-check: `rls_isolation_test.sql`, `document_types_test.sql`, `document_acceptance_test.sql`
and any suite where an `agent` reads a medical/lab document — the new `documents_select` hides it.
Update their expectations in DB-C (do not weaken the new policy).

**pgTAP suite C:** `db/supabase/tests/database/privacy_execution_test.sql`:
- `agent` selects 0 `documents` of type `lab_results` (sensitive) but sees `national_id`; `underwriter` sees both; `restricted_documents()` lists the hidden one for the agent and nothing for the underwriter;
- `access_log`, `staff_acknowledgements`, `data_transfers`, `incident_events` update/delete throw for service_role; authenticated cannot insert any of them directly;
- `log_access` on another tenant's client writes nothing; `agent`/`underwriter` select 0 rows from `access_log`;
- `execute_dsr_erasure(…, true)` changes nothing (row counts/hash of `clients` row identical); `false` anonymizes a declined-only client, **blocks** a client with an approved application, and leaves a T2 client with the same DUI untouched; audit rows of the client have `metadata->>'redacted' = 'true'`;
- `retention_candidates` ignores unapproved policies, a legal hold, a `blocked` client and `retain_after_decline`;
- `dsr_access_report` for a T1 DSR never contains a T2 client id (`not (report::text like '%<T2 client id>%')`); third-party keys absent; fraud signals listed in `withheld`;
- `privacy_response` refuses without staff identity verification and without a fresh code;
- `underwriter` cannot `open_incident`; tenant_admin cannot mark `responsible`;
- every `personal_data_stores.retention_class` exists in the seeded `retention_policies` classes; invariant test from A still green.

### 2.4 What each consumer needs

- **ai-orchestrator:** `processing_gate`, `retention_candidates`, `retention_apply`, `record_retention_run`,
  `privacy_daily`, `privacy_deadline_alerts`, `claim_intake_notifications` (unchanged; new kinds and the
  `client_id`/`dsr_id` columns flow through `returning n.*`), product `form_schema` for minimization.
- **web (user client, RLS):** every staff function marked *authenticated*; reads of `privacy_settings`,
  `processing_purposes`, `consent_texts`, `client_consent_state`, `consent_records` (no ip/ua),
  `consent_requests` (safe columns), `dsr_list`, `dsr_events`, `dsr_subjects`, `dsr_attachments`,
  `dsr_responses`, `dsr_propagations`, `field_locks`, `retention_policies`, `legal_holds`, `access_log`,
  `data_transfers`, `security_incidents`, `incident_tenants`, `incident_events`, `subprocessors`,
  `personal_data_stores`, `business_holidays`.
- **web (service client, public routes only):** `consent_link_*`, `privacy_*`; Storage bucket `privacy`;
  bucket `documents` removal after erasure.

---

## 3. ai-orchestrator (package ORCH)

Start after the intake-removal change has landed in `ai-orchestrator` (`src/intake/` is already gone;
`src/queue/index.ts` was edited by it). New directory `src/privacy/`.

| File | Content |
| --- | --- |
| `src/privacy/gate.ts` | `export type GateReason = 'processing_limited'\|'processing_opposed'\|'processing_blocked'\|'processing_erased'\|'ai_processing_not_consented'\|'not_found'\|'gate_unavailable'`; `export async function processingGate(applicationId: string): Promise<{ allowed: boolean; reason: GateReason \| null }>` — rpc `processing_gate`; an rpc error ⇒ `{allowed:false, reason:'gate_unavailable'}` (**fails closed**, logged at error). Pure `export function gateFromRpc(data: unknown)` for tests. |
| `src/privacy/minimize.ts` | `export function minimizeForModel(formData: Record<string, unknown>, formSchema?: unknown): Record<string, unknown>` — drops keys whose schema field has `category: 'contact'` or `pii: true`, plus keys matching `/^(full_?name\|name\|nombre\|email\|correo\|phone\|telefono\|tel\|national_id\|dui\|nit\|passport\|pasaporte\|address\|direccion\|address_line\d)$/i` and nested objects under `beneficiaries\|dependents\|beneficiarios\|dependientes` (replaced by `{count:n}`); adds `"subject": "el solicitante"`. Keeps `date_of_birth` only as `age` (integer) — rules about age stay possible. Never mutates input. |
| `src/privacy/retention.ts` | `export async function runRetention(deps = defaultDeps): Promise<{applied:number; skipped:number; filesRemoved:number}>`: rpc `privacy_daily()`; rpc `retention_candidates(200)`; per candidate remove `storage_paths` from bucket `documents` first (log failures, continue — like the old `intake.purge`), then rpc `retention_apply(data_class, entity_id)`; finally rpc `record_retention_run({<tenant_id>: {<data_class>: count}})`. Deps injectable for tests. |
| `src/queue/index.ts` | `export const QUEUE_PRIVACY_RETENTION = "privacy.retention"`; create with `SCHEDULED_POLICY`; `boss.work(QUEUE_PRIVACY_RETENTION, () => runRetention())`; `boss.schedule(QUEUE_PRIVACY_RETENTION, "23 4 * * *")` plus a catch-up `send` at boot, mirroring how the purge catch-up was done. |
| `src/applications/process.ts` | (1) select `products!applications_product_id_fkey(sla_hours, form_schema)`. (2) Extract the playbook resolution block (current lines ~437–480, both branches + tenant check) into `async function resolvePlaybook(application): Promise<PlaybookRow>` with no behaviour change. (3) **Gate** immediately after the application row is loaded, before the readiness/deferral check: `const gate = await processingGate(applicationId); if (!gate.allowed) { const playbook = await resolvePlaybook(application); await recordBlocked(applicationId, application, playbook, gate.reason === 'ai_processing_not_consented' ? 'ai_processing_not_consented' : 'processing_restricted', { gate_reason: gate.reason }); return; }`. Extend `BlockedReason` with `'ai_processing_not_consented' \| 'processing_restricted'`. No grading-engine call, no model call (the plan's "rules-only score" is simplified to the blocked score that already routes to manual review). (4) Pass `minimizeForModel(application.form_data, product.form_schema)` instead of `application.form_data` to `runConsistencyAgent` and `runRiskNarratorAgent`. `resolveInputs` keeps the full `form_data` (rules are deterministic, no model). |
| `src/documents/extract.ts` | In `extractDocument`, after loading the document row and before the spend-cap check/model call: `const gate = await processingGate(doc.application_id); if (!gate.allowed) { logger.info(…); return <skipped result> }` — the document stays `uploaded` (not rejected: it becomes readable when consent arrives). Add `{ skipped: 'processing_not_permitted', reason }` to `ExtractionResult` and make callers (`queue/index.ts` worker, `after-extraction.ts`) treat it as a no-op. |
| `src/cases/routes.ts` + `src/cases/ask.ts` | Case Q&A: gate the case's application before `askAboutCase`; refused ⇒ `reply.status(403).send({ error: 'processing_not_permitted', reason })`. Minimize `form_data` inside the bundle sent to the model (`src/cases/bundle.ts`, where the bundle is assembled). |
| `src/ops/watchdog.ts` | `WatchdogSnapshot.dsr_due: {tenant_name, number, due_on, days_left}[]` from rpc `privacy_deadline_alerts`; `problemsOf` adds one problem per overdue DSR (`kind: 'dsr_overdue'`) and an aggregate for due-soon. |
| `src/ops/weekly-summary.ts` | Add a line "Solicitudes ARCO-POL: abiertas N, vencidas M" from `privacy_deadline_alerts`. |
| `src/notifications/templates.ts` | `NotificationKind` += `consent_copy, dsr_received, dsr_prevention, dsr_extended, dsr_resolved, dsr_returned, dsr_response_ready, privacy_deadline, incident_notice`. `NotificationPayload` += optional `tenant_slug, notice_title, notice_version, notice_path, decisions:{label,decision}[], signed_at, number, right, due_on, extended_due_on, message, resolution, note, deadline_list:{number,due_on,days_left}[]`. Spanish subject/body per kind; links = `PUBLIC_WEB_URL + path` (`/privacidad/<slug>/aviso/<v>`, `/privacidad/<slug>` — never a token). |
| `src/notifications/send.ts` + `whatsapp.ts` | New kinds over WhatsApp use one utility template `process.env.WHATSAPP_TEMPLATE_PRIVACY \|\| 'tramiq_aviso_privacidad'` with params `[tenant_name, one-line text]` (`whatsappParameters` returns them); existing kinds unchanged. |

Not gated (documented): document-type test bench and proposals (staff sample files, no subject),
playbook copilot (no subject data), DUI photo read at client registration (`/api/identity/read`, runs
before a client exists — listed in §8).

Tests (vitest, `src/privacy/__tests__/`): `gate.test.ts` (rpc shapes, error ⇒ closed), `minimize.test.ts`
(contact/pii/identifier keys removed, beneficiaries collapsed, input untouched, age kept),
`retention.test.ts` (files removed before `retention_apply`, a failed removal still applies, summary
counts). Extend `src/applications/__tests__/acceptance-process.test.ts` (or a new
`process-gate.test.ts` with the same mocks): gate refused ⇒ one `scores` insert with
`blocked_reason: 'ai_processing_not_consented'`, no agent call, no grading-engine call.
`src/notifications/__tests__/notifications.test.ts`: every new kind renders, no `token`/`code` in output.
`src/ops/__tests__/watchdog.test.ts`: overdue DSR becomes a problem. `src/__tests__/embeds.test.ts`
must still pass (name the embed).

---

## 4. web

### 4.1 Patterns to copy

- Staff pages are client components (`"use client"`) reading with `createClient()` from
  `@/lib/supabase/client` and writing through `.rpc(...)`; errors through `failure()` (`@/lib/db-errors`),
  toasts through `useToast()`, confirmations through `useConfirm()`. Copy `components/admin/consent-texts.tsx`
  (versioned editor), `app/(dashboard)/settings/tenant-flag-setting.tsx` (one switch → rpc),
  `app/(dashboard)/clients/page.tsx` (list + filters + `Pagination`/`pageRange` + CSV via `toCsv`/`downloadCsv`
  from `@/lib/csv`, `useUrlState`), `PageHeader` from `components/dashboard/dashboard-shell.tsx`,
  `Field/TextInput/Select/Textarea` from `components/ui/field.tsx`, `Badge/StatusBadge`, `TableSkeleton`.
- Staff route handlers: `requireStaff()` (`@/lib/api-session`), user client `createServerSupabase()`
  for anything RLS decides, `createAdminClient()` (`@/lib/supabase/admin`) **only** for Storage and mail.
  Copy `app/api/documents/[id]/url/route.ts` (RLS probe then admin signed URL).
- Public routes: helpers in `@/lib/public/server.ts` (`PublicError`, `clientIp`, `verifyCaptcha`,
  `sendPublicMail`, `sendCode`, `sendCodeMail`, `readBody`, `text`, `requestHost`, `pageHost`),
  `SlidingWindow` from `@/lib/rate-limit`, Turnstile widget `@/components/public/turnstile.tsx`,
  CSP `publicPageCsp` applied by `next.config.ts` to `/consentimiento/:path*` and `/privacidad/:path*`.
- DB types: **hand-written** (no generated `Database` type). All Plan 2 row/RPC types live in
  `web/src/lib/privacy/types.ts`, written from §2 of this file — so web packages build before the
  migrations exist (only runtime calls fail). Tests: `web/test/unit/*.test.ts` on Node's runner.

### 4.2 Shared foundation (created by WEB-1, step 1; everybody else imports only)

| File | Content |
| --- | --- |
| `web/src/lib/privacy/types.ts` | Types for every table/view/RPC result in §2: `PrivacySettings, ProcessingPurpose, PurposeCode, ConsentDecision, ConsentRecord, ClientConsentState, ConsentRequestRow, ConsentLinkState, ProcessingState, FieldLock, DsrRight, DsrStatus, DsrResolution, DsrListRow, DsrEvent, DsrAttachment, DsrResponse, AccessReport, PortabilityExport, ErasurePlan, RetentionPolicy, RetentionPreviewRow, LegalHold, AccessLogRow, SecurityIncident, IncidentTenant, DataTransfer, ComplianceSummary, ProcessingInventory, PersonalDataStore, Subprocessor, NoticeSection`. |
| `web/src/lib/privacy/labels.ts` | Spanish labels: `RIGHT_LABELS` (Acceso, Rectificación, Cancelación, Oposición, Portabilidad, Olvido, Limitación, Revocación del consentimiento), `RIGHT_DESCRIPTIONS` (one plain line each), `DSR_STATUS_LABELS`, `RESOLUTION_LABELS`, `DENIAL_REASON_LABELS` (art22_a…h), `PROCESSING_STATE_LABELS` (Activo, Tratamiento limitado, Oposición, Bloqueado, Eliminado), `CONSENT_CHANNEL_LABELS`, `ACCESS_ACTION_LABELS`, `ACCESS_PURPOSE_LABELS`, `RETENTION_CLASS_LABELS`, `NOTICE_SECTION_TITLES`, `GATE_REASON_LABELS`. |
| `web/src/lib/privacy/errors.ts` | `privacyErrorMessage(code: string): string` — Spanish text for every raised code in §2 (`notice_not_published`, `no_contact_on_file`, `identity_mismatch`, `link_locked`, `code_invalid`, `decisions_incomplete`, `signature_required`, `consent_missing: sensitive_health`, `processing_restricted`, `field_locked: <col>`, `denial_reason_required`, `motivation_required`, …). |
| `web/src/lib/privacy/download.ts` | `downloadJson(filename: string, data: unknown): void` (same mechanics as `downloadCsv`). |
| `web/src/lib/public/route.ts` | `server-only`. `publicRpc<T>(fn, args)` (admin client rpc; SQLSTATE `42501→401`, `P0002→404`, `22023→400`, message `^[a-z_: ]+$` ⇒ `PublicError(code)`; else `unavailable` 503), `publicFailure(err)`, `publicRoute(handler)` (same-origin check on non-GET + failure mapping — copy of the removed `intakeRoute`), `publicRateLimit(kind, key)` over `SlidingWindow`s: `consentIdentify 10/10min`, `consentCode 5/10min`, `consentWrite 30/10min`, `privacyOpen 5/10min`, `privacyCode 5/10min`, `privacyRead 60/10min` ⇒ `PublicError('rate_limited', 429)`; `readToken(body)` (64-hex or throw `link_invalid` 401); `publicOrigin(request)` (`PUBLIC_WEB_URL` else `siteOrigin`). |
| `web/src/lib/public/server.ts` | (after the move lands) export `sendWhatsAppTemplate` and add `sendWhatsAppLink(phone, template, params)` for the consent-link message. |
| `web/src/hooks/use-access-log.ts` | `useAccessLog(entityType, entityId, options?: {purpose?, enabled?})` — calls `createClient().rpc('log_access', …)` once per mount per id; never throws. `logExport(view, rows)` and `logSearch(view)` helpers. |
| `web/src/components/privacy/restricted-documents.tsx` | `<RestrictedDocuments applicationId />` — rpc `restricted_documents`; renders nothing when empty; else rows "Documento médico — acceso restringido" (label, status, date). |
| `web/src/components/privacy/printable.tsx` | `<Printable title subtitle>` page wrapper: print CSS (`@media print` hide chrome), "Imprimir / Guardar como PDF" button (`window.print()`), header with tenant name and generation date. |
| `web/src/components/privacy/privacy-nav.tsx` | Sub-nav tabs (role-filtered): Resumen `/privacy`, Ajustes `/privacy/settings`, Aviso `/privacy/notice`, Inventario `/privacy/inventory`, Finalidades `/privacy/purposes`, Consentimientos `/privacy/consents`, Solicitudes `/privacy/requests`, Retención `/privacy/retention`, Accesos `/privacy/access-log`, Transferencias `/privacy/transfers`, Incidentes `/privacy/incidents`, Personal `/privacy/acknowledgements`. Links to routes other packages create (plain hrefs). |
| `web/src/components/privacy/signature-pad.tsx` | Canvas pad (pointer events), `onChange(dataUrl \| null)`, "Borrar". (Created by WEB-1 so WEB-2 and nothing else depend on it — WEB-2 is its only user.) |

### 4.3 Screens and routes by package

Role rule for the whole section: nav "Privacidad" visible to `tenant_admin` and `superadmin`
(`canManagePrivacy(role)` added to `lib/roles.ts` by WEB-1). Agents/underwriters reach consent actions
from client/application screens only.

**WEB-1 — shell, settings, notice, inventory, public notice**

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `components/dashboard/dashboard-shell.tsx` (edit) | NAV item `{ href: "/privacy", label: "Privacidad", icon: ShieldCheck, visible: canManagePrivacy }` | — |
| `lib/roles.ts` (edit) | `canManagePrivacy`, `canSendConsent` (tenant_admin, agent, underwriter) | — |
| `src/proxy.ts` (edit) | `/privacy` in `PROTECTED_PREFIXES` | — |
| `app/(dashboard)/privacy/layout.tsx` | `PageHeader` "Privacidad y datos personales" + `<PrivacyNav>`; redirects roles without `canManagePrivacy` to `/forbidden` | — |
| `app/(dashboard)/privacy/settings/page.tsx` + `components/privacy/settings-form.tsx` | responsible data (Art. 24 a), contact, portal on/off + portal URL shown, deadlines, third-party keys, withhold fraud signals (L8 note), consent enforcement switch with date, MFA status read-only (`tenants.mfa_required`) with link to Configuración | `privacy_settings` select; `save_privacy_settings`; `set_consent_enforcement` |
| `app/(dashboard)/privacy/notice/page.tsx` + `components/privacy/notice-editor.tsx` | "Generar borrador" → `buildNoticeSections()`; edit each section (Textarea), title, `requires_reconsent` checkbox; save; publish (confirm); version history with links to the public version page | `processing_inventory`, `privacy_settings`, `consent_texts` (kind `privacy_notice`), `save_privacy_text`, `publish_privacy_text` |
| `lib/privacy/notice-generator.ts` | `buildNoticeSections(inv: ProcessingInventory, settings: PrivacySettings): NoticeSection[]` + `sectionsToBody(sections): string` — pure, plain Spanish, the 11 sections of §2.1; sensitive data listed explicitly with the Art. 37 sentence ("No está obligado a proporcionar datos sensibles; sin ellos no podemos evaluar…" [abogado]); automated decisions sentence (auto-approval only approves, never declines); subprocessors with country; retention table; rights + portal URL; revocation; cookies (session only) | — |
| `components/admin/company-settings.tsx`, `components/admin/tenant-detail.tsx` (edit) | Replace `<ConsentTextsManager>` with a link card "Aviso de privacidad → Privacidad › Aviso"; delete `components/admin/consent-texts.tsx` | — |
| `app/(dashboard)/privacy/inventory/page.tsx` + `components/privacy/rat-table.tsx` | RAT: one row per activity (products + fixed): actividad, finalidad, base legal, titulares, categorías (sensibles marcadas), origen, destinatarios, transferencias (país/garantía), conservación, medidas, sistemas; "Descargar CSV"; "Versión imprimible" → `/privacy/inventory/print`; stores registry table; unclassified counts | `processing_inventory` |
| `app/(dashboard)/privacy/inventory/print/page.tsx` | `<Printable>` RAT | same |
| `app/(dashboard)/privacy/subprocessors/page.tsx` | list; superadmin edits (inline form) | `subprocessors`, `save_subprocessor` |
| `app/privacidad/[slug]/page.tsx` (server component) | Public notice: tenant brand, current notice sections, contact, button "Ejercer mis derechos" → `/privacidad/[slug]/solicitud`; `notFound()` when null | `publicRpc('privacy_portal_info')` |
| `app/privacidad/[slug]/aviso/[version]/page.tsx` | Permanent notice version | `publicRpc('privacy_notice_version')` |
| `app/privacidad/layout.tsx` | public shell (no staff chrome), `robots: noindex` for `/seguimiento/*` handled per page | — |
| Tests | `test/unit/privacy-notice-generator.test.ts` (all 11 sections, sensitive sentence present iff sensitive activity, no empty section), `test/unit/privacy-labels.test.ts` (every DSR status/right/denial reason has a label) | |

**WEB-2 — purposes, consent link, paper form, client/application panels, revocation**

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `app/(dashboard)/privacy/purposes/page.tsx` + `components/privacy/purposes-table.tsx` | Edit label/description/legal basis/optional/active; core ones locked | `processing_purposes`, `save_processing_purpose` |
| `app/(dashboard)/privacy/consents/page.tsx` | Consent register: filter by purpose/decision/channel/date; row → client; "Ver firma" | `consent_records` (no ip/ua), `consent_requests` |
| `app/api/privacy/consents/[id]/signature/route.ts` | GET: user client select record (RLS) → admin signed URL (bucket `privacy`, 600 s) | — |
| `app/api/privacy/consent-requests/route.ts` | POST `{client_id, application_id?, channel?}`: `requireStaff` → user client `create_consent_request` → URL `publicOrigin + /consentimiento/<token>` → `sendPublicMail` (subject "Autoriza el tratamiento de tus datos — <aseguradora>") or `sendWhatsAppLink`; mail unconfigured outside production logs it. Response `{url, expires_at, sent_via}` (URL shown once with "Copiar enlace", useful for demos) | |
| `components/privacy/send-consent-button.tsx` | Button + dialog (channel choice from contacts on file) used on application detail and client detail | route above |
| `components/privacy/client-consent-panel.tsx` | On client detail: per purpose latest decision, date, channel, version; reconsent banner; pending link status; actions "Enviar consentimiento", "Registrar formulario firmado" (dialog: pick a `consent_form` document of the client's applications, tick purposes as written on paper, date, confirm "Verifiqué la firma"), "Revocar" (admin) | `client_consent_state`, `consent_requests`, `record_staff_consent`, `revoke_consent` |
| `components/privacy/processing-state-panel.tsx` | Badge + reason; admin actions limit/oppose/reactivate (dialog with reason); active `field_locks` list | `clients` (state columns), `field_locks`, `set_processing_state`, `unlock_field` |
| `components/clients/client-detail.tsx` (edit) | Mount both panels; `useAccessLog('client', id)`; "En revisión por rectificación" next to locked fields; show `field_sources` `source:'dsr'` as "corregido por solicitud N.º" | |
| `components/applications/application-detail.tsx` (edit) | Consent status strip (AI consent yes/no, enforcement flag `consent_enforced`), `<SendConsentButton>`, `<RestrictedDocuments>`, `useAccessLog('application', id)`, agent masking via `application_form_for_viewer` | |
| `lib/clients.ts` (edit) | `field_sources` union type adds `{source:'dsr', dsr_id, date}`; `Client` gains `processing_state*` | |
| `lib/score-status.ts`, `components/score/score-notice.tsx` (edit) | `ScoreNotice` += `{kind:'not_consented'}` ("Sin consentimiento para el análisis con IA: se revisa a mano. Envíe el enlace de consentimiento.") and `{kind:'processing_restricted', reason}` | |
| `app/consentimiento/[token]/page.tsx` + `components/privacy/consent-flow.tsx` | Client page. Stages: **identify** (DOB *or* DUI + Turnstile) → **code** (choose email/WhatsApp on file, hint shown, 6-digit input) → **review** (notice sections collapsible, per-purpose checkboxes — informed purposes listed without checkbox, optional unticked by default, mandatory marked "necesario para evaluar su solicitud"; when `requires_written`: typed full name + `<SignaturePad>` + explicit sentence about sensitive data) → **done** (summary, "le enviamos una copia"). `unavailable` shows reason and the insurer contact | API below |
| `app/api/public/consent/state/route.ts` | POST `{token}` → `consent_link_get`; strip `request_id`, `signature_path` | `publicRateLimit('consentWrite', ip)` |
| `app/api/public/consent/identify/route.ts` | POST `{token, date_of_birth?, national_id?, captcha}` → `verifyCaptcha` → `consent_link_verify_identity` | `consentIdentify` |
| `app/api/public/consent/code/route.ts` | POST `{token, channel?}` → `consent_link_issue_code` → `sendCode(issued, insurer, "tu autorización")` → `{sent:true, channel}` | `consentCode` |
| `app/api/public/consent/verify/route.ts` | POST `{token, code}` → `consent_link_verify_code` | `consentWrite` |
| `app/api/public/consent/sign/route.ts` | POST `{token, decisions, typed_name?, signature_png?}`: re-read state server-side; if written, decode `data:image/png;base64` (≤ 300 KB, PNG magic bytes) and upload with admin client to `signature_path` (`upsert:false`); then `consent_link_sign(..., clientIp(request), user-agent)`; then best-effort `POST /api/notifications/drain`-equivalent is **not** needed (orchestrator drains every minute) | `consentWrite` |
| Tests | `test/unit/consent-flow.test.ts` (stage → screen mapping, decision payload covers all purposes, signature required iff written), `test/unit/signature-png.test.ts` (data-URL validation) | |

After a successful sign, for each id in `rescore_applications` the sign route calls
`fetchService(`${AI_ORCHESTRATOR_URL}/applications/${id}/process`, { method: 'POST', body: '{"rescore":true}' })`
(best effort, failure only logged) so the demo does not wait for the 5-minute sweep; the uploaded
documents are extracted by the sweep's `extract` branch now that the gate allows them, and the process
job defers until they are read.

**WEB-3 — DSR queue/detail/actions, portal, reports, rectify/erase**

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `app/(dashboard)/privacy/requests/page.tsx` | Queue: folio, derecho, titular, recibida, vence (business days left: red ≤ 0, amber ≤ 3), estado, responsable; filters status/right; CSV | `dsr_list` |
| `app/(dashboard)/privacy/requests/new/page.tsx` | Staff registration (email/in person/letter; superadmin: tenant picker + `forwarded_by_processor`) | `register_dsr` |
| `app/(dashboard)/privacy/requests/[id]/page.tsx` + `components/privacy/dsr-detail.tsx` | Timeline (`dsr_events`), subject matching (candidates, link/unlink), attachments viewer, identity verification dialog (method + note), footprint preview (collapsible JSON-ish tables), actions by right and status: prevention, answer, extend, assign, return incompetent, resolve (resolution + Art. 22 reasons checklist + motivated note templates), execute: access/portability (generate → preview → release), rectification (`<RectifyForm>` from `requested_changes`, lock fields first), erasure (`<ErasurePanel>`: **Simular** shows the plan table; **Ejecutar** requires typing the folio), opposition/limitation (`execute_dsr_state`), revocation (`execute_dsr_revocation` with purposes), propagations list (add/complete). `useAccessLog('dsr', id, {purpose:'dsr_response'})` | functions of §2.2/§2.3 |
| `components/privacy/dsr-templates.ts` | Spanish text templates: prevention, extension, grant, partial, denial (inserts selected Art. 22 reasons), incompetence, rectification done, erasure done (mentions backups rotate in 7 days and the AI provider retention per contract — L3) | — |
| `app/api/privacy/requests/[id]/attachments/route.ts` | POST `{kind, file_name}` → user client `add_dsr_attachment` → admin `createSignedUploadUrl` in `privacy`. GET `[attachmentId]/url/route.ts` → RLS select then admin signed URL | |
| `app/api/privacy/requests/[id]/erasure/route.ts` | POST `{simulate}` → user client `execute_dsr_erasure`; not simulating: admin `storage.from('documents').remove(paths)` in batches of 100 → user client `record_dsr_files_removed` | |
| `app/(dashboard)/privacy/requests/[id]/report/page.tsx` | `<Printable>` access report from the latest `dsr_responses` (kind access) + "Descargar JSON"; portability: "Descargar JSON" (`tramiq.subject-export/v1`) + "Descargar CSV" (answers flattened) | `dsr_responses` |
| `components/privacy/access-report-view.tsx` | Renders `AccessReport` sections + glossary; reused by the staff print page and the portal page | — |
| `app/privacidad/[slug]/solicitud/page.tsx` + `components/privacy/portal-form.tsx` | Portal: choose right (cards with one plain line), identity (name, DUI, DOB, email/phone, representative/heir toggle), details (description; rectification: field + correct value; access: delivery modality), Turnstile → code → done screen: "Recibimos su solicitud N.º X; vence el …" + follow-up link; optional upload of identity/power of attorney | API below |
| `app/privacidad/[slug]/seguimiento/[token]/page.tsx` | Status timeline, prevention answer box, "Descargar respuesta" (asks a fresh code) → renders `<AccessReportView>` in `<Printable>` + JSON download | API below |
| `app/api/public/privacy/open/route.ts` | POST → captcha + `privacyOpen` → `privacy_open_request` → `privacy_issue_code` → `sendCode` → `{token}` (token kept by the page in memory/sessionStorage, never in a URL until verified) | |
| `app/api/public/privacy/code/route.ts`, `verify/route.ts` | issue/verify; on first verification `sendPublicMail` the follow-up URL `/privacidad/<slug>/seguimiento/<token>` to the verified email (WhatsApp: `sendWhatsAppLink`) | |
| `app/api/public/privacy/status/route.ts`, `prevention/route.ts`, `attachments/route.ts`, `response/route.ts` | `privacy_status`; `privacy_answer_prevention`; `privacy_add_attachment` + admin signed upload in `privacy`; `privacy_response` (after verify) | `privacyRead` / `privacyCode` |
| Tests | `test/unit/dsr-templates.test.ts`, `test/unit/portability-csv.test.ts`, `test/unit/business-days-display.test.ts` (colour thresholds) | |

**WEB-4 — retention, holds, access log, masking, acknowledgements, incidents, transfers, dashboard, evidence**

| Route / file | Purpose | Calls |
| --- | --- | --- |
| `app/(dashboard)/privacy/page.tsx` + `components/privacy/compliance-dashboard.tsx` | Resumen: tiles from `compliance_summary` (notice, consent coverage by channel, DSR open/due/overdue/avg, retention approved/pending, MFA staff with factor, acknowledgements, incidents, subprocessors without DPA, unclassified fields, processing states); each tile links to its screen; "Paquete de evidencia" button | `compliance_summary` |
| `app/(dashboard)/privacy/evidence/page.tsx` | `<Printable>` evidence package: summary, RAT (reuse WEB-1 `rat-table.tsx` read-only import), current notice + version list, ARCO-POL procedure text (static Spanish, from `dsr-templates.ts` section titles — import only), DSR register (all `dsr_list` rows with dates), latest 20 consent records with evidence, retention policies, incidents, subprocessors/DPA; "Descargar JSON" of everything | reads only |
| `app/(dashboard)/privacy/retention/page.tsx` + `components/privacy/retention-policies.tsx`, `legal-holds.tsx` | Edit/approve policies (unapproved highlighted "Propuesta [abogado L6]"); `retention_preview` table = simulation; legal holds list + place/release | `retention_policies`, `save_retention_policy`, `approve_retention_policy`, `retention_preview`, `legal_holds`, `place_legal_hold`, `release_legal_hold` |
| `app/(dashboard)/privacy/access-log/page.tsx` | Filter by client/staff/action/date; CSV | `access_log` (+ `profiles` names) |
| `app/api/documents/[id]/url/route.ts` (edit) | Replace `recordAudit(… 'document.viewed' …)` with user client `rpc('log_access', {p_action:'document.viewed', p_entity_type:'document', p_entity_id:id})` | |
| `components/case/case-detail.tsx` (edit) | `useAccessLog('case', caseId)`; `<RestrictedDocuments applicationId>` | |
| `app/(dashboard)/clients/page.tsx`, `app/(dashboard)/applications/page.tsx` (edit) | `logExport('clients'|'applications', rows)` after CSV download; `logSearch(view)` when a search term is applied (debounced, once per term) | |
| `components/applications/client-documents.tsx` (edit) | `<RestrictedDocuments>` beside the list for agents | |
| `app/(dashboard)/layout.tsx` (edit) + `components/privacy/ack-gate.tsx` | `<MfaGate><AckGate><DashboardShell>…` — `pending_acknowledgement()`; when non-null, full-screen text + "Acepto" → `acknowledge_confidentiality`; superadmin passes | |
| `app/(dashboard)/privacy/acknowledgements/page.tsx` | Staff list with accepted version/date; edit + publish new `staff_confidentiality` version (forces re-acceptance) | `staff_acknowledgements`, `profiles`, `save_privacy_text`, `publish_privacy_text` |
| `app/(dashboard)/privacy/incidents/page.tsx` + `[id]/page.tsx` | Superadmin: create (nature, categories, sensitive, known_at, tenants), 72 h countdown from `known_at` (red after), per tenant checkboxes responsible/ACE/FGR/subjects with timestamps, Spanish templates for ACE (Art. 25 a–e) and subjects (a, b, d, e) with copy buttons, "Notificar a titulares" (client picker) → outbox; event log. Tenant admin: read-only list of incidents affecting the tenant + mark ACE/FGR/subjects | incident functions |
| `app/(dashboard)/privacy/transfers/page.tsx` | List + "Registrar transferencia" form | `data_transfers`, `record_data_transfer` |
| Tests | `test/unit/incident-clock.test.ts` (72 h remaining / overdue), `test/unit/access-log-helpers.test.ts` (one log per id, export detail never carries search text) | |

---

## 5. Work packages

Order: **DB-A → DB-B → DB-C** (serial, one engineer). ORCH and WEB-1…4 start in parallel as soon as
this design and the intake removal are merged; they code against §2 contracts and are integrated once
the migrations are applied to `qualifier-dev`. Everyone works on `develop` of their repo.

| Package | Owns (creates or is the only one editing) | Depends on | Can do before migrations exist |
| --- | --- | --- | --- |
| **DB-A** | `db/supabase/migrations/20261111000000_privacy_inventory_consent.sql`, `db/supabase/tests/database/privacy_consent_test.sql` | — | everything; verify with PGlite replay |
| **DB-B** | `…20261111000100_privacy_state_requests.sql`, `…/privacy_requests_test.sql` | DB-A | — |
| **DB-C** | `…20261111000200_privacy_execution_security.sql`, `…/privacy_execution_test.sql`; edits to existing suites broken by `documents_select` (`rls_isolation_test.sql`, `document_*_test.sql` only where an agent reads a sensitive type) | DB-B | — |
| **ORCH** | everything under `ai-orchestrator/src/privacy/`, and edits to `src/queue/index.ts`, `src/applications/process.ts`, `src/documents/extract.ts`, `src/applications/after-extraction.ts` (only the skipped-result handling), `src/cases/routes.ts`, `src/cases/ask.ts`, `src/cases/bundle.ts`, `src/ops/watchdog.ts`, `src/ops/weekly-summary.ts`, `src/notifications/*`, their tests | intake removal merged | all code + unit tests with mocked rpc; deploy only after DB-B (gate) is in production — **deploying ORCH first fails every application closed** (`gate_unavailable`) |
| **WEB-1** | §4.2 shared files; `dashboard-shell.tsx`, `lib/roles.ts`, `src/proxy.ts`, `lib/public/server.ts` (additions only), `app/(dashboard)/privacy/layout.tsx`, `privacy/settings/**`, `privacy/notice/**`, `privacy/inventory/**`, `privacy/subprocessors/**`, `components/privacy/{settings-form,notice-editor,rat-table,privacy-nav,printable,restricted-documents,signature-pad}.tsx`, `lib/privacy/{types,labels,errors,download,notice-generator}.ts`, `lib/public/route.ts`, `hooks/use-access-log.ts`, `app/privacidad/layout.tsx`, `app/privacidad/[slug]/page.tsx`, `app/privacidad/[slug]/aviso/**`, `components/admin/{company-settings,tenant-detail}.tsx` (consent manager swap), deletes `components/admin/consent-texts.tsx` | intake removal merged (it edits the same admin files, proxy, next.config) | all |
| **WEB-2** | `privacy/purposes/**`, `privacy/consents/**`, `api/privacy/consents/**`, `api/privacy/consent-requests/**`, `app/consentimiento/**`, `api/public/consent/**`, `components/privacy/{send-consent-button,client-consent-panel,processing-state-panel,consent-flow,purposes-table}.tsx`, edits to `components/clients/client-detail.tsx`, `components/applications/application-detail.tsx`, `lib/clients.ts`, `lib/score-status.ts`, `components/score/score-notice.tsx` | WEB-1 step 1 | all |
| **WEB-3** | `privacy/requests/**`, `api/privacy/requests/**`, `app/privacidad/[slug]/solicitud/**`, `app/privacidad/[slug]/seguimiento/**`, `api/public/privacy/**`, `components/privacy/{dsr-detail,dsr-templates,access-report-view,portal-form,rectify-form,erasure-panel}.ts(x)` | WEB-1 step 1 | all |
| **WEB-4** | `app/(dashboard)/privacy/page.tsx`, `privacy/evidence/**`, `privacy/retention/**`, `privacy/access-log/**`, `privacy/acknowledgements/**`, `privacy/incidents/**`, `privacy/transfers/**`, `components/privacy/{compliance-dashboard,ack-gate,retention-policies,legal-holds}.tsx`, edits to `app/(dashboard)/layout.tsx`, `components/case/case-detail.tsx`, `components/applications/client-documents.tsx`, `app/(dashboard)/clients/page.tsx`, `app/(dashboard)/applications/page.tsx`, `app/api/documents/[id]/url/route.ts` | WEB-1 step 1; imports `rat-table.tsx` (WEB-1) and `dsr-templates.ts` (WEB-3) read-only — if WEB-3 is not merged yet, the evidence page renders the procedure section from `labels.ts` only | all |

**WEB-1 step 1** (first commit, half a day, everybody else branches after it): `lib/privacy/types.ts`,
`labels.ts`, `errors.ts`, `download.ts`, `lib/public/route.ts`, `hooks/use-access-log.ts`,
`components/privacy/{privacy-nav,printable,restricted-documents,signature-pad}.tsx`, `lib/roles.ts`
additions, `app/(dashboard)/privacy/layout.tsx`, the NAV item and the proxy prefix. After step 1, a
package needing a new shared type adds it **in its own file** (e.g. `components/privacy/dsr-detail.tsx`
local types) rather than editing `types.ts`; WEB-1 folds them in at the end.

Merge order for integration: DB-A/B/C applied to `qualifier-dev` → WEB-1 → WEB-2/3/4 (any order) →
ORCH → production rehearsal (transaction rolled back) → production `apply_migration` → promote web and
ai-orchestrator `develop → main`. Run `graphify update .` after each package.

---

## 6. Verification

Per package:

```bash
# db (each migration): full replay + new suites
node C:/Users/Sebas/AppData/Local/Temp/claude/170f4bc0089f9df9/83ca3cad-1521-429e-8771-899dcc964eff/scratchpad/db-replay/run.mjs privacy
node C:/Users/Sebas/AppData/Local/Temp/claude/170f4bc0089f9df9/83ca3cad-1521-429e-8771-899dcc964eff/scratchpad/db-replay/run.mjs   # every suite
cd ai-orchestrator && npm test && npx tsc --noEmit
cd web && npm run typecheck && npm run lint && npm test && npm run build
```

Then apply A, B, C to `qualifier-dev`, then a rehearsal on production inside `begin; … rollback;`
(Supabase connector `execute_sql`), then `apply_migration`. Postgres 17: no feature beyond PG 13 is used.

**Demo script** (tenant `medico`, admin with MFA optional; warm both services first):

1. **Ajustes** (`/privacy/settings`): fill razón social, domicilio, correo de privacidad; show
   "Consentimiento obligatorio desde <fecha de migración>" and MFA status.
2. **Aviso** (`/privacy/notice`): "Generar borrador" → sections appear with health data marked sensitive,
   Anthropic/Supabase in the US, 20 business days; edit one line; **Publicar**. Open
   `/privacidad/medico` in a private window: the notice is public, with "Ejercer mis derechos".
3. **Inventario**: RAT with one activity per product, health marked sensitive; download CSV; print view.
4. **Register** a client (with email you can read) and a health application; upload a DUI and lab
   results. Press **Enviar** → refused: "Falta el consentimiento escrito para datos de salud".
5. **Enviar consentimiento** on the application → link shown once (and emailed). In another browser
   open `/consentimiento/<token>`: DOB → code by email → read notice → tick purposes (leave
   *marketing* off) → type name, draw signature → "Firmar". Back in staff: client panel shows each purpose,
   channel "Enlace", version; "Ver firma" opens the PNG; the client got the copy email.
6. **Enviar** the application → AI runs (extraction, narrative, score) as before.
7. Variant: second client, *seguros* product, submit **without** consent → case lands in manual review
   with "Sin consentimiento para el análisis con IA"; send link, client signs → within a minute the
   documents are read and the case is rescored.
8. **Portal**: `/privacidad/medico/solicitud` → Acceso, same client's DUI/email → code → "Recibimos su
   solicitud N.º 1, vence el …". Staff **Solicitudes**: folio 1 with 20 business days left; open it →
   the client is suggested as a match → link → verify identity ("contacto registrado") → Generar
   informe → preview shows data, inferred score and narrative, who consulted (your own views from
   steps 5–6), consents; fraud signals listed as withheld → **Publicar respuesta** → Resolver
   "Concedida" with motivation. In the client's browser, follow-up page → "Descargar respuesta" (fresh
   code) → printable report + JSON.
9. **Supresión**: file a cancellation for a declined demo client → in detail **Simular**: plan per table,
   files to delete → **Ejecutar** (type the folio) → client shows "Titular eliminado", lists hide it.
   Repeat for a client with an approved policy → result is **Bloqueado** (Art. 11), invisible to the
   underwriter.
10. **Oposición** on another client → processing state "Oposición" → a rescore is refused by the gate.
11. **Retención**: preview counts per class; approve "Borrador del personal 90 días"; explain the daily job.
12. **Incidentes** (superadmin): open an incident known 70 h ago → clock shows 2 h left, red after; tick
    ACE/FGR; copy the ACE template; notify subjects → outbox rows.
13. **Resumen**: dashboard tiles reflect all of the above → **Paquete de evidencia** → print.
14. Log in as an **agent**: confidentiality text appears first; the lab results show "Documento médico —
    acceso restringido"; Privacidad is not in the nav.

---

## 7. LPD-0 owner checklist (no code)

- [ ] Rotate the Supabase DB password; update `DATABASE_URL` on ai-orchestrator (Render) and the secrets file (by script, key names only).
- [ ] Authentication → Providers: anonymous sign-ins **off**.
- [ ] Authentication → Passwords: leaked-password protection **on**.
- [ ] Authentication → URL configuration: correct Site URL (STATUS.md § 6.5).
- [ ] Delete `render-blocks.env` by hand.
- [ ] Decide on the paid Supabase plan with daily backups before any real data (BLK-4).
- [ ] Configure `WHATSAPP_TEMPLATE_PRIVACY` and the consent-link template in Meta if WhatsApp is demoed.
- [ ] (Optional, not in this plan) `mfa_required` per tenant — stays off for the demo.
- [ ] Legal track L1–L13 started with counsel (contracts, DPAs, notice review).

## 8. Open legal questions, carried as configuration (not blockers)

| # | Question | Where it lives |
| --- | --- | --- |
| L4 | Legal basis per purpose | `processing_purposes.legal_basis` (seeded with "[abogado]" texts) |
| L5 | Is typed name + drawn signature + OTP the "equivalent" of a handwritten signature for health data? | `processing_purposes.written_required`; `consent_records.signature_kind` already allows `certified_e_signature` |
| L6 | Retention periods per class | `retention_policies` (unapproved proposals; job runs only approved) |
| L7 | Is a US subprocessor an Art. 44 transfer; which safeguards suffice | `international_processing` purpose (`optional=false`), `subprocessors.safeguards` |
| L8 | May fraud signals be withheld from an access report | `privacy_settings.withhold_fraud_signals` (default true, shown as partial denial art22_c) |
| L9 | Beneficiaries/dependants: basis and information duty | `privacy_settings.third_party_form_keys` (excluded from reports and from model input) |
| L10 | Business-day calendar | `business_holidays` (national seed + tenant rows) |
| L11 | Does a prevention suspend the 20 days? | Design assumes **no** (clock from receipt — the conservative reading); `complete_at` column kept for a change |
| L13 | Staff confidentiality wording | `consent_texts` kind `staff_confidentiality` (seed text) |
| — | Health insurance vs "nobody may be obliged" (Art. 37) | Notice sentence in `notice-generator.ts`; `sensitive_health.optional=false` |
| — | Whether `audit_log` is itself a legal retention duty | `redact_audit_metadata()` redacts metadata, keeps action/actor/date |
| — | DUI photo read at client registration (model call before a client or consent exists) | Not gated; candidate for a tenant switch once counsel answers |
| — | Is the DUI photo biometric data | No facial comparison is done; revisit if selfie matching is added |
