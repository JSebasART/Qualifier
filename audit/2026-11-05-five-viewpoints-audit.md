# Tramiq — the whole product from five viewpoints, 2026-11-05

Measured on 2026-11-05 against the production database (read only, through
the Supabase connector), the five repos on `develop` (equal to `main` since
2026-11-04), and the public pages of the live web app. It builds on
[`2026-11-02-audit-and-business-proposal.md`](2026-11-02-audit-and-business-proposal.md)
and does not repeat its market, pricing or unit economics. Gap identifiers
(`BLK-4`, `CAL-1`, `FUN-8`…) are the ones in `docs/product-gap-analysis.md`.
Findings here are numbered `V-1`…`V-24`.

**Not seen signed in.** The staff screens were reviewed from their code; only
the sign-in page and the public product link were opened in a browser. A
signed-in walk-through is listed in § 8.

## 0. Fixed on 2026-11-06 (round 1: in production since 06:40 UTC)

Every finding rated S or M is fixed in code, plus bots 1 and 2 of § 7.
Migration `20261106000000_audit_fixes` was rehearsed on production in a
transaction that rolled itself back, applied (ledger `20261106063843`), and
the five repos promoted; STATUS.md records the live checks.

| Finding | Fixed in | How |
| --- | --- | --- |
| V-1 | ai-orchestrator | One document per type, chosen once by the requirement rule; rules and the identity check read only it |
| V-2 | ai-orchestrator | AI score `rubric-v1` computed from findings after identity and injection signals; the model's number kept as `ai_score_model`; an `approve` with fraud signals or an unconfirmed identity is stored as `manual_review` |
| V-3 | grading-engine, orchestrator, db seed, web | Ordered sources (document first, form as fallback); incomes scored on `min(declared, verified)`; the eight seeded playbooks rewritten so a US$400 salary is not a decline and overstating never pays; playbook lint in the editor |
| V-4 | db, orchestrator, web | `scores.inputs` and `scores.engine`; the case screen shows values, sources and versions |
| V-5 | db, orchestrator, web | `request_rescore()` records every rescore; `pipeline_sweep_candidates()` plus a sweep at boot and every 5 minutes; «Atascadas» on the dashboard |
| V-6 | ai-orchestrator | Values below 0.6 confidence are excluded and recorded as such |
| V-8 | db, web | `case_decisions` (backfilled), approval with conditions, reason codes, authority limits per product, `refer_case()`, optional second approver for publishing |
| V-9 | ai-orchestrator | One escalated re-read on poor legibility or a missing / low-confidence key |
| V-10, V-11 | db, web | Per-document check shown to the applicant; DUI photo fills «Tus datos» |
| V-12 | db, web | «Documentos vigentes del cliente», copied server-side and checked by `reuse_client_document()` |
| V-13, V-14 | db, web | `dashboard_metrics()` and the manager section; `case_bundle()` loads the case in one call |
| V-16 | grading-engine | Weights must sum to 1; sources may be lists; rules may carry a label; `/score` returns `engine_version` |
| V-18 | web | One closed state for an unavailable link; per-insurer page titles |
| V-19 | web | Two-pane case screen with «Declarado vs. documento» and values in the trace |
| V-20 | web | Semantic `success` / `warning` / `info` tokens, Inter, small SVG charts. **Also changed:** the primary colour is now the logo's green |
| Bot 1 | ai-orchestrator | Ops watchdog, off until `OPS_ALERT_EMAIL` is set |
| Bot 2 | web | Drafted information request («Usar borrador»), no model call |
| — | db | The vestigial storage policy is dropped; plain `UPDATE`s on playbooks are closed (they could publish around `publish_playbook()`) |

**Verified:** grading-engine 66 tests, ai-orchestrator 289, web 207 plus
typecheck, lint and the production build. db: all 16 suites (454 assertions,
82 new) pass in a PGlite replay of CI with a stand-in for pgTAP; the eight
seeded playbooks parse and evaluate in grading-engine with no unevaluated rule.
**Not verified:** a real pgTAP run on Postgres 17, any screen in a browser, and
the pipeline against the real model.

**Left open after round 1:**
- V-7, the editor rebuild (L);
- V-17 and every infrastructure item (paid tiers, `BLK-4`);
- the production data steps: renaming the `ingreso-auto` link, republishing the production playbooks, and closing the three stuck applications. The deployed sweep closed two of the three.
- bots 4–10 (bot 3 is V-10).

### Round 2 (2026-11-07, committed on `develop`, not pushed, not deployed)

| Finding | Fixed in | How |
| --- | --- | --- |
| V-5, found live | db, orchestrator | A received document with no file after 30 minutes (`orphan`), or stuck reading past 2 hours (`stalled`), is closed with a reason, so its application goes to manual review instead of waiting forever. médico N.º 6 is that case. |
| V-7 | web, orchestrator, grading-engine | Pickers from the form schema and document keys; a rule builder (campo · operador · valor) with the expression as «Avanzado»; «Probar con una solicitud»; a backtest over past applications with no model call; lint inline |
| V-15 | web, db, orchestrator, `qa/demo-files` | A missing file shows a calm state; `upload_demo_files.py` (dry run by default) fills the seeded rows' files; `tenants.is_demo` with a nightly date refresh |
| `required_if` | db, orchestrator, web | Evaluated the same way in all three, failing closed |
| `/analyze` | ai-orchestrator | Removed, along with the in-process pipeline runner only it used |
| Injection test | ai-orchestrator | Hostile fixtures, a fence-coverage unit test, and `scripts/injection-redteam.ts`. The script uses the real model, so it is run by the owner. |
| `SEC-8` | db, web | TOTP MFA opt-in per tenant. Enrolment and challenge screens. Thirteen transitions refuse an `aal1` session. |
| Bot 4 | db, orchestrator, web | Duplicate and fraud linker: the same file hash, the same DUI under another name, the same phone. The case screen links to the other application and client. |
| Bot 5 | db, web | Analysts confirm or correct each extracted value (`field_reviews`), with accuracy per field and a weekly «Muestreo de calidad» |
| Bot 6 / `FUN-8` | db, web | A printable decision letter from `case_decisions`, marked as needing legal review |
| Bot 7 | orchestrator, web | Playbook copilot: a manual's text becomes a validated draft, never published by itself |
| Bot 8 | db, orchestrator, web | The managers' weekly summary email, opt-in per tenant, numbers from SQL |
| Bot 9 | orchestrator, web | Case Q&A answered from stored values, with citations |
| Caveats | db, web | `intake_get` returns the tenant; the applicant's DUI read is audited; «Atascadas» count and list share one definition |

**Verified:**
- tests: grading-engine 70, ai-orchestrator 393, web 236;
- web's typecheck, lint and production build;
- db: 19 suites and 610 assertions (156 new) in the PGlite replay, which runs all three new migrations together.

**Not verified:**
- a real pgTAP run;
- any new screen in a browser;
- the copilot, case Q&A and red team against the real model.

**Still open:**
- V-17 and the infrastructure;
- bot 10 (WhatsApp), which needs a WhatsApp Business account;
- the owner's production and dashboard steps (STATUS.md).

## 1. Verdict

**The machinery is good. The judgement inside it is not ready yet.**

The parts that are hard to build are built well: the rules engine fails
closed, tenants are isolated by the database and tested from the attacker's
side, every decision is recorded with its playbook version, the pipeline is
idempotent, automatic approval is locked behind evidence, and a clean
two-document application costs about **US$0.06** on Sonnet 5.5 and reached a
case in 29 s.

A doubtful insurer would not attack any of that. They would attack the
*content* of a decision, and today they would win:

1. **The score mostly measures what the applicant declares.** Four of the
   eight published playbooks read only the form. Three of the other four use a
   document for one thing, checking the declared salary against the
   constancia. Only the médico plan scores on what a document says. AUTO-AMP
   requires three documents and no rule reads any of them.
2. **A quarter to a third of the score is an AI number with no rubric, and it
   decides tiers.** For a US$2,400 earner on the standard life plan, the gap
   between "revisión manual" and "aprobar" is an AI score of 96 versus 97.
3. **What produced a score is not kept.** The inputs a rule saw are not stored,
   so nobody can show "declared US$2,875, constancia US$2,400, 19.8 %", now or
   in an audit.
4. **The rules can read a different document from the one that passed the
   checks** (a bug, § 4.1).
5. **The sample life playbook recommends declining a US$400-a-month earner even
   with perfect documents**, and pays an applicant for overstating income.

All five can be fixed in weeks, mostly in the orchestrator and the playbooks.
That work turns "the AI reads documents" into "verified facts, scored the same
way every time, with the evidence on file", which is the product the website
already promises.

### The ten that matter most

| # | Finding | Severity | Effort | Who notices first |
| --- | --- | --- | --- | --- |
| V-1 | Rules read whichever document comes back first, flagged or stale included | High | S | Auditor, fraudster |
| V-2 | AI score: no rubric, decides tiers, ignores the identity check | High | M | Buyer, regulator |
| V-3 | Sample playbooks score declared values; documents unused | High | S–M | Buyer's underwriting manager |
| V-4 | A score's inputs, sources and model are not stored | High | M | Auditor, analyst |
| V-5 | Submission and processing are not atomic; stuck applications are invisible | High | S–M | Operations |
| V-7 | Playbook editor needs an engineer | High | L | Buyer, our own services cost |
| V-8 | Decisions are binary; no reason codes, no authority limits | Medium | M | Process owner, regulator |
| V-10 | The applicant uploads blind | Medium | M | Applicant, analyst |
| V-13 | The dashboard counts work and shows no value | Medium | M | Underwriting manager |
| V-15 | Demo data breaks on click (27 of 38 documents have no file) | Medium | S | Prospect, in the demo |

Effort: S ≤ 1 day, M 2–5 days, L 1–3 weeks.

## 2. What was checked

- **Production, read only:** counts by status, every score with its parts and
  findings, the eight published playbooks, `ai_usage` by agent and model,
  `decision_agreement`, `application_pipeline_timing`, Storage objects against
  `documents`, intake links, and the security advisor.
- **Code:** grading-engine (evaluator, JDM builder, `/score`), ai-orchestrator
  (pipeline, three agents, routing, field resolution, required documents,
  identity check, queue), db (`auto_decide_case`, `publish_playbook`, form
  validation), web (case screen, rule trace, dashboard, new application form,
  playbook editor, intake flow, design tokens, pipeline triggers).
- **Live, signed out:** the sign-in page and `/s/ingreso-auto` at desktop and
  phone widths.
- Not run here: the test suites (STATUS.md has them green on 2026-11-04:
  web 156, orchestrator 234, grading-engine 58, pgTAP), CI on GitHub
  (not readable from this machine).

**Production on 2026-11-05.** 2 tenants, 8 products, 8 published playbooks,
17 clients, 21 applications (all through the staff channel), 38 documents,
17 scores, 16 cases, 5 human decisions ever (3 approved, 2 declined), 43
model calls costing US$0.66 in all, 1 intake link, 0 consent texts, automatic
approval off everywhere. Last sign-in 2026-11-04 21:38 UTC.

## 3. The flow end to end, and where it breaks

| Stage | What happens | Weak point | Finding |
| --- | --- | --- | --- |
| Register client | Staff types it, or «Subir DUI» reads both sides | The applicant on a link types the DUI by hand | V-11 |
| New application | Product first; documents chosen before saving | A DUI already verified for this client is asked for again | V-12 |
| Upload | Extraction starts at once (≈ 6 s per document on 5.5) | Nobody tells the uploader what was read | V-10 |
| Submit | `submit_application()` commits; then the browser asks for processing | If that second call fails, nothing retries it | V-5 |
| Requirements | Presence and age of each required document | Checks one document, scores another | V-1 |
| Consistency | AI compares form and documents, returns an `ai_score` | No rubric; identity mismatch added after the score | V-2 |
| Narrative | AI writes the Spanish summary | Good. Not used to decide, as intended | — |
| Score | grading-engine evaluates the playbook | Scores declared values; inputs not stored | V-3, V-4 |
| Case | Opens with an SLA deadline | Approve/decline only; anyone may decide anything | V-8 |
| Decide | `decide_case()`, note required against the recommendation | Reason is free text | V-8 |
| After | Audit log; applicant notification on links | No letter, no metrics, no learning loop | V-13, V-14 |

## 4. Five viewpoints

### 4.1 The main developer

*Cares about: correctness, reproducibility, what breaks at 2 a.m.*

**What is genuinely strong.** The fail-closed sentinel row in
`grading-engine/src/engine/jdm-builder.ts` is the right idea, explained where
it lives. Database transitions go through role-checked functions, and the
tests are written from the attacker's side. The pipeline is idempotent,
refuses cross-tenant playbooks twice, records spend per tenant, and fences
document text as untrusted. `auto_decide_case()` refuses on every kind of
doubt: flags, fraud signals, medium or high mismatches, an unconfirmed
identity, a flagged document, an accepted outdated document, lapsed evidence.
The commit history explains *why*, which is rare.

**V-1. The rules can read a different document from the one that passed the
checks (High, S).** `processApplication` loads documents with no `order`
(`ai-orchestrator/src/applications/process.ts`, the `documents` select), and
keeps flagged ones. `checkRequiredDocuments` then picks the *newest clean*
document of each type to judge presence and age. `resolveFields` picks
`extractions.find(e => e.doc_type === docType)`, the *first* row Postgres
happens to return, flagged or stale included
(`src/applications/resolve-fields.ts`, `resolveSource`). The identity check
takes the *last* DUI of the same unordered list. With two constancias on file
(which "accept an outdated document" and "a newer constancia updates the
client" make common), the rule can score the salary from the old or
tamper-flagged letter while the requirement was met by the new one.
*Fix:* choose one document per type, once, by the same rule the requirement
check uses. Pass that set to `resolveFields` and the identity check, and record
its `document_id` beside every field (V-4). Add a test with two documents of a
type in both orders.

**V-2. The AI score has no rubric, decides tiers, and misses the identity
check (High, M).** `ai_score` is the consistency agent's own 0–100 "confidence
in this applicant's data" (`src/agents/consistency-agent.ts`). It carries 25–35
% of the final score in every playbook. Three problems:
- *It is not risk.* It measures whether documents agree with the form, then is
  added to a risk score as if it were one.
- *It sits on the tier boundary.* See Appendix A: on VIDA-STD a US$2,400
  earner needs AI ≥ 96.7 to be recommended for approval. Observed AI scores on
  clean QA documents were 95, 97 and 100. When the model thought a date was in
  the future (2026-10-17), one wrong judgement moved the final score ten points
  and the tier. Nobody has measured how much it moves when the same application
  is scored twice. Ten consistency calls cost about US$0.12.
- *It misses what the pipeline itself found.* The identity mismatch and the
  form-injection signal are appended to `fraud_signals` *after* the agent
  returned its score (`process.ts`), so a DUI that belongs to someone else
  does not lower the score. `auto_decide_case()` still refuses such a case,
  but the case screen shows the recommendation unchanged.

*Fix:* derive `ai_score` deterministically from the agent's findings (start
at 100; subtract fixed points per mismatch severity and per fraud signal; cap
it on an identity mismatch), or stop adding it and use it as a gate ("no
`approve` recommendation below N"). Either way, downgrade an `approve`
recommendation to `manual_review` when a fraud signal or identity mismatch
exists, so the screen and `auto_decide_case()` agree.

**V-4. What produced a score is not stored (High, M).** `scores` holds
`rule_trace` (rule id, passed, value) and `rationale`, but not the resolved
`fields` the engine evaluated, which document each came from, the extraction
confidence, the grading-engine version, the models or a prompt version
(columns checked in production). Re-extracting a document later changes what
the case screen shows beside an old score. An auditor cannot replay a decision.
`ai_usage` knows the model per call, but nothing ties it to the score.
*Fix:* `scores.inputs` (key → value, source, `document_id`, confidence) and
`scores.engine` (engine version, model ids, prompt hash). The rule trace then
shows values (V-19). This is also what a buyer's compliance team will ask for
first.

**V-5. Submission and processing are two separate requests (High, S–M).**
`submit_application()` commits, and then the browser sends a second request
that the server forwards to the orchestrator, waiting up to 90 s
(`web/src/lib/pipeline.ts`, `src/lib/service-client.ts`). If it fails, or the tab
closes in between, a toast asks the person to press «Ejecutar puntuación».
Nothing reconciles later. Production has **3 applications in `submitted`
with no score and no case**: N.º 9 and médico N.º 6 (seeded) and N.º 11
(2026-11-03 00:49 UTC, no documents). The dashboard counts them as «Esperando
decisión», but they sit in no underwriter's queue. *Fix:* enqueue in the same
transaction (an outbox row the orchestrator drains, or `pgboss.send` from SQL).
Add a sweep at boot and every few minutes for submitted applications with no
job, and an «Atascadas» count on the dashboard.

**V-6. Extraction confidence is ignored by the score (Medium, S).** Every
extracted field carries `confidence` 0–1. Only `documents/client-facts.ts`
reads it, to decide whether to update the client. A rule reads a 0.3 value
exactly like a 0.99 one. *Fix:* below a threshold, a field a playbook reads is
null, so the rule is indeterminate and a person looks. Show the confidence
beside the value.

**V-9. Escalation is configured, documented and never used (Low, S).**
`routing.ts` has an `escalate` path, and `docs/architecture.md` says the model
is chosen per playbook and escalates on ambiguous or high-value cases. Nothing
passes `escalate`. *Fix:* escalate extraction on `legibility: poor` or low
confidence on a playbook key, or correct the document.

**V-14. Client-side waterfalls (Medium, M).** Every staff page renders
«Verificando tu sesión…», then loads in the browser. The case screen waits on
three rounds of requests in a row (1, then 4, then 3). The dashboard sends one
count query per application status, plus several more. On a cold free-tier Supabase that is
seconds of skeletons. *Fix:* one `case_bundle(case_id)` RPC and one
`dashboard_metrics()` RPC; server components for first paint.

**V-16. Three copies of the playbook type (Low, M).** grading-engine,
ai-orchestrator (`resolve-fields.ts`) and web each define the shape, and the
seed playbooks are transcribed by hand into grading-engine's tests (the file
says it already drifted once). The engine accepts `ai_weight + rule_weight ≠ 1`
although the doc says they must sum to 1; only the editor checks it. *Fix:* a
shared JSON Schema in `docs/` or `db/`, validated in all three. Add the sum
check to `PlaybookSchema`.

**Carried over and still open** (STATUS.md, the 11-02 audit, the advisor
today): free tiers that sleep and pause, one environment and no rehearsed
restore (`BLK-4`); anonymous sign-ins on with 2 anonymous users, leaked-password
protection off, no MFA (`SEC-8`); the database password printed on 2026-11-02
and not yet rotated; prompt-injection defences never tested against hostile
documents; the vestigial `applicant_read_own_application_documents` storage
policy; `required_if` documented and not evaluated. **Closed since 11-02:** the
model retirement. The default is `claude-sonnet-5-5`, and 22 production calls
have run on it.

### 4.2 The doubtful buyer

*An underwriting manager at a mid-size Salvadoran insurer, burnt by a vendor
before. Asks the questions below, in this order.*

**"What does 85.1 Preferente mean?"** Today the honest answer is: 70 % of it is
how close the applicant's *declared* income is to US$3,000, and 30 % is the
model's confidence that their papers agree. That is not a risk class, and they
will say so. **What convinces them:** a playbook built from *their*
underwriting manual, scoring verified facts (V-3), with a score whose every
point traces to a value and a document (V-4).

**"Will it decline my customers?"** The standard life playbook recommends
"Rechazo" at US$500 a month unless the AI score is 95 or more, and *always* at
US$400, whatever the documents say. It can recommend
approval only above US$2,357 (Appendix A). A person decides every case, but
going against the recommendation needs a note, so the recommendation anchors
the analyst. Shown to a regulator, a rule that ranks applicants by income is a
fairness question. **What convinces them:** sample playbooks that look like
real underwriting (age bands, sum insured against income, medical requirements
by sum insured, smoker loading), plus a "decline-rate by income band" view
(V-13).

**"Show me where my documents are actually used."** On AUTO-AMP, nowhere: the
vehicle year, claims and driving years come from the form, and the licence and
registration card are collected but never read by a rule. The same holds for
GMM-IND v2's medical exam, HOGAR's property deed and DEUDA-PER's loan
statement: required, and read by nothing. **V-3 (High, S–M).** *Fix:*
read the document first and fall back to the form (`fields[].source` as an
ordered list). Score `min(declared, verified)` for amounts. Add a **playbook
lint** that warns when a required document feeds no rule, when a rule reads a
declared value that a document also carries, and when the weights cannot reach
the top tier or cannot fall below the bottom one.

**"Can someone game it?"** Yes, on VIDA-STD. An applicant earning US$2,000
who declares US$3,000 is caught (−15) and still scores 85 rule points against
66.7 for telling the truth. Declaring up to 17.6 % above the verified figure
is never penalised at all (Appendix B). The fix is the same as V-3.

**"What is your accuracy?"** Unknown (`CAL-1`). There are three QA fixture
sets, and no number. This was the first question in both earlier audits and is
still unanswered. A cheap way in is § 5's correction loop.

**"Can my team change the rules without you?"** Not yet (V-7, § 4.5). They would
type `document.proof_of_income.monthly_income` and test with raw JSON. Sell
configuration as a service until the editor is fixed.

**"Prove a past decision."** Partly. The playbook version and the audit row
are there. The inputs are not (V-4).

**"What does it cost and how fast is it?"** Strong answers: US$0.058 in model
cost for a clean two-document application on Sonnet 5.5 (2 × 0.0156
extraction, 0.0121 consistency, 0.0147 narrative, averages from `ai_usage`),
and 29 s from sending to case on N.º 13. Say it with the caveat that free-tier
cold starts add a minute.

**"Who else uses it?"** No one yet. 21 applications, all staff-entered, 5 human
decisions. Say so; offer the pilot.

### 4.3 The process engineer

*Maps the value stream, counts waits, rework and hand-offs, and asks what is
measured.*

**The stream today:** intake → upload → submit → read (≈ 6 s per document) →
check → narrate → score → queue → analyst → decision → notice. Machine time is
about half a minute. Everything else is waiting or rework, and none of it is
measured per stage.

**Waste found:**
- **Waiting.** Cold starts (a minute per sleeping service), the queue
  stopping while the orchestrator sleeps, and 6 of 7 open cases past their SLA
  today.
- **Rework.** An applicant learns a document was wrong only when the analyst
  asks (V-10). Application 14's 103-day constancia went all the way to scoring
  before anyone saw it.
- **Re-entry.** The same DUI is uploaded for each new application of the same
  client (V-12). On a link the applicant types the DUI that a photo could fill
  (V-11).
- **Invisible inventory.** Submitted applications with no case (V-5).

**V-8. Missing controls (Medium, M).**
- **Binary outcomes.** Approve, decline or ask for more. Insurance needs
  *approve with conditions*: an extra premium (loading), an exclusion, a lower
  sum insured, a waiting period. The tier "Subestándar" exists, and there is no
  way to record what it means for the policy. *Fix:* an outcome type plus
  structured conditions on the decision.
- **Free-text reasons.** A decline reason is a note. Nothing can count "declined
  for income inconsistency" across a month, which is what a regulator, a
  reinsurer or a product manager asks. *Fix:* reason codes per product, from
  the playbook's rule reasons plus a short list, alongside the note.
- **No authority limits.** Any underwriter can decide any case, whatever the
  sum insured. *Fix:* an authority matrix (role × product × sum insured) that
  `decide_case()` enforces, with referral to a senior.
- **One person publishes rules.** `publish_playbook()` lets one tenant
  administrator change every future decision, with no second approver and no
  impact shown. *Fix:* maker-checker on publication, with a backtest summary
  attached (§ 5).

**KPIs to compute (the data exists):** lead time per stage (`audit_log` has
`application.submitted`, `document.extracted`, `application.scored`,
`case.created`, `document.viewed`, `case.approved`); touch time (first view to
decision); first-pass yield (share decided without an information request);
SLA compliance; agreement between recommendation and decision
(`decision_agreement`); cost per decided case (`application_ai_cost`).

### 4.4 The web designer

*Looks at the public surfaces, information architecture, metadata and
performance.*

**V-17. The first impression can be a Render error page (Medium, S).** The first
request this session got HTTP 503 and Render's "Application loading" page.
A prospect clicking the link from an email sees that, not Tramiq. *Fix:* paid
instances before any prospect has the link; until then, an uptime ping and the
demo-day warm-up already in `demo/DEMO.md`.

**V-18. The public product link contradicts itself (Medium, S).**
`/s/ingreso-auto` says «Completa tus datos… Te toma unos 10 minutos», then
«Este producto todavía no recibe solicitudes en línea», then offers
«Enviarme un enlace» by email, which cannot send while mail is not configured.
The link is named "ingreso auto" and points at the life product. The page's
meta description is the staff app's («Revisión de solicitudes con IA… decisión
del analista»), which is what WhatsApp shows when an insurer shares the link.
*Fix:* a closed state with one sentence and the insurer's contact; per-tenant
title, description and Open Graph image on `/s/*`; rename or remove the link.

**Information architecture.** The menu (Panel, Clientes, Solicitudes, Casos,
Productos, Configuración, Usuarios) is the data model. An underwriter thinks
"my queue", an agent "my applications", a manager "how are we doing". *Fix:* a
home per role. The agent lands on their applications, the underwriter on «Mi
cola» (assigned to me, then unassigned by deadline), the manager on the
metrics of V-13. Fold «Casos» into the application page as its decision stage.

**Brand hierarchy.** Applicant pages correctly lead with the insurer («S
Seguros») and credit Tramiq in the footer. The insurer's avatar is a letter
in a square, so ask for the logo during configuration.

**Already right:** `lang="es"`, labelled inputs with `autocomplete`, no
horizontal scroll at 375 px, CSP and security headers, Spanish 404 and errors.
(CLAUDE.md still says `<html lang>` is `en`. It is `es` now.)

### 4.5 The UI designer

*Looks at screens, hierarchy, components and the design system.*

**V-19. The case screen asks for a decision before it shows the evidence
(Medium, M).** It is one long column: the decision panel first, then the
score, rule trace, documents (one preview at a time), form answers, comments
and history. The comparison the whole product exists for, *declared against
read*, is spread over three sections. The rule trace leads with English ids in
monospace (`income_consistency`), with the Spanish reason and the expression
hidden in a tooltip and no values. *Fix:* two panes. On the left, the evidence:
a "declared vs document" table for every field the playbook reads, each value
linked to its place in the previewed document. On the right, sticky: score,
findings, decision. In the trace, a Spanish label first ("Ingreso
consistente") and the values in the row ("declarado US$2,875 · constancia
US$2,400 · 19.8 % > 15 %"). This needs V-4's stored inputs.

**V-7. The playbook editor is an engineer's tool (High, L).** Rules are typed
as expressions; sources as `form.date_of_birth` or
`document.proof_of_income.monthly_income`; document types as `proof_of_income`;
the test panel takes raw JSON. It is complete and careful (versions, diff,
draft and publish, Spanish labels, a guided first playbook), but the product's
thesis is that an insurer's own people edit rules, and they cannot. *Fix:*
- pickers fed by the product's form schema and document types;
- a rule builder (campo · operador · valor · si no cumple), with the expression
  as an advanced view;
- «Probar con la solicitud N.º 13» instead of JSON;
- backtest a draft against past applications (§ 5) before publishing;
- the lint from V-3, shown inline.

**V-20. The design system is stock shadcn (Low, M).** Zero-chroma grays,
system fonts, and status colours hard-coded as Tailwind amber, emerald and sky
about 60 times instead of semantic tokens. There is no chart component, so the
dashboard cannot show a trend. It works and is consistent; it also looks like
every other admin template, next to a landing page with a real brand. *Fix:*
`--success`, `--warning` and `--info` tokens; one brand typeface; a small chart
set (bar, line, distribution) for the dashboard and the score.

**V-10 and V-11. The applicant's flow on a phone (Medium, M).** Steps are code
→ «Tus datos» → «Preguntas» → «Tus documentos» → «Revisar y enviar». The
DUI is typed, although staff already have a two-sided photo read
(`/api/identity/read`). The uploader shows the requirement («Emitido hace menos
de 90 días») and never whether the uploaded file met it. *Fix:* photograph the
DUI first and fill «Tus datos» from it. After each upload, show what was read
within a few seconds: right document type, legible, issue date within the
limit, both sides of the DUI. The extraction already runs on upload.

**Already right:** decision order on the case screen, a glossary with tooltips
on every term, confirmations before one-way actions, a note required against
the recommendation, Spanish errors instead of database English, relative
deadlines, toasts in a live region, and explicit failure states instead of
plausible empty screens.

## 5. Data: what we keep, what we use, what it could deliver

| Data we already hold | Used today for | Could deliver |
| --- | --- | --- |
| Extracted fields with confidence | Rules (without confidence), client updates | Confidence gates (V-6); a correction loop that builds the accuracy set |
| Form answers next to extractions | Consistency agent | A deterministic declared-vs-verified table on every case (V-19) |
| Scores, rule traces, playbook versions | The case screen | **Backtesting:** replay a draft playbook on past applications and show which recommendations change before publishing |
| Human decisions vs recommendations | `decision_agreement`, the auto-approval gate | Agreement per rule, per analyst, per tier: where the playbook is wrong |
| `audit_log` timestamps | History panels | Lead time per stage, touch time, first-pass yield (§ 4.3) |
| `ai_usage` | Spend cap | Cost per decided case, per product, per channel; migration comparisons (5.5 is 17 % cheaper per extraction) |
| Clients across products | Duplicate detection (`possible_duplicate_of`) | Client 360, reuse of valid documents (V-12), cross-sell (an approved life client offered AP-IND) |
| Document files | Extraction | A content hash: the same file submitted for two people, one constancia template with different salaries |
| Decline notes | Nothing | Reason codes, then decline reasons by product and month (V-8) |

**V-12. Valid documents are not reused (Medium, M).** Documents belong to an
application, not to a client. There is no `client_id` or content hash on
`documents`. A second application for the same client asks for the DUI again,
although its `expiry_date` was read the first time. *Fix:* «Documentos vigentes
del cliente», offered when a new application starts: a DUI until it expires, a
constancia within the product's `max_age_days`.

**V-13. The dashboard counts work and shows no value (Medium, M).** It shows
clients, applications, «Esperando decisión», open cases, a pipeline bar and
recent items. It does not show what the buyer pays for: time to decision, SLA
met, approval and decline rates, agreement, cost per case, decline reasons.
The views exist (`decision_agreement`, `application_pipeline_timing`,
`application_ai_cost`). *Fix:* a manager's page from one `dashboard_metrics()`
RPC. Include a decline rate by declared-income band, because of § 4.2.

**The correction loop (the cheapest path to `CAL-1`).** Let the analyst
confirm or correct each extracted value the playbook reads, one click per
field, on the case screen. Every correction is a labelled example. After a
month of pilot there is an accuracy number per field and document type, and
every model migration becomes a measured comparison instead of a guess.

## 6. Making procedures easier

| Who | Today | Easier |
| --- | --- | --- |
| Applicant | Types name, DUI and birth date; uploads blind; waits to hear | DUI photo fills the form; instant feedback per document; a status page |
| Agent | Re-uploads a client's DUI for every product | Valid documents are offered from the client's file (V-12) |
| Analyst | Reads trace, documents and answers in three places; types a free note | One declared-vs-verified table; reason codes; a drafted information request (§ 7) |
| Analyst | Asks for more information by writing from scratch | The request pre-filled from what is missing, stale or inconsistent |
| Manager | No view of throughput, quality or cost | A metrics home page (V-13) and a weekly summary |
| Tenant admin | Writes expressions; tests with JSON; publishes alone | Rule builder, test on a real application, backtest, second approver |
| Us (setup) | Transcribe an underwriting manual into JSON by hand | A playbook copilot drafts it (§ 7); the lint and backtest check it |
| Operations | Learns of a dead pipeline from a user | A watchdog message (§ 7) |

## 7. Other bots that would add value

The principle that already holds should stay: **bots draft and check, the
playbook scores, a person signs.** None of the bots below decides a case. Each
can reuse what exists: `callStructured`, the untrusted-content fence,
`ai_usage` for cost, and pg-boss.

| Rank | Bot | What it does | Value | Guardrail | Effort |
| --- | --- | --- | --- | --- | --- |
| 1 | **Ops watchdog** (no model needed) | Stuck submissions, dead letters, overdue SLAs, spend near the cap, a failing queue → WhatsApp or email to the team; a morning digest | Nobody learns of an outage from a user again (`NEG-2`) | Read-only | S |
| 2 | **Information-request drafter** | Drafts the message to the applicant from unmet requirements, stale documents and mismatches | Fewer round trips; consistent, polite Spanish | The analyst edits and sends | S |
| 3 | **Document pre-check** | On each upload, says in seconds whether it is the right document, legible, recent enough, both DUI sides | Cuts the "waiting on applicant" loop at the source | Advisory only; never blocks sending | M |
| 4 | **Duplicate and fraud linker** (deterministic) | Same file hash, same DUI with a different name, same phone across clients, one employer template with different salaries | Fraud caught across applications, which no single-case agent can see | Raises a signal; a person judges | M |
| 5 | **Calibration sampler** | Samples decided cases for field confirmation; optionally a second, cheaper model re-reads and flags disagreements | Builds `CAL-1` continuously; makes migrations measurable | Human labels are the truth | M |
| 6 | **Decision-letter drafter** (`FUN-8`) | Fills a legal-reviewed Spanish template with the decision, conditions and reason codes | A deliverable insurers expect; consistent wording to applicants | Template fixed by legal; the model fills facts only | M |
| 7 | **Playbook copilot** | Turns an insurer's underwriting manual into a draft form, required documents, playbook and test cases; explains a version diff in plain Spanish | Answers "who edits playbooks?" and cuts our setup cost per product line | Output is a draft that must pass lint, backtest and a second approver | L |
| 8 | **Manager's weekly summary** | Writes the week from the metrics views: volume, rates, SLA, cost, anomalies | The manager reads one message instead of a dashboard | Numbers come from SQL; the model only words them | S, after V-13 |
| 9 | **Case Q&A for analysts** | Answers "why 84.5?" or "what changed since the last score?" from the stored inputs and trace | Faster reading of long cases | Read-only; cites stored values; needs V-4 | M |
| 10 | **WhatsApp intake assistant** | The application as a conversation: answers, photos, status | The widest reach in El Salvador | Consent, injection and identity risk are highest here; only after 3 and 4 | L |

## 8. Roadmap

**Now (two weeks).** Correctness and credibility.
1. V-1: one document per type, chosen once, recorded per field.
2. V-2: a deterministic AI score or a gate. Fraud and identity signals
   downgrade an `approve`. Measure repeatability (ten runs of one
   application).
3. V-4: store inputs, sources, confidence, engine and model versions on each
   score.
4. V-5: atomic enqueue, a sweep, and a count of stuck applications. Close the
   three stuck ones.
5. V-3: playbook lint; sample playbooks rewritten to score verified values and
   to look like underwriting.
6. V-15, V-18: a real file behind every seeded document (the QA generator
   already makes signed and stamped PDFs), a nightly date refresh, the link
   renamed or closed properly, per-tenant metadata.
7. Carried: rotate the database password; anonymous sign-ins off and the two
   users deleted; leaked-password protection on.
8. A signed-in walk-through of every staff screen as each role, to confirm
   § 4.5 against the running app.

**Next (six weeks).** The product a manager buys.
- V-19: the two-pane case screen with the declared-vs-verified table and
  values in the trace.
- V-7: pickers, rule builder, test on a past application, backtest.
- V-8: outcome types with conditions, reason codes, authority limits,
  maker-checker on publication.
- V-13: the manager's metrics page.
- V-10, V-11, V-12: applicant pre-check, DUI photo first, reusable documents.
- Bots 1–3.
- Paid tiers, a second environment, backups and a rehearsed restore
  (`BLK-4`).

**Later, on evidence.** Bots 4–10, escalation routing (V-9), `required_if`, a
shared playbook schema (V-16), the design-system pass (V-20), automatic
approval for the first product that earns it.

## Appendix A. VIDA-STD: what the AI score has to be

Published playbook: `final = 0.7 × rule + 0.3 × AI`; `rule =
min(declared monthly income / 3000, 1) × 100` when income is consistent; tiers
A ≥ 85 approve, B ≥ 65 and C ≥ 40 manual review, D < 40 decline.

| Declared monthly income | Rule score | Best possible final (AI 100) | Recommendation reachable | AI needed |
| --- | --- | --- | --- | --- |
| US$400 | 13.3 | 39.3 | **Decline only** | — |
| US$500 | 16.7 | 41.7 | C at best | ≥ 94.4 to avoid decline |
| US$1,000 | 33.3 | 53.3 | C at best | ≥ 55.6 to avoid decline |
| US$2,000 | 66.7 | 76.7 | B at best | ≥ 61.1 for B |
| US$2,400 | 80.0 | 86.0 | A | **≥ 96.7 for approve** |
| US$3,000 | 100.0 | 100.0 | A | ≥ 50 for approve |

An approve recommendation is possible only from US$2,357 a month.

## Appendix B. VIDA-STD: overstating income pays

`income_consistency` fails when `|declared − verified| / declared > 0.15`,
costing 15 points; the base score uses the *declared* figure.

| Verified US$2,000, declares | Difference | Penalty | Rule score |
| --- | --- | --- | --- |
| US$2,000 (the truth) | 0 % | — | 66.7 |
| US$2,350 | 14.9 % | — | 78.3 |
| US$3,000 | 33.3 % | −15 | **85.0** |

The consistency agent will likely lower the AI score for the US$3,000 case.
Against an honest applicant at AI 100 (final 76.7), honesty wins only if the
overstater's AI score falls below about 57.

## Appendix C. Production evidence (2026-11-05, read only)

- **Applications:** 21. 1 draft, 3 submitted (no score, no case), 7 in manual
  review, 5 approved, 4 declined, 1 withdrawn. All `channel = staff`.
- **Documents:** 38. 35 extracted, 2 flagged, 1 uploaded. 15 Storage objects;
  11 documents have a file, so 27 cannot be opened.
- **Scores:** 17. Recommendations: 6 approve, 8 manual review, 3 decline.
  3 blocked for missing or outdated documents.
- **Cases:** 16. 7 open, 6 of them past their SLA.
- **Decisions by a person:** 5. `decision_agreement`: seguros VIDA-STD 2 of 2
  comparable agreed; médico 0 comparable.
- **`ai_usage` on Sonnet 5.5 (averages):** extraction 16 calls, 3,741 in / 816
  out tokens, US$0.0156, 5.9 s. Consistency 3 calls, US$0.0121, 5.7 s.
  Narrator 3 calls, US$0.0147, 7.6 s. On Sonnet 4.5: extraction US$0.0187,
  8.7 s.
- **Published playbooks:** a document value feeds a rule in four of eight:
  VIDA-STD, VIDA-T20 and DEUDA-PER (the constancia's salary, for the income
  consistency check) and the médico plan (glucose and conditions, which it
  scores). AP-IND, AUTO-AMP, GMM-IND v2 and HOGAR read only the form. Required
  and read by no rule: AUTO-AMP's licence and registration card, GMM-IND's
  medical exam, HOGAR's property deed, DEUDA-PER's loan statement. The DUI is
  read by the identity check in every product.
- **Security advisor:** 25 `SECURITY DEFINER` RPCs executable by
  `authenticated` (by design, each checks the role); anonymous sign-ins
  enabled; leaked-password protection off; `application_numbers` has RLS with
  no policy (only functions write it); pg-boss search paths.
- **Intake:** 1 product link (`ingreso-auto`, on VIDA-STD), 0 sessions, 0
  consent texts.
