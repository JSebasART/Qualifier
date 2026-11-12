# Plan 2 — execution state

*Started 2026-11-11; **deployed 2026-11-12**. Resume from here in a new session. Plan:
[`02-cumplimiento-lpdp-arco-pol.md`](02-cumplimiento-lpdp-arco-pol.md); technical design:
[`02-design.md`](02-design.md) (written by WP2).*

## Owner decisions (2026-11-11)

- Target is a presentable demo: every flow mostly built, not production-ready.
- Apply migrations to production (after the rolled-back rehearsal) and promote `develop` → `main`.
- **Applicant self-service intake leaves the product**: remove it from web and ai-orchestrator;
  the intake tables and `intake_*` functions stay in the database, dormant. The consent link
  and the ARCO-POL rights portal stay, reusing intake's captcha, rate limits, hashed tokens and
  one-time codes.
- Consent enforcement: a per-tenant switch, on in both tenants, applying only to applications
  created after it was turned on.
- MFA stays optional in the demo tenants.
- Publishing the generated notice in production: **owner said leave unpublished** (2026-11-12). The staff
  confidentiality text is seeded as a draft too (migration E). Admins publish both from Privacidad.
- LPD-0 dashboard actions are the owner's checklist.

## Work packages

| # | Package | Phase | Agent / model / effort | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| 1 | Self-service footprint map | Design | Explore / sonnet / medium | done | generic helpers move to `web/src/lib/public/server.ts` |
| 2 | Technical design → `02-design.md` | Design | general-purpose / opus / high | done | 991 lines; migrations `20261111000000/100/200`; ORCH deploys only after DB-B is in prod |
| 3 | Remove self-service from web | Implement | sonnet / medium | done | `7ea00a0` (develop, not pushed); typecheck ok, 336 tests pass (verified by conductor); build ok per agent |
| 4 | Remove self-service from orchestrator | Implement | haiku / low | done | `77fd914` (develop, not pushed); 492 tests pass; README purge text left for docs |
| 4b | Docs: retire self-service mentions | Docs | sonnet / medium | done | docs `08d1f4d`, ai-orchestrator `98756e6`; umbrella `RUNBOOK.md` + `SELF-SERVICE-PLAN.md` edited, uncommitted (go with the pin bump) |
| 5 | DB-A: LPD-1/2/3 | Implement | sonnet / high | done | db `31d738f`; replay 22 suites / 933 assertions (verified by conductor); verify fns return `{verified:false}` on a miss |
| 6 | DB-B: LPD-4/5/6 | Implement | sonnet / high | done | db `3c09407`; replay 23 suites / 1159 (verified). Web portal verify fix `7f13d10` |
| 7 | DB-C: LPD-7…13 | Implement | sonnet / high | done | db `e37dca1`; replay 24 suites / 1382 (verified). Drops A's `consent_records.actor_id` FK (staff deletion bug) |
| 7c | Apply C + D to `qualifier-dev` | Integrate | sonnet / high | done | dev ledger 53; both rehearsals green on PG17 (first C run caught a test that assumed no `auth.mfa_factors`, fixed in db `817ee29`); advisors: no anon findings. Tooling `scratchpad/apply4/` |
| 7d | Migration E: staff confidentiality text seeded as draft | Implement | sonnet / medium | done | db `948bd59`; replay 26 suites / 1470 (verified) |
| 16a | Dev E + production fingerprint, rehearsal, apply A–E | Integrate | sonnet / high | done | dev ledger 54; prod fingerprint = pre-Plan-2 replay; prod rehearsal 14 suites green (after fixture fix db `09c3e01`); prod ledger 36→41; enforcement on, staff texts draft, no notice published, 22 existing applications pass the gate |
| 13 | Contract cross-check: web/orch `.rpc()` + selects vs SQL | Test | sonnet / medium | done | ~155 calls, 0 arg mismatches; 1 real bug (evidence package `select("*")` on column-granted `consent_records`); ~90 SQL codes lack Spanish text; agent masking fallback. Scripts `scratchpad/contract-check/` | replaces a separate attacker-test package: implementers wrote attacker-side suites (574 new assertions) and the review covers the rest |
| 7b | Apply A+B to `qualifier-dev` (rehearse → apply → verify) | Integrate | sonnet / high | done | dev ledger 49→51 (`privacy_inventory_consent`, `privacy_state_requests`); rehearsal 8 suites green on PG17; advisors: nothing new at anon level. Tooling `scratchpad/apply3/` |
| 15 | Security review (A, B, C, web public + staff privacy routes, orch gate) | Review | opus / high | done | 7 findings: 1 high (DSR `contact_on_file` not checked vs contact), 4 medium (paper-consent reuse after revocation; agents read health data via scores/field_reviews; retention deletes files before apply; DUI read skips gate), 2 low (left-most XFF trusted + per-tenant portal cap; denylist minimization) |
| 15a | FIX-DB: migration D `20261111000300_privacy_review_fixes.sql` (findings 1, 2, 3, 6-db) | Fix | sonnet / high | done | db `6d4c00d`; replay 25 suites / 1447 (verified). Unjudged paper forms accepted on staff attestation (gate would otherwise deadlock the paper channel) |
| 15b | FIX-ORCH (findings 4, 5, 7) | Fix | sonnet / medium | done | ai-orchestrator `6a5b1b0`; 578 tests (verified). `/identity/read` gates only when web sends `client_id` |
| 15c | FIX-WEB: evidence select, right-most XFF, agent masking fallback, Spanish error codes, `client_id` to `/identity/read`, agent restricted-score text | Fix | sonnet / medium | done | web `ebdf842`; 397 tests, typecheck ok (verified); build ok per agent. Cases page and client detail still show a bare null score to agents (minor) |
| — | E2E note | — | — | — | No dev service-role key and no dev staff users: integration is checked by an rpc/table contract cross-check against dev's real schema, plus SQL flow scripts; UI E2E needs the owner's session |
| 8 | ORCH privacy changes | Implement | sonnet / high | done | ai-orchestrator `cd9f2ca`; 563 tests, tsc ok (verified). **Deploy only after DB-B is in prod** |
| 9 | WEB-1 shell, settings, notice, inventory, public notice | Implement | sonnet / medium | done | in web `63d9655` |
| 10–12 | WEB-2 consent, WEB-3 DSR + portal, WEB-4 retention/access/incidents/dashboard | Implement | sonnet / high, high, medium | done | web `63d9655` (all four packages); integrated typecheck, lint, 393 tests, build pass (conductor). Not yet run against a database |

2026-11-12: all six running agents (DB-A, ORCH, WEB-1…4) hit the account rate limit mid-work and were
resumed from their saved state once it reset. Their files are uncommitted in each repo's working tree.
| 13–14 | Attacker-side DB tests; web/orch test pass | Test | — | done | folded into row 13 (contract cross-check), the implementers' attacker-side suites and the conductor's re-runs |
| 16 | Promote develop→main, verify deployed | Integrate | conductor | done | docs `08d1f4d`, db `09c3e01`, ai-orchestrator `6a5b1b0` (live, boot sweep + retention run clean), web `ebdf842` (live: `/privacidad/medico`, portal, `/privacy` behind sign-in, `/s/…` 404). STATUS headline 2026-11-12 |

## Open issues

- A `qualifier-dev` Supabase project (`vtcrbrajexbsberrqwvo`) appeared on 2026-11-12 UTC with the
  full schema (49 ledger rows) and 2 tenants, set up by another session. Plan 2 migrations go there
  first, then to production. `web/.env.example` carries that session's uncommitted edit (first 10
  lines): do not commit it with Plan 2 work.
- Fixed routes: consent link `/consentimiento/[token]`, rights portal `/privacidad/[slug]`, APIs under
  `web/src/app/api/public/{consent,privacy}/**`.
- `STATUS.md` still describes self-service as live: update it in the final status entry.

## Contracts the web packages relied on (DB-B/DB-C must match)

WEB-4 (done, uncommitted): `compliance_summary(p_tenant_id)`, `retention_preview(p_tenant_id)`,
`save_retention_policy(p_data_class, p_retain_days, p_starts_from, p_action, p_legal_basis)`,
`approve_retention_policy(p_data_class)`, `place_legal_hold(p_client_id, p_application_id, p_reason, p_until)`,
`release_legal_hold(p_id)`, `log_access(p_action, p_entity_type, p_entity_id, p_purpose, p_detail)`,
`pending_acknowledgement()`, `acknowledge_confidentiality(p_text_id)`,
`open_incident(p jsonb: title, nature, data_categories, includes_sensitive, known_at,
affected_subjects_estimate, immediate_actions, recommendations, tenant_ids)` (**`title` is extra to the design**),
`update_incident(p_id, p jsonb {status})`, `close_incident(p_id, p_note)`,
`mark_incident_notified(p_incident_id, p_tenant_id, p_target)`,
`notify_incident_subjects(p_incident_id, p_tenant_id, p_client_ids, p_message) returns int`,
`record_data_transfer(p jsonb: client_id, recipient_kind, recipient_name, country, categories, legal_basis,
occurred_at, reference)`; reads `access_log`, `staff_acknowledgements`, `data_transfers`, `incident_tenants`,
`incident_events`, `profiles.is_active`, `privacy_settings.privacy_email`. Notes: `AckGate` fails open when
`pending_acknowledgement` errors; superadmin is read-only on retention (functions act on `current_tenant_id()`).

WEB-1 (done): superadmin gets a read-only notice editor (`save_privacy_text` acts on the caller's tenant);
`ProcessingInventory.retention?` optional, filled from `retention_policies`.

WEB-2 (done, uncommitted): argument names exactly as design §2 (`p_token`, `p_date_of_birth`,
`p_national_id`, `p_channel`, `p_decisions`, `p_typed_name`, `p_signature_path`, `p_ip`, `p_user_agent`…);
`save_processing_purpose(p jsonb: code,label,description,legal_basis,requires_consent,optional,
written_required,applies_to,active,sort_order)`; reads `consent_requests` (`ConsentRequestRow`) and
`applications.consent_enforced`. No `sendWhatsAppLink`: a WhatsApp-only contact gets `sent_via:"none"`
and staff copy the URL. Conductor fix: the identify/verify routes now turn DB-A's `{verified:false}`
answers into `identity_mismatch` / `link_locked` / `code_invalid` errors (they returned a bare stage).
Check WEB-3's portal verify route for the same pattern once DB-B defines `privacy_verify_code`.

WEB-3 (done): calls `register_dsr(p jsonb)`, `privacy_open_request(p_slug, p jsonb)`; `requested_changes`
`[{target:'client', field, value}]`; expects `privacy_verify_code` → `{number, due_on, status, contact}`,
`privacy_response` → `[{kind, content}]`, `add_dsr_attachment` → `{id, path}`, `privacy_add_attachment` →
`{path}`, `data_subject_footprint(p_tenant_id, p_client_ids)`, `execute_dsr_access|portability(p_dsr_id)`,
`release_dsr_response(p_response_id)`, `add_dsr_propagation(p_dsr_id, p_recipient_name, p_recipient_kind,
p_action)`, `complete_dsr_propagation(p_id, p_evidence)`, `unlock_field(p_lock_id)`,
`execute_dsr_revocation(p_dsr_id, p_purposes)`, `execute_dsr_state(p_dsr_id)`,
`rectify_subject_data(p_dsr_id, p_changes)`. Sent to DB-B; DB-C brief must carry the C-side ones.

## Production prerequisites for the client-facing pages (owner actions)

- Turnstile (`NEXT_PUBLIC_TURNSTILE_SITE_KEY` build ARG + `TURNSTILE_SECRET_KEY`) and Resend
  (`MAIL_API_KEY`, `MAIL_FROM`) are not configured on `qualifier-web` (STATUS 2026-10-30). In production
  `verifyCaptcha` and `sendPublicMail` fail closed (`captcha_unavailable`, `mail_unavailable`), so the consent
  link and the rights portal cannot be completed until they are set. No bypass was added: showing the code on
  screen would reopen the high review finding (identity by contact on file).
- A published privacy notice per tenant (owner chose to leave it unpublished): Privacidad → Aviso → Publicar.
- Optional: publish the staff confidentiality text (Privacidad → Personal) to switch on the acknowledgement gate.

## After deploy (2026-11-12)

| # | Package | Status | Notes |
| --- | --- | --- | --- |
| 17 | Agent "Puntaje restringido" on the cases page and client detail | done | web `53baf58` (develop, not yet promoted); typecheck ok |
| 18 | PGlite-backed local Supabase harness (`scratchpad/ui-harness2/`): real migrations, RLS and grants behind a PostgREST subset, fake GoTrue sessions | done | smoke 11/11 (+45/45 extra); every web env var set locally, egress guard refuses non-loopback; storage RLS not emulated, orchestrator stub processes nothing |
| 19 | Walk every Plan 2 screen signed in (tenant admin, underwriter, agent, superadmin) + consent link + portal on localhost | done | every step passed in the end; no SQL or console errors; 14 defects (D1: auto-matched DSR subject shown as linked, so an erasure could never run; the rest wording, dates, erased-client actions, incident template field) |
| 20 | Fix the 14 walk defects (web) | done | web `3b46c0c`; 408 tests, typecheck, lint, build (verified). Open: incident Art. 25 d) has no consequences column (placeholder for staff) |
| 21 | Re-walk the fixed defects locally | done | 12 of 14 fixed outright; D3 is the harness (the outbox copy is queued, the stub orchestrator sends nothing); D8 leftovers: the erasure plan now names people (web `139f413`), the inventory keeps technical table names by design. Web promoted: main `139f413` |
