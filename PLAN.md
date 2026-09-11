# Plan — from here to a demo

Updated 2026-09-11 against [`STATUS.md`](STATUS.md), after the audit.

The complete plan, in Spanish, is `docs/mvp-execution-plan.md`. It records
phases 0–3 as done in code, and they are deployed. This file is the short path
from today to a demo. Identifiers (`BLK-4`, `FUN-7`…) refer to
`docs/product-gap-analysis.md`. Audit identifiers (`C1`, `H2`…) refer to the
2026-09-11 audit summarised in STATUS.md § 4.

## Done on 2026-09-11

- **Dependencies patched on `develop`, not pushed:**
  - Next.js 16.3.5 in `web`, out of two critical RCE advisories;
  - fastify and fast-uri in both Fastify services.

  Every production tree now audits clean.
- **`db` CI fixed.** It had been red since 2026-07-31 and could not fail on an
  assertion. It now runs every pgTAP suite through `pg_prove`, including
  `publish_playbook_test.sql`, and it runs on `develop` too.
- **The whole project audited.** Its findings are steps 1–2 below and the
  "After the demo" list.

## Done on 2026-09-10

- **Pipeline restored.** Render's environment re-entered from the secrets file.
- **`develop` promoted to `main`** in all five repos and deployed.

## Step 1 — Push and promote today's commits

Production runs Next.js 16.2.12 until this happens.

1. Push `develop` in `db`, `web`, `grading-engine` and `ai-orchestrator`.
2. Watch `db`'s first real CI run. The PGlite replay could not exercise the apt
   package that provides `pg_prove`.
3. Promote as in RUNBOOK.md § "Promote develop to main". It deploys.
4. Bump the pins here.

## Step 2 — Close the audit's critical and high findings

**First, one migration**, mostly revokes and dropped policies (`C1`, `H1`,
`M3`, `M4`):

- `profiles` — revoke `update (role, tenant_id)` from `authenticated`, route
  role changes through an RPC, and require that a superadmin has no tenant.
- `scores` — drop `scores_system_write`, and revoke `insert, update` from
  `authenticated`. Only the pipeline's service role writes scores.
- `products` — drop `products_public_read_active`, a leftover from the removed
  applicant portal.
- `audit_log` — revoke `insert` from `authenticated`.

Add the matching probes from `audit/2026-09-11-probes.sql` to the pgTAP suite,
so each fix stays fixed.

**Then `decide_case()`** (`H2`, `H3`), built like `publish_playbook()`. It is
role-checked, runs in one transaction, and writes the comment and the audit row
itself. Move `case-detail.tsx` and the assignment in `cases/page.tsx` onto it.

Both must land before step 3's real run. The demo ends on an underwriter's
decision, and today that decision leaves no audit record.

## Step 3 — A human smoke test, then one real pipeline run (`BLK-5`)

Nobody has used the deployed code yet. Signed in as staff:

1. Sign in to each tenant, `seguros` and `medico`. Check the Spanish interface,
   each tenant's colour, and deadlines on the cases.
2. Open a playbook and use **test this version**. That proves web →
   grading-engine with the new token.
3. Register an application in each tenant and upload realistic, synthetic
   documents: DUI and salary certificate for `seguros`, the medical documents
   for `medico`. That proves web → orchestrator and runs the real pipeline.
4. Check the case appears scored, with a **Spanish** narrative — never observed
   yet.
5. Decide it, and check the decision appears in `audit_log` (`H3`).
6. Check `ai_usage` gains rows and the cost and timing views return numbers
   (`NEG-1`). The only timing sample so far is from 2026-08-16: 4.6 s extraction,
   13.2 s scoring.

Never use a real person's documents. Calibrating extraction against real
Salvadoran formats is the one piece of engineering still open, and the one most
likely to overrun.

## Step 4 — Settle the models

Both are your decision, because they change which model underwrites
applications:

- **`MODEL_DEFAULT`** — keep `claude-sonnet-4-5` (what Render runs), and set the
  secrets file back to it. A thinking model as default first needs a larger
  `max_tokens` on the default path (`ai-orchestrator/src/agents/routing.ts`).
- **`MODEL_ESCALATION`** — `docs/` records the decision as `claude-sonnet-5` now
  and `claude-opus-5` for production. Change `ai-orchestrator/render.yaml` on
  `develop` to match, then promote. The blueprint still declares the retired
  `claude-opus-4-1` (`M8`), and a dashboard-only fix can be undone by the next
  blueprint sync.

## Step 5 — Keep it alive (`NEG-2`, `BLK-4`)

- Uptime checks on web `/`, grading-engine `/health`, and the orchestrator's
  `/health/queue` **with the bearer header** — the only check that catches a
  dead worker. Frequent checks also keep both free tiers awake; mind the 750
  instance-hours a month in `docs/deployment.md`.
- Backups on the Supabase project, since it is production.
- For the month of a real presentation, consider paid plans on Render and
  Supabase. Switching is reversible.

## Step 6 — The demo

Script: `docs/mvp-execution-plan.md` § "Guion sugerido" — eight beats, 12–15
minutes, ending with the switch to `medico`, which now has staff accounts.

Before it:

- confirm the Supabase project is not paused;
- warm the three services;
- keep `/health/queue` open;
- have one processed application ready to fall back to.

Re-running `db/supabase/seed.sql` the day before keeps the queue's overdue cases
overdue, because its timestamps are relative to `now()`. It also deletes every
row in both tenants' data, including step 3's real runs.

## Housekeeping

- **Delete `render-blocks.env` by hand.** An automated delete was blocked by a
  permission check. Render has the values, and everything in the file is either
  in the secrets file or a public URL.
- **Add `develop` to the CI triggers** in `web`, `grading-engine`,
  `ai-orchestrator` and `docs` (`M6`). It's one line each.
- **vitest 3** in both Fastify services, to clear the dev-only advisories
  (`L1`).

## Before local development

Create a second Supabase project (`BLK-4`) and rebuild it from the repo
([`RUNBOOK.md`](RUNBOOK.md) § "Rebuild the database from zero"). Point local
`.env` files at it, not at production — a local orchestrator with
`WORKER_MODE=embedded` would take production's jobs. Then drop pgTAP from
production (`L3`).

## After the demo — Corte A

The rest of the audit first:

1. `M1` and `M7` — authenticate `/api/playbooks/test`, and add security headers
   to `web`.
2. `M2` and `M5` — foreign keys that carry the tenant, the orchestrator's own
   tenant assertions, and idempotent processing.
3. `L2` — gate the `/analyze` development route off in production.

Then, in `docs/mvp-execution-plan.md`'s order:

1. `SEC-1` and `SEC-2` — the audit log written server-side (step 2 does most of
   it) and document-access logging.
2. `SEC-5`, `SEC-8`, `SEC-11` — rate limiting, second factor, secret management.
3. `BLK-6` with `FUN-3` — email invitation, password reset and client
   notifications, which share the one missing piece: an email provider.
4. `SEC-4`, `SEC-6` — malware scanning and retention.
5. `NEG-2` in full, and `CAL-3` — `web` still has no tests.
6. `BLK-4` in full — three environments and a rehearsed restore.

The audit did not cover prompt-injection resistance of the three agents against
hostile document content. Look at it before real applicants' files arrive.

The legal track (`SEC-9`, `SEC-10`) has not started. It is calendar time, not
engineering effort, and it blocks the contract.

## Open decisions

- Pushing and promoting today's commits (step 1) — it deploys.
- The two model settings (step 4).
- Where step 3's realistic documents come from.
- Who on the insurer's side would edit playbooks — still the assumption the
  whole product rests on.

## What not to do

- **Copy `MODEL_DEFAULT=claude-sonnet-5` to Render** before the token budget is
  raised.
- **Point local services at production.**
- **Trust a CI badge nobody can see.** `db` was red for six weeks while its
  suite was cited as proof of isolation.
- **Let `develop` drift from `main` again.** Three weeks of finished work sat
  undeployed because the merge was never anyone's next task. Promote small and
  often.
- **Rewrite `grading-engine` in Go, move the queue to Redis, build self-serve
  onboarding or integrations.** Each is conditioned on evidence that does not
  exist yet.
