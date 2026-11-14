# Status — verified 2026-11-13

This file grew as a log. The headline below is current; everything after it is
history, each part as true as its date.

**Headline (2026-11-13, ~23:45 UTC): Plan 3 (client data, `DAT-1` to `DAT-9`) in production, built for a demo.**

- **What it adds.**
  - **Facts and profiles:** every value seen about a client, from documents,
    forms, analysts, rectifications and derivations, is a fact with its
    source. A consolidated profile is built from them by survivorship rules,
    with conflicts, and shown in the «Datos del cliente» tab.
  - **Extraction extras:** values found outside a document type's schema are
    kept and reviewed in «Campos no catalogados».
  - **Enrichment and catalogs:** deterministic enrichment and an employers
    catalog.
  - **Transcription:** `claude-haiku-5-5`, immediate or through Message
    Batches, opt-in per document type.
  - **Search:** Spanish full-text search in the top bar.
  - **Segments:** each carries a purpose, with consent and sensitivity
    enforced by the database. CSV export is audited.
  - **Dashboards:** data quality and portfolio panels.
  - **Semantic search:** pgvector plus Voyage AI. It fails closed: off until
    `VOYAGE_API_KEY` is set and a superadmin activates the Voyage AI
    subprocessor.
  - **Analytics replica:** pseudonymized, with k = 5.
  - Design and decisions: `plans/03-design.md`. Execution record:
    `plans/03-PLAN-STATE.md`.
- **Owner decisions (2026-11-12).** All of DAT-1 … DAT-9, including the two
  optional phases. Transcription runs in both immediate and batch modes. The
  backfill used existing extractions only, with no re-extraction.
- **Promoted** in deploy order:
  - docs `a3856fe`, db `943add3`, ai-orchestrator `41b3cd4`, web `9d4fdff`, then `90a8426` after the walk below;
    grading-engine is unchanged at `cc04cbd`.
  - The previous `main`s are docs `08d1f4d`, db `bf445aa`, ai-orchestrator
    `6a5b1b0` and web `81b2785`.
  - The orchestrator no longer writes client columns itself
    (`client-facts.ts` is gone). It calls `record_document_facts()`, so it
    must not run against a database without migration A.
- **Migrations**, ledger 42 → 45: `client_data_core`,
  `client_data_search_enrichment` and `client_data_vectors_analytics`
  (`20261113000000` … `000200`).
  - **Order.** Each was replayed locally in PGlite (35 suites), rehearsed
    rolled back on dev, applied to dev (ledger 55 → 58), then rehearsed rolled
    back on production and applied there with md5 guards.
  - **Production rehearsal.** 16 suites, 1,586 assertions, 0 failed, with the
    real `vector` extension. This includes the independent attacker suite
    (254) and every Plan 2 privacy suite. The count of security-definer
    functions executable by `anon` stayed at 0.
  - **Bugs the real-Postgres runs found.** One was a test that counted rows
    in the same snapshot as the function writing them (db `6ab72e3`). The
    other was a backfill regression report too strict about equal copies of
    one certificate (db `943add3`). Neither was a migration bug.
- **Backfill on production.** 40 documents produced 316 facts and 17 profiles.
  One document had not been read. The regression report has 0 rows, so the
  seven legacy client columns are unchanged. The analytics replica was
  refreshed: seguros has 5 subjects, all generalized to k = 5; medico's
  subjects were suppressed.
- **Reviews.**
  - A security and privacy review (opus) found 1 high, 2 medium and 2 low
    problems. The high one: catalogued fields of a sensitive document type
    reached agents.
  - An independent attacker suite found 3 more, in `merge_clients` and in how
    a sensitivity change propagates.
  - A contract cross-check found 1 problem (the page citation ref).
  - All are fixed before apply: db `dd17db7`, orchestrator `41b3cd4`, web
    `c4d0813` / `b3ece68` / `9d4fdff`.
- **Not exercised live yet:**
  - transcription and Message Batches against the real Anthropic API, so
    whether `claude-haiku-5-5` and Batches work with this key is unknown;
  - Voyage, which has no account yet;
  - the screens are walked; see below.
- **Walked signed in on the deployed site** (2026-11-14, tenant seguros):
  - the client data tab with its sources and derived values;
  - search by employer;
  - the semantic tab, off with its reason;
  - segments: income at least US$2,000 gives 6 clients, and the Mercadeo
    purpose gives 0 (6 excluded for lack of consent);
  - the data-quality and portfolio panels;
  - the replica page, the catalogs and the document viewer.

  There were no console errors. Two cosmetic fixes followed: equal copies
  fold into one row, and employment status shows in Spanish (web
  `de6fa5e`, `90a8426`).

**2026-11-12 headline (history): Plan 2 (LPDP / ARCO-POL, `LPD-1` to `LPD-13`) in production, built for a demo; applicant self-service removed.**

- **Owner decisions (2026-11-11/12).** Applicant self-service (`FUN-11`) leaves
  the product: its code is gone from web (`7ea00a0`) and ai-orchestrator
  (`77fd914`), and its `intake_*` tables and functions stay in the database,
  dormant and service-only. The consent link and the rights portal stay.
  Consent enforcement is a per-tenant switch, on in `seguros` and `medico`,
  stamped on each application at creation, so the 22 existing applications
  keep working. MFA stays optional. No migration publishes a permanent text:
  the privacy notice and the staff confidentiality commitment are drafts until
  an admin publishes them.
- **Promoted** in deploy order: docs `08d1f4d`, db `09c3e01`, grading-engine
  `cc04cbd` (unchanged), ai-orchestrator `6a5b1b0`, web `ebdf842` (then
  `139f413` after the walk below). To roll
  back, the previous `main`s are docs `fd77dd5`, db `3b27cc0`,
  ai-orchestrator `6646d27`, web `a075a84` — but the orchestrator must not run
  ahead of the database's `processing_gate()`, and the database has no
  rollback for the five migrations.
- **Migrations**, ledger 36 → 41: `privacy_inventory_consent`,
  `privacy_state_requests`, `privacy_execution_security`,
  `privacy_review_fixes`, `staff_confidentiality_draft`
  (`20261111000000` … `000400`). Procedure:
  - **Dev first.** All five went to the new `qualifier-dev` project
    (`vtcrbrajexbsberrqwvo`, ledger 54), each after a rolled-back rehearsal
    with its suites. Two test bugs surfaced on real Postgres and were fixed
    (db `817ee29`, `09c3e01`); no migration bug.
  - **Production baseline:** its fingerprint equalled the PGlite replay of the
    migrations before Plan 2 in every category (NOT NULL constraints excluded,
    which PGlite stores as rows).
  - **Rehearsal** on production, rolled back: A–E clean and 14 suites green
    (consent 125, requests 226, execution 224, review fixes 65, staff draft 22,
    write_authorization 38, rls_isolation 31, anon_surface 8, list_views 17,
    document_acceptance 137, document_types 61, intake 97, admin_deletion 28,
    client_audit 8). Then `apply_migration` with md5 guards.
  - **After:** enforcement set in both tenants, 12 purposes each, staff texts
    `draft`, no notice published, `processing_gate()` allows all 22 existing
    applications, no Plan 2 function executable by `anon`. Advisors: nothing
    new beyond the "signed-in users can execute SECURITY DEFINER" class (64 of
    107 are Plan 2 staff RPCs, by design).
- **Live:** the orchestrator restarted with the embedded worker; its boot sweep
  found nothing stranded and the new `privacy.retention` run (with
  `privacy_daily`) finished with zero candidates, no errors. Web serves
  `/privacidad/medico` ("todavía no ha publicado su aviso", correct: nothing
  published), the rights portal with its eight rights, `/privacy` behind
  sign-in, and the old `/s/...` links as 404.
- **Checked before deploy:** 1470 pgTAP assertions in 26 suites (PGlite);
  web 397 unit tests, typecheck, lint, build; ai-orchestrator 578 tests. A
  security review found seven defects (one high: "contact on file" identity
  verification never compared against the contact on file) and all were fixed
  (db migration D, web `ebdf842`, ai-orchestrator `6a5b1b0`). A cross-check of
  ~155 `.rpc()` calls against the SQL signatures found one bug (fixed).
- **Walked signed in, locally (2026-11-12, after the deploy).** A harness
  (scratchpad `ui-harness2/`) put the real schema — every migration, RLS,
  grants and functions — in PGlite behind a PostgREST subset with test
  sessions, and `next dev` on localhost (every outbound connection but
  loopback refused). Every Plan 2 screen was used as tenant admin,
  underwriter, agent and superadmin, plus the consent link (identity, code,
  notice, per-purpose decisions, drawn signature) and the rights portal
  (request, code, follow-up, report download), with no SQL or console
  errors. It found 14 defects, fixed in web `3b46c0c` and `139f413` and
  re-walked. The one that mattered: an auto-matched client showed as linked
  to a request, so a cancellation could be resolved with no subject and its
  erasure could never run. Not covered there: Storage policies (the harness
  does not emulate them) and the orchestrator (a stub).
- **Migration F** (`20261111000500_incident_consequences`, ledger
  `incident_consequences`, production 41 → 42, dev 54 → 55, each after a
  green rolled-back rehearsal): `security_incidents.consequences`, so the
  Art. 25 notice states the possible consequences instead of a placeholder.
  db `bf445aa`, web `81b2785`, both promoted.
- **Walked signed in on the deployed site (2026-11-12, owner's session).** All
  14 Privacidad screens, the client consent and processing-state panels and the
  application consent strip loaded with real data, no console or request
  errors. An application from before enforcement correctly says it is
  processed anyway.
- **Owner decision (2026-11-12): ready for the presentation.** Until real data
  arrives, the owner defers Resend, Turnstile, publishing the notice and the
  staff text, leaked-password protection (paid plan) and the legal review.
  Anonymous sign-ins are now off (the advisor no longer flags them). Pick
  these up before any real data:
  - The consent link and the rights portal cannot complete in production:
    Turnstile and Resend are not configured on `qualifier-web`, so they fail
    closed (`captcha_unavailable`, `mail_unavailable`), and no notice is
    published.
  - Owner checklist (LPD-0), run with `scripts/plan2-owner-checklist.sh`:
    rotate the DB password, leaked-password protection on, Site URL, delete
    `render-blocks.env`, paid plan, Turnstile + Resend, publish the notice
    (anonymous sign-ins: done). Details in
    `plans/02-cumplimiento-lpdp-arco-pol.md` § "Estado de implementación".

**Previous headline (2026-11-08, ~16:30 UTC): Plan 1 `DOC-2` to `DOC-9` in production.**

- **Promoted:** each `main` was fast-forwarded to `develop` in deploy order:
  db `3b27cc0`, grading-engine `cc04cbd`, ai-orchestrator `6646d27`, web
  `847f9f8`, docs `5955c22`. The pins here record them. To roll back, the
  previous `main`s are db `2f1938d`, grading-engine `9a6a746`,
  ai-orchestrator `a7d77ae`, web `487d529`, docs `f4bd47b`.
- **The migration** `20261108000000_document_acceptance` is ledger row
  `20261108161005 document_acceptance`. The procedure was the one from the
  previous round:
  - **Baseline:** production equalled the local build up to `20261107000300`
    in every fingerprint category.
  - **Staging:** a comment-stripped copy, proven to build the identical schema,
    was staged in 18 chunks, each checked by md5.
  - **Rehearsal:** one block that rolls back. The migration applied on
    production data and views were unchanged. No SECURITY DEFINER function is
    executable by `anon`, and no `intake_*` function by a user role. Each tenant
    has 11 types and there are 18 templates. A staff upload and the deployed
    orchestrator's writes still work, and a browser's `acceptance` is dropped.
    The suites passed 341 of 341: document_acceptance 137, document_types 61,
    intake 97, write_authorization 38, anon_surface 8.
  - **One test fix on the way** (db `3b27cc0`): the acceptance suite tried to
    give the real `storage.objects` the CI stub's shape. It now does that only
    on the stub.
  - **Apply and verify:** `apply_migration` ran with an md5 guard. Production
    now equals the local build of all 34 migrations in every category: 158
    functions, 96 indexes, 39 policies, 31 relations, 25 triggers and 207
    constraints. The ledger's `statements` holds the SQL that ran, `_staging`
    is dropped, and the advisors show nothing new beyond the two intended
    signed-in RPCs and the new indexes not used yet.
- **Live** (see the checks below): grading-engine serves `/documents/evaluate`
  (401 without the token), and ai-orchestrator restarted with the embedded
  worker, its first sweep found nothing stranded, and it logged no errors.
- **Judged live, end to end.** Two QA documents in seguros (applications in
  manual review, nothing waiting to score) were marked `pending` through
  `record_document_acceptance()`, keeping their status. The deployed sweep
  picked them up at 16:20 UTC (`acceptance: 2, reevaluated: 2`, no error in
  any service), and the deployed grading-engine judged each one against version
  1 of its type, from its stored reading and with no model call:
  - `11a0269e` (clean proof of income): `accepted`, still `extracted`;
  - `54ca269a` (one tamper flag): `flagged` by `sys_tamper` alone, still
    `flagged`.

  Both are exactly what `statusForExtraction()` gave them.
- **Applicant side, without a session:**
  - `intake_link_public('ingreso-auto')` now gives each required document its
    label, role, inherited age limit (proof of income 90 days) and the
    instruction and example keys, plus `identity_document` (DUI).
  - The public page renders with no console error. Its HTML carries
    `has_example`, never `example_path` or the tenant's id.
  - That link answers "todavía no recibe solicitudes en línea" because seguros
    has no published consent text (`no_consent`). That is the data, not this
    deploy.
- **Signed-in flows, at the database, as real staff of seguros.** These ran in
  one block that rolled back, and nothing persisted:
  - **The type editor's calls:** a type created from the bank statement
    template, a draft saved with a visual check and a rule, and version 1
    published. A repeated key was refused (`document_type_key_taken`).
  - **«Aceptar de todos modos» on the QA document flagged by `sys_tamper`:**
    it became effective `accepted` and `extracted`; withdrawing the acceptance
    returned it to `flagged`. A rule that had passed was refused
    (`rule_not_failed`).
- **The signed-in screens, rendered.** web ran locally in dev mode against a
  fake Supabase with seed-like data, and against the real grading-engine run
  locally. Every process was held to localhost: the only outbound attempts were
  Next's npm update checks, which a guard blocked. The harness is in the
  session scratchpad, not committed. What was seen, signed in as an
  administrator:
  - the type list;
  - the editor's Campos, Aceptación and Versiones tabs. «Validar» was answered
    by the real engine, and the generated `sys_*` rules and the diff show;
  - an application's acceptance panel. «Aceptar de todos modos» with a reason
    turned the document «Extraído» and «Cumple los requisitos», queued a
    rescore, and offered «Retirar aceptación»;
  - the same judgement on the case view.

  No new screen logged an error. One double period after the time of an
  accepted exception was fixed (web `c2aae20`, deployed).
- **First reading with the model in production, schema-guided (21:06 UTC).**
  Two synthetic QA documents in seguros were set back to `uploaded`, as
  «Re-extraer» would, and audited as `document.reextraction_requested`:
  - the constancia `54ca269a` and the DUI `d054f6ca` of Karla Hernández, the
    invented person in `qa/2026-10-02`;
  - their application is in manual review, with no rescore asked for.

  The deployed sweep read them with `claude-sonnet-5-5` (US$0.0174 and
  US$0.0141). The fields now come under the type's keys: `monthly_income`,
  `employer`, `job_title` and `issue_date` first, and `national_id` where the
  old reading said `dui_number`. The deployed grading-engine judged both
  `accepted`, both are `extracted` with their type version, and no service
  logged an error or warning.
- **The test bench from the editor, signed in (local harness).** The tab and
  web's route were exercised with the synthetic constancia, set on the file
  input by script, with the orchestrator canned and the real grading-engine
  judging: acceptance, cost, model, tokens, engine version and the rule table
  all show. The table now reads «Mensaje si no se cumple» and dims a passed
  rule's message (web `111831f`, deployed).
- **The applicant's self-service, rendered (local harness, personal link, no
  captcha).** The synthetic client was verified by date of birth and walked
  through Tus datos and Preguntas to Documentos:
  - the DUI read «Listo»;
  - the proof of income showed «Emitido hace menos de 90 días», the type's
    instructions, «Ver un ejemplo» with the image, and the visible problem
    «Sube una constancia firmada y sellada por tu empresa»;
  - a seeded `sys_tamper` entry appeared nowhere on the page.

  The walk also found that the example route answered with a signed Storage
  URL whose path carried the tenant's id and the file's name. It now returns
  the image as a `data:` URL, and the response holds neither (web `a075a84`,
  docs `fd77dd5`, deployed).
- **Still not seen:**
  - **The test bench reading a sample with the real model.** Its extraction
    and judgement are the path proven in production above, and its tab and
    route are seen locally. What is unseen is the deployed route's own call to
    the model. ai-orchestrator's
    own `runDocumentTypeTest()` was run locally against the fake Supabase and
    the real grading-engine, with the QA constancia (`qa/2026-10-02`). It got
    through the draft's validation, the sample's limits and the spend cap, and
    stopped at Anthropic.
    - **The `ANTHROPIC_API_KEY` in `qualifier-secrets.env.txt` is rejected**
      (401 "invalid x-api-key"). It is well-formed, so it was rotated or
      revoked. The deployed key lives on Render. Replace the local one before
      any local model run.
  - **A self-service upload in production.** Neither tenant has a published
    consent text, so no intake link (product or personal) opens there. A
    product link also passes a CAPTCHA.
- **What it contains:**
  - the document type editor;
  - acceptance evaluated per type by grading-engine, stored in
    `documents.acceptance`, with analyst overrides;
  - schema-guided extraction with visual checks;
  - max-age inheritance (`effective_requirements()`);
  - self-service instructions, example images and visible problems;
  - identity by `role`;
  - the editor's test bench and the AI field proposal.

  The repos involved:
  - db: migration `20261108000000_document_acceptance.sql`, suite
    `document_acceptance_test.sql` (137);
  - grading-engine 0.2.0: `/documents/evaluate`, `/documents/validate`;
  - ai-orchestrator: `/documents/:id/evaluate`, `/document-types/test`,
    `/document-types/propose`;
  - web: `/settings/document-types`;
  - docs.

  The details and where it departs from the design are in
  `plans/01-tipos-de-documento.md` § "Avance".
- **Verified locally only:**
  - db: the CI replay in PGlite (Postgres 18; production is 17.6), 21 suites,
    808 assertions, also applied over an already-seeded database;
  - grading-engine: 299 tests, typecheck and build;
  - ai-orchestrator: 495 tests, typecheck and build;
  - web: 372 tests, typecheck, lint and the production build.

  Plus a cross-repo check with no mock in between (scripts in the session
  scratchpad, not committed). The real grading-engine, run locally, answered
  ai-orchestrator's own context builder and client. Its answers then went
  through the migration's `record_document_acceptance()` and
  `accept_document_check()` in the PGlite replay, covering eight steps in
  order:
  - clean;
  - tampered;
  - an override;
  - re-evaluation keeping it;
  - unreadable dropping it;
  - a product reject that cannot be overridden;
  - pending;
  - clean again.

  The seeded definition in the database matched web's fixture byte for byte.
  Nothing ran against production, the model, or in a browser. A read-only
  security review from the attacker's side found one medium and three low
  issues, all fixed and covered by tests:
  - a tamper rejection visible to the applicant;
  - an override undoing a rejection;
  - file limits checked only against what the browser declared;
  - DUI checks dropped when the identity role moved.
- **Deploy order when it ships:** db (rehearse in a rolled-back block, then
  `apply_migration`, as before) → grading-engine → ai-orchestrator → web. Each
  step works with the one before: the old orchestrator never writes
  `acceptance`, so its documents read as before. ai-orchestrator must **not**
  go before grading-engine. Without `/documents/evaluate`, every judgement
  would be `pending`, and every application with a required document would go
  to manual review.

**Previous headline (2026-11-08, ~00:50 UTC).**

- **Round 2 of the 2026-11-05 audit and DOC-1 are in production.** The four
  migrations went first, then all five repos were promoted (db `2f1938d`,
  grading-engine `9a6a746`, ai-orchestrator `a7d77ae`, web `487d529`, docs
  `f4bd47b`); `develop` equals `main` in each. The previous `main`s, to roll
  back to: db `93c656f`, grading-engine `89dcaca`, ai-orchestrator `7129635`,
  web `8390cf7`, docs `14d0e69`.
  - Ledger: `20261108004218 pipeline_integrity`, `…004224 analyst_tools`,
    `…004229 intake_demo_security`, `…004234 document_types`. Each was applied
    from a staged copy whose MD5 matched the file stripped of full-line comments
    outside function bodies (bodies untouched; equivalence proven by a schema
    fingerprint of both builds). The staging schema is dropped, and each
    ledger row's `statements` now holds the SQL that ran.
  - Baseline first: production's schema matched a local build up to
    `20261106000000` in every table, column, privilege, policy, index, trigger
    and constraint. One function differed, `submit_application`, by whitespace and
    comments only (an earlier apply stripped them); `pipeline_integrity`
    replaces it.
  - Rehearsed on production in one rolled-back block: the four migrations, then
    the four new suites (pipeline_integrity 50, analyst_tools 43,
    intake_demo_security 63, document_types 61: 217 of 217), views unchanged, no
    SECURITY DEFINER function executable by `anon`, and a staff upload as the
    deployed web makes it (`national_id` accepted, an unknown type refused by
    the new FK) in both tenants.
  - After applying: production's schema fingerprint equals a local build of
    all 33 migrations, category by category. `seguros`, `medico` and the
    templates hold 11 published types each; no document lacks its type. No
    tenant has `mfa_required`, so nothing the deployed web does is gated yet.
  - Between the apply and the push (~10 minutes) the old orchestrator read the
    new sweep kinds (`orphan`, `stalled`, `hash`) and ignored them, as checked
    against its code beforehand.
- **Checked live after the deploy (00:45–00:49 UTC):**
  - Render reports all three services `live` on the new commits; `/health`
    answers ok on grading-engine and the orchestrator; web serves the Spanish
    build ("Iniciar sesión"). No error-level log line on any of the three.
  - The orchestrator booted with `WORKER_MODE=embedded`. Its boot sweep closed
    médico N.º 6's orphan document (`2d…0028`, `rejected:file_missing`, one
    audit row), released the application, which was processed and routed to
    manual review for its missing documents (case `unassigned`, no model call),
    and hashed 14 documents. The next sweep found nothing stranded.
- **Not seen in a browser signed in**, so the catalogue load (DOC-1), the new
  editor, MFA screens and analyst tools have not been looked at live.

**Headline (2026-11-06, ~06:55 UTC)** (history).

- **The 2026-11-05 audit's S and M fixes are in production**
  ([`audit/2026-11-05-five-viewpoints-audit.md`](audit/2026-11-05-five-viewpoints-audit.md)
  § 0). The migration went first:
  - It was rehearsed on production inside one transaction that raised at the end, so nothing stayed. 82 of 82 pgTAP assertions passed, and so did the compatibility checks for the web build then live:
    - the 3-argument `decide_case` still worked;
    - draft playbooks could still be inserted and edited;
    - a direct `status` update was refused.
  - Then it was applied: ledger `20261106063843 audit_fixes`.
  - Then all five repos were promoted (db `93c656f`, grading-engine `89dcaca`, ai-orchestrator `7129635`, web `8390cf7`, docs `14d0e69`).
  - The previous `main`s, to roll back to: db `5b5f668`, grading-engine `f6a4ee5`, ai-orchestrator `2f536ae`, web `7839c37`, docs `321431f`.
- **Checked live after the deploy:**
  - `case_decisions` holds the 5 past decisions, backfilled from `audit_log`.
  - No SECURITY DEFINER function is executable by `anon`, the sweep is service_role only, and the vestigial storage policy is gone.
  - The orchestrator's boot sweep found the three stuck submissions. N.º 11 and seguros N.º 6 became blocked manual-review cases (no documents), with no model call.
  - **médico N.º 6 is still stuck.** Its only document (`2d…0028`) has been `uploaded` with no file in Storage since 2026-10-29. The sweep only re-reads documents whose file exists, and processing defers while a document is unread. Being fixed on `develop` (round 2).
  - A rescore of `5553aece…` (seguros, QA) at 06:50 stored:
    - `engine`: grading-engine `0.1.0+89dcaca`, `claude-sonnet-5-5` for both agents, `rubric-v1`;
    - `inputs`: source, confidence and document id for each value;
    - an AI score of 90 from the rubric, next to the model's 88.
  - That same rescore shows the production playbooks still need republishing. VIDA-STD v1 still ranks by income size: a US$700 earner gets a rule score of 24.5 and lands in Subestándar. The rewritten sample definitions are only in the seed.
  - `/s/ingreso-auto` serves the new closed state and per-insurer metadata. grading-engine `/health` answers ok.
- **Not seen in a browser signed in.** The staff screens need the owner to sign in in the browser pane.
- **Round 2 is committed on `develop` (db `2d3d58f`, grading-engine `9a6a746`, ai-orchestrator `a7d77ae`, web `063f036`, docs `a61f930`), not pushed and not deployed.** It covers the findings round 1 left open (audit § 0, "Round 2"):
  - V-7, the editor rebuild with backtest and copilot;
  - bots 4–9;
  - V-15;
  - `required_if`;
  - removing `/analyze`;
  - staff MFA;
  - orphaned documents;
  - the round-1 caveats.

  Verified by grading-engine 70, ai-orchestrator 393 and web 236 tests, web's build, and a PGlite replay of 19 suites (610 assertions). Its three migrations (`20261107000000`, `…0100`, `…0200`) need the same rehearse-then-apply as round 1.

**Headline (2026-11-04, ~05:05 UTC)** (history).

- **Three more requests are in production.** The migration went first:
  `20261104000000` (ledger `document_age_acceptance_checklists`), after its 21
  pgTAP assertions passed on production in a transaction that rolled itself
  back. Then db `5b5f668`, docs `321431f`, ai-orchestrator `2f536ae` and web
  `7839c37` were promoted. The previous `main`s are the four listed below.
- **An analyst can accept an outdated document.** Application 14 (seguros)
  was sent with a constancia issued 2026-07-24, 103 days old against a 90-day
  limit. Sending was never blocked; scoring was, with no way forward but a new
  letter. Now a draft warns and can still be sent, and an underwriter or
  administrator can press "Aceptar de todos modos" on the requirement list,
  give a reason, and the application is rescored with it
  (`accept_document_age()`). The score says so
  (`rationale.accepted_outdated_documents`), and `auto_decide_case()` refuses
  it. **Application 14 has not been accepted yet**; it is waiting for the user
  to do it from its page.
- **The distrito is found by typing it**, and fills its municipio and
  departamento.
- **Declared conditions are a checklist** (`multiselect`, a new form field
  type; `count`, a new playbook transform). Production's GMM-IND asks it that
  way and scores with **playbook version 2** (`...0037`, published from v1
  plus `"transform": "count"`; v1 is archived). The seed instead edits
  playbook `...0032` in place, so a fresh database has one version where
  production has two.
- **Not seen signed in**, again: verified by web's 156 tests, tsc, eslint and
  build, the orchestrator's 234 tests, grading-engine's 58, and the pgTAP run.

**Headline (2026-11-03, evening)** (history).

- **The ten requests of 01:45 are in production since ~21:45 UTC.** The
  migration went first: `20261103000000` (ledger `20261103214202
  products_detail_deletion_client_sources`), after a rehearsal on production
  that rolled itself back (24 of its 28 pgTAP assertions; the other 4 ran the
  same way after it was applied). Then four repos were promoted: db
  `486b0ef`, docs `0eae2df`, ai-orchestrator `e2decf7`, web `277571f`. The
  previous `main`s were db `a6ff60e`, docs `14bacb2`, ai-orchestrator
  `a87935a`, web `12f268d`; the migration has no down.
- **The DUI error at 01:45 was the code's message, not the photo.** The
  orchestrator had been asleep since 04:49 UTC and never received the read;
  web turned whatever answered in its place into "una foto más nítida",
  without a log. The route now retries once while the service wakes, logs
  every refusal, and says what happened; the new-application form wakes the
  orchestrator when it opens (`/api/ops/warm`). The orchestrator read the QA
  DUI, both sides, correctly in 7 s that night.
- **What shipped:**
  - registering a client, an application or a product opens its own page
    (`/clients/new`, `/applications/new`, `/products/new`);
  - every editable phone has a country-code picker, and a client a country
    picker; in El Salvador the official departamento, municipio (44) and
    distrito (262) are lists, and a DUI's distrito finds its municipio;
  - products are described in full: code, sums, ages, term, premium,
    waiting period, coverages, exclusions;
  - administrators delete clients, applications, cases, products and staff
    accounts, through functions that decide and record it; an agent can no
    longer delete a client from the browser, which `clients_write` allowed;
  - a newer constancia or DUI updates the client (salary, employer,
    occupation, address, estado familiar), and the client page says which
    document set each value (`clients.field_sources`);
  - a guided start for a product's first playbook;
  - seguros has six more products, each with a published playbook (VIDA-T20,
    GMM-IND, AUTO-AMP, HOGAR, DEUDA-PER, AP-IND), and its standard life plan
    has its details. Loaded into production from the seed's own statements.
- **Not seen signed in.** Verified by tsc, eslint, 147 web and 226
  orchestrator tests, the web production build, grading-engine evaluating
  every new playbook, and the deploys going live. Nobody has opened the new
  screens with a session yet, and no document has updated a client live.
- **Found in passing:** seguros' `grading_scale.labels` are `A`–`D`, but its
  seeded playbooks map tiers to "Preferente"…"Rechazo", which the editor's
  check calls an error. The new catalogue follows the existing playbook; the
  guided start follows the tenant's scale. One of the two should change.

**Headline (2026-11-03, early morning)** (history).

- **Everything on `develop` is in production since 2026-11-03 ~01:23 UTC.**
  The migration went first: `20261102000000` (ledger `20261103012022
  submit_decide_deadlines_numbers`), after a rehearsal on production that
  rolled itself back. Then all five repos were promoted: docs `14bacb2`, db
  `a6ff60e`, grading-engine `09a0c19`, ai-orchestrator `1f4a206`, web
  `db29c85`. Render had each service live within 70 s. To roll back, the
  previous `main`s were docs `5e518b8`, db `278fdb7`, grading-engine `982f9a5`,
  ai-orchestrator `8503b9e` and web `8e43aee`, and the migration has no down.
- **The default model is Sonnet 5.5**, four weeks before Sonnet 4.5 retires
  (2026-11-30). The blueprint sync set `MODEL_DEFAULT=claude-sonnet-5-5`. The
  first live call was a DUI read of the QA fixture through the new
  `/identity/read`: every field right, one call, no refusal, 3,009 in and 734
  out tokens, US$0.0134, 5.4 s. **The full pipeline (consistency, narrator,
  scoring) has not run on 5.5 yet**; the next submitted application is the
  first.
- **What shipped**, from the 2026-11-02 review and requests:
  - an application cannot be sent without its required documents;
  - deciding with no score, or against the recommendation, needs a note;
  - a case waiting on the applicant has its deadline paused;
  - applications are numbered per tenant ("N.º 7");
  - a new application starts from the client's DUI, or registers the client
    in the form, and takes every document before it is saved or sent;
  - a document with no file says so.
  Also the 2026-10-30 work: applicant notifications and draft purging without
  waiting for the clock, zod 4, and CI on actions v5.
- **Tested end to end, signed in as admin-seguros, at ~01:38 UTC.** Seguros
  N.º 12 (Karla, the QA fixtures) went through the new form: DUI read, client
  found, documents chosen, sent. On Sonnet 5.5 it took 4 s per document read,
  scoring 74 s after sending (45 of them waking the grading-engine), and
  US$0.059 across four calls. It found four problems, fixed and deployed by
  01:51 (ai-orchestrator `156cfc1`, grading-engine `f6a4ee5`, web
  `fb6909b`):
  - Sonnet 5.5 echoed a document id as `<uuid>Fecha`, because adjacent prompt
    text blocks run together. The consistency agent called it a fraud signal.
    Blocks are now separated, and the row's id overrides the echo. A re-read
    stored the right id.
  - The tier was read from the unrounded score: 84.5 came back as 85 in tier B
    under an "A from 85" playbook. The score is now one decimal and tiered as
    shown. The deployed engine returns 84.5, tier B.
  - In the form, the document type picker stayed on "DUI" after the card was
    read, and there was a space before a period. Both fixed and seen live.
- **The QA PDFs are signed and stamped now** (`qa/2026-10-02/make_fixtures.py`).
  Sonnet 5.5 had flagged the constancia's blank signature line on a re-read
  ("no se observa firma ni sello de la empresa"), so N.º 12's constancia is
  `flagged` and a rescore of N.º 12 would block it. **N.º 13** used the
  regenerated constancia at 02:01 UTC: both documents clean, no fraud signal,
  rules 80 + AI 97 = **85.1 "Preferente", approve**. It was 29 s from sending
  to case, cost US$0.055, and is the clean seguros case to show.
- **The staff UI was reshaped on request and deployed at ~02:57 UTC** (web
  `fcac105`, with `107441a`), and was seen live as admin-seguros:
  - The menu has **Productos** and **Configuración** in place of
    "Empresas", which is now the superadmin's only. A product's page holds
    its form, its playbook and the documents it requires (marked Obligatorio
    or Opcional), automatic approval, and its links. Configuración holds the
    brand, own domain and privacy notice.
  - The new-application form starts from the product. The client is a new
    one by default; a search (accent-blind: "hernandez" finds "Hernández")
    and «Subir DUI» find a registered one. The documents are a list of
    required and optional rows.
- **Still open:**
  - The database password was printed into a working session on 2026-11-02:
    rotate it, then update `DATABASE_URL` on the orchestrator and the
    secrets file.
  - Supabase Auth: anonymous sign-ins on, leaked-password protection off.
  - Demo data: run `demo/refresh-demo-dates.sql` before a demo. None of the
    28 seeded documents has a file in Storage, so they cannot be opened. The
    seeded clients' DUIs fail the check digit.

**Headline of 2026-10-30** (history).

- **Self-service intake (`FUN-11`), all five phases, is in production since
  2026-10-29.** The migrations went first, after a rehearsal on production
  that rolled itself back. Then all five repos were promoted, and Render
  deployed grading-engine, ai-orchestrator and web without errors.
- **Nothing applicant-facing runs yet.** No consent text is published and no
  intake link exists, and Resend, Turnstile and ClamAV are not configured.
  Every phase-4 part is off until configured, and automatic approval cannot
  switch on before a product has 100 human decisions to measure.
- **Checked from outside only, on 2026-10-30.** The session that deployed
  could not reach `onrender.com`, so a later session probed it without
  signing in: both services answer `/health` with 200, `web` serves the
  Spanish Tramiq build ("Verificando tu sesión…"), and an unknown `/s/` link
  shows "Enlace no encontrado". Nobody has signed in since the deploy. A
  signed-in pass of the new staff screens is still owed: custom domain,
  embedding sites, the automatic-approval panel.
- **Supabase Auth settings to change:** anonymous sign-ins are still enabled,
  and leaked-password protection is off (§ 2).
- **Demo data is ageing out.** The seeded seguros proofs of income cross the
  playbook's 90-day limit around 2026-10-28 to 11-04. From then, a rescore
  blocks those applications as stale (2026-09-13 entry below).
- **The free tier sleeps the orchestrator after 15 idle minutes, and its
  scheduled jobs sleep with it** (§ 2, 2026-10-29). The 2026-10-30 work wakes it
  to send applicant notifications after a decision, and purges abandoned drafts
  when it wakes. That work, with zod 4 and CI on actions v5, was merged into
  `develop` in all five repos on 2026-11-02. It is **not deployed**: Render
  builds `main`.

**As of 2026-09-14** (history). Measured against the running services, the
production database (read only) and the repos. § 1 and § 3 were re-checked on
2026-09-13 around 20:10 UTC, after the `web` deploy. The rest of § 2 is from
2026-09-12 07:34–07:44 UTC.

The 2026-09-11 audit's fixes are live. Every critical, high and
medium finding is closed in production: the write side of the database is
authorised, the case screen's decisions go through role-checked functions that
record what happened, the playbook-test route no longer answers strangers, and
`web` runs Next.js 16.3.5 instead of a version with two critical RCE advisories.

What has still never happened is a real pipeline run (`BLK-5`), and now also a
signed-in pass through the new decision path. Nothing has exercised the RPCs
with a real session.

**2026-09-13.** The 2026-09-12 web audit's work is live: its three migrations
went to the database first (§ 2), then `develop` was promoted in `db` and `web`.
Live now: staff management (deactivation, role and tenant changes, invitation
and recovery links), a searchable and paged case queue, polling while the
pipeline runs, confirmations before one-way actions, audit history on every
record, toasts, and `web`'s first unit tests.

**Later on 2026-09-13: the first signed-in QA, and the pipeline was down.** With
the seven `@claude.test` accounts created, a pass as superadmin and
agent-seguros put one fictitious application through the real pipeline. It never
scored: **every `application.process` job had failed since `20260911000000`
reached production on 2026-09-12.** That migration's same-tenant composite
foreign keys made the orchestrator's only PostgREST embed, `products(sla_hours)`,
ambiguous. The fix, `ai-orchestrator` `5985020`, names the key, adds a test that
refuses unnamed embeds, and is live and confirmed: the QA application's retry
completed, was recorded as blocked, and opened a case with a 48 h deadline. Nothing
else had been submitted in that window.

After that QA (details in § 6):
- `web` `3170a77`, the fixes for the QA's UI findings, is **live** (22:23 UTC).
- **Extraction field names**: the playbooks' document keys now reach the
  extraction agent, `ai-orchestrator` `a1908f2`, **live** (22:34 UTC) and verified.
  Re-extracting the QA income letter returned `monthly_income: 2000` as a number,
  where the first run had `monthly_salary: "US$ 2,000.00"`. The audit entry
  records `expected_keys: ["monthly_income"]`, missing none. Documents extracted
  before this still carry the old keys, so re-extract them before rescoring.
- **`required_documents[].max_age_days` is enforced** (`ai-orchestrator` `22183a9`,
  `web` `a4e6ee2`, `db` `f818c0b`, `docs` `42e7439`, promoted 2026-09-13).
  - It had been declared, editable and read by nothing.
  - Age now counts from the issue date read from the document (the new
    `ExtractionResult.issue_date`, YYYY-MM-DD), and the newest clean document must
    be within the limit.
  - It fails closed: an unreadable, ambiguous or future issue date doesn't meet
    a limit. The application is blocked like one missing a document, and the
    rationale says which documents are stale or undated.
  - The `web` checklist mirrors the rule.
  - **Production data:** the 15 seeded dated documents (6 proof of income, 9
    médico lab results and medical reports) got a backfilled `issue_date` of
    their upload date minus 12, 20 and 30 days. The médico rows had no date and
    would have blocked on rescore. The seeded proofs of income will pass
    seguros' 90 days on about 2026-10-28 to 11-04, and from then a rescore blocks
    them as stale. That's the rule working on demo data that ages.
  - The seed now computes these dates from `now()`.
  - Verified by unit tests and a PGlite replay of `db` CI with the new seed
    (127/127). Not yet exercised end to end: that needs a real, unflagged
    document.

**2026-09-14: the smaller gaps after the web audit's fixes.** Two migrations
went to the database first (§ 2), then `db` `4725a9d`, `ai-orchestrator`
`fb21538`, `web` `adf7ae7` and `docs` `47b178e` were promoted.
- **Document preview.** "Ver" shows the file beside its extracted fields (PDF in
  an iframe, photo as an image), through the same audited signed-URL route.
- **Uploads** take drag-and-drop and show a percentage per file (XMLHttpRequest,
  the same request storage-js makes).
- **Lists page in the database.** `/clients` and `/applications` read the
  security_invoker views `client_list` and `application_list` instead of
  downloading tables. The case queue and client page read `latest_scores`.
  `/applications` sorts by client, product, status, score and date, has bulk
  "send drafts" and "rescore", and both lists export CSV (formula cells
  neutralised).
- **No raw database English** reaches a toast or banner (`lib/db-errors.ts`).
- **Field labels.** The extraction agent returns a Spanish `label` beside each
  English key, for keys nobody could list in advance.
- **Sign-ins are recorded.** Triggers on `auth.sessions` write `auth.signed_in`
  / `auth.session_ended` and `profiles.last_signed_in_at`, shown as "Último
  acceso" in the staff list.
- **Credential routes are rate-limited** (`/api/users`, recovery links).
- **CSP is enforced**, not report-only (M7).

Verified: 157 pgTAP assertions in the PGlite replay (30 new), 104 orchestrator
tests, 76 web tests, the web build, and mutation checks on the new safeguards.
In production, a rolled-back rehearsal of Supabase Auth's session insert and
delete wrote the expected rows, and each tenant's agent saw only its own rows
through the views. **Not yet used in a browser signed in.**

**2026-09-15: the demo portfolio was prepared.** Two changes to production
data, no code:
- **The QA run was removed.** The 2026-09-13 fictitious client, its application
  and the documents, score and case that hung off it are gone. Its `audit_log`
  rows stay — the table is append-only by design, and they are reachable only
  from screens that no longer exist — as do its three `ai_usage` rows, now with
  a null `application_id`, which are the only model cost ever measured. Its two
  files are still in the `documents` bucket: `storage.protect_delete` refuses a
  direct delete, so removing them needs the Storage API.
- **The seeded timestamps were moved forward** by the time since the seed ran
  (2026-08-18), which is what the seed itself computes from `now()`. Every open
  case deadline had been four weeks past, so the queue was entirely overdue.
  Now: 4 overdue, 3 due within two days, applications from 3 hours to 10 days
  old. Documents' `issue_date` moved with their upload, so every one is still
  inside its playbook's `max_age_days` — rescoring a seeded application will not
  block. `audit_log` was **not** shifted, so the history panels show the seeded
  entries at their real August timestamps.

**2026-10-16: found paused, restored, and audited for sale.** The Supabase
project was `INACTIVE`, so the live app was down and the orchestrator could not
boot. It was restored from the connector and came back `ACTIVE_HEALTHY` with its
data intact; all three services then answered 200. Nothing has been used since
2026-09-13 (last sign-in and last audit row). The `qa/2026-10-02/` `BLK-5` run
never reached production, and 5 seeded cases are overdue again. Nothing has been
deployed since 2026-09-14. Full findings, what is missing to sell, and the
website plan: [`audit/2026-10-16-sales-readiness.md`](audit/2026-10-16-sales-readiness.md).

**2026-10-17: renamed Tramiq, live.** `web` `2c25b8e` (new wordmark and icon,
the name in titles, loading and error screens) was promoted and went live about
75 s after the push. Checked from outside: the sign-in page renders the logo,
`/icon.svg` serves `image/svg+xml`, and the console shows no errors. The demo
guide is in [`demo/DEMO.md`](demo/DEMO.md). The seeded dates were refreshed with
`demo/refresh-demo-dates.sql` at 03:55 UTC. The newest application is now 3 h
old, 4 open cases are overdue and 3 are on time, across both tenants, and issue
dates run from 2026-09-13 to 2026-10-04. `audit_log` is untouched (19 rows), and
the five triggers it disables inside the transaction are re-enabled. Re-run it
the day before a demo.

**2026-10-17: the Anthropic API key is invalid, so the AI pipeline cannot run.**
The `BLK-5` QA, signed in as `admin-seguros@claude.test`, got further than ever
through the UI:
- client registered;
- application `8d835edc` saved as a draft;
- DUI and constancia uploaded, the per-file progress bar reaching 100%;
- both `document.extract` jobs queued.

Both jobs then failed at the Claude call with `401 authentication_error: invalid
x-api-key` (`request_id` `req_011Cg7B3EyUFZnqdBpNiaMMy`). The key in
`qualifier-secrets.env.txt` also gets 401 from `/v1/models`. `/health/queue`
kept answering `ok`, because retrying jobs are not "ready", so it cannot see this
failure. A new key is needed on the orchestrator's Render service. Then retry
both documents and submit the application.

**Later on 2026-10-17: with a new key, the first full pipeline run in production.**
With the new key in place, both extractions completed on their scheduled retries.
- **Constancia:** `monthly_income: 2400` as a number under the playbook's key,
  and `issue_date 2026-09-28`.
- **Labels:** every field carries a Spanish `label`.
- **Score:** `application.process` completed. Rule score 80 (as expected), AI
  score 65, final 76: tier "Estándar", `manual_review`. The case opened
  unassigned, with a 48 h SLA.
- **Cost:** `ai_usage` has rows for all three agents (extraction ×2,
  consistency, risk_narrator): 9,611 input and 2,054 output tokens, about
  US$0.06 per application at Sonnet 4.5 list prices.

**Later still on 2026-10-17: every problem found was fixed, deployed and verified
live.**

- **Agents know today's date** (`ai-orchestrator` `5227491`). Rescored, the same
  application went from AI 65, final 76 "Estándar" to **AI 100, final 86
  "Preferente", approve**. There is no false signal, and the narrative now gets
  the applicant's age right: 37, where the old run said 35.
- **"Volver a puntuar" really rescores** (`ai-orchestrator` `4d650cf`, `web`
  `655acb2`). It used to resume on the existing score and write nothing.
- **`/health/queue` reports `failing` (503)** when a queue's recent attempts
  all failed, with `last_error` (`7bd2b7b`). A dead API key is now visible.
- **The anon key can no longer call `app_current_role()` or
  `current_tenant_id()`** (`db` `76b222f`, migration `signed_in_only_policies`).
  The 19 RLS policies that used them are scoped to `authenticated`. Rehearsed in
  a forced-rollback transaction (10 checks), then applied. The advisor's
  anon-execute warning is gone.
- **UI clarity pass** (`web` `c6f79e6`, `4d4f300`):
  - a glossary with hover and focus tooltips on every product term;
  - the case screen in decision order, with the decision panel up top;
  - the score explained as Reglas 80 × 70% + IA 100 × 30%;
  - relative deadlines;
  - the case queue's decision columns visible;
  - a decluttered applications list;
  - the playbook editor in Spanish, with stored keys unchanged.
  Checked live in the browser, including a tooltip.
- **The first real decision in production.** Signed in as
  `admin-seguros@claude.test`, the QA case was approved with a note. The case is
  `resolved`, the application `approved`, the comment authored by that account,
  and `audit_log` has `case.approved` with that actor. Six `ai_usage` rows:
  13,281 input and 2,731 output tokens across two scorings.

**Later on 2026-10-17: the médico run, end to end, and what it broke.** Signed in
as `admin-medico@claude.test`, with the `qa/2026-10-02/medico/` documents:
- Client `46cac06f` registered, application `20e885b6` saved as a draft, and the
  DUI, medical report and lab results uploaded and extracted cleanly
  (`glucose_mg_dl 98`, `condition_count 1`, `bmi 27.4`, issue dates read).
- **Scoring failed on every attempt** with a ZodError: the risk narrator
  returned `warnings` and `notes` as strings, not arrays. Fixed in
  `ai-orchestrator` `1d0509c`: the agents' four string lists accept a
  serialized array or a bulleted paragraph and normalize it. The tool schema
  shown to the model is unchanged.
- **The form would have flagged a non-smoker.** "Fumador" was free text, so
  `form_data.smoker` was the string `"No"`, and `applicant.smoker == false`
  fails on it. Fixed twice:
  - `ai-orchestrator` `d74bbba` reads a whole "Sí"/"No" answer as a boolean;
  - `web` `2eed56c` makes yes/no fields a Sí/No select, saves numbers and
    booleans typed, and labels `bmi` "IMC".
- **A deploy orphaned the retry.** The old instance took it 17 s before being
  replaced, and Render's 30 s drain was shorter than the job. pg-boss expired
  it 15 min later, but only after a request woke the orchestrator. The free
  tier had spun it down, because queue work is not traffic.
- **Scored on the fixed code** at 06:35 UTC:
  - rule score 70.875 (all 6 rules evaluated and passed), AI 98, final 80;
  - tier B "Riesgo moderado", `manual_review`, as this playbook maps 65–84;
  - one low-severity consistency note: the declared dependents are on no
    document.
- **Approved** with a note as `admin-medico@claude.test`. The case is
  `resolved`, the application `approved`, and `audit_log` has `case.approved`
  with that actor.
- **Cost:** 12 `ai_usage` rows, 31,175 input and 6,739 output tokens (about
  US$0.19). A clean run is 5 calls, about US$0.09. The three failed narrator
  attempts and their consistency calls were billed too.
- **UI fixes from reading the case** (`web` `714a739`, `8acfe6a`, `328f679`):
  - the clients and applications tables pad their columns, which had run
    together;
  - the rule trace shows "-15 si no cumple" instead of a bare -15 beside
    passing rules;
  - the consistency notes, stored and never shown before, are listed with
    their severity;
  - the rule score shows one decimal.

**Still open:**
- **Queue work does not keep the orchestrator awake.** On the free tier,
  a retry scheduled more than 15 minutes after the last request waits until
  someone opens the app. Warm the services before a demo (`demo/DEMO.md`),
  or move to `starter`.
- **The secrets file.** Its `ANTHROPIC_API_KEY` is still the dead one; Render
  has the new key.
- **Your dashboard settings:** anonymous sign-ins off, leaked-password
  protection on, Site URL.

**Defect found (fixed above):** the consistency agent raised a false fraud signal. It called
the constancia's issue date of 2026-09-28 "una fecha futura". The model does not
know today's date, and that pulled the AI score down. The agents' prompts need
the current date. Both tenants' runs and decisions are now done (above).

## 0. How we got here

- **2026-09-06** — this file said the Supabase project had been deleted and
  every pin was current. Both were wrong: the project was *paused*, and pins had
  only been compared with `main`, missing a `develop` 27 commits ahead.
- **2026-09-10** — project restored, Render's environment re-entered, `develop`
  promoted in all five repos.
- **2026-09-11** — dependency patches and a `db` CI fix; the whole project
  audited (§ 4).
- **2026-09-12** — the audit's critical, high and medium findings fixed,
  re-audited, and deployed. The migration went to the database first; `web` and
  `grading-engine` then failed to build twice on a lockfile problem (§ 5) before
  going live.
- **2026-09-13** — the web audit's three migrations applied to production, then
  `develop` promoted in `db` (3 commits) and `web` (15, ending with toasts).
  `web` built on the first try. The first signed-in QA found scoring down since the
  day before; the orchestrator fix was promoted the same evening.

## 1. Services

`web` and `ai-orchestrator` redeployed and checked 2026-09-14 ~17:25 UTC.
`grading-engine` is unchanged since its 2026-09-12 07:43 UTC check.

| Service | Deployed commit | Check |
| --- | --- | --- |
| `qualifier-web` | `adf7ae7` (deploy `dep-dak2qe3rjlhs73con830`, live 2026-09-14 17:23 UTC). Checked from outside: the sign-in page renders with no console errors or CSP violations, `/api/users`, `/api/documents/[id]/url` and `/api/ops/queue` answer 401, and the CSP header is `Content-Security-Policy`, enforced, with the Supabase origin in `frame-src` and `img-src`. The rest of this row is from `45cb1c6`. | `/` 200. In a browser the sign-in form renders against the real Supabase, with "¿Olvidaste tu contraseña?", both toast live regions mounted, and no console errors. `lang="es"`. `/cases` and `/register` 307 to `/?next=…`. `/set-password` 200, unknown path 404 in Spanish. All ten API routes answer **401** unauthenticated. HSTS, frame, nosniff, referrer and permissions headers present; CSP enforced since `adf7ae7` (report-only before). |
| `qualifier-grading-engine` | `a828460` | `/health` 200; `/score` answers 400 to an empty body, so the token is accepted |
| `qualifier-ai-orchestrator` | `fb21538` (deploy `dep-dak2qcrrjlhs73con65g`, live 2026-09-14 17:22 UTC; no error or warning logs since). The check that follows is from `a1908f2`. | Extraction and scoring both ran for the QA application: two `document.extract` jobs completed, and `application.process` completed on its fifth attempt, the first on this build |

`docs` is at `47b178e` and `db` at `4725a9d`; neither deploys anything.

## 2. The database — `jskuoazhcgfyetxrmxyi`

Production, and the only project. **Migration `20260911000000` is applied**,
recorded in the ledger as `20260912073356` (apply-time versions, as the existing
15 rows are — see § 5).

Verified read-only afterwards:

- the three over-broad policies are gone (`scores_system_write`,
  `products_public_read_active`, `audit_log_insert`), and the four "for all"
  tenant policies are replaced by select-plus-narrow-write pairs;
- `decide_case`, `request_case_info`, `assign_case`, `submit_application` and
  `set_staff_role` exist, executable by `authenticated` and not by `anon`;
- `authenticated` can no longer insert into `scores` or `audit_log`, or write
  `cases`, `case_comments`, `applications.status` or `documents`;
- `profiles.role` and `profiles.tenant_id` are not updatable with a user JWT
  while `full_name` still is;
- 9 composite foreign keys, the superadmin constraint and the one-open-case
  index are in place.

**2026-09-13, three more.** Applied through the Supabase connector's
`apply_migration`, one transaction each, in order, after read-only checks that
production still had the schema the files expect:

| File | Ledger version | Verified afterwards |
| --- | --- | --- |
| `20260912000000_staff_management` | `20260913083440` | `profiles.is_active` (not null, default true) and `email`, backfilled for all 9 profiles. Both helpers filter on `is_active`. `set_staff_role(uuid,text,uuid)` replaces the two-argument version, and `set_staff_active` exists; both are executable by `authenticated` and not `anon`. `profiles_self_update` exists. A user JWT can update `full_name` but not `is_active` or `email`. |
| `20260912000100_intake_inserts_start_at_the_start` | `20260913083542` | `applications_intake_write` requires `draft` with no submission or playbook fields. `documents_intake_write` requires `uploaded` with empty `extracted_data` and `validation`. This closes the forged-extraction insert that was open in production. |
| `20260912000200_client_changes_audited` | `20260913083626` | `clients_audit` trigger enabled; `audit_client_change()` not executable by `authenticated` or `anon` |

**2026-09-14, two more**, the same way, after checking that none of their objects
existed:

| File | Verified afterwards |
| --- | --- |
| `20260914000000_list_views` | `latest_scores`, `application_list`, `client_list` exist with `security_invoker=true`; `authenticated` can select and not update, `anon` cannot select. As agent-seguros and agent-medico, in a rolled-back transaction: 10 + 6 applications, 9 + 6 clients, 7 + 5 latest scores, which add up to the tables' totals, and no other tenant's rows. `applications_client_id_idx` already existed, so only the scores index was new. |
| `20260914000100_sign_ins_recorded` | Both triggers enabled on `auth.sessions`. A rehearsal of Supabase Auth, rolled back: a session insert and delete for agent-seguros wrote `auth.signed_in` and `auth.session_ended` against seguros and set `last_signed_in_at`; the superadmin's session set `last_signed_in_at` and wrote no audit row. Afterwards, no `auth.%` rows and no `last_signed_in_at` remained. `authenticated` cannot update the column. The trigger function has no `EXECUTE` grant for `supabase_auth_admin`, which Postgres does not check when a trigger fires; that was confirmed on Postgres 17 before relying on it. |

The security advisor raised nothing new: its warnings are the by-design
`SECURITY DEFINER` RPCs, pg-boss's search paths and leaked-password protection
being off.

**2026-10-29, five more: self-service intake (`FUN-11`), phases 0–4.** Applied
through the connector's `apply_migration`, one transaction each, in order, after
a full rehearsal on production that ran all five inside one transaction and
raised at the end to force a rollback (RUNBOOK.md § "Apply a migration"). Each
was sent wrapped in a guard that checks its MD5 against the file before
running it, so what ran is byte-identical to the repo, minus full-line comments
outside function bodies.

| File | Ledger version |
| --- | --- |
| `20261028000000_typed_form_schema` | `20261029043059` |
| `20261028000100_self_service_intake` | `20261029043639` |
| `20261028000200_intake_lifecycle` | `20261029043904` |
| `20261029000000_auto_approval` | `20261029044028` |
| `20261029000100_intake_channels_domains_embed` | `20261029044251` |

Verified afterwards:

- **Matches the repo.** Production's `public` schema matches a database built
  from the repo's files: all 675 objects, including what `anon`,
  `authenticated` and `service_role` may each do with every function, table,
  view and column. Before the apply, production already matched the files
  through `20261017000000`; the only differences were in how Postgres 17
  writes grants.
- **Locked down.** No `SECURITY DEFINER` function is executable by `anon`, and
  `anon` holds nothing on the new tables or views.
- **What `main` still does keeps working.** In rolled-back transactions as a
  seguros tenant admin:
  - they see the tenant's 10 applications, directly and in `application_list`;
  - a client and application inserted as `main`'s web inserts them get
    `source = staff` and `channel = staff`;
  - `intake_start` is refused to them, and `intake_link_public` to `anon`.
- **Data untouched.** 2 tenants, 2 products, 16 clients, 17 applications, 13
  cases, 14 scores, 33 documents, 41 audit rows. Every existing application is
  `staff`, and every existing document got `received_at` at apply time. No
  intake link, consent text or domain exists. Automatic approval is off
  everywhere. Seguros' life product, the one checked, has 1 of the 100
  decisions it needs.

**Later on 2026-10-29: promoted and deployed.** `develop` was fast-forwarded
into `main` in all five repos:

| Repo | `main` |
| --- | --- |
| docs | `5e518b8` |
| db | `278fdb7` |
| grading-engine | `982f9a5` (the 2026-10-27 fastify patch) |
| ai-orchestrator | `8503b9e` |
| web | `8e43aee` (Next.js 16.4.3) |

Render deployed the three services within two minutes, and each went live:

- **grading-engine** and **ai-orchestrator** answer `/health`. The
  orchestrator came up in embedded worker mode.
- **pg-boss** has the two new queues (`intake.notifications`, `intake.purge`,
  policy `singleton`) and their schedules. The notifications job completed
  once a minute until the free instance spun down after 15 idle minutes. As
  with every queue here, scheduled jobs run only while the service is awake.
- **web** runs Next.js 16.4.3 and passed Render's health check on `/`.
- No service logged an error or a warning outside the build.

Not checked by hand: this session's network policy refused connections to
`onrender.com`, so nobody has loaded the sign-in page or `/s/` since the
deploy.

The security advisor raised nothing new in kind:
- `authenticated` can execute `SECURITY DEFINER` functions: 19 entries, the new
  staff RPCs among them, each of which checks the caller's role itself.
- pg-boss's search paths.
- Leaked-password protection is off.
- "Anonymous Access Policies" on every table with a policy `to authenticated`,
  the new ones included. That lint fires because **anonymous sign-ins are still
  enabled in Supabase Auth**. Nothing calls `signInAnonymously()`, and an
  anonymous user has no profile, so `current_tenant_id()` is null and every
  policy returns nothing. Turning it off (Authentication > Providers) is still
  the right move; `web/README.md` already says so.

Contents are unchanged from the demo portfolio seeded on 2026-08-18: two
tenants, 14 clients, 15 applications, 11 cases, 28 documents, 11 scores, 11
audit entries (all seeded), 9 staff profiles, 11 auth users, `ai_usage` 0, no
pg-boss jobs.

## 3. Repositories

`main` equals `develop` equals the umbrella's pins in all five repos, and all of
it is pushed.

| Repo | `main` | What landed most recently |
| --- | --- | --- |
| `db` | `4725a9d` | 2026-09-14: list views, sign-ins recorded; eight pgTAP suites (157 assertions) |
| `web` | `adf7ae7` | 2026-09-14: document preview, upload progress, database-side lists with bulk and export, Spanish errors, rate limits, enforced CSP; 76 unit tests |
| `ai-orchestrator` | `fb21538` | 2026-09-14: Spanish field labels; 2026-09-13: embed fix, playbook keys, document max age; 104 tests |
| `grading-engine` | `a828460` | CI on `develop`, rebuilt lockfile |
| `docs` | `47b178e` | 2026-09-14: list views and sign-in recording in supabase-schema.md |

Verification before promoting: 79 pgTAP assertions across three suites in a
step-by-step replay of `db`'s CI workflow; 70 orchestrator tests; 51
grading-engine tests; `web` typecheck, lint and production build; and the audit's
twelve original probes passing 12 of 12 against the fixed schema.

## 4. Audit — found 2026-09-11, fixed and deployed 2026-09-12

Full report: [`audit/2026-09-11-report.html`](audit/2026-09-11-report.html).
Probes: [`audit/2026-09-11-probes.sql`](audit/2026-09-11-probes.sql); their
durable form is `db`'s `write_authorization_test.sql`, which runs on every push.

Twelve of fifteen findings are fixed and live — `C1`, `H1`–`H3`, `M1`–`M8`. The
three open ones are low: `L1` vitest's dev-only advisories, `L2` the `/analyze`
development route being reachable in production, `L3` pgTAP installed in the
production database.

## 5. What went wrong on the way out

Worth keeping, because both cost real time:

- **`supabase db push` would have been a disaster.** The ledger keys migrations
  by apply-time version and none of its rows match the repo's filenames, so a
  push would have judged all 14 files unapplied and started again from
  `init_schema`. The migration was applied as one transaction instead, behind
  pre-flight checks for every constraint it adds.
- **A lockfile written on Windows was not installable on Linux.** `web` and
  `grading-engine` both failed in thirteen seconds on `npm ci` with
  `Missing: @emnapi/… from lock file`, entries an earlier `npm audit fix` had
  pruned here, where those optional packages never install.
  `npm install --package-lock-only` does not repair it — it reports "up to
  date". Deleting `node_modules` and the lockfile and reinstalling does. The
  trap is now in CLAUDE.md.

## 6. Open issues and risks

1. **`BLK-5`, partly done.** One fictitious application went through extraction
   and scoring on 2026-09-13. Its documents were marked "ficticio", so the model
   flagged them and scoring was blocked: the consistency agent, the narrator and
   grading-engine did not run on real extractions. No decision, assignment or
   comment has been made signed in.
2. **Extraction field names didn't match the playbooks — fixed and live in
   `a1908f2`, verified on one document.** `extraction-agent.ts`
   asked for "every relevant field" and never passed the keys the playbook reads.
   The QA run returned `monthly_salary`, `document_number` and `issue_date`,
   while the seguros playbook reads `document.proof_of_income.monthly_income`,
   and values came back as "US$ 2,000.00" and "1 de septiembre de 2026". Rules
   fed by documents will be indeterminate on real files. Only the seeded data
   works, because its keys were written to match.
3. **Fixed and live in `web` `3170a77`:**
   - the case screen reports a blocked score as "0 reglas no se pudo evaluar";
   - birth dates show a day early (UTC parsing);
   - a superadmin's queue offers other tenants' analysts;
   - the copy claims scoring runs without documents;
   - raw Postgres errors on client forms;
   - English extraction labels;
   - sign-in doesn't retry a Supabase 504.
4. **Supabase gateway 504s.** Twice in ten minutes on 2026-09-13, auth and REST
   requests timed out at the gateway after 5 s, with Postgres idle.
5. **Supabase Auth's Site URL looks like `http://localhost:3000`**, since every
   auth log line reports that referer. If so, the emailed password-reset link
   points at localhost. Check Authentication → URL Configuration.
6. **`MODEL_DEFAULT`.** The secrets file still says `claude-sonnet-5`, which the
   default path's 2048-token budget can't carry. Render runs `claude-sonnet-4-5`;
   keep it. `MODEL_ESCALATION` is now `claude-sonnet-5` in the blueprint.
7. **One Supabase project, and it is production** (`BLK-4`), with no rehearsed
   restore.
8. **Nothing watches it** (`NEG-2`).
9. **`render-blocks.env` is still on disk.** An automated delete was blocked;
   delete it by hand.
10. The three low audit findings.

## 7. Not verified

- The 2026-09-14 web changes signed in: the preview, drag-and-drop with
  progress, the lists' sorting, bulk actions and export, "Último acceso", and
  the enforced CSP on signed-in screens. A real sign-in creating an
  `auth.signed_in` row, as opposed to the rolled-back rehearsal.
- The extraction agent actually filling `fields[].label` on a real document.

- Signed in as an underwriter or tenant admin: a real decision landing in
  `audit_log`, an assignment, the playbook engine test. Superadmin and
  agent-seguros were covered on 2026-09-13 (submission, uploads, extraction, audit).
  The other tenant accounts' permissions were checked through SQL as each user, in
  a transaction that was rolled back.
- GitHub Actions results. The repos are private and there is no `gh` CLI here.
  CI ran on `develop` for the first time today; nobody has read the outcome, and
  `db`'s `pg_prove` step has still never run on a real runner.
- Prompt-injection resistance of the three agents against hostile document
  content. Out of scope for the audit, and worth its own pass before real
  applicants' files arrive.
