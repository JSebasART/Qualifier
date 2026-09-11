# Runbook

Operational procedures. `docs/deployment.md` explains *why* the deployment is
shaped the way it is and is worth reading once; this file is what you run.

Current state: [`STATUS.md`](STATUS.md). Next steps: [`PLAN.md`](PLAN.md).

## Identifiers

| Thing | Value |
| --- | --- |
| Render workspace | `tea-cspp9nl6l47c73cu695g` (region `ohio`, free plan) |
| `qualifier-web` | `srv-da0nst5bedkc73b76bc0` — https://qualifier-web.onrender.com |
| `qualifier-grading-engine` | `srv-da0n6ak9v7es739oo1eg` — https://qualifier-grading-engine.onrender.com |
| `qualifier-ai-orchestrator` | `srv-da0n7dlbedkc73b5lg8g` — https://qualifier-ai-orchestrator.onrender.com |
| Supabase project | `jskuoazhcgfyetxrmxyi` (`us-east-1`, free plan) — **production**, and the only one |

Tenants in production: `seguros` (`00000000-0000-0000-0000-000000000001`) and
`medico` (`00000000-0000-0000-0000-000000000011`).

## Branches

Work lands on each repo's `develop`. Render builds `main`. The umbrella pins
`main`. Comparing a pin with `origin/main` says nothing about undeployed work —
compare with `origin/develop` too:

```bash
for r in docs db web grading-engine ai-orchestrator; do git -C "$r" fetch -q origin && echo "$r: $(git -C "$r" rev-list --count origin/main..origin/develop) commits on develop not on main"; done
```

## Secrets

One git-ignored file holds every value: `qualifier-secrets.env.txt` at the
umbrella root. Every value is entered once, and scripts copy it wherever it is
needed.

- **Never paste its contents into a chat**, and don't open it with an agent's
  file tools: some harnesses echo a changed file's contents into the
  conversation. Scripts that read it print key names only.
- Render paste blocks are generated from it into `render-blocks.env.txt`, one
  block per service. Both that name and a renamed `render-blocks.env` are
  git-ignored (`*.env.txt`, `*.env`). Delete the file after use, and regenerate
  it after changing the secrets file.
- `SERVICE_AUTH_TOKEN` must be **byte-identical in all three services**. A
  mismatch fails closed: every `/score` returns 401, every application lands in
  manual review, and it reads like a scoring bug.

### Applying the secrets to Render

In each service: **Environment → Add from .env**, paste its block, then **Save,
rebuild, and deploy**. Order: grading-engine, ai-orchestrator, web.

The blocks leave out `MODEL_*`, `WORKER_MODE`, `LOG_LEVEL` and
`QUEUE_STALL_SECONDS`, which `render.yaml` declares as literal values.

Confirm the token afterwards: `/health/queue` should answer 200 with the file's
token (below), and grading-engine's `/score` should answer an empty body with
400, not 401:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $(grep '^SERVICE_AUTH_TOKEN=' qualifier-secrets.env.txt | cut -d= -f2 | tr -d '\r ')" -H "Content-Type: application/json" -d '{}' https://qualifier-grading-engine.onrender.com/score
```

## Health checks

Liveness, no credentials needed — this is what Render probes:

```bash
curl -sS https://qualifier-grading-engine.onrender.com/health
```

```bash
curl -sS https://qualifier-ai-orchestrator.onrender.com/health
```

Whether the **queue consumer** is alive, which the checks above cannot answer —
the API is fine whether or not anything is consuming:

```bash
curl -sS -H "Authorization: Bearer $(grep '^SERVICE_AUTH_TOKEN=' qualifier-secrets.env.txt | cut -d= -f2 | tr -d '\r ')" https://qualifier-ai-orchestrator.onrender.com/health/queue
```

It returns `200` with `"status":"ok"`, or **`503` with `"status":"stalled"`**
once a job has sat unclaimed longer than `QUEUE_STALL_SECONDS`, and `401` if
the token is not the one Render holds.

Read **`oldest_ready_seconds`**, not `ready`. A busy worker has a deep queue and
a tiny age; a dead worker has an age that only climbs. `dead_letter` counts jobs
that exhausted all five retries and need a human.

On the free plan the first call after 15 idle minutes pays roughly a minute of
cold start. A slow first response is not necessarily a fault.

When the orchestrator does not answer at all, read its logs in the Render
dashboard: it exits at boot, before listening, when it cannot reach Postgres. A
healthy boot logs `worker running in-process (WORKER_MODE=embedded)`. Render's
own probe of `HEAD /` gets a 401 and logs "rejected unauthenticated request";
that is expected.

To tell which `web` build is live, look for UI text — the Spanish sign-in says
"Iniciar sesión". `<html lang>` is `en` in every build, so it proves nothing.

## Promote develop to main

This deploys: Render rebuilds each service on a push to `main`. Pushes run in
deploy order — `docs` and `db` deploy nothing, then grading-engine, the
orchestrator and web.

```bash
for r in docs db grading-engine ai-orchestrator web; do git -C "$r" fetch origin && git -C "$r" checkout main && git -C "$r" merge --ff-only origin/develop && git -C "$r" push origin main || break; done
```

`--ff-only` refuses rather than creates a merge commit if `main` has diverged.
Then record the new pins:

```bash
git add docs db grading-engine ai-orchestrator web && git commit -m "Bump pins: promote develop to main"
```

Before promoting, check two things: whether `develop` adds a migration that
production does not have yet, and whether it reads an environment variable
Render lacks.

## Environment variables

**grading-engine** — `SERVICE_AUTH_TOKEN`, `LOG_LEVEL`. Stateless: it receives
the playbook in the request body. Never give it a connection string.

**ai-orchestrator** — `ANTHROPIC_API_KEY`, `DATABASE_URL`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `SERVICE_AUTH_TOKEN`, `GRADING_ENGINE_URL`,
`WORKER_MODE`, `MODEL_DEFAULT`, `MODEL_ESCALATION`, `LOG_LEVEL`,
`QUEUE_STALL_SECONDS`. The service-role key bypasses RLS by design, and must
never reach a browser.

**web** — `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `SERVICE_AUTH_TOKEN`, `AI_ORCHESTRATOR_URL`,
`GRADING_ENGINE_URL`.

### Rules that are not style preferences

**`DATABASE_URL` must be Supabase's session pooler.** Exactly one of the three
connection strings works on Render, and the two obvious choices both fail:

| Connection | Why not |
| --- | --- |
| Direct — `db.<ref>.supabase.co:5432` | IPv6-only, and Render has no IPv6 egress. Fails at boot with `ENETUNREACH`, naming no service and no variable. |
| Transaction pooler — `:6543` | Reachable, but breaks pg-boss. Worse than failing: it starts fine and jobs are simply never picked up. |
| **Session pooler — `:5432` on `pooler.supabase.com`** | **The one that works.** |

```text
postgresql://postgres.<project-ref>:<password>@aws-<region>.pooler.supabase.com:5432/postgres
```

Copy it from **Connect → Session pooler** rather than assembling it. The
username is `postgres.<project-ref>`, not `postgres`. A password containing
`@`, `:`, `/` or `#` must be URL-encoded inside the string, or authentication
fails with an error that looks like a wrong password.

**`NEXT_PUBLIC_*` are build-time.** Next inlines them into the browser bundle,
so they are `ARG`s in `web/Dockerfile`. Changing one needs **Manual Deploy →
Clear build cache & deploy**, not a restart. Get it wrong and the deploy reports
success while the browser calls the old host, with no server-side error.

**Never put `sync: false` in a Render `envVarGroup`.** Render ignores such
variables silently. Secrets go directly on the service's own `envVars`.

**Literal `value:` entries in `render.yaml` can be re-applied** on a blueprint
sync, undoing a dashboard edit to the same key. Change model settings in the
blueprint, not only in the dashboard.

## Supabase paused

A free project pauses after about a week without activity. That is what took the
system down between 2026-08-18 and 2026-09-10. The symptoms point elsewhere:

- the orchestrator crash-loops with `tenant/user postgres.<ref> not found`;
- `<ref>.supabase.co` stops resolving;
- the web app loads and nobody can sign in.

Fix: Supabase dashboard → the project → **Restore**. Data is kept. Then check
the orchestrator reconnects on its own, and restart it from Render if not.

## Staff accounts

Production already has all of them: a superadmin, and a tenant admin, agent and
underwriter in each tenant. There is no self-serve signup. New staff are created
in-app at `/register` by a `tenant_admin` or `superadmin`.

Bootstrap scripts in `web/scripts/`:

- `create-test-accounts.mjs` prompts for each password with echo off, and skips
  accounts that already exist. Prefer it; see its header for usage.
- `create-underwriter.mjs` takes the password as an argument, so it lands in
  shell history and the process table.

## Verify end to end

The real exit criterion, which no health check proves. Sign in, register an
application, upload a document, and watch a job move through:

1. `/health/queue` shows `ready: 1`, then returns to `0` within seconds.
2. The orchestrator's logs show `worker: extracting document`.
3. A scored case appears in `/cases`, with a Spanish narrative.

If `ready` climbs and never falls, nothing is consuming the queue.

## Rebuild the database from zero

For a new dev or demo project (`BLK-4`), or disaster recovery.

1. Create the project and note its ref.
2. Apply the migrations:

   ```bash
   cd db && npx supabase link --project-ref <new-project-ref> && npm run db:push
   ```

3. Seed. `db:push` does not seed. Run `db/supabase/seed.sql` through the SQL
   editor, or with `psql` against the session pooler. It is re-runnable: it
   deletes the tenants' contents before inserting, never the tenant rows, since
   deleting those would cascade to the staff profiles.
4. Verify with `cd db && npm run db:test`.
5. Create staff accounts with `create-test-accounts.mjs`.

## Local development

**Not against production.** The only Supabase project is production, and a
local orchestrator with `WORKER_MODE=embedded` consumes the production queue.
Create a dev project first (above).

```bash
cd db && npm install && npm run db:start && npm run db:reset
```

This requires Docker: the Supabase CLI runs Postgres, Auth and Storage in
containers. Then, in each service, fill `.env` (`web`: `.env.local`) and run
`npm install && npm run dev`.

## Tests

```bash
cd grading-engine && npm test
```

```bash
cd ai-orchestrator && npm test
```

```bash
cd db && npm run db:test
```

As of 2026-09-10: grading-engine 4 test files and ai-orchestrator 9, all
passing. `web` has no tests (`CAL-3`); its production build is the strongest
check available there:

```bash
cd web && npm run typecheck && npm run lint && npm run build
```

## Before a demo

1. Confirm the Supabase project is not paused.
2. Warm all three services. `web` is the one a visitor experiences.
3. Keep `/health/queue` open in a tab while it runs.
4. Have one processed application ready to fall back to, and use the retry
   button rather than restarting the demo.
5. For a high-stakes presentation, move the services to `starter` for the month.
6. Never use a real person's data, even if the prospect offers it.

The script — twelve to fifteen minutes, eight beats — is in
`docs/mvp-execution-plan.md` § "Guion sugerido".
