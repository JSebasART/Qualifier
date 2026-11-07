# Plan 3 — Todos los datos del cliente: captura completa, clasificación, ficha 360 y enriquecimiento

*Propuesta, 2026-11-07. Tercer plan del orden recomendado (ver [`README.md`](README.md)).
Identificadores: `DAT-1` … `DAT-9`.*

| | |
| --- | --- |
| **Repos** | `db`, `ai-orchestrator`, `web`, `docs` |
| **Tamaño** | L–XL — unos 25–30 días de una persona (sin las opciones marcadas) |
| **Depende de** | Plan 1 (esquema de campos por tipo de documento, `canonical`, sensibilidad); Plan 2 (finalidades y `has_consent`, `processing_state`, `field_locks`, acceso por sensibilidad, registro de almacenes, `access_log`) |
| **Habilita** | Plan 4 (perfil canónico del cliente como origen de la exportación, catálogo de atributos para el mapeo, segmentos como alcance de sincronización) |

---

## 0. Resumen y respuesta corta

**Qué se pide.** Tener acceso, desde el sistema, a **todos** los datos de cada
cliente, incluidos los que vienen dentro de los documentos; clasificarlos; y
usarlos para enriquecer el perfil.

**¿Una base NoSQL aparte? No por ahora.** La recomendación es **quedarse en
Postgres (Supabase)** con tres piezas nuevas:

1. una **tabla de hechos** tipada (`client_facts`), donde cada valor observado de
   un cliente —de un documento, del formulario, de una corrección del analista, de
   una solicitud de rectificación o de un cálculo— es una fila con su procedencia,
   confianza y clasificación;
2. un **perfil consolidado** (`client_profiles`, JSONB más columnas clave), que
   elige el valor vigente de cada atributo con reglas de supervivencia
   declaradas, y muestra los conflictos;
3. la **transcripción** del documento con búsqueda de texto completo en español,
   y opcionalmente búsqueda semántica con pgvector.

JSONB da la flexibilidad de un almacén de documentos sin abrir un **segundo lugar
con datos personales**. Una base NoSQL externa obligaría a: replicar el aislamiento
por tenant que hoy hace RLS, borrar en dos lugares cada solicitud de supresión
(Plan 2), sumar un subencargado más y otra transferencia internacional, y
sincronizar dos bases. Ninguna ventaja de rendimiento lo justifica al volumen
actual (decenas de solicitudes; incluso 100 000 documentos son unos 3 millones de
filas de hechos, cómodas en Postgres). El § 3 dice cuándo convendría reconsiderar.

**"Extraer todo", con dos límites que pone el Plan 2:**

- **Minimización y finalidad** (LPDP Arts. 5 lit. d y 32): se extrae todo lo que
  **el esquema del tipo de documento define** (Plan 1) — que ya es "todo lo útil",
  decidido por el asegurador y declarado en su aviso — más los campos que el modelo
  encuentre fuera del esquema, guardados como **no catalogados** para que un
  administrador decida si entran al esquema. En tipos con datos sensibles los
  campos fuera del esquema no se guardan.
- **Uso comercial** (ofertas, perfiles, segmentos de mercadeo) solo para titulares
  con el consentimiento `marketing` o `profiling_offers`, y nunca con datos
  sensibles.

---

## 1. Qué existe hoy

| Pieza | Dónde | Limitación |
| --- | --- | --- |
| Resultado de la extracción | `documents.extracted_data` (forma `ExtractionResult`: `fields[{key,label,value,confidence}]`, fechas, legibilidad, señales) | Una llave por documento, en JSON; nombres elegidos por el modelo para lo que el playbook no pidió; sin clase de valor; no se puede consultar entre documentos ni entre clientes |
| Llaves pedidas | `expected-fields.ts` (las del playbook) + `CLIENT_FACT_FIELDS` | Lo demás queda a criterio del modelo ("every relevant field") |
| Perfil del cliente | Columnas de `clients` + `clients.field_sources` (procedencia por columna) | Solo 7 columnas se actualizan desde documentos (`client-facts.ts`): salario, patrono, ocupación, dirección, distrito, departamento, estado familiar |
| Correcciones del analista | `field_reviews` + `review_document_field()` | Corrigen un valor del documento, no alimentan al perfil |
| Búsqueda | `client_list.search_text` (nombre, correo, teléfono, DUI, ciudad, patrono, referencia, etiquetas) | Nada de lo que dicen los documentos |
| Preguntas sobre un caso | `/cases/:id/ask` sobre `case_bundle()` | Sin el texto de los documentos |

---

## 2. Opciones de almacenamiento

| Opción | Qué es | A favor | En contra | Veredicto |
| --- | --- | --- | --- | --- |
| **A. Tabla de hechos tipada en Postgres** | Una fila por valor observado, con columnas por tipo (`value_text`, `value_number`, `value_date`, `value_bool`, `value_json`) | Consultas tipadas e indexables; historial completo; procedencia por valor; RLS; un solo lugar para ARCO-POL | Consultas tipo EAV más largas de escribir | **Sí**: fuente de verdad |
| **B. JSONB por cliente** (estilo documento) | `client_profiles.attributes jsonb` | Lectura rápida de la ficha; flexible | Sin historial; difícil de auditar | **Sí**, como vista materializada del perfil vigente encima de A |
| C. NoSQL externa (MongoDB Atlas, Firestore, DynamoDB) | Otra base con documentos JSON | Esquema libre, escala horizontal | Segundo almacén de datos personales; sin RLS; doble borrado; nuevo subencargado y transferencia; sincronización | **No** ahora |
| D. Motor de búsqueda (OpenSearch, Typesense, Meilisearch) | Índice secundario alimentado por eventos | Búsqueda difusa y facetada a gran escala | Otro sistema que operar y otro almacén personal | **Después**, si la búsqueda en Postgres no alcanza |
| E. Almacén analítico (BigQuery, ClickHouse, DuckDB) | Copia seudonimizada para análisis | Consultas analíticas pesadas sin cargar producción | Copia más; requiere seudonimizar (Art. 4 lit. q) | **Después**, para analítica de cartera |
| F. Vectores (pgvector en el mismo Postgres) | Fragmentos de texto con embeddings | Búsqueda semántica y preguntas sobre documentos | Necesita un proveedor de embeddings (subencargado nuevo) | **Opcional** (`DAT-8`) |

**Cuándo reconsiderar C/D/E:** más de ~20 millones de hechos o búsquedas difusas
lentas (> 1 s p95) con índices correctos → D; necesidad de cruzar cartera de
varios años con BI → E, siempre seudonimizado. Ninguno reemplaza a A como
fuente de verdad.

---

## 3. Arquitectura

```text
           Documento ──▶ extracción guiada por el esquema del tipo (Plan 1)
                              │  fields (catalogados) + extras (no catalogados) + checks
                              ▼
   Formulario ──▶ record_*_facts() ──▶ client_facts  ◀── correcciones (field_reviews)
   (al enviar)                          (ledger)       ◀── rectificaciones (Plan 2, dsr)
                              │                        ◀── derivados (client.enrich)
                              ▼
                   refresh_client_profile()  ── reglas de supervivencia por atributo
                              │
              ┌───────────────┼─────────────────────────┬─────────────────────┐
              ▼               ▼                         ▼                     ▼
      client_profiles   attribute_conflicts     columnas de clients    eventos de cambio
      (ficha 360,       (para el analista)      (formularios, listas)  (los consume el Plan 4)
       segmentos)
           Documento ──▶ document.transcribe (opcional) ──▶ document_texts (tsvector) ──▶ búsqueda
```

---

## 4. Modelo de datos (`db`)

### 4.1 Catálogo de atributos canónicos — `client_attributes`

```sql
create table client_attributes (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid references tenants (id),        -- null = de la plataforma
  key text not null check (key ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$'),  -- 'income.monthly_gross', 'custom.club_member'
  label text not null,
  kind text not null check (kind in ('text','number','money','date','boolean','enum','id_number','phone','email','address')),
  options text[],
  category text not null,                        -- el mismo vocabulario del Plan 1
  sensitive boolean not null default false,
  cardinality text not null default 'single' check (cardinality in ('single','multi','series')),
  survivorship text not null default 'latest_evidence'
    check (survivorship in ('latest_evidence','highest_confidence','form_first','document_first','manual_only')),
  conflict_tolerance numeric,                    -- p. ej. 0.10 = difieren más de 10 % ⇒ conflicto
  client_column text,                            -- columna de clients que refleja este atributo, si hay
  client_column_transform text,                  -- 'monthly_to_annual', …
  identity boolean not null default false,       -- nunca se sobreescribe solo (como hoy client-facts)
  status text not null default 'active',
  unique (tenant_id, key)
);
```

**Semilla de la plataforma** (llaves en inglés): `identity.full_name`,
`identity.national_id`, `identity.date_of_birth`, `identity.nationality`,
`contact.email`, `contact.phone`, `address.line1`, `address.district`,
`address.municipality`, `address.department`, `address.country`,
`family.marital_status`, `family.dependents_count`, `employment.status`,
`employment.employer_name`, `employment.employer_id` (catálogo, § 6),
`employment.job_title`, `employment.occupation_code`, `employment.start_date`,
`employment.tenure_years` (derivado), `income.monthly_gross`,
`income.annual_gross`, `income.band` (derivado), `health.bmi`,
`health.condition_count`, `health.smoker`, `health.glucose_mg_dl`,
`vehicle.year`, `vehicle.plate`, `property.value`, `credit.loan_amount`,
`credit.term_months`, `document.national_id_expiry` (para avisar vencimientos).
Los `health.*` llevan `sensitive = true`.

Los campos de los tipos de documento (Plan 1) y las preguntas del formulario
(`form_schema.fields[].canonical`, nuevo) apuntan a estas llaves. Un tenant agrega
las suyas bajo `custom.*`.

### 4.2 Hechos — `client_facts`

```sql
create table client_facts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null,
  client_id uuid not null,
  attribute_key text,                            -- null = no catalogado (extra)
  source_kind text not null check (source_kind in ('document','form','analyst','dsr','derived','import','crm')),
  -- procedencia
  document_id uuid, document_type_version_id uuid, field_key text,   -- source_kind = document
  application_id uuid,                                               -- document o form
  field_review_id uuid, dsr_id uuid, actor_id uuid,                  -- analyst / dsr
  method text,                                                       -- derived: 'income_band@1'
  -- valor (exactamente uno no nulo, check)
  value_text text, value_number numeric, value_date date, value_bool boolean, value_json jsonb,
  raw_value text,                                -- como se leyó, antes de normalizar
  label text,                                    -- etiqueta en español del modelo para extras
  confidence numeric check (confidence between 0 and 1),
  evidence_date date,                            -- issue_date del documento, fecha de la respuesta, etc.
  -- clasificación copiada al escribir (así una reclasificación posterior no reescribe la historia)
  category text not null, sensitive boolean not null,
  status text not null default 'current' check (status in ('current','superseded','excluded','retracted')),
  excluded_reason text,                          -- 'low_confidence', 'unparseable', 'document_flagged', 'document_rejected'
  superseded_by uuid,
  created_at timestamptz not null default now(),
  foreign key (tenant_id, client_id) references clients (tenant_id, id) on delete cascade
);
create index client_facts_client_attr on client_facts (tenant_id, client_id, attribute_key) where status = 'current';
create index client_facts_attr_num   on client_facts (tenant_id, attribute_key, value_number) where status = 'current';
create index client_facts_attr_text  on client_facts using gin (value_text gin_trgm_ops) where status = 'current';
create index client_facts_document   on client_facts (document_id);
```

- **Escritura**: solo `service_role` y funciones (`record_document_facts`,
  `record_form_facts`, `record_analyst_fact` — la llama `review_document_field()`
  —, `record_dsr_fact` del Plan 2, `record_derived_facts`). Ningún rol de usuario
  inserta, actualiza ni borra.
- **Re-extraer** un documento marca sus hechos anteriores `superseded` y escribe
  los nuevos; nada se borra salvo por supresión (Plan 2) o retención.
- **Documentos `flagged` o `rejected`** (Plan 1): sus hechos se escriben con
  `status = excluded` y el motivo, para verlos en la ficha sin que ganen.
- **Lectura**: el personal del tenant; los hechos `sensitive` solo
  `underwriter`, `tenant_admin`, `superadmin` (política RLS que usa la misma
  regla del Plan 2 `LPD-10`); `blocked` y `erased` invisibles.

### 4.3 Perfil consolidado — `client_profiles` y conflictos

```sql
create table client_profiles (
  tenant_id uuid not null, client_id uuid not null,
  attributes jsonb not null,      -- {"income.monthly_gross": {"value": 2400, "fact_id": "…", "source": "document",
                                  --   "evidence_date": "2026-09-28", "confidence": 0.97, "sensitive": false}, …}
  completeness numeric,           -- % de atributos esperados presentes
  version integer not null,       -- sube en cada cambio; lo usa el Plan 4
  refreshed_at timestamptz not null,
  primary key (tenant_id, client_id)
);
create index client_profiles_attrs on client_profiles using gin (attributes jsonb_path_ops);

create table attribute_conflicts (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null, client_id uuid not null, attribute_key text not null,
  fact_ids uuid[] not null, detail jsonb,
  status text not null default 'open' check (status in ('open','resolved','dismissed')),
  resolved_by uuid, resolved_at timestamptz, resolution_fact_id uuid
);
```

**Reglas de supervivencia** (`refresh_client_profile(p_client_id)`, idempotente):

1. Un hecho `dsr` (rectificación del titular, Plan 2) gana sobre todo.
2. Luego un hecho `analyst` (corrección o confirmación).
3. Luego la regla del atributo: `latest_evidence` (el de evidencia más reciente con
   confianza ≥ umbral), `highest_confidence`, `form_first`, `document_first` o
   `manual_only`.
4. Atributos `identity = true` **nunca** se reemplazan solos: una diferencia abre
   un conflicto y el agente de consistencia la sigue viendo como hoy. Es la misma
   regla de `client-facts.ts` ("overwriting the record would hide it").
5. Dos hechos vigentes que difieren más que `conflict_tolerance` abren un
   conflicto; el perfil muestra el ganador con el aviso.
6. Un atributo con `field_locks` (Plan 2) no cambia mientras dure el bloqueo.

La función actualiza también las columnas de `clients` que tengan
`client_column`, con `field_sources` como hoy. **`client-facts.ts` se reduce a
llamar a esta función**: la lógica de "solo si es al menos igual de reciente" pasa a
ser la regla `latest_evidence`.

### 4.4 Texto de los documentos — `document_texts`

```sql
create table document_texts (
  document_id uuid primary key, tenant_id uuid not null, client_id uuid not null,
  pages integer, text text not null,             -- transcripción en Markdown, por página
  -- unaccent() no es IMMUTABLE; una columna generada exige una envoltura que sí lo sea
  -- (función SQL immutable que llama a public.unaccent('public.unaccent', $1)).
  tsv tsvector generated always as (to_tsvector('spanish', unaccent_immutable(text))) stored,
  model text, prompt_version text, created_at timestamptz default now()
);
create index document_texts_tsv on document_texts using gin (tsv);
```

Lectura con las mismas reglas que el documento (incluida la sensibilidad del
Plan 2). Se registra en `personal_data_stores` con `erase_handler = delete`.

### 4.5 Segmentos — `client_segments`

```sql
create table client_segments (
  id uuid primary key default gen_random_uuid(), tenant_id uuid not null,
  name text not null, purpose text not null,     -- 'operations' | 'commercial_management' | 'marketing'
  definition jsonb not null,                     -- {"all": [{"attr": "income.monthly_gross", "op": ">=", "value": 1500}, …]}
  owner_id uuid, shared boolean default false, created_at timestamptz default now()
);
```

La definición solo puede usar atributos no sensibles cuando `purpose` es
comercial o de mercadeo (check en la función que la guarda), y la evaluación
excluye titulares sin el consentimiento de esa finalidad o con
`processing_state` distinto de `active`.

### 4.6 Registro en el inventario (Plan 2)

| Tabla | `access_handler` | `erase_handler` | `retention_class` |
| --- | --- | --- | --- |
| `client_facts` | `include` (con fuente y fecha) | `delete` (sus valores; se conserva el conteo) | la de su solicitud o documento |
| `client_profiles` | `include` | `delete` y reconstruir vacío | igual |
| `attribute_conflicts` | `include` | `delete` | igual |
| `document_texts` | `include` (o resumen, según modalidad) | `delete` | `document_file` |
| `client_segments` | `exclude` (sin datos personales) | — | — |

---

## 5. Pipeline (`ai-orchestrator`)

### 5.1 Extracción completa

- El prompt ya lista los campos del esquema del tipo (Plan 1, `DOC-3`). Se agrega
  una instrucción: "además de estos, reporta en `extras` cualquier otro dato que el
  documento imprima, con una llave en inglés snake_case y su etiqueta en español".
  `extras` es un arreglo separado de `fields` para que nunca se confunda con una
  llave del playbook.
- En tipos con algún campo `sensitive`, **no se piden extras** (minimización).
- Cada extra se guarda como hecho con `attribute_key = null`. La pantalla
  **Tipos de documento → Campos no catalogados** los agrupa por llave y frecuencia
  ("`afp_name` apareció en 37 constancias"), y un clic los agrega al esquema en un
  borrador nuevo del tipo, con su atributo canónico.

### 5.2 Escritura de hechos

Dentro del mismo job `document.extract`, después de la evaluación de aceptación:
`record_document_facts(p_document_id, p_facts jsonb)` con los valores ya
normalizados por clase (Plan 1), la clasificación del campo en esa versión del
tipo, y el `excluded_reason` de los que no pasaron la confianza mínima. Al enviar
la solicitud, `record_form_facts(p_application_id)` hace lo mismo con las
respuestas del formulario que tengan `canonical`.

### 5.3 Transcripción (opcional por tipo, `DAT-6`)

Job aparte `document.transcribe`, de baja prioridad, solo para tipos con
`extraction.transcribe = true` y titulares con `ai_processing` consentido. Dos
modos:

| Modo | Modelo | Costo aproximado por página (≈1 600 tokens de entrada, 500–1 200 de salida) | Cuándo |
| --- | --- | --- | --- |
| Inmediato | Haiku 4.5 (US$1/US$5 por millón) | ≈ US$0.004–0.008 | Cuando el analista lo necesita pronto |
| Por lotes | Haiku 4.5 con la API de lotes (≈50 % menos) | ≈ US$0.002–0.004 | Por defecto, y para el relleno histórico |
| Dentro de la extracción | El mismo Sonnet 5.5 (US$2/US$10) | ≈ US$0.005–0.012 extra | No recomendado: alarga la llamada que bloquea el puntaje |

Una solicitud típica de 3–4 páginas: **≈ US$0.01–0.03 más** con Haiku por lotes,
sobre los ≈ US$0.055 de hoy. Cada llamada se registra en `ai_usage` con
`agent = 'transcription'` y respeta el tope de gasto del tenant.

### 5.4 Enriquecimiento derivado (`client.enrich`, `DAT-5`)

Determinista, versionado (`method = 'nombre@versión'`), sin modelo:

| Atributo | Método |
| --- | --- |
| `identity.age` | Desde la fecha de nacimiento |
| `identity.national_id_valid` | Dígito verificador del DUI (`web/src/lib/dui.ts`, portado) |
| `address.*` normalizada | Distrito, municipio y departamento oficiales desde el texto de la dirección (`web/src/lib/sv-geography.ts`, portado o expuesto como tabla) |
| `contact.phone` normalizado | E.164 como `intake_phone()` |
| `contact.email_kind` | personal / corporativo (dominio) |
| `employment.employer_id` | Catálogo por tenant `employers (id, name, aliases[], sector, nit)` con coincidencia por alias y trigramas; las coincidencias dudosas quedan para confirmar |
| `employment.tenure_years` | Desde `employment.start_date` |
| `employment.occupation_code` | Catálogo de ocupaciones (p. ej. CIUO-08) por coincidencia; opcional |
| `income.annual_gross`, `income.band` | Desde el mensual; bandas configurables (las de `dashboard_metrics()` por defecto) |
| `document.national_id_expiry` y "vence pronto" | Para avisar al personal antes de que un DUI vencido bloquee una renovación |

**Enriquecimiento externo** — fuera de este plan, cada uno con su propia
evaluación legal: buró de crédito (diseño completo en
`docs/research/2026-11-06-credit-bureaus-el-salvador.md`; **sus datos no entran a
`client_facts`** por el deber de reserva del D.L. 695, viven en sus tablas
cifradas), validación de identidad contra un registro (`IDENTITY_REGISTRY_URL`
ya existe), geocodificación.

### 5.5 Consolidación y eventos

Después de escribir hechos: `refresh_client_profile()` (job `client.profile_refresh`,
llave única por cliente para no repetir). Si el perfil cambió, sube
`client_profiles.version` — es la señal que el Plan 4 usa para sincronizar.

### 5.6 Relleno histórico (`DAT-2`)

Un script de una sola vez convierte cada `documents.extracted_data` existente en
hechos (sin costo de modelo), aplica las reglas de supervivencia y genera los
perfiles. Re-extraer documentos viejos para obtener los campos nuevos del esquema
es opcional y cuesta como una extracción (≈ US$0.013 por documento).

---

## 6. Acceso desde el sistema (`web`)

1. **Ficha 360** — pestaña **Datos** en la página del cliente:
   - atributos agrupados por categoría (identidad, contacto, domicilio, empleo,
     ingresos, salud…), con valor, fuente ("Constancia del 28-sep-2026",
     "Formulario de la solicitud N.º 13", "Corregido por Ana López"), confianza y
     fecha;
   - **historial** de cada atributo (todos los hechos, incluidos los excluidos y
     sustituidos, con el motivo);
   - **conflictos** abiertos con "Elegir este valor" (crea un hecho `analyst`);
   - insignias del Plan 2: "En revisión por rectificación", "Tratamiento limitado";
   - datos sensibles ocultos para quien no tiene el rol, con "acceso restringido";
   - **completitud** del perfil y qué falta;
   - cada apertura escribe `client.viewed` en `access_log` (Plan 2).
2. **Documento** — el visor muestra todos los campos del esquema (los
   obligatorios primero), los extras, y la transcripción con el texto buscado
   resaltado.
3. **Búsqueda global** en la barra superior: nombre, DUI, teléfono, correo,
   patrono y, para quien tenga permiso, el texto de los documentos (`tsvector`
   con `unaccent`, más `pg_trgm` para errores de tipeo). Resultados agrupados por
   cliente, solicitud y documento. Se registra `search.performed` (sin el texto).
4. **Filtros avanzados y segmentos** en Clientes: constructor de condiciones sobre
   atributos del perfil (operadores según la clase), conteo en vivo, guardar como
   segmento con su finalidad, exportar CSV (con `export.generated` en
   `access_log`). El Plan 4 agrega "Sincronizar con el CRM".
5. **Preguntas sobre el caso** (`/cases/:id/ask`): el paquete gana los hechos
   vigentes y la transcripción, y las citas pueden señalar documento y página.
   Sigue la minimización del Plan 2 (`minimizeForModel`).
6. **Analítica**: distribución de ingresos, ocupaciones, geografía y completitud
   por producto en el panel, siempre agregada y con un mínimo de 5 titulares por
   grupo para que nada identifique a una persona.

**API interna** (RPC `security invoker`, para `web` y luego para la API pública
del Plan 4): `client_profile_get(p_client_id)`, `client_fact_history(p_client_id,
p_attribute)`, `search_clients(p_query, p_filters)`, `segment_preview(p_definition,
p_purpose)`, `segment_members(p_segment_id, p_cursor)`.

---

## 7. Calidad de datos (`DAT-7`)

- **Cobertura** por atributo y por tipo de documento: % de documentos donde el campo
  se leyó con confianza suficiente.
- **Precisión**: `field_review_accuracy()` ya existe; se agrega por versión del tipo
  de documento y por versión del prompt, para ver si un cambio de modelo empeoró un
  campo (`CAL-1`).
- **Conflictos**: tasa por atributo; un atributo con muchos conflictos indica una
  extracción mala o un formulario confuso.
- **Extras**: qué llaves aparecen fuera del esquema (alimenta el catálogo).
- Alerta en el vigilante si la confianza media de un campo cae más de 10 puntos en
  una semana.

---

## 8. Privacidad aplicada (lo que este plan hereda del Plan 2)

| Regla del Plan 2 | Cómo se aplica aquí |
| --- | --- |
| Inventario obligatorio | Las cinco tablas de § 4.6 se registran en la misma migración; la prueba pgTAP del invariante las exige |
| Acceso (Art. 8) | `data_subject_footprint()` incluye hechos, perfil, conflictos y transcripciones; el informe muestra la fuente de cada valor |
| Portabilidad (Art. 14) | Solo hechos `form` y documentos subidos por el titular; los `derived` son inferidos: van en el acceso, no en la portabilidad |
| Rectificación (Art. 9) | `record_dsr_fact()` escribe el valor corregido, que gana la supervivencia; `field_locks` congela el atributo durante la revisión |
| Supresión (Art. 10) | Borra hechos, perfil, conflictos y textos; los segmentos no guardan personas |
| Limitación, oposición, bloqueo | Excluidos de búsqueda (bloqueados), de segmentos y de exportes; visibles en la ficha con la insignia |
| Finalidad y consentimiento | Segmentos comerciales y de mercadeo solo con `commercial_management` / `marketing` / `profiling_offers`; transcripción y extras solo con `ai_processing` |
| Sensibles | Ocultos por rol; nunca en segmentos comerciales; sin extras en tipos sensibles |
| Retención | Hechos y textos siguen la clase de su documento o solicitud |

---

## 9. Cambios por repo

| Repo | Trabajo |
| --- | --- |
| `db` | Migraciones de § 4; funciones `record_*_facts`, `refresh_client_profile`, `search_clients`, segmentos; `unaccent`, `pg_trgm` (y `vector` si `DAT-8`); RLS por sensibilidad y estado; registro en `personal_data_stores`; `form_schema.fields[].canonical`; suites `client_facts_test.sql` y `search_test.sql` |
| `ai-orchestrator` | `extras` en la herramienta de extracción; escritura de hechos; `client-facts.ts` → `refresh_client_profile`; jobs `document.transcribe`, `client.enrich`, `client.profile_refresh`; script de relleno; paquete de `/cases/:id/ask` |
| `web` | Ficha 360, visor con extras y transcripción, búsqueda global, filtros y segmentos, campos no catalogados, editor del catálogo de atributos y de patronos, analítica |
| `docs` | `supabase-schema.md` § "Client facts"; `architecture.md` (nueva sección de datos); esquema `tramiq.subject-export/v1` actualizado |

---

## 10. Fases

| Fase | Contenido | Tamaño |
| --- | --- | --- |
| `DAT-1` | Catálogo de atributos, `client_facts`, escritura desde extracción y formulario, RLS, inventario, pruebas | 5–6 días |
| `DAT-2` | Perfil consolidado, reglas de supervivencia, conflictos, reemplazo de `client-facts.ts`, relleno histórico | 5 días |
| `DAT-3` | Ficha 360 y visor de documento completo | 4–5 días |
| `DAT-4` | Extras y campos no catalogados | 2–3 días |
| `DAT-5` | Enriquecimiento derivado y catálogo de patronos | 3–4 días |
| `DAT-6` | Transcripción y búsqueda global | 3–4 días |
| `DAT-7` | Filtros avanzados, segmentos y calidad de datos | 4 días |
| `DAT-8` (opcional) | pgvector y búsqueda semántica (necesita proveedor de embeddings: nuevo subencargado, pasa por el Plan 2) | 3 días |
| `DAT-9` (opcional) | Réplica analítica seudonimizada | 4–5 días |

---

## 11. Pruebas

**pgTAP, desde el atacante:** ningún rol de usuario inserta, actualiza o borra
hechos, perfiles ni textos; un `agent` no lee hechos sensibles ni transcripciones
de documentos sensibles; un tenant no lee los de otro, ni por `search_clients` ni
por `segment_preview`; los titulares `blocked` y `erased` no aparecen en búsquedas
ni segmentos; un segmento de mercadeo con un atributo sensible es rechazado; un
segmento de mercadeo no devuelve titulares sin consentimiento; `anon` no ve nada.

**Orquestador:** supervivencia (cada regla, identidad nunca sobreescrita,
`field_locks`), conflictos con tolerancia, re-extracción sustituye, documentos
marcados excluidos, extras separados de `fields`, sin extras en tipos sensibles,
relleno idempotente.

**web:** constructor de segmentos, máscara por rol, historial.

**Regresión:** las 7 columnas de `clients` que hoy actualiza `client-facts.ts`
quedan con los mismos valores tras el relleno sobre los datos sembrados.

---

## 12. Riesgos

- **El catálogo crece desordenado.** Mitigación: llaves canónicas de la plataforma
  primero, `custom.*` para lo propio, y la cola de no catalogados con frecuencia.
- **Tamaño de la base.** ~30 hechos por documento; 100 000 documentos ≈ 3 millones
  de filas y ≈ 1 GB con índices y textos. El plan gratuito de Supabase (500 MB) no
  alcanza: plan pagado antes de datos reales (también lo pide el Plan 2).
- **Usar datos para lo que el titular no autorizó.** Toda consulta comercial pasa
  por la finalidad del segmento; ninguna pantalla permite exportar fuera de un
  segmento con finalidad.
- **Conflictos que nadie resuelve.** Aparecen en el caso y en el panel; el
  agente de consistencia ya ve las diferencias que importan para el riesgo.

---

## 13. Lo que deja para el Plan 4

- **`client_profiles` como única fuente** de lo que se exporta: llaves estables
  (`client_attributes.key`) que el editor de mapeos ofrece como origen, con su
  clase y sensibilidad.
- **`client_profiles.version`**: el Plan 4 agrega el disparador que emite
  `client.profile_changed` a su bandeja de salida.
- **Segmentos con finalidad** como alcance de una sincronización ("enviar al CRM
  los clientes del segmento X").
- **`custom.*`** y el catálogo de patronos como datos que el CRM puede recibir.
