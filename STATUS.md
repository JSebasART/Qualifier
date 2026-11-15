# Status — verified 2026-11-15

One snapshot of what is true now. Until 2026-11-15 this file was a dated log
of every deploy since 2026-09-06 (1,300 lines). That log is in git history:
`git log -p -- STATUS.md`.

## Headline

**Plans 1–4b are in production, built for a demo.** The product reads and
judges a client's documents, consolidates everything known about the client
into one profile with provenance, enforces El Salvador's data-protection law
(LPDP) in the database, and sends the profile to a CRM. There is no paying
customer and no real applicant data yet; the two tenants hold demo and QA
data.

## Services

| Service | Render id | Deployed commit (`main`) |
| --- | --- | --- |
| `qualifier-web` | `srv-da0nst5bedkc73b76bc0` | `5012156` |
| `qualifier-ai-orchestrator` | `srv-da0n7dlbedkc73b5lg8g` | `5c9fc1f`, embedded worker |
| `qualifier-grading-engine` | `srv-da0n6ak9v7es739oo1eg` | `cc04cbd` |

`db` is at `23ddcb5` and `docs` at `9cdd3d9`. In every repo `develop` equals
`main` equals the umbrella's pin. All three services are on Render's free
plan: they sleep after 15 idle minutes, so warm them before a demo
(RUNBOOK.md).

Last checked 2026-11-15 ~15:40 UTC: the orchestrator booted clean, web serves
the Spanish build and redirects to sign-in, `/health` answers 200, and no
service logged an error.

## Database

| Project | Ref | Ledger rows |
| --- | --- | --- |
| Production | `jskuoazhcgfyetxrmxyi` | 50 |
| Development | `vtcrbrajexbsberrqwvo` | 63 |

Every migration since Plan 1 was replayed locally, rehearsed in a rolled-back
transaction on dev and then on production, and applied with an md5 guard
(RUNBOOK.md § "Apply a migration"). Invariants checked on production after
the last apply:

- RLS is on for every public table, and every personal-data table is in
  `personal_data_stores`.
- No security-definer function is executable by `anon`, and `anon` holds no
  write grant on any table.
- The privacy wrapper chain (Plan 2 `*_base`, Plan 3 and Plan 4 hooks,
  Plan 4b `privacy_p4_erase_base`) is intact.
- `analytics_private` and `integration_private` are unreachable to signed-in
  users.

Data: two tenants, `seguros` (life) and `medico` (health); 12 published
document types each; 17 clients with 17 profiles and 316 facts; consent
enforcement on in both tenants; 0 integration destinations.

## Tests (2026-11-15)

- db: 45 pgTAP suites in the local replay, including three attacker suites.
- ai-orchestrator: 1,379 tests. grading-engine: 299 tests.
- web: 622 unit tests, typecheck, lint and the production build.

## What each plan added

| Plan | In production since | Summary |
| --- | --- | --- |
| Base product | 2026-09 → 11 | Extraction, consistency and narrator agents; playbook scoring that fails closed; cases with SLA; tenant isolation; audit trail |
| 1. Document types | 2026-11-08 | Editable types, versioned acceptance rules judged by grading-engine with no model call, analyst overrides, test bench |
| 2. LPDP / ARCO-POL | 2026-11-12 | Purposes and consents, `processing_gate()` before every model call, processing state, inventory (RAT), rights requests and portal, erasure, notices, incidents |
| 3. Client data | 2026-11-13 | Facts with source and date, survivorship profile with conflicts, enrichment and employer catalogue, transcription, full-text and semantic search, segments, dashboards, pseudonymized analytics replica |
| 4. CRM export | 2026-11-15 | `integration_payload()`, event outbox, signed webhooks, public API v1, CSV/XLSX CRM templates, propagation of erasures and restrictions |
| 4b. Native connectors | 2026-11-15 | HubSpot, Dynamics 365 and Odoo with wizard and versioned mappings, «CRM simulado», retention deletes the CRM copy |

Design records: [`plans/`](plans/README.md). Integration guide:
`docs/integrations.md`.

## Open

In the order they should be done.

1. **Live webhook test on the deployed site.** Needs the owner signed in:
   create a webhook destination pointed at the in-app test receiver, send
   only the synthetic test event, walk a «CRM simulado» HubSpot destination,
   then disconnect both.
2. **Not yet exercised against the real services:** transcription and Message
   Batches (Anthropic), Voyage AI (no account), and any real HubSpot,
   Dynamics or Odoo account (adapters are tested against recorded responses
   only).
3. **Owner checklist before any real data** (`LPD-0`, guided by
   `scripts/plan2-owner-checklist.sh`):
   - rotate the database password, then update `DATABASE_URL` on the
     orchestrator and in the secrets file;
   - turn on leaked-password protection, and check the Auth Site URL;
   - delete `render-blocks.env` by hand;
   - choose a paid plan (the free tier sleeps, so scheduled jobs and
     integrations wait for traffic, and there are no backups);
   - configure Turnstile and Resend on `qualifier-web`: until then the consent
     link and the rights portal fail closed (`captcha_unavailable`,
     `mail_unavailable`);
   - publish the privacy notice and the staff confidentiality text;
   - approve a retention policy (none exists, so retention has never run on
     real data);
   - legal review (L1–L13).
4. **Known risks.** Nothing monitors the services (`NEG-2`). Prompt-injection
   resistance of the agents against hostile documents has not been tested.
   GitHub Actions results cannot be read from this machine.
