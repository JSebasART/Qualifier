# Status — verified 2026-09-12

Measured against the running services, the production database (read only) and
the repos. The checks below ran between 07:34 and 07:44 UTC on 2026-09-12,
after the deploy.

**Headline.** The 2026-09-11 audit's fixes are live. Every critical, high and
medium finding is closed in production: the write side of the database is
authorised, the case screen's decisions go through role-checked functions that
record what happened, the playbook-test route no longer answers strangers, and
`web` runs Next.js 16.3.5 instead of a version with two critical RCE advisories.

What has still never happened is a real pipeline run (`BLK-5`), and now also a
signed-in pass through the new decision path. Nothing has exercised the RPCs
with a real session.

> **2026-09-13: production's database is ahead of production's `web`.** The
> three migrations from the 2026-09-12 web audit are applied (§ 2), but that
> audit's `web` work is only on `develop` (`45cb1c6`, pushed, not promoted).
> Until it is promoted, the live "Registrar y enviar" button fails: it inserts
> an application already `submitted`, which `20260912000100` now refuses. Saving
> a draft and submitting it from the application's page still works. **Promote
> `web` next.** § 1 and § 3 below still describe 2026-09-12.

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
- **2026-09-13** — the web audit's three migrations applied to production.
  `develop` pushed in `web` (15 commits, including toasts) and `db` (3); neither
  promoted.

## 1. Services

All three live, checked 2026-09-12 07:43 UTC.

| Service | Deployed commit | Check |
| --- | --- | --- |
| `qualifier-web` | `3b40927` | `/` 200; `/api/playbooks/test` **401** unauthenticated; `/api/users` and `/api/documents/…/extract` 401; all six security headers present, CSP naming the real Supabase origin; no `x-powered-by` |
| `qualifier-grading-engine` | `a828460` | `/health` 200; `/score` answers 400 to an empty body, so the token is accepted |
| `qualifier-ai-orchestrator` | `afee9ce` | `/health/queue` 200 `ok`, three queues empty, `dead_letter` 0 |

`docs` is at `5a5baa3` and `db` at `66208c2`; neither deploys anything.

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

The security advisor raised nothing new: its warnings are the by-design
`SECURITY DEFINER` RPCs, pg-boss's search paths and leaked-password protection
being off.

Contents are unchanged from the demo portfolio seeded on 2026-08-18: two
tenants, 14 clients, 15 applications, 11 cases, 28 documents, 11 scores, 11
audit entries (all seeded), 9 staff profiles, 11 auth users, `ai_usage` 0, no
pg-boss jobs.

## 3. Repositories

`main` equals `develop` equals the umbrella's pins in all five repos, and all of
it is pushed.

| Repo | `main` | What landed today |
| --- | --- | --- |
| `db` | `66208c2` | write-authorization migration, 38-assertion suite, CI mirroring Supabase's default privileges |
| `web` | `3b40927` | decisions via RPCs, route authenticated, security headers, rebuilt lockfile |
| `ai-orchestrator` | `afee9ce` | tenant assertions, resumable processing, escalation model, CI on `develop` |
| `grading-engine` | `a828460` | CI on `develop`, rebuilt lockfile |
| `docs` | `5a5baa3` | CI on `develop` |

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

1. **`BLK-5`: no application has gone through the pipeline**, and no signed-in
   session has exercised the new decision path. Both belong to the same smoke
   test (PLAN.md step 1).
2. **`MODEL_DEFAULT`.** The secrets file still says `claude-sonnet-5`, which the
   default path's 2048-token budget can't carry. Render runs `claude-sonnet-4-5`;
   keep it. `MODEL_ESCALATION` is now `claude-sonnet-5` in the blueprint.
3. **One Supabase project, and it is production** (`BLK-4`), with no rehearsed
   restore.
4. **Nothing watches it** (`NEG-2`).
5. **`render-blocks.env` is still on disk.** An automated delete was blocked;
   delete it by hand.
6. The three low audit findings.

## 7. Not verified

- A signed-in pass through the UI: a real decision landing in `audit_log`, an
  assignment, a submission. This is the first thing to do.
- GitHub Actions results. The repos are private and there is no `gh` CLI here.
  CI ran on `develop` for the first time today; nobody has read the outcome, and
  `db`'s `pg_prove` step has still never run on a real runner.
- Prompt-injection resistance of the three agents against hostile document
  content. Out of scope for the audit, and worth its own pass before real
  applicants' files arrive.
