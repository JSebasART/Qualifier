# Plan — from here to a demo

Updated 2026-09-12 against [`STATUS.md`](STATUS.md), after the audit's fixes
went live.

The complete plan, in Spanish, is `docs/mvp-execution-plan.md`. It records
phases 0–3 as done in code, and they are deployed. This file is the short path
from today to a demo. Identifiers (`BLK-4`, `FUN-7`…) refer to
`docs/product-gap-analysis.md`; audit identifiers (`C1`, `H2`…) to
[`audit/2026-09-11-report.html`](audit/2026-09-11-report.html).

## Done on 2026-09-12

Every critical, high and medium audit finding — fixed, re-audited and **live**:

- **`db`** — the write side is authorised: role and tenant are not writable with
  a user JWT, `scores`/`audit_log`/`cases`/`case_comments` are not writable at
  all, four role-checked functions own the staff transitions, foreign keys carry
  the tenant, and an application can have only one open case. Migration applied
  to production before anything was promoted.
- **`web`** — decisions, information requests, assignment and submission go
  through those functions; `/api/playbooks/test` requires a staff session;
  security headers added, CSP report-only. Next.js 16.3.5 is finally in front of
  users.
- **`ai-orchestrator`** — refuses a playbook or a storage path belonging to
  another tenant, and resumes rather than repeating a partly-finished
  application.
- **All repos** — CI runs on `develop`; escalation points at a model that
  exists.

Verified before promoting: 79 pgTAP assertions, 70 + 51 service tests, `web`
typecheck/lint/build, and the audit's twelve probes passing 12 of 12. Verified
after: the live site answers 401 where it used to forward, with every security
header present, and all three services are healthy.

Two things went wrong on the way out — `supabase db push` would have re-run
every migration from scratch, and a Windows-written lockfile would not install
on Linux. Both are recorded in STATUS.md § 5 and CLAUDE.md.

## Done on 2026-09-11

- Dependency patches: Next.js 16.3.5 (two critical RCE advisories), fastify and
  fast-uri in both services.
- `db` CI fixed: red since 2026-07-31 and unable to fail on an assertion.
- The whole project audited.

## Step 1 — A human smoke test, then one real pipeline run (`BLK-5`)

Nobody has used the deployed code, and nothing has exercised the new decision
path with a real session. Signed in as staff:

1. Sign in to each tenant, `seguros` and `medico`. Check the Spanish interface,
   each tenant's colour, and deadlines on the cases.
2. Open a playbook and use **test this version**. That proves web →
   grading-engine with the token, and that the route still works for the people
   who should reach it.
3. Register an application in each tenant and upload realistic, synthetic
   documents: DUI and salary certificate for `seguros`, the medical documents
   for `medico`. That proves web → orchestrator and runs the real pipeline.
4. Check the case appears scored, with a **Spanish** narrative — never observed
   yet.
5. Decide it as an underwriter, and check the decision, the note and the
   assignment all appear in `audit_log`. Nothing this product has ever done has
   produced one of those rows.
6. Sign in as an agent and confirm the decision buttons are gone.
7. Check `ai_usage` gains rows and the cost and timing views return numbers
   (`NEG-1`). The only timing sample so far is from 2026-08-16: 4.6 s extraction,
   13.2 s scoring.

Never use a real person's documents. Calibrating extraction against real
Salvadoran formats is the one piece of engineering still open, and the one most
likely to overrun.

## Step 2 — Settle `MODEL_DEFAULT`

Keep `claude-sonnet-4-5` (what Render runs) and set the secrets file back to it.
A thinking model as default first needs a larger `max_tokens` on the default
path (`ai-orchestrator/src/agents/routing.ts`). `MODEL_ESCALATION` is now
`claude-sonnet-5`; `docs/` records `claude-opus-5` as the production choice when
you want it.

## Step 3 — Keep it alive (`NEG-2`, `BLK-4`)

- Uptime checks on web `/`, grading-engine `/health`, and the orchestrator's
  `/health/queue` **with the bearer header** — the only check that catches a
  dead worker. Frequent checks also keep both free tiers awake; mind the 750
  instance-hours a month in `docs/deployment.md`.
- Backups on the Supabase project, since it is production.
- For the month of a real presentation, consider paid plans on Render and
  Supabase. Switching is reversible.

## Step 4 — The demo

Script: `docs/mvp-execution-plan.md` § "Guion sugerido" — eight beats, 12–15
minutes, ending with the switch to `medico`, which now has staff accounts.

Before it:

- confirm the Supabase project is not paused;
- warm the three services;
- keep `/health/queue` open;
- have one processed application ready to fall back to.

Re-running `db/supabase/seed.sql` the day before keeps the queue's overdue cases
overdue, because its timestamps are relative to `now()`. It also deletes every
row in both tenants' data, including step 1's real runs.

## Housekeeping

- **Read the CI results.** They ran on `develop` for the first time today and
  nobody can see them from this machine (private repos, no `gh`). `db`'s
  `pg_prove` step has never run on a real runner — it is the one part the local
  replay cannot exercise.
- **Delete `render-blocks.env` by hand.** An automated delete was blocked by a
  permission check. Render has the values, and everything in the file is either
  in the secrets file or a public URL.
- The three low audit findings: **vitest 3** in both Fastify services (`L1`),
  gate `/analyze` off in production (`L2`), drop pgTAP from the production
  database (`L3`).
- Move the CSP out of report-only once its violations are known (`M7`).

## Before local development

Create a second Supabase project (`BLK-4`) and rebuild it from the repo
([`RUNBOOK.md`](RUNBOOK.md) § "Rebuild the database from zero"). Point local
`.env` files at it, not at production — a local orchestrator with
`WORKER_MODE=embedded` would take production's jobs.

## After the demo — Corte A

In `docs/mvp-execution-plan.md`'s order, with what the audit closed struck from
it:

1. `SEC-2` — document-access logging. `SEC-1` is mostly done: staff actions are
   audited server-side by the case functions, and nobody else can write to
   `audit_log`.
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

- `MODEL_DEFAULT`, and when escalation moves to `claude-opus-5` (step 2).
- Where step 1's realistic documents come from.
- Who on the insurer's side would edit playbooks — still the assumption the
  whole product rests on.

## What not to do

- **Run `supabase db push` against production.** Its ledger keys migrations by
  apply-time version and none of the rows match the repo's filenames, so a push
  judges all of them unapplied and starts from `init_schema`. Apply a migration
  as one transaction (RUNBOOK.md § "Apply a migration").
- **Trust a lockfile `npm audit fix` produced on Windows.** It can be missing
  entries only Linux needs, and `npm ci` here will not tell you. See CLAUDE.md.
- **Copy `MODEL_DEFAULT=claude-sonnet-5` to Render** before the token budget is
  raised.
- **Point local services at production.**
- **Trust a CI badge nobody can see.** `db` was red for six weeks while its
  suite was cited as proof of isolation.
- **Let `develop` drift from `main` again.** Promote small and often.
- **Rewrite `grading-engine` in Go, move the queue to Redis, build self-serve
  onboarding or integrations.** Each is conditioned on evidence that does not
  exist yet.
