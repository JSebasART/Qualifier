# Plans — design records

Four plans were requested on 2026-11-07 and built in order between 2026-11-08
and 2026-11-15. All are in production; what is still open is in
[`STATUS.md`](../STATUS.md) § "Open".

This folder keeps only the documents that code comments cite for the reasoning
behind a piece. The original requests and the execution records
(`*-PLAN-STATE.md`) were removed on 2026-11-15 and remain in git history.

| Plan | What it built | Record kept |
| --- | --- | --- |
| 1. Document types (`DOC`) | Editable document types with versioned acceptance rules, schema-guided extraction, the editor's test bench | [`01-tipos-de-documento.md`](01-tipos-de-documento.md) |
| 2. LPDP / ARCO-POL (`LPD`) | Purposes, consents, processing state, data inventory, rights requests, erasure, notices | [`02-design.md`](02-design.md) |
| 3. Client data (`DAT`) | Facts with provenance, the consolidated profile, enrichment, search, segments, the analytics replica | [`03-design.md`](03-design.md) |
| 4. CRM export (`CRM`), generic layer | One payload builder, signed webhooks, public API v1, CRM file exports, erasure propagation | [`04-design.md`](04-design.md) |
| 4b. Native CRM connectors | HubSpot, Dynamics 365, Odoo, the mapping editor, «CRM simulado», retention propagation | [`04b-design.md`](04b-design.md) |

## Why this order

Each plan assumed the ones before it. Document types produced the field
catalogue (class, category, sensitivity) the others needed. Privacy came
before collecting more data (Plan 3) or sending it out (Plan 4), so both were
born with purpose, consent and erasure rules. The consolidated client profile
came before CRM export, so a CRM receives one profile with provenance rather
than reading five tables.
