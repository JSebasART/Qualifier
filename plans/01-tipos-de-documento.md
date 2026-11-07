# Plan 1 — Tipos de documento configurables y requisitos de aceptación

*Propuesta, 2026-11-07. Primer plan del orden recomendado (ver [`README.md`](README.md)).
Identificadores de este plan: `DOC-1` … `DOC-9`.*

| | |
| --- | --- |
| **Repos** | `db`, `grading-engine`, `ai-orchestrator`, `web`, `docs` |
| **Tamaño** | L — unos 20–23 días de una persona |
| **Depende de** | Nada. Es el primero. |
| **Habilita** | Plan 2 (clasificación y sensibilidad por campo, tipos de documento para consentimientos y solicitudes ARCO-POL), Plan 3 (esquema de extracción por tipo, atributos canónicos), Plan 4 (catálogo de campos que se pueden mapear a un CRM) |

---

## 0. Resumen y respuesta corta

**Qué se pide.** Que un administrador del asegurador pueda crear y editar tipos de
documento (no solo los 11 que hoy están escritos en código) y configurar, por tipo,
qué hace falta para aceptar un documento: vigencia, vencimiento, campos obligatorios,
legibilidad, firma y sello, reglas propias.

**¿Un playbook por documento? No en su forma completa, pero sí su idea.** Lo
recomendado es una **definición de tipo de documento versionada**: un esquema de
campos más una lista de **reglas de aceptación** escritas en el mismo lenguaje de
expresiones que los playbooks y evaluadas por el mismo motor (zen-engine, en
`grading-engine`). No lleva pesos, tiers ni `ai_weight`, porque un documento no se
puntúa: se **acepta, se marca o se rechaza**.

**El costo casi no cambia.** Lo que cuesta dinero son las llamadas al modelo, y
la evaluación de reglas no hace ninguna:

| Qué se agrega | Costo de modelo por documento (Sonnet 5.5: US$2 / US$10 por millón in/out) | Latencia |
| --- | --- | --- |
| Reglas de aceptación deterministas sobre lo ya extraído | **US$0** | 5–30 ms en grading-engine |
| 10 campos más en el esquema del tipo | ≈ +US$0.002–0.004 (≈ +300 tokens de entrada, +150–300 de salida) | ≈ +1–2 s |
| Una verificación visual (¿firma?, ¿sello?, ¿foto?) | ≈ +US$0.0002 cada una (≈ 20 tokens de salida) | despreciable |
| **Un "playbook completo" por documento con su propio puntaje de IA** (una llamada más por documento) | ≈ +US$0.01–0.02 por documento; una solicitud de 3 documentos pasa de ≈ US$0.055 a ≈ US$0.09–0.11 | +5–10 s por documento |
| Segunda lectura de verificación con el modelo de escalamiento (Opus 5: US$5 / US$25) | ≈ +US$0.03–0.05 por documento | +10–20 s |

Referencias: una lectura de DUI costó US$0.0134 (3,009 tokens de entrada, 734 de
salida, `STATUS.md` 2026-11-03); una solicitud limpia de seguros, US$0.055.
Precios de `ai-orchestrator/src/lib/pricing.ts`.

**Conclusión:** control completo por tipo, sin llamadas nuevas al modelo. El costo
real es de mantenimiento: más configuración que alguien del asegurador tiene que
entender. Por eso el editor parte de plantillas y de un banco de pruebas
(`DOC-8`).

---

## 1. Qué existe hoy

Los tipos de documento son cadenas en inglés (`proof_of_income`) y viven en **seis
lugares de código** que hay que mantener a mano y en sincronía:

| Lugar | Qué guarda |
| --- | --- |
| `web/src/lib/constants.ts` `DOC_TYPES` | Los 11 tipos y su etiqueta en español. Lo usan `docTypeLabel()` (`labels.ts`) y el selector de respaldo |
| `web/src/lib/playbook-catalog.ts` `DOCUMENT_KEYS`, `REQUIRABLE_DOCUMENTS` | Las llaves que se pueden leer de cada tipo, para los selectores del editor de playbooks |
| `ai-orchestrator/src/playbooks/copilot.ts` `DOCUMENT_CATALOGUE` | La misma lista para el copiloto de playbooks ("no shared package; change both") |
| `ai-orchestrator/src/documents/client-facts.ts` `CLIENT_FACT_FIELDS` | Llaves que se piden siempre a constancias y DUI para actualizar al cliente |
| `ai-orchestrator/src/agents/language.ts` y `extraction-agent.ts` | Reglas del prompt; las llaves por documento llegan de `expected-fields.ts` (las que lee el playbook) |
| `db` — `intake_add_document()` | Acepta los `doc_type` que el playbook exige, más `supporting_document` |

**Las reglas de aceptación están repartidas** y ninguna es configurable por tipo:

| Regla | Dónde | Configurable |
| --- | --- | --- |
| MIME y 5 MiB | bucket `documents` (`20260816000000`) y `web/src/lib/constants.ts` | No (global) |
| Malware | `ai-orchestrator/src/documents/malware.ts` | No |
| Ilegible, señales de alteración o tipo equivocado ⇒ `flagged` | `ai-orchestrator/src/documents/status.ts` | No |
| Confianza mínima 0.6 por valor | `MIN_FIELD_CONFIDENCE` (audit V-6) | No (global) |
| `max_age_days` y `required_if` | `required_documents[]` del playbook; evaluado en `db`, en `ai-orchestrator/src/applications/required-documents.ts` y en `web/src/lib/required-documents.ts` | Sí, por producto |
| Aceptar un documento vencido con motivo | `accept_document_age()` (`20261104000000`) | Solo la edad |
| DUI vencido no se reutiliza | `reuse_client_document()` (`20261106000000`) | No (código fijo para `national_id`) |
| Identidad contra el DUI | `ai-orchestrator/src/applications/identity-check.ts` | No (código fijo para `national_id`) |

Lo que falta: crear un tipo nuevo sin desplegar código, decir qué campos lleva,
cuáles son obligatorios, y reglas como "la constancia debe tener firma y sello",
"el DUI no debe estar vencido", "el estado de cuenta debe tener al menos 3 meses",
"el NIT debe tener formato válido".

---

## 2. Objetivos y no objetivos

**Objetivos**

1. Los tipos de documento son **datos por tenant**, no código: crear, editar,
   versionar, archivar.
2. Cada tipo declara su **esquema de campos** (llave en inglés, etiqueta en
   español, clase de valor, obligatoriedad, formato, descripción para el modelo) y
   su **clasificación** (categoría de dato, sensible sí/no), que los planes 2–4
   consumen.
3. Cada tipo declara sus **requisitos de aceptación**: formatos, tamaño, páginas,
   legibilidad mínima, vigencia por defecto, vencimiento, campos obligatorios,
   verificaciones visuales y reglas propias en lenguaje de expresiones.
4. Los requisitos se **evalúan de forma determinista**, con el mismo motor de los
   playbooks, y **fallan cerrado**.
5. Cada documento registra **la versión exacta** de la definición con la que se
   leyó y se aceptó (como un puntaje registra su versión de playbook).
6. Una sola fuente de verdad: desaparecen las seis listas en código.

**No objetivos**

- Puntuar documentos individualmente. El puntaje sigue siendo de la solicitud.
- Mover la decisión de *qué documentos exige un producto* fuera del playbook. El
  playbook sigue diciendo cuáles, `required_if` y la vigencia del producto.
- Un OCR propio. Sigue siendo lectura directa del modelo.
- Reglas que crucen varios documentos (eso es del playbook y del agente de
  consistencia).

---

## 3. Opciones de diseño

| Opción | Qué es | A favor | En contra | Costo de modelo |
| --- | --- | --- | --- | --- |
| **A. Playbook completo por documento** | Cada tipo tiene un playbook con reglas, pesos, tiers y puntaje de IA | Máxima expresividad | Un documento no necesita puntaje; dos niveles de tiers confunden; el agente de consistencia por documento duplica llamadas | +US$0.01–0.02 por documento |
| **B. Definición de tipo versionada con reglas de aceptación (recomendada)** | Esquema de campos + requisitos declarativos + reglas `condition` con `on_fail: reject \| flag \| warn`, evaluadas por zen-engine | Mismo lenguaje y motor que los playbooks ("las reglas son datos"); cero llamadas nuevas; resultado explicable por regla | Un endpoint nuevo en grading-engine; una pantalla nueva | US$0 |
| C. Solo configuración declarativa (sin expresiones) | Casillas: vigencia, vencimiento, firma, campos obligatorios | Más simple de editar | Se queda corto en la primera regla rara ("ingreso > 0", "placa con formato") | US$0 |
| D. Extender el playbook del producto | Todo en `required_documents[]` | Sin tablas nuevas | Se repite la definición en cada producto; el tipo sigue sin existir como cosa | US$0 |

**B incluye a C**: el editor muestra casillas para los requisitos comunes y un
constructor de reglas (el de playbooks, `web/src/lib/playbook-rule-builder.ts`)
para lo demás. Los requisitos declarativos se traducen a reglas al evaluar, así
todo sale en una sola traza.

**Reparto de responsabilidades resultante**

| Pregunta | La responde |
| --- | --- |
| ¿Qué es una "constancia de ingresos", qué campos tiene y cuándo es aceptable? | El **tipo de documento** (tenant) |
| ¿Qué documentos pide este producto, cuándo (`required_if`) y con qué vigencia? | El **playbook** del producto |
| ¿Cómo pesa el ingreso en el riesgo? | El **playbook** del producto |
| ¿El documento es coherente con el formulario y con los demás documentos? | El **agente de consistencia** |

---

## 4. Modelo de datos (`db`)

Una migración nueva, `2026MMDD000000_document_types.sql`. Siguiendo
`supabase-postgres-best-practices` y el patrón de `playbooks`.

```sql
-- El tipo: identidad estable. La llave nunca cambia (los documentos y los
-- playbooks la referencian por texto).
create table document_types (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid references tenants (id) on delete cascade,   -- null = plantilla del sistema
  key          text not null check (key ~ '^[a-z][a-z0-9_]{1,62}$'),
  label        text not null check (length(btrim(label)) between 1 and 120),
  description  text,
  category     text not null default 'other'
               check (category in ('identity','income','financial','medical','vehicle',
                                   'property','credit','legal','consent','privacy','other')),
  kind         text not null default 'standard' check (kind in ('standard','catch_all')),
  status       text not null default 'active' check (status in ('active','archived')),
  current_version_id uuid,                                   -- la publicada vigente
  created_by   uuid references profiles (id) on delete set null,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (tenant_id, key),
  unique (tenant_id, id)                                     -- para FKs compuestas del mismo tenant
);

-- Las versiones: inmutables una vez publicadas (trigger, como playbooks).
create table document_type_versions (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid,
  document_type_id  uuid not null,
  version           integer not null check (version >= 1),
  status            text not null default 'draft' check (status in ('draft','published','archived')),
  definition        jsonb not null,                          -- § 5
  publication_requested_by uuid references profiles (id) on delete set null,
  publication_requested_at timestamptz,
  published_by      uuid references profiles (id) on delete set null,
  published_at      timestamptz,
  created_at        timestamptz not null default now(),
  unique (document_type_id, version),
  foreign key (tenant_id, document_type_id) references document_types (tenant_id, id) on delete cascade,
  constraint definition_valid check (document_type_definition_valid(definition))
);
create unique index document_type_versions_one_published
  on document_type_versions (document_type_id) where status = 'published';

-- Lo que cada documento usó.
alter table documents
  add column document_type_version_id uuid references document_type_versions (id) on delete restrict,
  add column acceptance jsonb;                               -- § 6.3
```

**Integridad de `documents.doc_type`.** Hoy es texto libre. Se agrega una FK
compuesta `documents (tenant_id, doc_type) → document_types (tenant_id, key)`.
Antes de aplicarla, la migración siembra para **cada tenant** los 11 tipos
actuales (con las llaves y etiquetas de `DOC_TYPES`, los campos de
`DOCUMENT_KEYS` y `CLIENT_FACT_FIELDS`) y además cualquier `doc_type` distinto que
aparezca en `documents` o en una definición de playbook (consulta de pre-vuelo,
como pide `RUNBOOK.md` § "Apply a migration"). Ningún documento cambia de llave.

**Plantillas del sistema.** Filas con `tenant_id is null`, mantenidas por
migración o por un superadmin. Un tenant no las edita: las **copia** a su catálogo
(`import_document_type_template(p_template_id)`). Así el catálogo base puede
crecer (pasaporte, NIT, estado de cuenta, recibo de servicio, declaración de
renta F-11, constancia de AFP, partida de nacimiento, formulario de
consentimiento firmado…) sin tocar los tipos que un asegurador ya ajustó.

**Funciones** (todas `security definer`, con `require_mfa_if_tenant_requires()` y
`audit_log`, igual que las de playbooks):

| Función | Quién | Qué hace |
| --- | --- | --- |
| `create_document_type(p_key, p_label, p_category, p_from_template default null)` | `tenant_admin`, `superadmin` | Crea el tipo y su versión 1 en borrador. Refusa una llave repetida o reservada |
| `save_document_type_draft(p_type_id, p_definition)` | `tenant_admin`, `superadmin` | Crea o reemplaza el borrador (nunca toca una publicada). Editar el borrador borra la solicitud de publicación (como `playbooks_clear_publication_request`) |
| `request_document_type_publication(p_version_id)` | `tenant_admin`, `superadmin` | Pide la publicación (maker-checker) |
| `publish_document_type_version(p_version_id)` | `tenant_admin`, `superadmin` | Archiva la publicada y publica el borrador en una transacción; actualiza `current_version_id`. Si `tenants.playbook_approval_required` está activo, exige que otra persona lo haya pedido (`second_approver_required`). Rechaza una definición que deje sin campo a un playbook publicado que lee `document.<key>.<campo>` (`breaks_published_playbook`) |
| `archive_document_type(p_type_id)` | `tenant_admin`, `superadmin` | Refusa si un playbook en borrador o publicado lo exige (`in_use`). Los documentos existentes siguen apuntando a él |
| `rename_document_type(p_type_id, p_label, p_description, p_category)` | `tenant_admin` | Solo metadatos; la llave no cambia (trigger) |
| `effective_requirements(p_playbook_id)` | `authenticated` (security invoker), `service_role` | Une `required_documents[]` del playbook con los valores por defecto del tipo (§ 6.4). Una sola definición para `db`, `ai-orchestrator` y `web` |
| `accept_document_check(p_document_id, p_check_id, p_reason)` | `underwriter`, `tenant_admin`, `superadmin` | Generaliza `accept_document_age()`: acepta un documento que falló una regla marcada `overridable`. Motivo obligatorio; `null` retira. `accept_document_age()` queda como envoltorio |

**RLS y privilegios.**

- `document_types` y `document_type_versions`: `select` para el personal del tenant
  y para todos los `authenticated` cuando `tenant_id is null` (plantillas). Ningún
  `insert`, `update` o `delete` para `authenticated`: solo las funciones.
- `documents.document_type_version_id` y `documents.acceptance`: no actualizables
  con JWT de usuario (privilegio de columna, como `content_sha256`).
- `anon`: nada (`anon_surface_test.sql` no cambia).

---

## 5. La definición de un tipo (`document_type_versions.definition`)

Llaves en inglés (invariante del workspace), textos en español.

```jsonc
{
  "schema_version": 1,

  // ── Campos ───────────────────────────────────────────────────────────────
  "fields": [
    {
      "key": "monthly_income",              // ^[a-z][a-z0-9_]{0,62}$, único en el tipo
      "label": "Ingreso mensual",
      "kind": "money",                      // text | number | money | date | boolean | enum | id_number | phone | email | address
      "currency": "USD",                    // solo money
      "required": true,                     // obligatorio para ACEPTAR el documento
      "description": "Salario bruto mensual que certifica la empresa", // va al prompt
      "min_confidence": 0.7,                // opcional; por defecto 0.6 (MIN_FIELD_CONFIDENCE)
      // Clasificación (la consumen los planes 2, 3 y 4):
      "category": "financial",              // identity | contact | demographic | financial | employment | health | biometric | vehicle | property | legal | other
      "sensitive": false,                   // dato personal sensible (LPDP Art. 4 lit. g)
      "pii": true,
      "canonical": "income.monthly_gross"   // atributo del cliente que alimenta (Plan 3); null si ninguno
    },
    { "key": "employer", "label": "Patrono", "kind": "text", "required": true,
      "category": "employment", "sensitive": false, "pii": false, "canonical": "employment.employer_name" },
    { "key": "job_title", "label": "Cargo", "kind": "text", "required": false,
      "category": "employment", "sensitive": false, "pii": false, "canonical": "employment.job_title" },
    { "key": "employee_since", "label": "Fecha de ingreso", "kind": "date", "required": false,
      "category": "employment", "sensitive": false, "pii": false, "canonical": "employment.start_date" }
  ],

  // ── Requisitos de aceptación ─────────────────────────────────────────────
  "acceptance": {
    "accepted_mime": ["application/pdf", "image/jpeg", "image/png"],   // subconjunto del bucket
    "max_size_mb": 5,                        // ≤ límite del bucket
    "pages": { "min": 1, "max": 3 },
    "sides": null,                           // ["front","back"] para el DUI
    "min_legibility": "poor",                // good | poor  (unreadable siempre falla)
    "must_match_type": true,                 // matches_doc_type === false ⇒ falla
    "tamper": "flag",                        // flag | reject
    "issue_date": { "required": true, "default_max_age_days": 90 },
    "expiry": { "must_be_valid": false, "min_days_left": 0 },
    "visual_checks": [
      { "id": "signature_present", "question": "¿El documento tiene firma de un responsable?" },
      { "id": "stamp_present",     "question": "¿El documento tiene sello de la empresa?" }
    ],
    "rules": [
      { "id": "signed_and_stamped", "label": "Firmada y sellada", "type": "condition",
        "expression": "check.signature_present == true and check.stamp_present == true",
        "on_fail": "flag", "overridable": true, "applicant_visible": true,
        "message": "La constancia debe estar firmada y sellada por la empresa",
        "applicant_message": "Sube una constancia firmada y sellada por tu empresa" },
      { "id": "income_positive", "label": "Ingreso legible y positivo", "type": "condition",
        "expression": "doc.monthly_income > 0",
        "on_fail": "flag", "overridable": true, "applicant_visible": false,
        "message": "No se pudo leer un ingreso mayor que cero" }
    ]
  },

  // ── Extracción ───────────────────────────────────────────────────────────
  "extraction": {
    "instructions": "Las constancias salvadoreñas suelen indicar el salario en letras y en números; usa el número.",
    "escalate_when_missing_required": true,  // usa el escalamiento existente (audit V-9)
    "transcribe": false                      // Plan 3 lo usa
  },

  // ── Para el solicitante (autoservicio) ───────────────────────────────────
  "applicant": {
    "instructions": "Constancia de salario emitida por tu empresa en los últimos 90 días.",
    "example_path": null                     // imagen de ejemplo en el bucket document-examples
  }
}
```

**Cómo se traducen los requisitos declarativos a reglas.** Al evaluar, el
orquestador antepone reglas generadas a las del usuario, con ids reservados
`sys_*`, de modo que la traza las muestra igual:

| Requisito | Regla generada | `on_fail` por defecto |
| --- | --- | --- |
| `required: true` en un campo | `sys_field_<key>`: el valor existe y su confianza ≥ mínimo | `flag` |
| `min_legibility` | `sys_legibility` | `flag` (`reject` si `unreadable`) |
| `must_match_type` | `sys_type_matches` | `flag` |
| `tamper` | `sys_tamper` | lo que diga `tamper` |
| `issue_date.required` | `sys_issue_date` | `flag` |
| `expiry.must_be_valid` | `sys_not_expired`: `doc.days_to_expiry >= min_days_left` | `reject` |
| `pages`, `sides` | `sys_pages`, `sys_sides` | `flag` |
| `accepted_mime`, `max_size_mb` | se validan **antes** de extraer (web e `intake_add_document`) | `reject` sin gastar modelo |

La vigencia (`default_max_age_days`) **no** se evalúa como regla del documento:
sigue siendo un requisito *del producto* (§ 6.4), porque depende de para qué se
usa el documento.

**Validación.** `document_type_definition_valid()` (check constraint) y su espejo
en `web` y en `grading-engine` (zod): llaves únicas y con forma correcta, `kind`
conocido, `enum` con opciones, límites dentro de los del bucket, ids de regla
únicos y que no empiecen con `sys_`, `on_fail` válido, a lo más 60 campos y 40
reglas. `grading-engine` además compila cada expresión (como hace con los
playbooks) antes de que se pueda publicar.

**Contexto de las expresiones.** Para no depender de funciones de fecha de ZEL, el
orquestador entrega números ya calculados:

| Variable | Valor |
| --- | --- |
| `doc.<key>` | El valor normalizado del campo (null si falta o si su confianza quedó bajo el mínimo) |
| `doc.age_days`, `doc.days_to_expiry`, `doc.pages` | Enteros; null si no se pueden calcular |
| `doc.legibility` | `"good"`, `"poor"` o `"unreadable"` |
| `check.<id>` | `true`, `false` o null para cada verificación visual |
| `form.<key>` | Respuesta del formulario de la solicitud (para reglas como `doc.national_id == form.national_id`) |

Una variable null hace la regla **indeterminada**, y una regla indeterminada se
trata como fallida con su `on_fail` (falla cerrado), salvo que la regla diga
`"on_indeterminate": "pass"` explícitamente — permitido solo para `warn`.

---

## 6. Evaluación de la aceptación

### 6.1 Dónde

`grading-engine` gana `POST /documents/evaluate` (con el mismo `SERVICE_AUTH_TOKEN`):

```ts
// Entrada
{ definition: DocumentTypeDefinition, context: { doc, check, form } }
// Salida
{ engine_version: "0.2.0+<sha>",
  outcome: "accepted" | "flagged" | "rejected",
  results: [{ rule_id, label, passed: true | false | null, on_fail, overridable, applicant_visible, message }] }
```

Reutiliza la traducción a JDM (`src/engine/jdm-builder.ts`) con una política más
simple: el resultado es el peor `on_fail` entre las reglas que fallaron
(`reject` > `flag` > `warn`).

¿Por qué en grading-engine y no dentro del orquestador? Porque así hay **un solo
motor de reglas con un solo `engine_version`**, y el editor puede probar una
definición con el mismo código que la aplicará. El costo es una llamada HTTP
interna más por documento, y que grading-engine debe estar despierto (en el plan
gratuito tarda ~45 s en despertar).

### 6.2 Cuándo

```text
subida ─▶ (web) MIME/tamaño/páginas de la definición ─▶ malware ─▶ extracción con el
esquema del tipo (§ 7) ─▶ POST /documents/evaluate ─▶ status + acceptance ─▶ client-facts
                                                         │
application.process ─────────────────────────────────────┘ re-evalúa si falta o si la
                                                           versión publicada cambió y alguien lo pidió
```

- Si grading-engine no responde, el documento queda `extracted` con
  `acceptance.outcome = "pending"`. El barrido (`pipeline_sweep_candidates`, nuevo
  tipo `acceptance`) lo reintenta. `application.process` **no puntúa** con un
  documento requerido en `pending`: lo evalúa en ese momento y, si sigue sin
  poder, bloquea a revisión manual como un documento faltante. Falla cerrado.

### 6.3 Qué se guarda

```jsonc
// documents.acceptance
{
  "document_type_id": "uuid",
  "document_type_version_id": "uuid",
  "version": 3,
  "engine_version": "0.2.0+abc1234",
  "evaluated_at": "2026-11-20T15:02:11Z",
  "outcome": "flagged",                       // accepted | flagged | rejected | pending
  "results": [
    { "rule_id": "sys_field_monthly_income", "passed": true },
    { "rule_id": "signed_and_stamped", "passed": false, "on_fail": "flag", "overridable": true,
      "message": "La constancia debe estar firmada y sellada por la empresa" }
  ],
  "overrides": [                               // escritas solo por accept_document_check()
    { "rule_id": "signed_and_stamped", "by": "uuid", "at": "…", "reason": "Firma digital verificada por teléfono" }
  ]
}
```

**Estados.** `rejected` es terminal para ese archivo (se pide otro);
`flagged` llega a la persona y no alimenta reglas, como hoy; `warn` deja el
documento `extracted` con la advertencia visible. Un documento con todas sus
fallas `overridable` aceptadas por un analista vuelve a contar como limpio para
los requisitos, y el puntaje lo lista en `rationale.accepted_document_exceptions`;
`auto_decide_case()` rechaza aprobar automáticamente una solicitud que tenga
alguno (ya lo hace con `accepted_outdated_documents`).

**`statusForExtraction()` desaparece como regla fija**: sus tres condiciones pasan a
ser `sys_legibility`, `sys_tamper` y `sys_type_matches`, con los mismos valores por
defecto, así el comportamiento de hoy es el valor por defecto de cada tipo.

**Al solicitante** (`intake_get()`), cada documento sigue llevando
`check.problems`, ahora con las reglas `applicant_visible: true` que fallaron y su
`applicant_message`. **Nunca** se muestran reglas de alteración ni de fraude
(invariante del 2026-11-06: decirle al falsificador qué se notó le enseña).

### 6.4 Precedencia entre tipo y playbook

`effective_requirements(p_playbook_id)` devuelve, por cada `required_documents[]`:

| Propiedad | Regla |
| --- | --- |
| `required`, `required_if` | Solo del playbook |
| `max_age_days` | Si el playbook **tiene la llave** (aunque sea `null` = sin límite) manda el playbook. Si no la tiene, hereda `acceptance.issue_date.default_max_age_days` del tipo |
| `extra_rules` (nuevo, opcional) | Reglas adicionales del producto sobre ese documento (p. ej. crédito exige firma digital) en el mismo formato; se agregan a las del tipo |

Hoy `max_age_days` se evalúa en tres lugares que "deben coincidir" (db,
orquestador, web). Con `effective_requirements()` los tres leen la misma
respuesta y solo queda una implementación de la herencia.

### 6.5 Casos particulares que hoy están en código

- **Identidad (`identity-check.ts`) y reutilización con vencimiento
  (`reuse_client_document`)** dependen de `national_id`. Se generalizan con una
  propiedad del tipo: `"role": "identity_document"` (a lo más un tipo por tenant
  la tiene). La comparación de nombre, número y fecha de nacimiento usa los campos
  con `canonical` `identity.full_name`, `identity.national_id`,
  `identity.date_of_birth`. Así un tenant puede usar pasaporte para extranjeros.
- **Lectura del DUI desde la cámara (`/api/identity/read`)** sigue siendo del tipo
  con `role = identity_document`.

---

## 7. Cambios en la extracción (`ai-orchestrator`)

1. **El esquema del tipo reemplaza a `playbookKeysBlock`.** El mensaje al modelo
   lista todos los campos de la versión publicada del tipo (llave, etiqueta, clase,
   descripción, obligatorio), más las llaves que el playbook lea y no estén en el
   esquema (el linter del editor lo impide para lo nuevo, pero los playbooks
   publicados antes deben seguir funcionando). `CLIENT_FACT_FIELDS` desaparece: lo
   reemplazan los campos con `canonical`.
2. **Verificaciones visuales.** El esquema de la herramienta (`record_extraction`)
   gana `checks: [{ id, value: boolean | null, note }]`, construido en cada llamada
   con los `visual_checks` del tipo. `ExtractionResultSchema` lo acepta opcional, así
   las extracciones guardadas siguen siendo válidas.
3. **Normalización por clase** después del modelo, en código: `money` y `number`
   con `parseAmount()` (ya existe), `date` a AAAA-MM-DD o null, `id_number` con
   validadores por formato (DUI con dígito verificador — `web/src/lib/dui.ts` tiene
   la lógica —, NIT), `phone` a E.164 como `intake_phone()`, `enum` contra sus
   opciones. Un valor que no se puede normalizar queda null con
   `excluded: "unparseable"`.
4. **Instrucciones del tipo** (`extraction.instructions`) van en el mensaje, no en
   el *system prompt*, para no romper el caché del prompt ni el
   `prompt_version` de todos los demás tipos.
5. **Escalamiento**: `extractionEscalation()` ya escala cuando falta una llave que
   el playbook lee; con `escalate_when_missing_required` también escala si falta un
   campo `required` del tipo. Un reintento por documento, como hoy.
6. **Versión registrada**: el job escribe `documents.document_type_version_id`
   antes de llamar al modelo; `scores.engine` gana
   `document_types: {"proof_of_income": 3, …}`.
7. **Copiloto de playbooks** (`DOCUMENT_CATALOGUE`) y `expected-fields.ts` leen el
   catálogo de la base de datos.

---

## 8. Interfaz (`web`)

**Configuración → Tipos de documento** (solo `tenant_admin` y `superadmin`).

1. **Lista**: nombre, llave, categoría, versión publicada, borrador pendiente,
   "usado en N productos", estado. Botones: *Nuevo*, *Desde plantilla*.
2. **Editor** con pestañas:
   - **General**: nombre, llave (solo al crear, con sugerencia desde el nombre y la
     advertencia de que no cambia), categoría, descripción, rol (documento de
     identidad).
   - **Campos**: tabla editable — etiqueta, llave, clase, obligatorio, sensible,
     categoría, atributo del cliente (selector del catálogo del Plan 3; mientras
     no exista, texto libre validado), descripción para el modelo. Insignia
     "sensible" en rojo.
   - **Aceptación**: casillas y números para lo declarativo (formatos, tamaño,
     páginas, legibilidad, vigencia por defecto, vencimiento, firma, sello) y el
     constructor de reglas del editor de playbooks para lo demás. Cada regla
     muestra `on_fail` (Rechazar / Marcar para revisión / Solo advertir), si un
     analista puede aceptarla y si el solicitante la ve.
   - **Solicitante**: instrucciones y una imagen de ejemplo.
   - **Prueba** (`DOC-8`): subir un archivo de muestra (sintético; la pantalla lo
     advierte) y ver la extracción, la evaluación regla por regla y el costo.
   - **Versiones**: diferencias entre versiones (reusar el diff del editor de
     playbooks), pedir publicación, publicar.
3. **"Usado en"**: productos y versiones de playbook que exigen el tipo.

**Otras pantallas que cambian**

- Editor de playbooks: los selectores de documento y de llave leen el catálogo; la
  regla del linter "la llave no está en el esquema del tipo" es error al publicar
  (antes de esto, "Otra llave" era libre).
- Lista de requisitos en la solicitud y en el caso: muestra cada regla de
  aceptación fallida con su mensaje, y "Aceptar de todos modos" para las
  `overridable` (generaliza el botón actual de documentos vencidos).
- Visor de documento: los campos en el orden del esquema, con los obligatorios
  primero y los que no se leyeron marcados.
- `docTypeLabel()` y `DOC_TYPES` se reemplazan por un proveedor de catálogo
  cargado en el layout del panel (una consulta por sesión, cacheada).

---

## 9. Cambios por repo

| Repo | Trabajo |
| --- | --- |
| `db` | Migración (tablas, FK, siembra por tenant, funciones, RLS, privilegios de columna, trigger de inmutabilidad y de llave fija); `effective_requirements()`; `accept_document_check()`; `intake_add_document()` valida contra la definición (MIME, tamaño); `intake_get()` devuelve etiquetas, instrucciones y problemas visibles; nuevo tipo `acceptance` en `pipeline_sweep_candidates()`; `seed.sql` crea el catálogo; suite `document_types_test.sql` |
| `grading-engine` | `POST /documents/evaluate`, validación zod de la definición, compilación de expresiones, pruebas |
| `ai-orchestrator` | Carga de la definición; prompt con esquema; `checks` dinámicos; normalización por clase; llamada a evaluate; estados; `client-facts.ts` lee `canonical`; identidad por `role`; copiloto y `expected-fields.ts` desde la BD; ruta `POST /document-types/test`; pruebas |
| `web` | Pantallas de § 8; ruta `POST /api/document-types/test` (sesión de admin, límite de tasa, reenvía al orquestador); proveedor de catálogo; eliminar `DOC_TYPES`, `DOCUMENT_KEYS`, `REQUIRABLE_DOCUMENTS`; pruebas de las librerías |
| `docs` | `supabase-schema.md` § "Document types"; `playbook-schema.md` § herencia de `max_age_days` y `extra_rules`; `architecture.md` "What reaches a rule" |

---

## 10. Migración y compatibilidad

- **Ninguna llave cambia.** Los documentos, los playbooks publicados y los puntajes
  guardados siguen siendo válidos.
- **Los documentos anteriores** quedan con `document_type_version_id` y
  `acceptance` en null. Se tratan con las reglas de hoy (las `sys_*` por defecto
  reproducen `statusForExtraction()`), y un botón "Re-evaluar" (sin costo de
  modelo) les aplica la definición vigente. "Re-extraer" (con costo) solo si se
  quieren los campos nuevos.
- **Producción**: ensayar la migración en una transacción que se revierte, como
  las anteriores; luego `apply_migration`. El orden de despliegue es `db` →
  `grading-engine` → `ai-orchestrator` → `web`; cada paso funciona con el
  anterior (la evaluación es opcional mientras grading-engine no tenga el
  endpoint: `pending` no bloquea hasta que el orquestador nuevo esté desplegado).
- **Semilla**: los 11 tipos con los mismos campos de hoy, y las reglas por defecto
  que reproducen el comportamiento actual. Una versión 1 publicada por tipo.

---

## 11. Pruebas

**pgTAP (`document_types_test.sql`), desde el atacante:**

- un `agent` o un `underwriter` no crea, edita, publica ni archiva tipos;
- un tenant no lee ni modifica los tipos de otro, ni sus versiones;
- un `tenant_admin` no edita una plantilla del sistema ni una versión publicada;
- la llave no se puede cambiar, ni con `update` directo ni con una función;
- un documento con un `doc_type` que no existe en su tenant es rechazado por la FK;
- `documents.acceptance` y `document_type_version_id` no se escriben con JWT;
- `accept_document_check()` es rechazado para un `agent`, otro tenant, una regla no
  `overridable` y una solicitud ya decidida;
- con `playbook_approval_required`, quien pide no puede publicar;
- archivar un tipo exigido por un playbook publicado falla con `in_use`;
- publicar una versión que quita un campo leído por un playbook publicado falla;
- `anon` no ve nada.

**grading-engine:** evaluación con reglas que pasan, fallan e indeterminadas; peor
`on_fail` gana; expresión inválida rechazada al validar; `engine_version` presente.

**ai-orchestrator:** el prompt contiene el esquema; `checks` dinámicos se validan;
normalización por clase; grading-engine caído deja `pending` y no puntúa; las
reglas `sys_*` por defecto dan los mismos estados que `statusForExtraction()` sobre
las fixtures existentes (prueba de regresión).

**web:** validación de la definición; precedencia de `max_age_days`; el linter de
llaves; la etiqueta de un tipo desconocido no rompe la pantalla.

**De punta a punta:** con las fixtures de `qa/2026-10-02/`, una constancia sin
firma queda `flagged` por `signed_and_stamped`; un analista la acepta con motivo;
la solicitud se puntúa y no se aprueba automáticamente.

---

## 12. Fases

| Fase | Contenido | Tamaño |
| --- | --- | --- |
| `DOC-1` | Tablas, FK, siembra, funciones, RLS, pruebas pgTAP. `web` lee el catálogo de la BD (etiquetas y selectores). Sin cambio de comportamiento | 3–4 días |
| `DOC-2` | Editor de tipos (general, campos, versiones, publicación) | 4–5 días |
| `DOC-3` | Extracción guiada por el esquema, verificaciones visuales, normalización por clase | 3 días |
| `DOC-4` | `POST /documents/evaluate`, `acceptance`, estados, `accept_document_check()`, `effective_requirements()`, integración con puntaje y aprobación automática | 5–6 días |
| `DOC-5` | Pestaña de aceptación en el editor (casillas + constructor de reglas) | 2–3 días |
| `DOC-6` | Autoservicio: instrucciones, ejemplo, problemas visibles | 2 días |
| `DOC-7` | Identidad por `role` (pasaporte u otro documento de identidad) | 1–2 días |
| `DOC-8` | Banco de pruebas en el editor | 2 días |
| `DOC-9` (opcional) | Copiloto: proponer campos y reglas a partir de un documento de ejemplo | 2 días |

`DOC-1` a `DOC-4` son el núcleo; `DOC-5` a `DOC-9` se pueden entregar después.

---

## 13. Riesgos y preguntas abiertas

- **Reglas demasiado estrictas bloquean el flujo.** Mitigación: el banco de
  pruebas, `warn` como opción, la aceptación con motivo, y una métrica en el panel:
  porcentaje de documentos rechazados o marcados por regla y por tipo.
- **Verificaciones visuales poco fiables** (firma y sello). El modelo puede
  equivocarse; por eso su valor por defecto es `flag` (revisa una persona) y no
  `reject`. Medirlas con `field_reviews` (precisión por verificación) antes de
  permitir `reject`.
- **Un tenant crea muchos tipos casi iguales.** Plantillas y "Desde plantilla"
  reducen la dispersión; el Plan 3 los une por `canonical`.
- **Latencia de grading-engine dormido** en el plan gratuito. Se suma a la que ya
  tiene el puntaje. Con un plan pagado desaparece.
- **Pregunta**: ¿quién del asegurador editará esto? Es la misma pregunta que sigue
  abierta para los playbooks (`PLAN.md` § "Open decisions"). El banco de pruebas y
  las plantillas son la respuesta parcial.

---

## 14. Lo que este plan deja listo para los siguientes

| Para | Qué deja |
| --- | --- |
| **Plan 2 (LPDP)** | `sensitive`, `category` y `pii` por campo, que alimentan el inventario de datos y el registro de actividades de tratamiento; tipos `consent_form` (formulario de consentimiento firmado, con `signature_present` como regla), `dsr_identity` (identificación de quien ejerce un derecho ARCO-POL) y `power_of_attorney` (poder del representante), sembrados como plantillas con `category: consent` o `privacy`; sensibilidad por tipo para restringir quién ve qué documento |
| **Plan 3 (datos)** | El esquema por tipo, que convierte "extraer todo" en "extraer todo lo definido", con clase de valor para normalizar y `canonical` para consolidar en la ficha del cliente; `extraction.transcribe` reservado |
| **Plan 4 (CRM)** | Un catálogo de campos con etiqueta, clase y sensibilidad que el editor de mapeos ofrece como origen; la sensibilidad limita qué se puede exportar |
