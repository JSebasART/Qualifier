# Status — verified 2026-09-11

Measured against the running services, the production database (read only)
and the repos, not inferred from documents. Checks ran on 2026-09-11 from
20:12 UTC (the afternoon in El Salvador).

**Headline.** Production is healthy and unchanged since the 2026-09-10
promotion, and nobody has used it. There has been one staff sign-in and no
application has been processed, so `BLK-5` is still open. Today's work is
committed on `develop` in four repos but **not pushed**:

- a Next.js upgrade out of two critical RCE advisories, which production is
  still exposed to;
- dependency patches for both Fastify services;
- a `db` CI that had been red since 2026-07-31.

An audit the same day found that RLS isolates tenants' *reads* but not their
writes or their roles. It found one critical and three high findings, all in
the database policies and the case screen (§ 4).

## 0. How we got here

- **2026-09-06** — this file said the Supabase project had been deleted and
  every pin was current. Both were wrong. The project was *paused* (a paused
  project stops resolving and its pooler answers "tenant not found", exactly
  like a deleted one), and pins had only been compared with `main`, missing a
  `develop` branch 27 commits ahead.
- **2026-09-10** — the project was restored with all data intact. Render's
  environment was re-entered from `qualifier-secrets.env.txt`, and `develop` was
  fast-forwarded into `main` in all five repos and deployed.
- **2026-09-11** — re-verified, housekeeping done on `develop`, and the whole
  project audited.

## 1. Services

| Service | Deployed commit | Live since (UTC) | Check, 2026-09-11 20:12 UTC |
| --- | --- | --- | --- |
| `qualifier-grading-engine` | `891a435` | 2026-09-11 00:57 | `/health` 200; accepts the token (`/score` answers 400 to an empty body, not 401) |
| `qualifier-ai-orchestrator` | `5b57702` | 2026-09-11 00:57 | `/health` 200; `/health/queue` `ok`, three queues empty, `dead_letter` 0 |
| `qualifier-web` | `5d7d8de` | 2026-09-11 00:57 | 200 |

- All three answered after a cold start of about 12 s. No error or warning log
  lines since the deploys.
- The orchestrator spun down at 01:14 UTC and stayed down until the 20:12 probe,
  so nothing used it in between. The grading engine's only `/score` call all
  day was that probe.
- Unauthenticated POSTs: `/api/documents/…/extract` and `/api/users` answer
  401, as they should. `/api/playbooks/test` forwards to the grading engine
  (audit `M1`).

## 2. Repositories

`main` equals the umbrella's pins and is what is deployed. `develop` is ahead by
one local, unpushed commit in four repos.

| Repo | `main` (pinned, deployed) | `develop` (local) | What it adds |
| --- | --- | --- | --- |
| `docs` | `ce31b99` | = `main` | — |
| `db` | `b522794` | `3c96a75` | CI fixed: real `auth.users` stub columns, pgcrypto, `pg_prove` over every suite, runs on `develop` |
| `grading-engine` | `891a435` | `dbc40a1` | fastify 5.12.4, fast-uri |
| `ai-orchestrator` | `5b57702` | `f6c7a3a` | fastify 5.12.4, fast-uri |
| `web` | `5d7d8de` | `2c6b73e` | Next.js 16.3.5 (GHSA-2xp9-vwfh-vxw4, GHSA-p293-qw3h-jr36), sharp, postcss |

How each was verified:

- **Fastify services:** typecheck plus tests, 63 in ai-orchestrator and 51 in
  grading-engine.
- **`web`:** typecheck, lint and a production build.
- **Dependencies:** `npm audit` is clean for the production tree of all three
  Node services. What remains is vitest's dev-only tree (audit `L1`).
- **`db` CI:** replayed step by step against PGlite. Before the fix it fails at
  `column "instance_id" of relation "users" does not exist`; after it, both
  suites pass (41/41). The fix has not yet run on a GitHub runner.

Promoting deploys every changed service. See RUNBOOK.md § "Promote develop to
main".

## 3. The database — `jskuoazhcgfyetxrmxyi`

Production, and the only project. Up and not paused. Contents are unchanged
from the demo portfolio seeded on 2026-08-18:

- two tenants, `seguros` and `medico`, each with one published v1 playbook;
- 14 clients, 15 applications, 11 cases, 28 documents, 11 scores;
- 11 audit entries, all seeded `system application.scored`;
- 9 staff profiles and 11 auth users;
- `ai_usage` 0, pg-boss jobs 0.

Other checks:

- **Sign-ins:** one since the promotion, at 2026-09-11 02:11 UTC.
- **Schema:** every public table has RLS on and at least one policy. The
  documents bucket is private, capped at 5 MB, and allowlists MIME types. Views
  run as `security_invoker`.

## 4. Audit — 2026-09-11

Full report: [`audit/2026-09-11-report.html`](audit/2026-09-11-report.html).
The twelve probes are in [`audit/2026-09-11-probes.sql`](audit/2026-09-11-probes.sql),
ready to move into `db`'s pgTAP suite as each fix lands. Findings were reproduced against the repo's migrations in a local
Postgres 17 replay, with twelve probes. Production's policies were read from
its catalog and match the repo's. Nothing was attempted against production.

- **C1 (critical)** — a `tenant_admin` can promote themselves to `superadmin`
  through their own `profiles` row, and then read and write every tenant. The
  policy's check reads the pre-update role.
- **H1** — underwriters can insert `scores`, including into another tenant.
- **H2** — an `agent` can approve applications and resolve cases. Decision
  authority exists only in React.
- **H3** — the case screen's audit entries and comments are rejected by RLS
  (they omit `tenant_id`), and the UI ignores the error. No decision made in the
  UI has ever reached `audit_log`.
- **Medium:**
  - `M1` — the playbook-test proxy is unauthenticated.
  - `M2` — the pipeline follows cross-tenant pointers.
  - `M3` — the anon key can list every tenant's products.
  - `M4` — staff can forge `system` audit entries.
  - `M5` — processing isn't idempotent.
  - `M6` — CI runs only on `main` in four repos.
  - `M7` — the web app sends no security headers.
  - `M8` — the escalation model is retired.
- **Low:** `L1` vitest dev advisories, `L2` `/analyze` live in production,
  `L3` pgTAP installed in production.

## 5. Open issues and risks

1. **Production runs Next.js 16.2.12** until `develop` is pushed and promoted.
2. **Audit C1 and H1–H3.** Fix them before real data, and before the demo's
   final beat: an underwriter's decision that today leaves no record.
3. **`BLK-5`: no application has gone through the deployed pipeline.** The
   Spanish narrative has never been observed.
4. **Models.** `render.yaml` still declares the retired `claude-opus-4-1` for
   escalation. The secrets file still says `MODEL_DEFAULT=claude-sonnet-5`,
   which the default token budget can't carry.
5. **One Supabase project, and it is production** (`BLK-4`). It is idle enough
   to pause again.
6. **Nothing watches it** (`NEG-2`).
7. **`render-blocks.env` is still on disk.** An automated delete was blocked;
   delete it by hand. Everything in it is in the secrets file or is a public
   URL.

## 6. Not verified

- Signing in to the web app. That needs staff credentials, which were not used.
- GitHub Actions results. The repos are private and there is no `gh` CLI here.
  That is how `db` stayed red for six weeks unnoticed. Its fix needs its first
  real run, to prove the apt package that provides `pg_prove`.
- The Supabase MCP connector refused queries with a permission error. The
  database was read with a read-only script instead, and the connection string
  was never printed.
