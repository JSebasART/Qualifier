# Status — verified 2026-09-13

Measured against the running services, the production database (read only) and
the repos. § 1 and § 3 were re-checked on 2026-09-13 around 20:10 UTC, after the
`web` deploy. The rest of § 2 is from 2026-09-12 07:34–07:44 UTC.

**Headline.** The 2026-09-11 audit's fixes are live. Every critical, high and
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
  extraction agent, on `ai-orchestrator` `develop` (`a1908f2`), **not promoted**.
  Until it is, real documents still come back with keys the playbooks don't read.

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

`web` redeployed and checked 2026-09-13 ~20:10 UTC. The other two are unchanged
since their 2026-09-12 07:43 UTC check.

| Service | Deployed commit | Check |
| --- | --- | --- |
| `qualifier-web` | `3170a77` (live 2026-09-13 22:23 UTC; the checks here are from `45cb1c6` and repeated for `3170a77` from outside: API 401s, redirects, headers, and the new sign-in copy in the served bundle) | `/` 200. In a browser the sign-in form renders against the real Supabase, with "¿Olvidaste tu contraseña?", both toast live regions mounted, and no console errors. `lang="es"`. `/cases` and `/register` 307 to `/?next=…`. `/set-password` 200, unknown path 404 in Spanish. All ten API routes answer **401** unauthenticated. HSTS, frame, nosniff, referrer and permissions headers present, CSP report-only. |
| `qualifier-grading-engine` | `a828460` | `/health` 200; `/score` answers 400 to an empty body, so the token is accepted |
| `qualifier-ai-orchestrator` | `5985020` (deploy `dep-dajhm9gjo6nc73ce2ur0`, live 2026-09-13 21:53 UTC) | Extraction and scoring both ran for the QA application: two `document.extract` jobs completed, and `application.process` completed on its fifth attempt, the first on this build |

`docs` is at `5a5baa3` and `db` at `02b0414`; neither deploys anything.

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

| Repo | `main` | What landed most recently |
| --- | --- | --- |
| `db` | `02b0414` | 2026-09-13: staff management, intake inserts that start at the start, client changes audited; three pgTAP suites (48 assertions) |
| `web` | `45cb1c6` | 2026-09-13: the web audit's findings, test accounts script, 42 unit tests on Node's runner (in CI), toasts |
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

1. **`BLK-5`, partly done.** One fictitious application went through extraction
   and scoring on 2026-09-13. Its documents were marked "ficticio", so the model
   flagged them and scoring was blocked: the consistency agent, the narrator and
   grading-engine did not run on real extractions. No decision, assignment or
   comment has been made signed in.
2. **Extraction field names don't match the playbooks — fixed on `develop`
   (`a1908f2`), not deployed.** `extraction-agent.ts`
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
