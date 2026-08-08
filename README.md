# Qualifier

AI-assisted underwriting / pre-qualification engine. Applicants apply for an insurance (or credit) product, the system extracts and validates documents, scores risk, and hands underwriters an explainable decision instead of a black-box number.

This is a multi-repo project. Each folder below is an **independent git repository**, tracked here as a git submodule. This repo is an umbrella index — it holds no application code of its own.

| Repo | Path | Purpose |
|---|---|---|
| `qualifier-docs` | `docs/` | Architecture, playbook schema, Supabase schema, roadmap |
| `qualifier-web` | `web/` | Next.js app — applicant portal + underwriter/admin dashboard |
| `qualifier-grading-engine` | `grading-engine/` | Rules + scoring service (deterministic playbook evaluation) |
| `qualifier-ai-orchestrator` | `ai-orchestrator/` | Extraction / consistency / risk-narrator agents against the Claude API |
| `qualifier-db` | `db/` | Supabase Postgres schema, RLS policies, migrations, seed data |

## Clone

```
git clone --recurse-submodules git@github.com:JSebasART/Qualifier.git
```

Already cloned without the flag? `git submodule update --init --recursive`.

Each submodule tracks its own `main`. To move them all up to their latest
upstream commits: `git submodule update --remote`, then commit the resulting
pointer changes here.

## Start here

1. Read `docs/architecture.md` for the module map and how the pieces talk to each other.
2. Read `docs/roadmap.md` for the phased build plan (MVP → multi-tenant → scale-out).
3. Read `docs/playbook-schema.md` and `docs/supabase-schema.md` before touching the rules engine or the database.

## Local dev (once services are wired together)

Each repo has its own `README.md` with setup instructions. At a glance:

- `db/` — apply migrations to a local or hosted Supabase project first.
- `grading-engine/` and `ai-orchestrator/` — copy `.env.example` to `.env`, `npm install`, `npm run dev`.
- `web/` — `npm install`, `npm run dev`, needs the Supabase project URL/anon key and the grading-engine URL.

Commit application code in the submodule repos themselves, not here. This repo
only records *which commit* of each repo the workspace is pinned to; after
pushing a submodule, commit its updated pointer here to keep the pin current.
