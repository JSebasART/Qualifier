# Status — verified 2026-09-12

Measured against the running services, the production database (read only) and
the repos. Service checks ran 2026-09-11 from 20:12 UTC; nothing has been
deployed since, so they still describe production. The code checks below ran on
2026-09-12.

**Headline.** Production is unchanged since the 2026-09-10 promotion and has
still processed nothing (`BLK-5` is open). Six commits now sit on `develop`,
**unpushed**, carrying the 2026-09-11 audit's fixes: every critical, high and
medium finding. Production therefore still has all of them, including a
Next.js version with two critical RCE advisories.

**The next action has an order that is not optional.** The database migration
`20260911000000` must be applied *before* the new `web` build is promoted. The
case screen now calls functions that migration creates; with the migration but
without the build, the old direct writes are refused.

## 0. How we got here

- **2026-09-06** — this file said the Supabase project had been deleted and
  every pin was current. Both were wrong. The project was *paused*, and pins had
  only been compared with `main`, missing a `develop` branch 27 commits ahead.
- **2026-09-10** — the project was restored with all data intact, Render's
  environment re-entered from the secrets file, and `develop` promoted to `main`
  in all five repos.
- **2026-09-11** — re-verified; dependency patches and a `db` CI fix committed;
  the whole project audited (§ 4).
- **2026-09-12** — the audit's critical, high and medium findings fixed and
  re-audited. Nothing pushed.

## 1. Services

| Service | Deployed commit | Live since (UTC) | Check, 2026-09-11 20:12 UTC |
| --- | --- | --- | --- |
| `qualifier-grading-engine` | `891a435` | 2026-09-11 00:57 | `/health` 200; accepts the token (`/score` answers 400 to an empty body, not 401) |
| `qualifier-ai-orchestrator` | `5b57702` | 2026-09-11 00:57 | `/health` 200; `/health/queue` `ok`, three queues empty, `dead_letter` 0 |
| `qualifier-web` | `5d7d8de` | 2026-09-11 00:57 | 200 |

- All three answered after a cold start of about 12 s, with no error or warning
  log lines since the deploys.
- The orchestrator spun down at 01:14 UTC and stayed down until the 20:12 probe.
  Nothing used it in between, and the grading engine's only `/score` call all
  day was that probe.
- Production still answers an unauthenticated `POST /api/playbooks/test` by
  forwarding it to the grading engine (audit `M1`), because the fix is not
  deployed.

## 2. Repositories

`main` equals the umbrella's pins and is what is deployed. `develop` is ahead in
all five repos, all of it local.

| Repo | `main` (deployed) | `develop` (local) | What it adds |
| --- | --- | --- | --- |
| `db` | `b522794` | `66208c2` | CI fix (2026-09-11), then the write-authorization migration and its 38-assertion suite |
| `web` | `5d7d8de` | `9d65674` | Next.js 16.3.5, then case decisions through RPCs, the playbook-test route authenticated, security headers |
| `ai-orchestrator` | `5b57702` | `afee9ce` | fastify patch, then tenant assertions, resumable processing, escalation model, CI on `develop` |
| `grading-engine` | `891a435` | `f9320bc` | fastify patch, then CI on `develop` |
| `docs` | `ce31b99` | `5a5baa3` | CI on `develop` |

Verification on 2026-09-12:

- **`db`:** the CI workflow replayed step by step against PGlite — 79 assertions
  across three pgTAP suites, all passing (31 read isolation, 38 write
  authorization, 10 publish).
- **`ai-orchestrator`:** typecheck, 70 tests (63 before).
- **`grading-engine`:** typecheck, 51 tests.
- **`web`:** typecheck, lint, production build. The built app was then run
  locally and probed: `/api/playbooks/test` answers 401 unauthenticated, and all
  six security headers are present.
- **The audit's twelve probes:** 12 of 12 pass against the fixed schema, each
  refused by a named mechanism (column privileges, revoked grants, composite
  foreign keys).

## 3. The database — `jskuoazhcgfyetxrmxyi`

Production, and the only project. Up, not paused, and **still on the old
schema** — `20260911000000` has not been applied. Contents are unchanged from
the demo portfolio seeded on 2026-08-18:

- two tenants, `seguros` and `medico`, each with one published v1 playbook;
- 14 clients, 15 applications, 11 cases, 28 documents, 11 scores;
- 11 audit entries, all seeded `system application.scored`;
- 9 staff profiles and 11 auth users, one sign-in since the promotion
  (2026-09-11 02:11 UTC);
- `ai_usage` 0, pg-boss jobs 0.

Every constraint the new migration adds is already satisfied by this data: no
cross-tenant references, no duplicate open cases, every storage path inside its
own application's folder, and only the superadmin without a tenant.

## 4. Audit — found 2026-09-11, fixed 2026-09-12

Full report: [`audit/2026-09-11-report.html`](audit/2026-09-11-report.html).
The twelve probes are [`audit/2026-09-11-probes.sql`](audit/2026-09-11-probes.sql);
their durable form is now `db`'s `write_authorization_test.sql`, which runs on
every push.

RLS isolated tenants' reads and almost nothing else. Twelve probes, all failing.
**Twelve of the fifteen findings are fixed** (every critical, high and medium);
the three left are low.

| | Finding | State |
| --- | --- | --- |
| `C1` | a tenant admin could promote themselves to superadmin | fixed — column privileges, `set_staff_role()` |
| `H1` | underwriters could write scores, including into another tenant | fixed — policy dropped, grants revoked |
| `H2` | an agent could approve applications and resolve cases | fixed — role-checked RPCs own the transitions |
| `H3` | no decision had ever reached `audit_log` | fixed — the RPCs write it, from `auth.uid()` |
| `M1` | the playbook-test route answered anyone | fixed — staff session required, body capped |
| `M2` | the pipeline followed cross-tenant pointers | fixed — composite FKs, plus read-time assertions |
| `M3` | the anon key could list every tenant's products | fixed — leftover policy dropped |
| `M4` | staff could forge `system` audit entries | fixed — insert revoked |
| `M5` | re-running an application duplicated score, case and spend | fixed — resumable, with a unique open-case index |
| `M6` | CI ran only on `main` in four repos | fixed — `develop` added everywhere |
| `M7` | no security headers | fixed — headers added, CSP report-only |
| `M8` | the escalation model was retired | fixed — `claude-sonnet-5` in the blueprint |
| `L1` `L2` `L3` | vitest dev advisories, `/analyze` live in production, pgTAP installed in production | open |

## 5. Open issues and risks

1. **Nothing is deployed.** Production runs the old code, with every finding
   above still live, including Next.js 16.2.12's critical advisories.
2. **Deploy order.** Migration first, then promote. See the headline.
3. **`BLK-5`: no application has gone through the deployed pipeline.** The
   Spanish narrative has never been observed.
4. **`MODEL_DEFAULT`.** The secrets file still says `claude-sonnet-5`, which the
   default path's 2048-token budget can't carry. Render runs
   `claude-sonnet-4-5`; keep it.
5. **One Supabase project, and it is production** (`BLK-4`). Idle enough to
   pause again.
6. **Nothing watches it** (`NEG-2`).
7. **`render-blocks.env` is still on disk.** An automated delete was blocked;
   delete it by hand. Everything in it is in the secrets file or is a public URL.

## 6. Not verified

- Signing in to the web app. That needs staff credentials, which were not used.
- GitHub Actions results — private repos, no `gh` CLI here. The `db` fix needs
  its first real run, which is also the only thing the local replay cannot
  exercise: the apt package that provides `pg_prove`.
- The new RPCs against production, since the migration is not applied there.
- Prompt-injection resistance of the three agents against hostile document
  content. Out of scope for this audit, and worth its own pass.
