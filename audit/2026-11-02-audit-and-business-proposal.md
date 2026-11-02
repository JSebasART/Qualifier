# Tramiq — audit and business proposal, 2026-11-02

Measured on 2026-11-02 against the production database (read only, through the
Supabase connector), Render, the five repos on `develop`, and Anthropic's live
model documentation. It builds on three earlier records:
[`2026-10-16-sales-readiness.md`](2026-10-16-sales-readiness.md), the 2026-10-27
report (`audit/2026-10-27-report.html`, which exists only on the unmerged
umbrella branch `claude/busy-cray-3x65vz`), and `docs/product-gap-analysis.md`,
whose identifiers (`BLK-4`, `CAL-1`, `FUN-11`…) are used here.

Prices and market figures from outside the repo carry a link in § 8. Anything
marked **assumption** has to be confirmed with a real insurer before it goes
into a proposal.

## 1. Summary

**The product is ready to demo and to run a paid pilot with close support. The
business is not started.** Nobody has signed in since 2026-10-17, there is no
customer, no price list and no contract, and the infrastructure is on free
tiers.

- **One deadline comes before everything else.** `claude-sonnet-4-5`, the model
  all three agents run on, **retires on 2026-11-30**, 28 days from now. This is
  confirmed on Anthropic's deprecations page. After that date no document is
  read and no application is scored. Its replacement (`claude-sonnet-5-5`)
  rejects the forced tool call the agents use, so the switch needs code
  changes. That work is under way in a separate session.
- **The engine is a real asset.** Rules are data, scoring fails closed,
  tenants are isolated in the database (305 pgTAP assertions), decisions carry
  an audit trail, and the agents speak Spanish. Self-service intake (`FUN-11`)
  is now in production. **It is switched off** until a consent text, mail,
  captcha and a malware scanner exist.
- **The AI cost per application is measured and small:** about **US$0.07 for a
  clean two-document application** on today's model, and US$0.19 for the worst
  real run. The variable cost does not limit pricing. Sales time, support time
  and trust do.
- **In El Salvador, labour savings alone will not sell this.** An underwriting
  analyst costs roughly US$500–1,300 a month, fully loaded. Selling on "replace an analyst"
  makes the ROI thin. Selling on **speed, consistent and defensible decisions,
  fraud control and a new digital sales channel** makes it clear (§ 5.5).

**The five things to do first:** migrate the model before 11-30; promote
`develop`; switch the Auth settings and delete the 2 anonymous users; move to
paid tiers with backups before the first pilot; then take the pilot offer in
§ 5.3 to three insurers.

## 2. What the program does, in plain terms

An insurer's staff member (or, through a link, the applicant) fills in the
product's form and uploads documents: DUI, a salary letter (constancia), lab
results, a medical report. Then, in the background:

1. **Read.** Claude reads each document, PDF or photo, and extracts the fields
   the insurer's rules ask for, as typed values. "US$ 2,000.00" becomes 2000.
2. **Check.** It compares the extracted data with the form answers and with
   each other. It flags inconsistencies, signs of tampering, stale documents
   and a DUI that does not match the person.
3. **Explain.** It writes a short risk narrative in Spanish.
4. **Score.** The insurer's **playbook** scores the application: a versioned set
   of rules, weights and tiers, edited on screen, never in code. A rule that
   cannot be evaluated sends the case to a person; it never passes silently.
5. **Decide.** An underwriter gets a case with the score, the rule-by-rule
   trace, the narrative, the flags and the documents side by side, with an SLA
   deadline. They approve, decline or ask the applicant for more. Each step is
   recorded with who, what and when, plus the exact playbook version used.

Around that: a case queue, assignment, per-tenant branding, staff management,
CSV export, cost per application, and since 2026-10-29 self-service links.
Self-service covers personal links, public product links, WhatsApp, the
insurer's own domain and a form embedded in the insurer's website. Approving
clean cases automatically is built too, and it stays locked until a product
has 100 human decisions to measure against.

## 3. Audit: the state on 2026-11-02

### 3.1 Deployment

| Piece | State |
| --- | --- |
| Render `qualifier-web`, `-ai-orchestrator`, `-grading-engine` | `plan: free`, region Ohio, deploying `main`. Last deploy 2026-10-29. All three answered `/health` 200 on 2026-10-30, after a ~13 s cold start. |
| Supabase `jskuoazhcgfyetxrmxyi` | `ACTIVE_HEALTHY`, Postgres 17.6, us-east-1, free plan. The only environment. No backups you can download, and no point-in-time recovery. |
| `develop` vs `main` | `develop` is 1–3 commits ahead in every repo since today's merge: the notification wake-up, the purge catch-up, zod 4 and CI on actions v5. **Not deployed.** |
| Live web build | Spanish, Tramiq brand. `/s/<unknown>` answers "Enlace no encontrado". Nobody has signed in since the 2026-10-29 deploy. |

### 3.2 What production holds

| | Count | Note |
| --- | --- | --- |
| Tenants / products / published playbooks | 2 / 2 / 2 | `seguros` (life), `medico` (health) |
| Clients / applications | 16 / 17 | Every application came through the staff channel |
| Documents / scores / cases | 33 / 14 / 13 | Cases: 5 in review, 2 waiting on the applicant, 6 resolved |
| Open cases past their SLA | **7 of 7** | The demo queue looks neglected again |
| Staff profiles / auth users | 16 / 18 | **2 anonymous users** from 2026-08-13, still present |
| AI calls recorded (`ai_usage`) | 21 | US$0.33 spent in all |
| Intake links / sessions / consent texts / domains | 0 / 0 / 0 / 0 | Self-service is deployed and unused |
| Products with automatic approval on | 0 | 1 comparable decision exists; 100 are needed |
| Last sign-in, last AI call, last audit row | 2026-10-17 | **16 days without use** |

### 3.3 Measured cost and time (production, `claude-sonnet-4-5`)

| Agent | Calls | Average tokens in / out | Average cost per call | Average latency |
| --- | --- | --- | --- | --- |
| Extraction, one per document | 8 | 2,932 / 663 | US$0.0188 | 8.7 s |
| Consistency check | 7 | 2,266 / 235 | US$0.0103 | 5.3 s |
| Risk narrator | 6 | 2,112 / 733 | US$0.0173 | 14.2 s |

A clean application costs **about US$0.065 with two documents and US$0.084
with three**: one extraction per document, plus one consistency check and one
narrative. The two-document seguros run took **33 s of model time**; three
documents should take about 45 s. The real runs cost more:
US$0.081 for seguros (rescored once) and US$0.195 for médico (three failed
narrator attempts before a fix). Budget **US$0.10–0.25 per application** to
cover retries and rescoring.

Elapsed time end to end was minutes, not seconds. Both runs were dominated by
retries: an invalid API key, a deploy that orphaned a job, and free-tier cold
starts. **There is no clean measurement of the time from upload to case yet.**

### 3.4 Code quality

- Tests on `develop`: `db` 305 pgTAP assertions in 12 suites (CI on
  2026-10-29); `ai-orchestrator` 181; `grading-engine` 55; `web` 107. The last
  three were re-run locally today, with typecheck, lint and build clean.
- `npm audit --omit=dev`: **0 vulnerabilities** in all three services on
  `develop`. zod 4 closed the last high advisory; it is not deployed yet.
- CI results on GitHub could not be read from this machine: the repos are
  private and there is no `gh` CLI.
- No code sends `temperature`/`top_p`, which API version `2026-10-21` removed.

### 3.5 Security

Closed since the 2026-10-27 audit: Next.js 16.4.3 is live. The prompt-injection
rule, fence and detector are in the orchestrator and live since 10-29; they
have not been tested against a hostile document set. db CI runs. zod 4 is on
`develop`.

Still open (Supabase advisor, today):
- **Anonymous sign-ins are enabled**, and the 2 anonymous users exist. No data
  is exposed: every policy needs a staff profile. But anyone with the public key
  can create users, and the advisor flags 19 tables because of it.
- **Leaked-password protection is off.** No MFA for staff (`SEC-8`).
- 19 `SECURITY DEFINER` RPCs executable by `authenticated`. This is by design:
  each checks the caller's role. Expect a buyer's pentest to ask about it.
- A vestigial storage policy, `applicant_read_own_application_documents`, from
  the retired `/apply` portal.
- One environment, no restore ever rehearsed (`BLK-4`). Data in the US
  (`SEC-10`). No legal documents (`SEC-9`).
- The Supabase Auth **Site URL** has never been confirmed. If it still points at
  `localhost`, the first "forgot password" email breaks.

### 3.6 The 2026-10-27 findings, re-checked

| ID | Finding | Status today |
| --- | --- | --- |
| AUD-01 | Production model retires 2026-11-30 | **Open, critical.** Date confirmed on Anthropic's page. Migration session running. |
| AUD-02 | One environment, no backups (`BLK-4`) | Open |
| AUD-03 | Free tiers sleep and pause | Open. The wake-up for applicant notifications is on `develop`. |
| AUD-04 | Extraction accuracy unmeasured (`CAL-1`) | Open |
| AUD-05 | Agents had no defence against injected instructions | Built and live; not tested with hostile documents |
| AUD-06 | Legal track not started (`SEC-9`, `SEC-10`) | Open; nothing in the repos says it started |
| AUD-07 | Anonymous sign-ins, leaked-password protection, MFA | Open; the 2 anonymous users are still there |
| AUD-08 | Nobody is alerted when the queue fails (`NEG-2`) | Open; no external monitor is recorded |
| AUD-09 | Docs said untrue things | Mostly closed (STATUS headline 10-30, CLAUDE.md, PLAN.md). The 10-16/17 notes are still uncommitted. |
| AUD-10 | Demo data aged | **Open again:** 7 of 7 open cases overdue. Seeded proofs of income pass the 90-day limit by 2026-11-04. |
| AUD-11 | zod high advisory | Closed on `develop`, not deployed |
| AUD-12 | Minor items | Open: `/analyze` is still live; `pgtap` is installed in production; the CSP has `unsafe-inline`; `required_if` is not evaluated; Ohio and Virginia regions |

### 3.7 New findings

- **N-1. The commercial assets live outside git.** The 10-16 sales audit, the
  demo guide (`demo/`), the landing page and brand (`site/`) and the QA
  fixtures (`qa/`) are untracked files on one machine. The 10-27 report is on an
  unmerged branch. These are what you sell with. Commit them.
- **N-2. Self-service is the strongest new selling point and cannot be shown
  live yet.** A product link fails closed without Turnstile, Resend, ClamAV
  (about 1.5 GB of RAM, so not a free instance) and a published consent text.
  A personal link works today. **Demo the personal link.**
- **N-3. The 100-decision gate on automatic approval is a sales hook.** The
  pilot in § 5.3 runs about 170 applications a month. If roughly half are
  recommended for approval, it reaches 100 decided approve recommendations in
  about six weeks. They also have to be at least 98% approved. "Before the
  pilot ends, clean approvals can go straight through" is a concrete next
  stage to sell.
- **N-4. Anthropic retires models about once a year.** Opus 4.1 was retired in
  August, Sonnet 4 in June, and Sonnet 4.5 goes on 11-30. Each retirement has
  been a code change here. A fixed accuracy test set (`CAL-1`) would make every
  future migration a measured, routine task. Without one, each migration is a
  guess.
- **N-5. No metering exists to bill by.** `ai_usage` measures cost, but nothing
  counts submitted applications per tenant per month, the unit proposed in
  § 5.3.

## 4. The market

- **El Salvador has about 23 insurers.** In 2025 they wrote a record **US$1,011
  million in net premiums, up 9%**. Growth was led by medical insurance, up
  **11%**, and accidents and illness reached **US$203.9 million, about 20% of
  the market**. Premiums grew another 5.8% in the first four months of 2026.
- **The market is concentrated.** About eight insurers hold most premiums; the
  largest, Asesuisa, had 16.8% in 2025. **The first sales list is short: about
  eight names, plus the brokers that underwrite.**
- **The buyer** is the underwriting manager or technical director. IT and
  compliance can veto. The SSF supervises.
- **The trend** fits the product: medical insurance is growing faster than the
  market, and insurers want applicants to file through a link on a phone.
  That is exactly `FUN-11`.

Alternatives a buyer will compare:

| Alternative | Weakness we can point to |
| --- | --- |
| Status quo: email, paper, Excel and an analyst's judgement | Slow, inconsistent between analysts, hard to defend in an audit |
| A module of their core or policy system | Rules buried in configuration screens or code. No document AI. Long vendor projects |
| Global AI-underwriting vendors (Sixfold, Cytora; nsur.ai at about US$1.75–2 per application) | English-first, built for US and UK commercial lines. No DUI, constancia or SSF context. Enterprise contracts |
| A local software house building it custom | Months of work, no tenant isolation or audit model proven by tests, and the insurer owns the maintenance |

**Our edge:** Spanish end to end, Salvadoran documents, rules the insurer owns,
a defensible audit trail, a self-service channel included, and prices sized
for Central America.

## 5. Business proposal

### 5.1 What the insurer is buying

| Outcome the insurer pays for | How Tramiq delivers it | Evidence today |
| --- | --- | --- |
| **Decide in minutes, not days** | Documents read and cross-checked automatically; the analyst gets a finished case | 33 s of model time for a two-document application, measured in production |
| **The same criteria for every applicant** | Playbooks: versioned, tested before publishing, and immutable once published (enforced by the database) | The playbook editor, its "Probar esta versión" panel and the immutability trigger |
| **Decisions they can defend** to the SSF, an auditor or a complaint | Rule-by-rule trace, AI narrative, flags, exact playbook version, and an append-only audit log | The case screen; `audit_log` records `case.approved` with its actor |
| **Less fraud and fewer bad documents** | Tampering flags, consistency checks, the identity check against the DUI, maximum document age | The consistency notes and identity result on the case |
| **A new digital sales channel** | Personal and product links, WhatsApp, the insurer's own domain, an embeddable form | In production, off until configured |
| **Grow volume without growing the team** | Automatic approval of clean cases, once 100 decisions prove agreement | Built, locked by design |
| **Data that stays theirs and separate** | Tenant isolation in Postgres, tested from the attacker's side | 305 pgTAP assertions in CI |

### 5.2 What we get paid for

Four revenue streams, in the order they will arrive:

1. **Setup and configuration (services).** Turning the insurer's underwriting
   manual into a playbook, a form and required documents, plus the consent
   text and training. This also answers the open product question *"who on the
   insurer's side edits playbooks?"*. If nobody will, we do it, and it is paid.
2. **Platform subscription.** A monthly fee per insurer (tenant), by plan.
3. **Usage.** A fee per **submitted application** above the plan's included
   volume. A submitted application is the unit the self-service design already
   chose: spam and abandoned drafts never bill the insurer, and the per-tenant
   spend cap bounds our cost before submission.
4. **Add-ons and projects.** The self-service channel (on the higher plan), a
   dedicated environment or data residency, integrations quoted per client
   (credit bureau, RNPN, policy system), and automatic approval once eligible.

### 5.3 Pricing hypothesis

Validate it in the first three discovery meetings. Prices in US dollars,
excluding VAT.

| Plan | Monthly | Includes | Above the included volume | For |
| --- | --- | --- | --- | --- |
| **Piloto** (90 days) | US$500 | 1 product line, up to 500 applications in all, staff channel plus personal links, weekly review with us | — | First contact. **US$2,500 setup**, credited against the first year if they sign |
| **Esencial** | US$700 | 1 product line, 300 applications/month, 10 staff seats | US$1.25 each | A small insurer or a broker that underwrites |
| **Crecimiento** | US$1,500 | Up to 3 product lines, 1,000 applications/month, self-service (product links, WhatsApp, own domain, embedded form), identity check | US$0.90 each | The core target: a mid-size life or health insurer |
| **Empresarial** | from US$3,000 | Dedicated database, a data-residency choice, written SLA, priority support; automatic approval when eligible | negotiated | The top three insurers |

Services: **US$1,500 per new product line** configured. Playbook changes come
out of included hours, then about US$50 an hour.

The effective price works out to US$2.33 per application on Esencial and
US$1.50 on Crecimiento. That is in line with the only public benchmark found
(about US$1.75–2 per application in the US), and below it at volume.

### 5.4 Unit economics

**Variable cost per application** (AI only; storage and bandwidth are
negligible at this scale):

| Model setup | Cost per clean application | Source |
| --- | --- | --- |
| Today: Sonnet 4.5 for all three agents | US$0.065–0.084 | Measured (§ 3.3) |
| Sonnet 5.5 for all three agents (US$2/US$10 per million tokens) | about US$0.06–0.10 | **Estimate.** Cheaper per token, but the newer tokenizer counts about 30% more tokens and the model thinks before it answers. Re-measure after the migration |
| Haiku 5.5 for extraction (US$0.10/US$0.50 per million tokens), Sonnet 5.5 for the rest | about US$0.03–0.04 | **Estimate.** Extraction becomes about 15–20× cheaper per document. Only if the accuracy set shows quality holds |

Budget **US$0.10–0.25** per application with retries, whatever the setup.

**Fixed platform cost at production grade.** Approximate list prices; confirm
each before budgeting.

| Item | Monthly |
| --- | --- |
| Render: web and grading-engine on Starter, orchestrator on Starter | about US$21 |
| Render: a ClamAV instance with about 2 GB of RAM | about US$25 |
| Supabase Pro (daily backups, no pausing) | US$25 |
| Supabase point-in-time recovery add-on | price it before committing |
| Second Supabase project for development (`BLK-4`) | free tier |
| Email (Resend), captcha (Turnstile), uptime monitor | US$0–20 |
| Domain and business email | about US$10 |
| **Total** | **about US$100–200 a month**, plus point-in-time recovery |

**One customer covers the platform.** For example, one Crecimiento insurer at
800 applications a month:

| | Monthly |
| --- | --- |
| Revenue | US$1,500 |
| AI cost (800 × US$0.10–0.25) | US$80–200 |
| Platform share (if it were the only customer) | US$100–200 |
| **Gross margin** | **about US$1,100–1,300 (73–88%)** |

The cost that grows with customers is **people**: configuration, support,
sales and model migrations. Price services so that configuration work pays for
itself.

### 5.5 The insurer's return

Every number below is an **assumption** to replace with the insurer's own in
the first meeting.

| Input | Assumption |
| --- | --- |
| Individual life and health applications a month | 400 |
| Analyst time per application today (collect, type, check, decide) | 45 min |
| Analyst time with Tramiq (review a finished case, decide) | 15 min |
| Analyst cost, fully loaded | US$500–1,300 a month (Paylab's insurance salaries, about US$400–1,000, plus about 30% employer costs) |

- **Labour freed:** 30 min × 400 = 200 hours a month, about 1.25 analysts, or
  **US$600–1,600 a month**. That alone roughly pays for Crecimiento. **It is not
  a strong enough reason on its own**, so don't lead with it.
- **The stronger reasons**, which the insurer can value better than we can:
  - **Speed.** An applicant decided the same day doesn't go to a competitor.
    Each policy kept is worth its annual premium, and the insurer knows that
    number.
  - **The self-service channel.** Volume from a link on their website or on
    WhatsApp, without an agent typing anything.
  - **Defensible, consistent decisions.** Fewer complaints, cleaner SSF and
    reinsurer audits.
  - **Fraud caught at intake.** One avoided fraudulent health claim pays for
    months of the platform.

**The pitch** (from the 10-16 audit, still right): *"Your underwriting
criteria, applied the same way to every application, with the reason for
every result written down — and now applicants can file from their phone."*

### 5.6 The offer for the first three insurers

1. **Discovery, one meeting.** Volume, the current process, who would edit
   rules, the documents they require, what IT and compliance will ask.
2. **Configured demo, one week.** Their product, their rules and their
   documents, anonymized, on our demo tenant.
3. **Paid pilot, 90 days.** One product line, personal links and the staff
   channel. Success criteria are agreed up front: agreement between
   recommendation and decision, time to decision, and the share of cases that
   needed manual review.
4. **Conversion.** To Crecimiento, with the setup credited. Turn on the product
   link once its prerequisites are met. Offer automatic approval when the
   100-decision evidence exists.

## 6. How to improve it, by horizon

### Horizon 0: this month (before 2026-11-30)

| # | Action | Why | Effort |
| --- | --- | --- | --- |
| 0.1 | **Migrate the agents to `claude-sonnet-5-5`**, test on the `qa/2026-10-02/` documents, then promote | AUD-01: without it, the product stops on 11-30 | 2–3 days (in progress) |
| 0.2 | **Promote `develop` to `main`** once 0.1 is on it | Notification wake-up and zod 4 are waiting | Hours |
| 0.3 | **Auth settings:** turn anonymous sign-ins off, delete the 2 anonymous users, turn leaked-password protection on, confirm the Site URL | AUD-07, and the first password-reset email | 30 min, in the dashboard |
| 0.4 | **Commit the commercial assets** (`audit/`, `demo/`, `site/`, `qa/`) and the uncommitted STATUS/RUNBOOK notes | N-1 | Minutes |
| 0.5 | **External monitor** on `/health/queue`, alerting by email | AUD-08: a dead pipeline is silent | 1 hour |
| 0.6 | **Refresh the demo data** and record the 3-minute demo video | AUD-10; a fallback if the network fails | 1 hour |
| 0.7 | **Start the legal track**: privacy notice, consent wording, a DPA, an SSF opinion, a position on data residency | Calendar time; it blocks the contract | Start this week |
| 0.8 | **File the Tramiq trademark**, after a search at the CNR (classes 9, 42, 35), and register `tramiq.ai` and `tramiq.lat` | Only a preliminary search has been done (10-16) | Days, through a local agent |

### Horizon 1: ready for a paid pilot (4–8 weeks)

- **Paid tiers, a second environment, backups and one rehearsed restore**
  (`BLK-4`, AUD-02/03). Move Render to the Virginia region at the same time,
  next to the database.
- **Accuracy set** (`CAL-1`): 30–50 Salvadoran documents per type, including
  phone photos and a few hostile ones. Report per-field accuracy. This becomes
  the regression test for every future model change (N-4) and the best sales
  number we could have.
- **Mail (Resend)** for invitations, password resets and applicant notices
  (`BLK-6`, `FUN-3`).
- **MFA for staff** (`SEC-8`), a retention policy (`SEC-6`), ClamAV deployed
  (`SEC-4`).
- **Configure self-service:** consent text, Turnstile, `PUBLIC_WEB_URL`. Then
  run a full product-link test against real services, which has never been
  done.
- **A signed-in pass of the phase-4 staff screens:** domains, embed origins,
  the automatic-approval panel. So far they have only been typechecked.

### Horizon 2: sellable again and again (2–4 months)

- **Show the value on screen.** Cost and time per case, and agreement between
  recommendation and decision. The data already exists (`application_ai_cost`,
  `application_pipeline_timing`, `decision_agreement`); only the views are
  missing. The cheapest change with the most commercial effect.
- **Portfolio analytics** (`FUN-4`): approval rate, score distribution, cycle
  time per product and per analyst.
- **Billing metering** (N-5, `NEG-3`): submitted applications per tenant per
  month, against the plan's included volume. Invoicing can stay manual at first.
- **PDF decision letter and case summary** (`FUN-8`); **bulk client import**
  (`FUN-9`); evaluate `required_if`.
- **Cost:** test Haiku 5.5 for extraction against the accuracy set.
- **Operations:** a status page, a support channel with response times, a
  written SLA (`NEG-4`); an automated end-to-end test (`CAL-4`).
- **Integrations only when a signed customer asks** (`NEG-6`), quoted as
  projects.

### Later, on evidence

- Automatic approval in production for the first product that clears the
  100-decision bar.
- A second vertical as configuration, not code: credit or microfinance
  pre-qualification, then Guatemala and Honduras with a local partner.

## 7. Decisions for the owner

1. **Pricing:** accept, change or replace § 5.3 before the first meeting.
2. **Who edits playbooks?** If the answer is "us", configuration becomes a
   service line, and its hourly rate matters.
3. **When to pay for infrastructure** (about US$100–200 a month): now, or at
   the first signed pilot. A public product link cannot run on free tiers.
4. **The legal track:** which lawyer, and the budget.
5. **The first five names:** from the eight largest insurers and the brokers
   that underwrite.

## 8. Method and sources

**Internal, measured today:**
- Production, read only through the Supabase connector: counts, `ai_usage` by
  agent, `application_ai_cost`, `application_pipeline_timing`,
  `decision_agreement`, the security advisor.
- Render service list.
- `npm ci`, typecheck, lint, tests and build in `ai-orchestrator`,
  `grading-engine` and `web` on `develop`; `npm audit --omit=dev`.
- Reading the repos and the earlier audits.

**External:**
- Anthropic, [Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations):
  `claude-sonnet-4-5-20250929` deprecated 2026-09-30, retiring 2026-11-30,
  replaced by `claude-sonnet-5-5`. Model prices from Anthropic's models
  overview, as cached on 2026-10-06.
- Market size and growth, ASES figures as reported by
  [El Mundo](https://diario.elmundo.sv/economia/sector-asegurador-alcanza-record-al-rebasa-los-1000-millones-en-primas-en-2025)
  and [Revista E&N](https://www.revistaeyn.com/finanzas/el-mercado-de-seguros-en-el-salvador-crecio-cerca-del-9-en-2025-NC29183385);
  2026 first four months from
  [El Mundo](https://diario.elmundo.sv/economia/las-primas-de-seguros-crecieron-5-8-durante-el-primer-cuatrimestre-de-2026).
- Number of insurers:
  [MAPFRE El Salvador](https://www.mapfre.com.sv/media/2025-PDF-1.pdf) and
  [Moody's Local on ASSA](https://www.bolsadevalores.com.sv/files/58477/MLSLV_Informe_ASSA_Cia_de_Seguros_29.04.2025_v1_.pdf).
  Confirm against the SSF's official list.
- Asesuisa's market share:
  [Zumma Ratings, December 2025](https://bolsadevalores.com.sv/files/74688/ASESUISA_DIC2025_ZUMMA.pdf).
- Per-application benchmark (nsur.ai, US$1.75–2) and other vendors' pricing
  models: [actuary.info](https://actuary.info/insights/nsur-ai-2-dollar-underwriting-copilot-build-vs-buy-2026).
  A single secondary source; indicative only.
- Salaries: [Paylab El Salvador, insurance](https://www.paylab.com/sv/salarios/seguros?lang=es).
  Its ranges are in colones and not fully consistent; converted at 8.75 per
  dollar. Treat as an order of magnitude.

**Not verified:** CI on GitHub (not readable from here); the Supabase Auth Site
URL; the phase-4 staff screens with a signed-in session; any figure marked
**assumption** or **estimate** above; infrastructure list prices.
