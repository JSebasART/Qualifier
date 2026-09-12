# Qualifier — workspace guide

Orientation for anyone (human or agent) picking this project up cold. This file
covers *how the workspace works*. For what is true right now, read
[`STATUS.md`](STATUS.md) first — it is dated and evidence-backed, and it is the
one file most likely to be stale in a way that matters.

## The one-paragraph version

AI-assisted insurance underwriting. A staff member registers a client and an
application, uploads documents, and a background pipeline extracts the fields,
cross-checks them against the form answers, writes a risk narrative, and scores
the application against a per-tenant **playbook** — a JSON rules document, not
code. An underwriter gets an explainable case (rule trace + AI narrative +
flags), not a black-box number. Multi-tenant, isolated by Postgres RLS.

## Repo layout — this is a multi-repo project

This repo holds **no application code**. Each directory is an independent git
repository tracked as a submodule.

| Path | Repo | Owns |
| --- | --- | --- |
| `docs/` | `qualifier-docs` | Architecture, schemas, roadmap, product analysis |
| `web/` | `qualifier-web` | Next.js staff workspace (the only UI) |
| `grading-engine/` | `qualifier-grading-engine` | Fastify service — playbook evaluation + scoring |
| `ai-orchestrator/` | `qualifier-ai-orchestrator` | Fastify service — the three Claude agents + pg-boss queue |
| `db/` | `qualifier-db` | Supabase Postgres schema, RLS, migrations, seed, pgTAP tests |

### Branches — `develop` is where the work is

Work lands on each repo's `develop`. Render builds `main`, and this repo pins
`main`. So "every pin matches `origin/main`" says nothing about undeployed
work. From 2026-08-16 to 2026-09-10, `develop` sat 27 commits ahead with the
whole presentable-MVP feature set while production ran the older code. It was
promoted on 2026-09-10. Compare with `origin/develop` before describing the
state of anything — the command is in [`RUNBOOK.md`](RUNBOOK.md) § "Branches".

Promoting is a fast-forward per repo, and it deploys — see RUNBOOK.md §
"Promote develop to main".

### Committing across submodules — get this right

Application code is committed **in the submodule**, never here. This repo only
records *which commit* of each repo the workspace is pinned to.

```bash
# 1. work and commit inside the submodule, on develop
cd web && git add -A && git commit -m "web: ..." && git push && cd ..
# 2. once it reaches main, record the new pin here
git add web && git commit -m "Bump pins: ..."
```

Pulling a fresh clone: `git submodule update --init --recursive`.
Moving every pin to upstream `main`: `git submodule update --remote`, then
commit the pointer changes here.

A submodule left at a detached HEAD is normal — that is what a pin *is*. Before
starting work in one: `git -C <path> checkout develop && git -C <path> pull`.

## Read-first order

1. [`STATUS.md`](STATUS.md) — verified current state, and what is broken.
2. [`PLAN.md`](PLAN.md) — what to do next, in order.
3. `docs/architecture.md` — module map and how the pieces talk.
4. `docs/roadmap.md` — the phased build history, with what each phase actually
   shipped. Dense but authoritative; the checkbox annotations carry real detail.
5. `docs/playbook-schema.md` and `docs/supabase-schema.md` — read before
   touching the rules engine or the database.
6. `docs/product-gap-analysis.md` — what is missing before this can be sold,
   with stable identifiers (`BLK-1`, `FUN-3`, `SEC-2`…) used across all planning
   docs. `docs/mvp-execution-plan.md` sequences them, and its "Estado
   verificado" section is the fullest status record from 2026-08-18.
7. [`RUNBOOK.md`](RUNBOOK.md) — deploy, recover, verify, demo.

## Language convention

- `docs/` and code comments: **English**.
- `docs/product-gap-analysis.md` and `docs/mvp-execution-plan.md`: **Spanish** —
  deliberately, they are business documents with a different audience.
- **The product speaks Spanish** (`FUN-7`, live since 2026-09-10), including the
  three agents' output. The target market is Salvadoran; the domain speaks of
  DUI and the SSF.

## Invariants worth not breaking

These are load-bearing decisions, each one already paid for once.

- **Rules are data, not code.** A playbook is JSON in the `playbooks` table,
  evaluated by GoRules zen-engine. Never encode a tenant's business rule in a
  TypeScript branch. This is the product thesis, not an implementation detail.
- **Scoring fails closed.** A rule that cannot be evaluated is reported as
  `indeterminate` and forces manual review. It must never silently vanish from
  the trace and let an application pass.
- **Published playbook versions are immutable**, enforced by a database trigger,
  not just by the UI. Publication goes through the `publish_playbook()` RPC so
  archive-old + publish-new is one transaction.
- **The database is the security boundary, and it takes three mechanisms.**
  Route protection in `web` is client-side only. RLS decides which *rows* a
  caller may touch — `rls_isolation_test.sql` (31 assertions) proves that read
  isolation holds. It cannot decide *columns*, which is why `role` and
  `tenant_id` are closed with column privileges instead, and it cannot express a
  *transition*, which is why deciding a case goes through `decide_case()` and
  its siblings rather than an UPDATE. `write_authorization_test.sql` (38
  assertions) covers that side, and both run in CI only since `db` `3c96a75`
  (2026-09-11) — before that the step could not pass at all. Do not add a table
  without an RLS policy and a test, and write the test from the attacker's side:
  an assertion that a role *cannot* do something.
- **The service-role key bypasses RLS and must never reach a browser.** In `web`
  it is reachable only through `src/lib/service-client.ts`, marked `server-only`
  so a client-side import is a build error.
- **`SERVICE_AUTH_TOKEN` must be byte-identical across all three services.** A
  mismatch fails closed and misreads badly: every `/score` returns 401, every
  application lands in manual review, and it looks like a scoring bug.
- **Every decision records the exact playbook version that produced it.** That
  link is what makes the audit trail worth anything.
- **Schema keys stay English, everywhere.** The UI and the agents speak Spanish,
  but `fields[].key` and the other schema keys are never translated — not in the
  playbook editor, not in the agent prompts. Telling an agent to answer
  everything in Spanish resolved `fields[].key` to null and still scored the
  application (from the `FUN-7` commit notes).

## Traps that have already cost time

Each of these was learned the expensive way. The reasoning is preserved in the
relevant commit message, in `docs/deployment.md`, or in
[`RUNBOOK.md`](RUNBOOK.md).

- **`DATABASE_URL` must be Supabase's session pooler.** The direct connection is
  IPv6-only and Render has no IPv6 egress; the transaction pooler (`:6543`)
  connects fine and then silently breaks pg-boss, so jobs are simply never
  picked up. Only `postgres.<ref>@aws-<region>.pooler.supabase.com:5432` works.
  Note the username is `postgres.<project-ref>`, not `postgres`.
- **`NEXT_PUBLIC_*` values are build-time, not runtime.** Next inlines them into
  the browser bundle, so they are `ARG`s in `web/Dockerfile`. Changing one
  requires a **rebuild**, not a restart — and if it is wrong the deploy still
  reports success while the browser fails with no server-side error to find.
- **Never put `sync: false` in a Render `envVarGroup`.** Render ignores such
  variables silently — no warning, no prompt, no error. Secrets go directly on
  the service's own `envVars`.
- **Literal values in `render.yaml` can come back.** A blueprint sync can
  re-apply them over a dashboard edit. The retired `claude-opus-4-1` is declared
  there as `MODEL_ESCALATION` today.
- **An API-only deploy of `ai-orchestrator` is the worst kind of broken.**
  Uploads succeed, the API returns `202`, the queue fills, nothing is ever
  scored, and nothing errors. `WORKER_MODE=embedded` (what ships) folds the
  consumer into the API so this cannot happen by omission — but it also means
  that if the API is down, *nothing is consuming the queue at all*.
- **`/health` does not prove the worker is alive.** It probes the API, which is
  fine either way. Use `/health/queue` with the bearer header, and read
  `oldest_ready_seconds` rather than queue depth — a busy worker has a deep
  queue and a tiny age; a dead one has an age that only climbs.
- **A paused Supabase project looks like a deleted one.** Its hostname stops
  resolving and the pooler answers `tenant/user postgres.<ref> not found`. That
  was misdiagnosed as deletion on 2026-09-06. Both free tiers sleep when idle,
  and each removes the traffic that keeps the other awake. Restore it from the
  dashboard; the data is kept.
- **`MODEL_DEFAULT` must not be a thinking model yet.** Default-path calls get
  `max_tokens` 2048, and only escalation raises it to 8192
  (`ai-orchestrator/src/agents/routing.ts`). Sonnet 5 thinks by default, and
  thinking shares that budget with the JSON the agents must return.
- **A lockfile edited on Windows can be one Linux cannot install.** `npm audit
  fix` here — especially twice, or after an `--omit=dev` run pruned the tree —
  can leave a `package-lock.json` missing entries for packages that only resolve
  on Linux (the `@emnapi/*` packages reached through `sharp`'s wasm fallback did
  it on 2026-09-12). `npm ci` passes locally, because those optional packages
  are not installed here, and then the deploy dies in thirteen seconds with
  `npm error code EUSAGE … Missing: @emnapi/runtime@… from lock file`.
  `npm install --package-lock-only` does **not** repair it: npm answers "up to
  date" and keeps the hole. Delete `node_modules` *and* the lockfile, then
  `npm install`. Only the image build proves a lockfile.
- **Secrets live in one git-ignored file**, `qualifier-secrets.env.txt`. Never
  paste it into a chat or open it with file tools — a changed file can be echoed
  into the conversation. Read it with scripts that print key names only.
- **`<html lang>` does not tell you which `web` build is live** — it is `en` in
  both the English and the Spanish builds. Look for UI text instead, such as the
  sign-in page's "Iniciar sesión".

## Deployed environment

Render (workspace `tea-cspp9nl6l47c73cu695g`, region `ohio`), one blueprint per
repo, all three services on `plan: free`, deploying `main` on push. Free-tier
consequences — spin-down after 15 idle minutes, ~1 minute cold start, 750
instance-hours/month — are real and are discussed in `docs/deployment.md`. Warm
every service before a demo.

Supabase project `jskuoazhcgfyetxrmxyi` (`us-east-1`, free plan) hosts Postgres,
Auth and Storage. **It is production, and the only project** — there is no dev
environment yet (`BLK-4`), so never point a local orchestrator at it. Its
tenants are `seguros` (life) and `medico` (health). `roadmap.md`'s older
entries call them `acme-life` and `bright-auto`; the UUIDs are the same.

## Conventions

- Commit subjects are prefixed with the repo: `web: …`, `db: …`. Bodies explain
  *why*, and the existing history sets a high bar worth matching.
- Migrations are timestamped and append-only. Never edit an applied migration —
  add a new one. Production's ledger records migrations under apply-time
  versions, so its names will not match the files; compare content, not names.
- Tests: `grading-engine` and `ai-orchestrator` use vitest; `db` uses pgTAP in
  CI against real Postgres. **`web` has no tests at all** (`CAL-3`) — the repo
  with the most churn and all the business flow. Its production build is the
  strongest check available there.
