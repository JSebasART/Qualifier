# Sales readiness — 2026-10-16

What it takes to sell Qualifier, measured against the running services, the
production database and the five repos on 2026-10-16 (around 23:45–00:10 UTC).
Gap identifiers (`BLK-4`, `CAL-1`…) are the ones in
`docs/product-gap-analysis.md`.

## Verdict

**You can sell a pilot now, with close support. You cannot sell a product yet.**

The engine is the hard part, and it is done well: rules as versioned data,
scoring that fails closed, an explainable case file, database-enforced tenant
isolation, and a Spanish-speaking pipeline. What is missing is proof (no
accuracy number, no cost per case, no end-to-end run with the narrator), keeping
it running (it was down when this audit started), and the paperwork a regulated
buyer asks for (security answers, privacy notice, data processing agreement,
SSF review).

The order that follows: four things before any demo (days), then a pilot-ready
package (`Corte A`, weeks), then the repeatable product (`Corte B`).

## 1. What is live today

### The system was down

**The Supabase project was paused** (`status: INACTIVE`). Every sign-in, every
list and every upload failed. The orchestrator could not boot without its
database, so `/health` timed out after 90 and 120 s. It was **restored during
this audit** and came back `ACTIVE_HEALTHY` with its data intact. Then the
orchestrator answered `/health` 200 in 0.5 s.

This is the trap described in CLAUDE.md: both free tiers sleep when idle. A
prospect who opens the link a week after a demo sees a dead product.

### Services (Render, `ohio`, all `plan: free`)

| Service | Live deploy | Check today |
| --- | --- | --- |
| `qualifier-web` | `adf7ae7` (2026-09-14) | `/` 200 after a 13.8 s cold start; CSP enforced, HSTS present |
| `qualifier-grading-engine` | `a828460` (2026-09-12) | `/health` 200 after a 12.7 s cold start |
| `qualifier-ai-orchestrator` | `fb21538` (2026-09-14) | timed out while the DB was paused; `/health` 200 once it was restored |

Nothing has been deployed since 2026-09-14. In all five repos, `main` equals
`develop` equals the umbrella pin, and nothing is dirty or unpushed.

### Database (`jskuoazhcgfyetxrmxyi`, Postgres 17, `us-east-1`, free)

- **Nobody has used it for a month.** The last sign-in and the last `audit_log`
  row are both 2026-09-13 22:41 UTC. The synthetic documents in
  `qa/2026-10-02/` were prepared for a `BLK-5` run that never reached
  production: no audit rows and no `ai_usage` rows after 2026-09-13.
- **No decision has ever been recorded.** `audit_log` holds 19 rows, and none
  is `case.approved`, `case.declined`, `case.info_requested` or
  `case.assigned`. `decide_case()` has never run with a real session.
- **Only extraction has ever been measured.** `ai_usage` has 3 rows, all
  extraction on `claude-sonnet-4-5`, at 2.0–2.9 k input and 0.5–0.9 k output
  tokens. The consistency agent and the narrator have no measured cost. At
  Sonnet 4.5's list price ($3 / $15 per million tokens; check current pricing)
  that is about 2 US cents per document.
- **Demo data has aged again.** 5 cases are past their SLA, against 4 when the
  dates were moved on 2026-09-15. Re-run the date shift (or the seed) before a
  demo.
- Contents: 2 tenants (`seguros` life, `medico` health, both with branding
  set), 2 published playbooks (v1 each), 14 clients, 15 applications, 28
  documents, 11 scores, 11 cases (5 in review, 2 waiting on the applicant, 4
  resolved), 16 staff profiles (2 superadmin, 5 tenant_admin, 4 underwriter, 5
  agent), 18 auth users. The QA run's leftover files are still in Storage (4
  objects in all).
- Storage bucket: 5 MB limit, PDF and images only (`SEC-3`, closed).
- 21 migrations in the ledger, latest `20260914172008`. `pgtap` is still
  installed (`L3`).

### Security advisor (today)

Expected by design: the eight `SECURITY DEFINER` staff RPCs and pg-boss's two
search paths. Still open and cheap to fix:

- **Anonymous sign-ins are enabled.** Nothing uses them, and the advisor flags
  every table's policies because of it (`SEC-7`).
- **`app_current_role()` and `current_tenant_id()` are executable by `anon`**
  over `/rest/v1/rpc` (`SEC-7`).
- **Leaked-password protection is off.**

## 2. The strong points: what to sell

Each claim has evidence a buyer's technical team can check. The website uses
only these.

1. **Explainable decisions.** Every score stores its `rule_trace`, the AI risk
   narrative, the flags and the exact playbook version that produced it. The
   underwriter sees why, rule by rule.
2. **It fails closed.** A rule that cannot be evaluated (an unreadable value, a
   missing document) becomes `indeterminate` and forces manual review. It never
   passes silently. The same applies to stale or undated documents
   (`max_age_days`, enforced since 2026-09-13).
3. **The insurer's rules are data, not code.** Playbooks are JSON on GoRules
   zen-engine, edited in a visual builder with draft → publish, a test panel,
   a diff between versions, atomic publication, and **immutability enforced by
   a database trigger**. Changing underwriting criteria needs no developer.
4. **Real multi-tenancy.** Isolation is enforced in Postgres (RLS + column
   privileges + role-checked functions), not in the UI. **157 pgTAP assertions**
   are written from the attacker's side. The two demo tenants are different
   lines of business: different documents, rules, formulas and rating scales.
5. **Complete audit trail.** `audit_log` is append-only and not writable by
   users. Decisions, assignments, submissions, client changes, document views
   and sign-ins are recorded server-side.
6. **Built for the Salvadoran market.** The interface and the three agents'
   output are in Spanish. It understands the DUI, salary certificates, lab
   results and medical reports, reads "US$ 2,000.00" as a number, and parses
   Salvadoran dates.
7. **Document intelligence.** Claude reads PDFs and photos directly (vision), so
   there is no separate OCR. It extracts the keys the playbook asks for, checks
   them against the form answers, and flags inconsistencies and tampering.
8. **An operational workspace.** A case queue with SLA deadlines per product,
   assignment, information requests, comments, a document preview beside the
   extracted fields, drag-and-drop uploads, lists that search, sort and export
   CSV, bulk rescoring, staff management with invitation and recovery links,
   and per-tenant branding.
9. **Durable pipeline.** pg-boss on Postgres, with 5 retries, exponential
   backoff, a dead-letter queue and deduplication. A partly processed
   application resumes instead of repeating.
10. **Hardened web layer.** An enforced CSP, HSTS, rate limits on credential
    routes, a service key that cannot reach the browser (a build error), and
    Next.js kept on patched versions.
11. **Product-agnostic.** The same pattern (documents → extraction → rules →
    score → decision) serves life, health, auto or credit pre-qualification.

**Do not claim** (not true or not measured yet): an accuracy rate, a processing
time, a cost per case, MFA, malware scanning, email notifications,
integrations, a certification (SOC 2 or ISO 27001), data residency in El
Salvador, customer logos or testimonials.

## 3. What is missing to sell it

### Tier 0: before any demo (1–3 days)

| # | Item | Why it blocks |
| --- | --- | --- |
| 0.1 | **Keep it awake.** Supabase Pro ($25/month) or uptime pings every ~10 min on all three services and the DB. | It was paused today. A dead link after a demo loses the deal. |
| 0.2 | **Run `BLK-5` with `qa/2026-10-02/`**, end to end, in both tenants, then decide one case as an underwriter. | The narrator, the consistency agent and `decide_case()` have never produced a row in production. The demo's core beat is unproven. |
| 0.3 | **Fix the auth basics.** Site URL in Authentication → URL Configuration (the reset link may point at `localhost`), leaked-password protection on, anonymous sign-ins off. | A prospect's first "forgot password" email would break. |
| 0.4 | **Refresh the demo data.** Shift the seeded dates and remove the QA leftovers. | 5 overdue cases make the queue look neglected. |

### Tier 1: before signing a paid pilot (`Corte A`, 4–8 weeks)

| Item | IDs | Notes |
| --- | --- | --- |
| **Accuracy number** on 30–50 synthetic or consented Salvadoran documents per type | `CAL-1` | The first question every buyer asks, and today's answer is "unknown". A good, audited number is also the best sales asset. |
| **Cost per application**, full pipeline | `NEG-1` | Needed before any price goes on paper. Only extraction has been measured. |
| **Separate environments, backups, a rehearsed restore** | `BLK-4` | Production is the only project, on a free plan, with no restore ever run. |
| **Monitoring and alerts** on `/health/queue` (`oldest_ready_seconds`) | `NEG-2` | A dead worker is silent. |
| **Email provider** for invitations, password resets and notifications | `BLK-6`, `FUN-3` | Links are generated and handed over by hand. "Solicitar información" reaches nobody. |
| **MFA**, session expiry, password policy | `SEC-8` | A standard line in insurers' security questionnaires. |
| **Malware scanning**, a written **retention** policy | `SEC-4`, `SEC-6` | Uploaded files are served to other staff. |
| **Prompt-injection review** of the three agents | — | Never audited; hostile documents are the realistic attack. |
| **Secret rotation**, close `SEC-7` and `L1`–`L3` | `SEC-11`, `SEC-7` | Cheap, and they show up in a pentest. |
| **Legal**: an SSF opinion, terms, privacy notice, a DPA, a stated data residency position | `SEC-9`, `SEC-10` | Calendar time, not effort. **Start this week**; it blocks the contract. |
| **Paid tiers** for the pilot month (Render Starter + Supabase Pro) | — | No cold starts, no pauses, point-in-time recovery. |

### Tier 2: to sell it repeatedly (`Corte B`)

- **The analytics a buyer pays for** (`FUN-4`, `CAL-2`): approval rate,
  distribution by tier, cycle time per product and underwriter, and the
  AI–underwriter agreement rate, which is the path to auto-approving clear
  cases.
- **Deliverables** (`FUN-8`): a PDF decision letter and a case file summary.
- **Onboarding an existing book** (`FUN-9`): bulk client import (`external_ref`
  exists; the importer does not).
- **`required_if`** conditions in `required_documents` are still not evaluated.
- **Commercial terms** (`NEG-3`, `NEG-4`): pricing, metering per tenant,
  billing, an SLA, a support channel, a status page.
- **Quality at scale** (`CAL-4`–`CAL-6`): an automated end-to-end test, a load
  test with a committable throughput figure, an accessibility pass.
- **Integrations** (`NEG-6`): credit bureau, ID validation, policy admin. Quote
  them per client; don't build them in the abstract.

### The commercial package (parallel, non-engineering)

| Asset | Status |
| --- | --- |
| Marketing website with lead forms | **Skeleton built today** (§ 5) |
| Domain and business email (`ventas@…`) | Missing; the site has a config slot for them |
| 3-minute demo video of the 8-beat script (`mvp-execution-plan.md`) | Missing; doubles as the network-failure fallback |
| One-page PDF brochure (Spanish) | Missing |
| Pre-filled security questionnaire (architecture, RLS, audit, encryption, subprocessors: Render, Supabase/AWS, Anthropic) | Missing; most of the answers are in `docs/` |
| Pilot proposal and contract template | Missing |
| Pricing sheet | Blocked on `NEG-1` |

## 4. Positioning

- **Positioning (revised 2026-10-16, at the owner's direction).** A decision
  engine for any document-based process. Insurance is the first use case, not
  the market boundary. The site lists credit and microfinance, customer
  onboarding, vendor onboarding, leasing, and grants and subsidies. Only life
  and health are demonstrable today. Each other use case needs a playbook and
  form schema, which is configuration, not code.
- **Who buys first.** Life and health insurers, and brokers that underwrite, in El
  Salvador first, then Central America. The buyer is the underwriting manager
  or technical director; IT and compliance have a veto.
- **The pitch.** *"Your underwriting criteria, applied the same way to every
  application, with the reason for every result written down."* It saves time,
  but consistency and auditability are what a regulated buyer can defend.
- **The offer.** A paid pilot on one product line: diagnosis, playbook
  configured together, accompanied operation, and an evaluation against agreed
  metrics (agreement rate, cycle time, share of cases needing manual review).
- **The pricing hypothesis** (confirm after `NEG-1`): a setup fee for
  configuration, plus a monthly platform fee per tenant, plus a fee per
  processed application above an included volume. Keep the per-application fee
  well above the measured model cost. Publish no prices on the site until then.
- **The open product question** (from `PLAN.md`): *who on the insurer's side
  edits playbooks?* If nobody will, sell configuration as a service. Ask it in
  the first meeting.

## 5. The website: plan and skeleton

**Built:** a single-page site in Spanish with two lead forms. Source:
`site/landing.html`. Private review link:
<https://claude.ai/artifact/2QeCKcPNnasThM5RaoFheE>. The file is in
Artifact format (no `<!doctype>`, `<head>` or viewport meta, which the Artifact
host adds). To deploy it, wrap it in a document skeleton with
`<meta name="viewport" content="width=device-width, initial-scale=1">`.

### Goal and audience

Its one job is to turn an underwriting manager's visit into a demo or pilot
request. Its second job is to answer the IT and compliance reviewer's first
questions without a call.

### Sections

1. **Header.** Wordmark, anchors, "Solicitar demo".
2. **Hero.** The thesis, plus a live sample case file with three tabs. Vida and
   Salud evaluate the real seguros and medico playbook rules on fictitious
   applicants: one clean case, and one that fails closed into manual review.
   Crédito is illustrative, labelled "playbook de ejemplo", because no credit
   playbook exists yet.
3. **The problem.** Manual document review, criteria that live in people's
   heads, decisions that are hard to audit.
4. **How it works.** The 7-step pipeline, a true sequence.
5. **Playbooks.** Rules as data: a JSON excerpt, versioning, test before
   publishing, immutability.
6. **The case file.** Trace, narrative, flags, version, fail closed.
7. **Use cases.** Life, health, other lines; the four roles.
8. **Security and control.** Only verified claims, plus an explicit "on the
   roadmap" list, which earns more trust than overclaiming.
9. **Pilot program.** Four phases.
10. **FAQ.**
11. **Contact.** Two tabs. *Agendar demo* is short. *Cotizar piloto* asks
    qualifying questions: line of business, monthly volume, current process,
    timeline.
12. **Footer.**

### Lead capture: needs a decision before launch

The form posts JSON to `CONFIG.leadsEndpoint` at the top of the page script.
While that is empty (as in the preview), the form validates, then says plainly
that nothing was sent. It never fakes a success. A hidden honeypot field
discards bot submissions.

- **v1 (an hour):** a hosted form endpoint (Formspree, Basin or Getform) that
  emails the sales inbox. No backend to run.
- **v2:** a `leads` table in a **separate** Supabase project (never the
  product's production database), behind an Edge Function with Cloudflare
  Turnstile, a rate limit, and an email notification. Optionally sync to a CRM
  (HubSpot free).

### Hosting and launch checklist

- [ ] Its own repo (`qualifier-site`), deployed as a **Render static site**
      (free, no cold start for static) or Cloudflare Pages.
- [ ] Domain plus a business email; set `CONFIG.salesEmail`.
- [ ] Lead endpoint connected and a test lead received.
- [ ] Privacy notice page reviewed by a lawyer (`SEC-10`), linked from the
      forms' consent box.
- [ ] Open Graph image, favicon, `sitemap.xml`, `robots.txt`, Spanish meta
      description.
- [ ] Privacy-friendly analytics (Plausible or Umami): visits, CTA clicks, form
      submissions.
- [ ] The pilot phase durations on the page are a proposal; confirm or edit
      them.
- [ ] An English version if regional or multinational insurers are targeted.
- [ ] Before launch, re-check every claim on the page against § 2's "do not
      claim" list.

## 6. Naming: preliminary availability check (2026-10-16)

This is not legal clearance. It is a preliminary search: domains through
public RDAP and DNS, trademarks in WIPO's Global Brand Database. **That database
does not cover El Salvador, Guatemala, Honduras, Nicaragua, Panama or the
Dominican Republic.** It does cover Costa Rica, Mexico, the US, Brazil, Spain
and the EU. El Salvador needs a search at the CNR (Registro de la Propiedad
Intelectual) through a local agent.

**Rúbrica: not clear, so the page keeps "Qualifier".**

- Domains:
  - taken: `rubrica.com` (an Argentine woodworking studio, since 1999),
    `rubrica.ai`, `rubrica.io`, `rubrica.app`, `rubrica.com.sv`,
    `getrubrica.com` (registered 2026-08-20, under construction);
  - for sale: `rubrica.co` (parked at Afternic);
  - free: `rubrica.lat`, `rubricahq.com`, `rubricaai.com`.
- Trademarks: 73 records contain "rubrica". The ones that block software
  (classes 9 and 42) in target or expansion markets:
  - Mexico: RUBRICA, class 9, pending since 2024-03-22 (La Venta Capital
    Investment); RUBRICA and GRUPO RUBRICA, class 42, registered 1996 (Grupo
    Rubrica);
  - US, EU and UK: RÚBRICA, classes 37 and 42, registered (Rubrica Ingeniería
    y Arquitectura);
  - Brazil: Rubrica Digital, class 42, registered 2021 (digital certificates);
    Rubrica Signature, class 42, pending;
  - Korea: RUBRICA, classes 35, 36, 38 and 42, pending since 2026-05-28.
- It is also phonetically close to **Rubrik**, a large US data-security
  software company. That is an opposition risk in classes 9 and 42.

**Other shortlisted names:**

| Name | Free domains | Taken domains | WIPO (exact word) |
| --- | --- | --- | --- |
| **Dictamina** | `.ai`, `.io`, `.lat` | `.com` (a Spanish forensic expert-report firm, active) | **0 records** |
| Razona | `.ai`, `.lat` | `.com`, `.io` | 15; active: Spain class 42+45, Mexico class 35 |
| Pondera, Veredicta, Evidenta, Indicio | `.lat` only | `.com`, `.ai`, `.io` | not searched |
| Arbitra, Cotejo, Trazo, Fundamenta | none of the four checked | `.com`, `.ai`, `.io`, `.lat` | not searched |

Dictamina is the cleanest result so far: no mark anywhere WIPO covers, and the
`.ai` and `.io` domains are free. Before adopting it, run a CNR search in El
Salvador (classes 9, 42 and 35), a fuzzy and phonetic search for "dictamen",
and register the domains.

### Coined names: second round (2026-10-16)

Dictionary words almost never have a free `.com`. Of 44 coined candidates, 7
had both `.com` and `.ai` free. Three were dropped on meaning: "juzgara" is a
real verb form, "fallarix" carries *fallar* (to fail), and "veredano" sounds
like *verano*. Each finalist was searched in WIPO with **fuzzy** matching, so
the search catches similar spellings, not only exact ones.

| Name | Idea | Domains | Closest marks (WIPO, fuzzy) | Verdict |
| --- | --- | --- | --- | --- |
| **Dictarum** | *dictar* (a ruling) + Latin *-arum*: "of the rulings" | `.com`, `.ai`, `.io`, `.lat`, `.co` and `.app` all free | DICTRUM (Mexico, class 10, medical); Dictamus (Germany, 42/38, **expired** 2021) | **Cleanest** |
| Tramiq | *trámite* + IQ | `.ai` free; `.com` is an active tech firm (TRAMIQ International, Pakistan) | TRAMIT (Spain, class 35) | Usable regionally; no `.com` |
| Dicterra | *dictamen* + *terra* (solid ground) | all free | **PICTERRA**, a geospatial AI company, classes 9 and 42, registered in the US, EU, Canada and Switzerland (one letter off) | Risky outside Central America |
| Veredant | *veredicto* + English *verdant* | all free | **VERDANT**, classes 9 and 42, EU 2024, plus many others | Too close |
| Trazanta | *trazar* + *-anta* | all free | **TRAZANTO**, class 9, registered in the US, EU, UK, Mexico and Brazil | Too close |
| Veredia | *veredicto* + IA | `.ai`, `.io`, `.lat` free; `.com` taken since 2000 | **VEREDA.IA** (Brazil, classes 35, 36, 42 and 44, pending) | Out |

The caveats from § 6 still apply. This is not legal clearance, and El Salvador
is not in WIPO's database. Before committing to a name: run a CNR search
(classes 9, 42 and 35), register the domains the same day (availability
changes), and file the mark.

### Coined names: third round (2026-10-16)

Another 47 candidates. Short coinages (Laudia, Peritia, Verazia, Cribia…) all
had their `.com` taken. Longer blends with the *-anza* ending (as in
*confianza* and *balanza*) were free. Finalists, searched in WIPO with fuzzy
matching, with `.com`, `.ai`, `.io`, `.lat`, `.co` and `.app` all free unless
noted:

| Name | Idea | Closest marks (WIPO, fuzzy) | Verdict |
| --- | --- | --- | --- |
| **Ponderanza** | *ponderar* + *balanza*: weighing with criteria; the playbook's weights | 11 results; nearest PINDELANZA (Spain, construction), PONDERADA (Brazil, class 35, pending) | **Cleanest of all three rounds** |
| **Clarianza** | *claridad* + *confianza*: explainability that builds trust | CLARIANA (Spain and Brazil; stationery, transport, chemicals), CLARIANZ (Indonesia, cosmetics). Nothing in software | **Clean; the most marketable** |
| **Tamizia** | *tamiz* + IA: screening applications | Unrelated marks (TAMILIA cosmetics, TAMIEIA Italy). Nothing in software | Clean |
| **Peritanza** | *peritaje* + *confianza*: expert assessment you can trust | PERTANZA (Wyeth, pharmaceuticals, class 5) | Clean; leans toward insurance |
| Dictanza | *dictamen* + *-anza* | DISTANZA (Bridgestone bicycles, Ping golf); sounds like *distancia* in Latin American Spanish | Clean, but a weak association |
| Laudanza, Cribanza, Veredanza | — | not searched | `.com` and `.ai` free |

Across all three rounds, the clean candidates are **Ponderanza, Clarianza,
Tamizia, Peritanza and Dictarum**. The earlier caveats stand: this is not legal
clearance, El Salvador needs a CNR search, and domains should be registered the
day a name is chosen.

### Decision: Tramiq (2026-10-16)

The owner chose **Tramiq** (*trámite* + IQ), and the site now uses it.

- **Domains:** `tramiq.com` belongs to an active technology company, TRAMIQ
  International (Private) Limited, apparently in Pakistan: embedded software,
  RF, power electronics. Free on 2026-10-16: `tramiq.ai`, `tramiq.io`,
  `tramiq.lat`, `tramiq.co`, `tramiq.app`, `tramiq.la`, `gettramiq.com`,
  `usetramiq.com`. Register at least `tramiq.ai` and `tramiq.lat` now, plus
  `gettramiq.com` for email deliverability.
- **Trademarks (WIPO, fuzzy):** no TRAMIQ mark. The nearest live mark is TRAMIT
  (Spain, class 35). TRAMIQ International has no registration in WIPO's
  coverage, but it uses the name in tech. Ask the CNR search to cover this.
- **Still to do:** a CNR search in El Salvador (classes 9, 42 and 35), then file
  the mark. The product (`web`) still says "Qualifier" in its UI; renaming it is
  a separate change.
