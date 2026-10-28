# Plan — self-service intake links

Drafted 2026-10-28 against `develop` in all five repos, and built the same day.

## Implementation status — 2026-10-28

**Phases 0–3 are built in code, tested, and pushed. None of it is deployed or
applied to production.** Every repo carries the work on branch
`claude/awesome-mccarthy-fecr2l`, cut from `develop`:

| Repo | Head | What it carries |
| --- | --- | --- |
| `db` | `2e567e0` | `20261028000000` typed form fields, `20261028000100` the intake tables and functions, `20261028000200` spend cap, purge, outbox; `intake_test.sql` |
| `ai-orchestrator` | `656cf64` | prompt-injection rule, fence and detector; ClamAV scan; spend cap; scoring waits for documents; outbox sender and nightly purge |
| `web` | `8dd2d13` | `/s/` pages and `/api/intake/*`; staff screens (links, consent, form editor, personal links, duplicates, origin, applicant message); typed staff form |
| `docs` | `9b7607e` | architecture, module overview, schema, roadmap, `FUN-11` in the gap analysis |

The umbrella's pins still point at `main`, as `CLAUDE.md` requires: bump them
only once the branches are merged to `develop` and promoted.

**Verified:**

- `db`: all 10 pgTAP suites pass, 262 assertions, in a local replay of CI on
  Postgres 16. `intake_test.sql` adds 97 from the attacker's side.
  `anon_surface_test.sql` passes unchanged. Mutation checks (granting
  `intake_start` to `anon`, dropping the provenance trigger, exposing
  `token_hash`, dropping consent immutability) each fail a named assertion.
- `ai-orchestrator`: 159 tests (15 new, including a fake clamd speaking the
  real protocol). Typecheck and build are clean.
- `web`: 94 unit tests (18 new), typecheck, lint, the production build, and
  `npm ci` from a clean `node_modules`.
- End to end in Chromium at phone size, against the real database functions
  (local Postgres, a stand-in for PostgREST RPC and Storage):
  - A product-link applicant went from landing to submitted. A wrong code,
    an invalid DUI and an out-of-range answer were each refused.
  - An applicant answered a request for more information. The internal note
    stayed hidden, and the case returned to the queue with a rescore
    requested.
  - A personal link refused a wrong date of birth and then opened, with the
    insurer's record locked.
  - Without the cookie the session reads 401; a cross-site POST gets 403.

**Not verified:** anything against real Supabase, Storage, Resend, Turnstile,
ClamAV or the Anthropic API. The orchestrator's database calls go through
mocks in its unit tests, and the end-to-end run had no orchestrator behind it.

**Decided while building**, following the recommendations under "Open
decisions" below:

1. Both link kinds are built. The product link **fails closed in production**
   without a captcha and mail configured, and its documents are rejected unread
   without a malware scanner. Personal links depend on none of these.
2. The decision email is set per link (`decision_notice`). The default is
   "there is an answer, the insurer will contact you".
3. Email through Resend. Agents send a personal link by copy or WhatsApp share.
   No SMS or WhatsApp API.
4. Links live on Tramiq's domain (`/s/<slug>`, `/s/p/<token>`).
5. Token sessions; no applicant accounts.
6. Pricing is not engineering. The per-tenant spend cap bounds the cost question.

**Left, and none of it is code:**

- Apply the three migrations to production, as single transactions
  (`RUNBOOK.md` § "Apply a migration", never `supabase db push`), then
  merge and promote.
- The privacy and consent wording, written with the lawyer (`SEC-9`,
  `SEC-10`). The seed adds a **draft** per tenant and publishes nothing.
- Accounts and configuration:
  - Resend: `MAIL_API_KEY` and `MAIL_FROM` on web and ai-orchestrator, with a
    verified domain.
  - Cloudflare Turnstile: `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, a build argument,
    and `TURNSTILE_SECRET_KEY`.
  - A ClamAV service at `CLAMAV_HOST`. It needs about 1.5 GB of RAM, so not
    a free instance.
  - `PUBLIC_WEB_URL` on both services.
- `BLK-4` and paid plans, before a product link is published.
- Phase 4 stays unbuilt, as the plan says: on evidence only.


Identifiers (`FUN-3`, `SEC-4`…) refer to `docs/product-gap-analysis.md`; sizes
use its scale (**S** days, **M** one to two weeks, **L** three weeks or more).
Proposed identifier for this work: **`FUN-11`**.

## The question: does this exist?

**No.** There is no route an applicant can use today. Every application is
filed by a signed-in staff member, from `/applications` or a client's page.
Every other page redirects to sign-in, and every API route answers 401 without
a staff session.

**It used to.** An anonymous-auth portal at `/apply` existed through Phase 2.2.
It was deleted on purpose (`docs/roadmap.md`, Phase 2.2: "close the self-serve
question"). Since then, the security work has closed every mechanism it relied
on:

- `products_public_read_active` was dropped (`db` `20260911000000`). It made
  every tenant's active products world-readable.
- Every tenant policy is scoped `to authenticated`, so the anon key reaches no
  row (`db` `20261017000000`, proven by `anon_surface_test.sql`).
- The applicant storage policies have no caller, the `applicant` role is
  vestigial, and nothing writes `applications.applicant_id`.
- `web` comments state the opposite of this plan: `login-form.tsx` and
  `use-staff-session.tsx` say "no self-serve intake".

So the answer isn't "turn `/apply` back on". It is: build a self-service
channel that doesn't reopen the anonymous surface those migrations closed.

## What the insurer is asking for

The insurer wants a link that belongs to them. They post it on their website,
send it on WhatsApp, put it in an ad, or give it to a broker. A person opens it
on a phone and sees the insurer's brand. They answer the product's questions,
photograph their documents, accept the privacy notice and submit.

From there it is an ordinary application. It enters that insurer's client book
and goes through the same pipeline and the same published playbook version. The
same underwriters decide it, with the same audit trail. The applicant is told
what happened.

There are two kinds of link, and the insurer will want both:

| | **Personal link** (`enlace personal`) | **Product link** (`enlace del producto`) |
| --- | --- | --- |
| For | A person an agent is already working with | Anyone |
| Created by | `agent` / `tenant_admin`, from the client's page | `tenant_admin`, on the product |
| Lifetime | One applicant, one application, expires (e.g. 7 days) | Long-lived; paused or revoked by the admin |
| Client record | Already exists, so answers attach to it | Created by the submission, possibly a duplicate |
| Who can spend your tokens | Whoever the agent sent it to | Anyone on the internet |
| Needs before it ships | The shared core | The core **plus** the controls in § "What a public link exposes" |

The personal link is the same agent workflow with the typing moved to the
applicant. The product link is the one the self-service health market is
growing around, and it carries all the new risk.

## Why this doesn't reverse the Phase 2.2 decision

The decision recorded in `docs/architecture.md` is "the book of business
belongs to the insurer". A link the insurer issues, in its brand, that lands in
its own `clients` table and its own queue is an insurer channel. What Phase 2.2
removed was a Tramiq front door built on anonymous Supabase sessions, which sat
in tension with staff-registered applications. Keep both halves of that
decision:

- **No Tramiq-level applicant account or marketplace.** A link names one
  tenant and one product, and a submission can only land there.
- **No anonymous Supabase session, and no new `anon` grant.** See the next
  section.

`PLAN.md`'s "do not build self-serve onboarding" is about *tenants* onboarding
themselves. This plan doesn't touch it.

## Design

### The rule: the applicant never holds a database credential

```
applicant's phone
   │   /s/<link>  public pages, in the tenant's branding
   ▼
web  /api/intake/*         abuse control: captcha, rate limits, sizes
   │   server-side only, one module (src/lib/intake/, server-only)
   ▼
db   intake_* functions    the authority: token check, tenant and product
   │                       taken from the link, draft-only, schema-checked
   ├── Storage: one signed upload URL per document row, for one exact path
   └── ai-orchestrator /documents/:id/extract, /applications/:id/process
       (SERVICE_AUTH_TOKEN, unchanged)
```

- **The applicant's credential is a session token, not a Supabase JWT.** It is
  random (≥128 bits) and stored only as a hash, like a password-reset link. It
  lives in an `httpOnly` cookie scoped to `/s`, and a resume link carries it.
  It grants exactly one draft application.
- **The database still decides what a write can be.** Each step is a
  `security definer` function that checks the token itself and performs one
  transition: `intake_start`, `intake_verify`, `intake_save`,
  `intake_add_document`, `intake_submit`. The tenant and product come from the
  link row, never from the request. `form_data` keys must exist in the
  product's `form_schema`. A document is born `uploaded` with empty
  extraction, exactly as `20260912000100` requires of staff. An application
  stays `draft` until `intake_submit`.
- **The functions are executable by `service_role` only.** Revoke them from
  `public`, `anon` and `authenticated`. If they were granted to `anon`, anyone
  holding the public key could call them through `/rest/v1/rpc` and skip
  `web`'s captcha and rate limits. `web` calls them from one server-only
  module, and nothing else in `web` gains a service-role write path.
  Hardening option for the security review: a dedicated Postgres role allowed
  to execute only `intake_*`, instead of the service role.
- **Uploads go to Storage through signed upload URLs.** `intake_add_document`
  creates the document row and returns its path,
  `{tenant_id}/{application_id}/{document_id}/{filename}`. The server mints a
  signed upload URL for that path only. No new `storage.objects` policy is
  needed. The bucket's 5 MiB limit and MIME allowlist (`SEC-3`) still apply.
- **Audit.** Every step writes `audit_log` with `actor_type = 'applicant'`
  (already in the check constraint), `actor_id` null (the column is nullable)
  and the intake session id in `metadata`.

### `db` — new objects

| Object | Purpose |
| --- | --- |
| `intake_links` | `tenant_id, product_id, kind ('personal' \| 'product'), slug_or_token_hash, client_id (personal only), name, status (active \| paused \| revoked), expires_at, daily_cap, created_by, created_at`. Staff of the tenant can read it. `tenant_admin` writes product links, and `tenant_admin`/`agent` write personal links. `anon` gets nothing. |
| `intake_sessions` | `tenant_id, link_id, application_id, client_id, token_hash, contact_email, contact_phone, contact_verified_at, otp_hash, otp_attempts, otp_expires_at, consent_text_id, consent_accepted_at, status (started \| verified \| submitted \| expired), last_seen_at, expires_at`. Staff read it through a view that leaves out the hashes. Only the functions write it. |
| `consent_texts` | One row per tenant and version, holding the Spanish privacy notice and consent wording. Immutable once published, enforced by a trigger, like playbooks. A submission records the exact version the person accepted, for the same reason a decision records its playbook version. |
| `applications.channel`, `applications.intake_link_id` | `staff \| personal_link \| product_link`. Add it to `application_list`: views expand `*` when they are created, so they need recreating. |
| `intake_*` functions | Listed above, plus `intake_respond` in phase 3. |

`applications_has_subject` needs no change. A self-service application always
gets a `client_id`, because the function creates the `clients` row with status
`prospect`. `applicant_id` stays dead.

**Duplicates fail safe.** If a product-link submission's email or DUI matches
an existing client, the function **creates a new prospect** and records
`possible_duplicate_of`. It never attaches the submission to the existing
record and never tells the applicant a match exists. Either would let a
stranger write to, or test for, someone else's record. Staff merge. One
collision to handle: the partial unique index on `(tenant_id, lower(email))`.
The duplicate row keeps the email in `intake_sessions` until the merge.

### `web` — public pages

The proxy's `PROTECTED_PREFIXES` doesn't include `/s`, so the session refresh
won't redirect these pages.

1. **`/s/<link>`**, the landing page. It shows the tenant's brand
   (`tenants.branding`, `FUN-6`), from first paint because the link names the
   tenant. It also shows the product, what to have at hand (the playbook's
   `required_documents`, with their `max_age_days` written as "emitido hace
   menos de 6 meses"), the time it takes, and the privacy notice.
2. **Contact and verification.** The product link uses a captcha and then a
   one-time code by email (or SMS/WhatsApp, see the decisions below). For the
   personal link, possession of the link is the first factor, and the person
   confirms their date of birth or DUI against the client record.
3. **Tus datos.** Name, DUI (format and check digit), date of birth, phone.
   This becomes the `clients` row.
4. **Preguntas del producto,** from `form_schema`, validated on the server by
   the same code the staff form uses.
5. **Documentos.** Camera capture on a phone (`accept="image/*" capture`) and
   downscaling in the browser to stay under 5 MiB. The "2 de 3" indicator
   comes from `lib/required-documents.ts`.
6. **Revisión y envío.** The person reviews everything, ticks consent for the
   current `consent_texts` version, and submits. Submitting triggers
   processing exactly as the staff flow does.
7. **`/s/estado/<token>`**, a status page: Recibida → En revisión →
   Necesitamos algo más → Decidida. It is the resume link and, in phase 3,
   the reply channel.

Work is saved at every step, so a person can stop on a phone and finish later.

### `web` — staff screens

- **Tenant page → "Enlaces de solicitud"** for each product: create, copy,
  QR code, pause, revoke, daily cap. It also shows a funnel: opened → verified
  → submitted → decided.
- **Client page → "Enviar enlace personal"** (agent). The agent copies it into
  WhatsApp. Phase 1 needs no email provider.
- **Lists and queue:** a channel filter and an "Autoservicio" badge.
- **Application detail:** "Registrada por el solicitante mediante «Salud
  Individual — web», contacto verificado 14:02, aviso de privacidad v3". Also
  the duplicate hint and a merge action.
- What the applicant answered is now the applicant's own testimony.
  `authenticated` already cannot `UPDATE applications`, so staff can't quietly
  rewrite it. Keep it that way. A correction is a new, audited function.

### `ai-orchestrator`

- **No new endpoint.** `web` triggers extraction when an upload completes and
  processing on submit, as it does now.
- **A daily spend cap per tenant**, read from `ai_usage` (`NEG-1`) before a job
  calls the model. Over the cap, the job doesn't run the model. The application
  goes to manual review with a stated reason. That fails closed, like every
  other gap in scoring, and isn't a silent drop.
- **Prompt injection becomes a blocker.** `STATUS.md` § 7 lists it as never
  reviewed, "worth its own pass before real applicants' files arrive". A
  product link is exactly the point where strangers' files arrive.

## What a public link exposes

| Threat | Control |
| --- | --- |
| Bots filing applications | A captcha on `intake_start`, rate limits per IP and per link (`lib/rate-limit.ts`, with the same two layers as the credential routes), the link's `daily_cap`, and a verified contact before any upload |
| Strangers spending Anthropic tokens | No extraction before verification; the per-tenant daily spend cap; documents per session capped at the playbook's list plus a small margin |
| Malware in files that staff then open | **`SEC-4` becomes a prerequisite.** Scan before a document can be previewed or extracted |
| Hostile text inside documents steering the agents | The prompt-injection review, before the product link opens |
| Checking whether someone is a client | Never merge or reveal a match (see "Duplicates fail safe" above) |
| Stolen or replayed tokens | Tokens stored hashed, short expiry, a single-use code with an attempt limit, and a personal link spent by its first submission |
| Abandoned drafts holding health data | **`SEC-6`:** a retention job deletes unsubmitted drafts and their files after N days without activity, and says so in the privacy notice |
| A captcha script on the page | The CSP is enforced (`next.config.ts`). The captcha's origin is added to `script-src`/`frame-src`, on the `/s` routes only if Next allows it |

## Prerequisites before a product link goes public

Most of these are already in the backlog. A public link moves each of them from
"before a contract" to "before launch".

- **`FUN-10`, typed form schema.** `form_schema.fields` is a list of names,
  and `web` guesses each input's type from the name
  (`lib/application-form.ts`). Staff can work around a bad guess; an applicant
  cannot. Fields become objects, `{key, label, type, required, min, max,
  options, help}`, and the plain-string form stays readable. **Keys stay
  English**, per the workspace invariant. The Spanish goes in `label`.
- **`FUN-3` / `BLK-6`, an email provider.** It sends the one-time code, the
  resume link, "recibimos tu solicitud", "necesitamos algo más" and the
  decision notice.
- **`SEC-4` and the prompt-injection review**, from the table above.
- **`SEC-9` / `SEC-10`, legal.** Health data collected directly from a consumer
  needs a privacy notice and consent wording per tenant. The tenant is the
  controller and Tramiq the processor, which the data-processing contract has
  to say. Ask the lawyer whether the SSF has rules for selling insurance
  through a digital channel. This is calendar time, so start it in phase 0.
- **`BLK-4`, a second environment.** A public form can't be tested against the
  only database, which is production.
- **`NEG-2` and paid plans.** On the free tier, the first visitor after 15 idle
  minutes waits about a minute, and a stranger on a phone leaves. A paused
  Supabase project makes the link dead. A public link is a 24/7 promise.
- **`BLK-5` / `CAL-1`.** Self-service routes more volume, and worse photos than
  staff scans, into a pipeline that hasn't yet scored a real, unflagged
  document end to end. Measure extraction on phone photos before promising
  turnaround.

## Phases

### Phase 0 — Decide (S)

Settle the open decisions below with the insurer. Record the reversal in `docs`:
`architecture.md` ("There is no applicant-facing surface…"),
`module-overview.md`, `supabase-schema.md` (the `applicant` role and
`actor_type`) and step 1 of `mvp-execution-plan.md`'s demo script. Add `FUN-11`
to `product-gap-analysis.md` as a dated addendum, since that document is a
snapshot. Start the legal track.

### Phase 1 — The shared core, opened through personal links (M)

- `db`: `intake_links`, `intake_sessions`, `consent_texts`,
  `applications.channel`, the five functions, and the pgTAP suite (next
  section).
- `web`: the public pages, signed uploads, "Enviar enlace personal" on the
  client page, the channel badge and filter.
- `FUN-10`'s typed schema, at least for the products that get a link.
- Verification is possession of the link plus date of birth or DUI. The agent
  sends the link by hand. No email provider is needed yet.

This gives agents an immediate win. Their clients fill in their own forms and
photograph their own documents, while the risk stays bounded to people the
agent chose. It also runs the whole core in production before any stranger can
reach it.

### Phase 2 — The product link (M–L)

Captcha, the one-time code (the email provider arrives here), duplicate
handling and merge, per-link caps, the per-tenant spend cap, the link
management screen with QR and funnel, and the retention job. **Gated on every
prerequisite above.**

### Phase 3 — Close the loop (M)

- The status page and notifications.
- **"Necesitamos algo más", answered through the link.** `request_case_info()`
  already moves the case to `waiting_on_applicant`, and today that reaches
  nobody. `intake_respond` lets the applicant upload the missing document, and
  the case returns to `in_review`.
- The decision notice, worded the way the tenant chooses (see the decisions
  below).

### Phase 4 — On evidence only

- A custom domain per tenant (`solicitudes.<aseguradora>.com`).
- An embeddable form. Today `frame-ancestors 'none'`, so this would mean
  per-tenant framing rules.
- WhatsApp as a full channel.
- Identity verification against the DUI (`NEG-6`).
- Approving clear cases automatically, which is where self-service speed
  really comes from. That one stays gated on `CAL-2`'s agreement rate, as the
  gap analysis already says.

## Tests that prove it, written from the attacker's side

pgTAP, in a new `intake_test.sql`:

- `anon` and `authenticated` cannot execute any `intake_*` function, and
  `anon_surface_test.sql` passes **unchanged**: the public key still reaches
  zero rows.
- A token for one session cannot read or write another. A revoked, paused or
  expired link refuses `intake_start`, and a link at its `daily_cap` refuses
  the next session.
- `intake_save` rejects keys absent from `form_schema` and can't set
  `status`, `submitted_at` or the playbook fields.
- `intake_add_document` refuses a `doc_type` the playbook doesn't list, and
  the row is born `uploaded` with empty `extracted_data`.
- `intake_submit` refuses an unverified product-link session, a missing or
  stale consent version, and a second submit.
- A product-link submission whose email or DUI matches an existing client
  leaves that client unchanged, creates a new prospect, and returns nothing
  that reveals the match.
- A personal link can't be used for another client or for a second
  application.
- A published `consent_texts` row can't be edited.

`web`: unit tests for the schema validation that staff and public forms share.
A Playwright run of the whole public flow on the non-production environment is
the first concrete `CAL-4`.

## Open decisions

1. **Personal link first, or straight to the product link?** Recommendation:
   personal first. It is the same core with bounded exposure, and it doesn't
   wait on the email provider, the malware scan or legal. If the insurer needs
   the product link at launch, ship phases 1 and 2 together, but don't open
   the product link before its prerequisites are met.
2. **What the applicant is told about a decision.** The exact outcome, or
   "tu solicitud tiene una respuesta; te contactaremos". Likely per tenant and
   per decision. A decline is a regulated conversation for some insurers.
3. **Email, SMS or WhatsApp** for the code and the notices. WhatsApp probably
   matters most in this market. Confirm with the insurer, and check what a
   WhatsApp Business account requires of them.
4. **Domain.** A path on Tramiq's domain in phases 1–3, or the insurer's
   subdomain from the start.
5. **Applicant accounts, or token sessions?** Recommendation: token sessions.
   Real Supabase Auth users for consumers would put an applicant arm back on
   the policies that `20261017000000` scoped to staff, and would add consumers
   to `auth.users` beside staff. Revisit only if applicants need to come back
   for several applications over the years.
6. **Pricing (`NEG-3`).** Does a spam or abandoned session cost the insurer
   anything? Billing per *submitted* application, with model spend before
   submission capped, keeps that question small.
