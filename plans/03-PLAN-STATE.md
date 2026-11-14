# Plan 3 — execution state

Execution record for [`03-datos-del-cliente-y-enriquecimiento.md`](03-datos-del-cliente-y-enriquecimiento.md),
run with the plan-conductor skill. Technical design: [`03-design.md`](03-design.md).

## Starting point (2026-11-12)

- Plan 2 complete and in production: main pins db `bf445aa`, web `81b2785`, ai-orchestrator `6a5b1b0`,
  docs `08d1f4d`, grading-engine `cc04cbd`; umbrella `ce70c4a`. Develop-only leftovers ride the next
  promotion: web `789557b`, ai-orchestrator `dc84f3b` (blueprint tidy-ups, no behaviour change).
- Production `jskuoazhcgfyetxrmxyi`: ledger 42; 41 documents (all extracted), 17 clients, 22 applications,
  0 field reviews, 24 MB. Extensions installed: pgtap, pgcrypto, uuid-ossp, pg_stat_statements, vault;
  available: pg_trgm, unaccent, vector, pg_cron.
- Dev `qualifier-dev` `vtcrbrajexbsberrqwvo`: ledger 55, schema only (no clients or documents), no pgtap.

## Owner decisions (2026-11-12)

- Apply migrations to dev, then production, and deploy (same procedure as Plan 2).
- Transcription (DAT-6): immediate mode **and** Message Batches mode; opt-in per document type.
- Include the optional phases: DAT-8 (pgvector semantic search) and DAT-9 (pseudonymised analytics replica).
- Backfill: existing `extracted_data` → facts and profiles only; no re-extraction.
- Context: the project is being readied for a presentation; flows must be mostly built, not production-hardened.

## Notes

- Transcription model: `claude-haiku-5-5` (US$0.10 / US$0.50 per MTok, batches 50% off), configurable.
- Embeddings: Voyage AI (new subprocessor; fails closed until the owner sets `VOYAGE_API_KEY`).
- Out of scope but urgent: the orchestrator's `MODEL_DEFAULT=claude-sonnet-4-5` retires 2026-11-30.

## Work packages

| # | Package | Phase | Model / effort | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 0 | Technical design `plans/03-design.md` | Design | opus / high | done | 998 lines; 3 migrations (A core, B search/enrichment, C vectors/analytics); deviations D2 (refresh in DB, no job), D3 (profile via definer RPC), D4/D5 (human facts win until newer evidence; 60-day conflict window), D6 (Plan 2 report/erasure functions wrapped as `*_base`), D8/D9 deferred (occupation codes, configurable income bands) |
| 0b | Replay runner loads pg_trgm + unaccent | Integrate | conductor | done | baseline 27 suites still pass |
| 1 | DB-A migration `20261113000000_client_data_core.sql` + suites | Implement | sonnet / high | done | db `72bbe31` (develop, not pushed); 2898 lines; replay 29 suites / 1634 assertions (re-run by conductor). Deviations: `record_form_facts(…, p_only_keys)`, empty-value facts deleted not superseded, hooks run once inside the erasure wrapper, phones compared by digits. Gap `merge_clients` doesn't move facts ⇒ assigned to DB-B (wrapper). Interrupted once by the usage limit |
| 2 | ORCH-A extras, `record_document_facts` call, case Q&A bundle | Implement | sonnet / medium | done | ai-orchestrator `1fc7445` (develop, not pushed); `client-facts.ts` deleted; new citation kinds `fact`/`page` ⇒ web `lib/case-qa.ts` must accept them (assigned to WEB-C) |
| 3 | ORCH-B transcription (immediate + batch), embeddings, enrich, replica job | Implement | sonnet / high | done | ai-orchestrator `8f38633`; together 715 tests, tsc clean (verified by conductor). Env: `MODEL_TRANSCRIPTION`, `TRANSCRIPTION_MAX_TOKENS` (16000), `TRANSCRIPTION_BATCH_SIZE`, `EMBEDDING_MODEL`, `VOYAGE_API_KEY` (`sync: false`). Needs from DB-B: `transcription_request_context` returns `attempts`; reads `transcription_requests (id, attempts, batch_id, status)` with service role. Semantic status adds reason `status_unavailable` (sent to WEB-B). Interrupted once by the usage limit |
| 4 | WEB-A shared foundation + «Datos del cliente» tab | Implement | sonnet / medium | done | web `b93b2d5` (develop, not pushed); 426 tests, typecheck, lint; history as a modal; `client.viewed` already logged on page load |
| 5 | DB-B migration `…000100` search, enrichment, segments, quality (+ `merge_clients` wrapper, `attempts` in transcription context) | Implement | sonnet / high | done | db `54fc689`; 2015 lines; A's suites now count derived facts separately; search uses `<%` word similarity |
| 6 | DB-C migration `…000200` vectors, analytics replica | Implement | sonnet / high | done | db `ccaeea9`; 761 lines; replay with A+B+C: 34 suites / 2070 assertions (conductor re-ran). Real `vector` path untested in PGlite ⇒ dev rehearsal. Plan 2 consent suite now expects 7 subprocessors |
| 10 | Contract cross-check web/orchestrator ↔ migrations | Test | sonnet / medium | done | ~57 calls/reads match (names, named args, grants, shapes, 3 routes). One mismatch: page citation ref has no `page:` prefix ⇒ web `c4d0813` parses the bare ref |
| 11 | Attacker-side suite `plan3_attacker_test.sql` | Test | sonnet / medium | done | 253 assertions, 5 real failures: sensitivity change not propagated (= review #2); `merge_clients` moves facts into a limited/erased kept client; an agent can merge clients it cannot see. Observation: `request_transcription` queues for a client without AI consent (orchestrator refuses later) |
| 14 | FIX-DB: review #1–#4 + attacker findings + refuse transcription without consent, editing unapplied A/B/C in place | Implement | sonnet / high | done | db `dd17db7`; replay 35 suites all pass incl. attacker 254/254 (conductor re-ran). Web follow-ups `9d4fdff`: Spanish message for `ai_processing_not_consented`; browser `logExport("segment")` dropped (the DB audits each page). Note: `segment_members` logs `export.generated` on every page it returns, including on-screen browsing |
| 15 | Dev staging v2 (55 chunks / 830 KB incl. attacker suite) | Integrate | haiku / low, then sonnet / low for 6 re-uploads | done | The plugin connector declines chunks containing destructive-looking SQL from background agents; owner reconnected the claude.ai Supabase connector. Haiku mistyped 6 of 32 chunks (md5 caught them; renamed `bad3_*`), sonnet re-sent them. All 19 files assembled, md5 match |
| 16 | Dev rehearsal 1 (rolled back) | Integrate | conductor | done | A, B, C apply on Supabase with the real `vector` extension; secdef executable by anon 0 → 0; 14 of 15 suites pass in full (privacy 125/226/224/65, attacker 254, rls 31, write 38, anon 8); `semantic_search_test` 5/49 fail: re-storing a document's chunks does not replace them (footprint has 3, wants 2) |
| 17 | Debug `record_document_chunks` on dev (rolled-back probes only) and fix | Implement | sonnet / high | done | Cause was the TEST: function call and `count(*)` in one statement share a snapshot that predates the function's writes. Function correct (RLS not forced; owner has BYPASSRLS). db `6ab72e3` fixes the suite; dev probe 49/49; replay all pass. Migration C unchanged |
| 17b | Dev rehearsal 2 + apply | Integrate | conductor | done | Rolled-back rehearsal: 15 suites, 1584 assertions, 0 failed, real `vector`; anon secdef 0 → 0. Applied A, B, C with md5-guarded `apply_migration`: dev ledger 55 → 58; 41 platform attributes |
| 18b | Production rehearsal (rolled back) | Integrate | conductor | done, 1 open issue | 55 chunks / 19 files md5-verified on prod `_staging.files`. A, B, C apply; anon secdef 0 → 0; real `vector`. Backfill: 40 documents, 235 facts (316 with derived), 17 profiles, 1 doc not read. 15/16 suites clean (1584+ assertions); `client_profile_test` #60 fails because `backfill_regression_report()` returns 2 rows for client c9da5162 (`annual_income` and `occupation`, source proof_of_income 54ca269a). Column and profile values are IDENTICAL (28800.00 / «Analista de Compras"), so it looks like a false positive in the report (likely `field_sources` not stamped with `fact_id`, or a text/numeric comparison), not a data change. NEXT: fix the report or the stamping in migration A (unapplied on prod), re-stage that file, re-rehearse, then apply A/B/C to prod, run backfill, promote develop→main (docs, db, orchestrator, web), bump pins, walk the deployed site. Then Plan 4 |
| 18c | Regression-report false positive | Implement | conductor | done | Production client c9da5162 has the same constancia in three applications (equal values, equal issue date): the profile keeps one copy, the legacy `field_sources` names another. db `943add3`: a different source document is reported only when it holds no current fact with the winner's value; new fixture for the tie; replay 35 suites all pass. Dev: the fixed function replaced in place (dev applied A before the fix). Prod: chunks 01_8, 06_1, 06_2 re-staged |
| 19 | Production rehearsal 2 + apply + backfill | Integrate | conductor | done | Rolled back: 16 suites, 1586 assertions, 0 failed; backfill 40 docs → 316 facts, 17 profiles, regression 0. Applied A (md5 `ad59f8df…`), B, C: ledger 42 → 45. Backfill run for real (same numbers), regression 0, anon secdef 0, Voyage subprocessor inactive, `vector` installed. `analytics_refresh()`: seguros 5 subjects generalized, medico suppressed |
| 20 | Promote develop → main | Integrate | conductor | done | docs `a3856fe`, db `943add3`, ai-orchestrator `41b3cd4` (blueprint sync, live 23:42 UTC; boot sweep clean, enrichment and replica jobs ran, no error logs), web `9d4fdff` |
| 21 | Walk the deployed site signed in (owner's session, tenant seguros) | Verify | conductor | done | «Datos del cliente» (Karla, 3 apps): grouped attributes with sources, derived age/DUI check/annual/band/expiry, completeness 50 %; top-bar search "nubeluna" finds her by employer; «Por significado» disabled with "Voyage AI no está activado como subencargado"; segment builder: monthly income ≥ 2000 → 6 clients (correct), purpose Mercadeo → 0, "6 excluidos por no tener consentimiento"; dashboard «Calidad de datos» and «Cartera» (groups < 5 folded/hidden); replica page 5 subjects, CSV per dataset; employers and uncatalogued pages load (uncatalogued counts only new `extras`, so empty until new extractions — by design); document viewer lists schema fields required first; transcription panel hidden until the type opts in (by design). No console errors. Fixed in passing: web `de6fa5e` folds equal copies in «Otros datos de documentos»; web `90a8426` Spanish employment status in «Cartera». Open: segment builder shows "valor no válido" before typing (cosmetic); live transcription/Batches untested (needs a type switched on in production — owner's config) |
| 18 | Production staging: 51 final chunks (all but migration C and the semantic suite) into `_staging` on `jskuoazhcgfyetxrmxyi` (ledger 42, staging was empty) | Integrate | 4 × sonnet / low | running | |
| 12 | Security and privacy review | Review | opus / high | done | 5 findings. HIGH: catalogued fields of a sensitive document type stored non-sensitive (A:1105) ⇒ agents read them via profile `other_facts`, history, `client_facts`, search. MED: `save_client_attribute` sensitivity change not propagated to stored facts; replica `application_count`/`has_employer`/`completeness_band` outside k=5 grouping. LOW: `segment_members` export audited client-side only; `embedQuery` skipped spend cap (fixed: orchestrator `41b3cd4`, web `b3ece68`). DB findings ⇒ FIX-DB (edit unapplied migrations A/B/C). Interrupted once by the usage limit |
| 13 | Dev rehearsal staging (`scratchpad/apply7`, 49 chunks / 715 KB, 3 migrations + 14 suites) | Integrate | 4 × haiku / low upload | paused | 39/49 chunks staged on dev before the usage limit; the `b159d102` Supabase connector then failed on every call (server error), the `plugin:supabase` connector reaches the same org and is used instead. Rebuild after FIX-DB and re-upload only changed/missing chunks |
| 7 | WEB-B search, segments, dashboard, replica page | Implement | sonnet / medium | done | web `d0d6ff8` (develop, not pushed). Conductor verified the whole web tree: typecheck, lint, 464 tests, production build. Sensitive attributes stay selectable for commercial purposes (non-agents) so the DB refusal shows; `between` sent as `[a,b]`, `in` as an array. Interrupted once by the usage limit |
| 8 | WEB-C viewer, transcription, catalogs, uncatalogued fields, case-qa citation kinds | Implement | sonnet / medium | done | web commit after `b93b2d5` (develop, not pushed); 451 tests, typecheck, lint 0 errors. Conductor passed `extras` at the two `ExtractedFields` call sites (application and case detail). Direct selects on document types instead of an unspecified RPC; a `page` citation opens the PDF at that page in a new tab. Interrupted once by the usage limit |
| 9 | DOCS (`docs/supabase-schema.md`, `docs/architecture.md`, subject export) | Implement | sonnet / medium | done | docs `a3856fe` (+469 lines); `merge_clients` documented as a sixth wrapper. CLAUDE.md invariants + model wording done by the conductor (uncommitted, umbrella) |

## Production answers to the design's questions (2026-11-12, read-only)

- Canonical keys used by published document types all exist in the §3.1 catalog (incl. passport, NIT).
- 2 clients have `field_sources` today, so the production regression check is not vacuous (small).
- Documents attached to versioned types: seguros `proof_of_income` 2, `national_id` 1. Demo transcription type:
  `proof_of_income` (seguros).
- `MODEL_DEFAULT` on main's blueprint is already `claude-sonnet-5-5`; CLAUDE.md's `claude-sonnet-4-5` wording is stale.
