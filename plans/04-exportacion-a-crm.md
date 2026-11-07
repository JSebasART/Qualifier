# Plan 4 — Exportación a CRM (HubSpot, Dynamics 365, Odoo y cualquier otro)

*Propuesta, 2026-11-07. Cuarto plan del orden recomendado (ver [`README.md`](README.md)).
Identificadores: `CRM-0` … `CRM-10`.*

| | |
| --- | --- |
| **Repos** | `db`, `ai-orchestrator` (módulo de integraciones), `web`, `docs` |
| **Tamaño** | Núcleo (`CRM-1` a `CRM-4` + un conector + `CRM-8`): unos 30 días; cada conector adicional, 4–6 días |
| **Depende de** | Plan 3 (perfil canónico `client_profiles`, catálogo `client_attributes`, segmentos), Plan 2 (consentimientos, estado de tratamiento, `data_transfers`, propagación con plazos, aviso que lista destinatarios), Plan 1 (catálogo de campos con sensibilidad) |
| **Cierra del análisis de brechas** | Parte de `NEG-6` (integraciones con sistemas del cliente) |

---

## 0. Resumen y recomendación

**Advertencia del propio análisis de brechas (`NEG-6`):** "no construir en
abstracto: preguntar qué exige el primer cliente". Este plan lo respeta así:
construir primero **una base genérica que sirve para cualquier CRM** (bandeja de
eventos, webhooks firmados, API pública y exportación de archivos), y después
**solo el conector nativo que pida el primer cliente**, sobre una interfaz común.

**Arquitectura recomendada, en capas:**

| Capa | Qué es | Cubre |
| --- | --- | --- |
| 0. Modelo canónico + bandeja de salida | Qué se exporta (`tramiq.crm.v1`, construido sobre el perfil del Plan 3), cuándo (eventos transaccionales) y a quién (destinos por tenant), con los filtros de privacidad del Plan 2 | Todo lo demás |
| 1. Entrega genérica | **Webhooks** firmados (estándar *Standard Webhooks*), **API REST** de lectura con llaves por tenant, **archivos** CSV/XLSX con las plantillas de importación de cada CRM | "Cualquier otro": Salesforce, Zoho, Pipedrive, Monday… vía Zapier, Make, n8n o Power Automate, o importación manual |
| 2. Conectores nativos | Adaptadores con la misma interfaz: HubSpot, Dynamics 365 (Dataverse), Odoo | Los tres pedidos, sin que el asegurador programe nada |
| 3. Opcional | Nango autoalojado (OAuth y sincronización para cientos de APIs) o una API unificada comercial | La cola larga, si la demanda aparece |

**Por qué no empezar con una API unificada comercial** (Merge, Apideck,
Unified.to): resuelve muchos CRM con una integración, pero cobra por cuenta
conectada, hace pasar los datos personales por un tercero (subencargado nuevo y
transferencia internacional, Plan 2 `LPD-12`) y su cobertura de Odoo es dudosa.
Queda como opción documentada (§ 3).

---

## 1. Qué existe hoy

- `clients.external_ref`: el id del cliente en el sistema anterior del tenant,
  único por tenant. Sirve para reconciliar importaciones.
- Exportación CSV de las listas de clientes y solicitudes (celdas de fórmula
  neutralizadas).
- El patrón de **bandeja de salida** con `claim_*` / `finish_*` y `SKIP LOCKED`
  (`intake_notifications`), que este plan reutiliza.
- `pg-boss` en el orquestador, con barrido y vigilante.
- Nada de integraciones.

---

## 2. Requisitos

**Funcionales**

1. Enviar al CRM del asegurador: el **cliente** (contacto/persona), la
   **solicitud** (oportunidad/negocio) con su estado, y la **decisión** (aprobada,
   rechazada, condiciones, motivo), con actualizaciones cuando cambian.
2. Elegir qué se envía (campos, productos, estados, segmentos) y cómo se llama del
   otro lado (mapeo) **sin código**.
3. No duplicar: cada cliente y solicitud se crea una vez y luego se actualiza
   (*upsert* por un identificador externo estable).
4. Ver qué se envió, qué falló y por qué; reintentar; pausar.
5. (v2) Recibir cambios del CRM y crear una solicitud desde un negocio del CRM.

**No funcionales**

- Entrega al menos una vez, idempotente, con orden por entidad.
- Fallas de un destino no afectan el pipeline de evaluación ni a otros destinos.
- Credenciales nunca legibles desde el navegador ni desde tablas.
- Respetar los límites de cada API (§ 6).

**De privacidad (del Plan 2), no negociables**

- Solo titulares con `processing_state = active` y con el consentimiento o la base
  legal de `commercial_management` (y `international_processing` si el CRM está
  fuera de El Salvador).
- **Ningún dato sensible** (salud, biometría) sale, salvo una excepción
  configurada por un superadmin con justificación legal registrada. El tope se
  aplica en la base de datos, no en la pantalla.
- Ningún archivo ni URL firmada de documentos sale. A lo sumo, un enlace al
  expediente en Tramiq que exige iniciar sesión.
- Cada envío se registra en `data_transfers` (Art. 8: el titular tiene derecho a
  saber con quién se compartió).
- Rectificaciones, supresiones, limitaciones y revocaciones se propagan a cada
  destino en **≤ 5 días hábiles** (Arts. 21 ¶3 y 30), con alerta si no.
- Cada destino activo aparece como destinatario en el aviso de privacidad (lo
  genera el Plan 2).

---

## 3. Opciones de arquitectura

| Opción | Esfuerzo | Costo recurrente | Cobertura | Riesgo LPDP | Mantenimiento |
| --- | --- | --- | --- | --- | --- |
| **A. Solo archivos** (CSV/XLSX con plantilla de importación de cada CRM, manual o por SFTP) | Bajo (3–4 d) | 0 | Cualquier CRM que importe archivos | Bajo (el tenant descarga) | Bajo |
| **B. Webhooks + API pública** (el tenant conecta con su iPaaS: Zapier, Make, n8n, Power Automate) | Medio (8–10 d) | 0 para Tramiq; el iPaaS lo paga el tenant | Cualquiera, con trabajo del tenant | Medio: el iPaaS es otro encargado del tenant | Bajo: un contrato estable |
| **C. Conectores nativos propios** sobre una interfaz común | Alto (núcleo + 4–6 d por CRM) | 0 | Los que se construyan | Bajo: datos directo de Tramiq al CRM | Medio: cada API cambia (versiones de HubSpot, deprecaciones de Odoo) |
| **D. API unificada comercial** (Merge, Apideck, Unified.to) | Medio | Por cuenta conectada (cotizar; suele ser de cientos de US$ al mes) | Amplia en CRM grandes; Odoo dudoso | **Alto**: los datos pasan por el proveedor (subencargado y transferencia) | Bajo |
| **E. Nango autoalojado** (código abierto: OAuth y scripts de sincronización) | Medio-alto | Infraestructura propia | Amplia, escribiendo cada sincronización | Bajo: en infraestructura propia | Medio |
| **F. iPaaS embebido** (Paragon, Prismatic, Workato embedded) | Medio | Alto | Amplia | Alto | Bajo |

**Recomendado: A + B como base (capa 1), C para HubSpot, Dynamics y Odoo (capa
2), y E solo si aparece demanda de muchos CRM distintos.** A y B ya responden
"cualquier otro" desde el primer día.

---

## 4. Arquitectura

```text
db (misma transacción que el cambio)                    ai-orchestrator — módulo src/integrations/
─────────────────────────────────────                   ─────────────────────────────────────────────
clients, client_profiles.version ─┐                     integration.dispatch  (barre la bandeja)
applications.status               ├─▶ integration_events ──▶ por destino que coincide (filtros + privacidad)
case_decisions                    │   (bandeja, append)        │
consent_records, processing_state ┘                            ▼
                                                        integration_deliveries (una por destino y entidad;
                                                        se coalescen: se envía el ESTADO actual)
                                                               │
                                     ┌─────────────────────────┼──────────────────────────┬────────────┐
                                     ▼                         ▼                          ▼            ▼
                              WebhookAdapter            HubSpotAdapter            DataverseAdapter  OdooAdapter
                              (firma HMAC)              (batch upsert)            (PATCH por clave   (JSON-2 /
                                                                                   alternativa)       XML-RPC)
                                     │   límites de tasa · cortacircuitos · reintentos · cola muerta
                                     ▼
                      integration_links (entidad ↔ id externo) · data_transfers (Plan 2) · dsr_propagations
web: Configuración → Integraciones (asistente, mapeos, bitácora) · /api/v1/* (API pública con llaves)
```

**Dónde corre.** Como módulo del orquestador (`src/integrations/`), con sus propias
colas de pg-boss y su propio límite de concurrencia, para no desplegar un servicio
más ahora. La frontera queda limpia (no importa nada de `agents/` ni de
`applications/`) para separarlo en un servicio `qualifier-integrations` cuando el
volumen o el aislamiento de credenciales lo pidan. **Requiere un plan pagado**: en
el gratuito el servicio duerme a los 15 minutos y la sincronización espera a que
alguien abra la aplicación.

---

## 5. Modelo canónico de exportación — `tramiq.crm.v1`

Se construye en la base de datos, con una función
`integration_payload(p_destination_id, p_entity, p_id) returns jsonb`
(`service_role`), que **es el único lugar donde se decide qué sale**: aplica el
alcance de campos del destino, el tope de sensibilidad y los filtros de privacidad.
Así ningún adaptador puede enviar de más por error.

```jsonc
// Persona (cliente)
{ "schema": "tramiq.crm.v1/person",
  "id": "uuid", "tenant_ref": "external_ref del tenant", "updated_at": "…", "profile_version": 14,
  "attributes": {                                   // del perfil del Plan 3, solo las llaves del alcance
    "identity.full_name": "…", "contact.email": "…", "contact.phone": "+503…",
    "address.municipality": "…", "employment.employer_name": "…", "income.band": "1000-1999" },
  "privacy": { "processing_state": "active", "under_rectification": ["income.monthly_gross"] },
  "links": { "tramiq_url": "https://…/clients/<id>" } }

// Solicitud
{ "schema": "tramiq.crm.v1/application",
  "id": "uuid", "number": 13, "person_id": "uuid", "product": { "id": "…", "code": "VIDA-STD", "name": "…" },
  "status": "manual_review", "channel": "staff", "submitted_at": "…",
  "form": { "coverage_amount": 50000 },             // solo llaves no sensibles del alcance
  "score": null,                                    // apagado por defecto (dato inferido); ver § 9
  "decision": { "decision": "approved", "decided_at": "…", "conditions": [ … ], "reason_codes": [ … ] } }
```

**Eventos** (`integration_events.kind`): `person.upserted`, `person.restricted`,
`person.erased`, `consent.revoked`, `application.created`,
`application.status_changed`, `application.decided`, `application.withdrawn`. El
webhook recibe el evento con el estado completo; los conectores nativos solo usan
el evento como aviso y envían el **estado actual** (sincronización por estado), de
modo que el orden de llegada deja de importar.

---

## 6. Modelo de datos (`db`)

```sql
create table integration_destinations (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id),
  kind text not null check (kind in ('webhook','hubspot','dynamics','odoo','salesforce','file_export','api_pull')),
  name text not null,
  status text not null default 'draft' check (status in ('draft','active','paused','error','disconnected')),
  country char(2),                         -- dónde están los datos del CRM (para LPD-12 y el aviso)
  config jsonb not null default '{}',      -- no secreto: URL de la instancia, ids de pipeline, región…
  secret_ref uuid,                         -- id en vault.secrets; nunca el secreto
  scope jsonb not null,                    -- {"entities": ["person","application"], "attributes": [...],
                                           --  "form_keys": [...], "include_score": false, "products": [...],
                                           --  "segment_id": null, "events": [...]}
  sensitivity_cap text not null default 'non_sensitive' check (sensitivity_cap in ('non_sensitive','sensitive_approved')),
  sensitive_approval jsonb,                -- quién y con qué fundamento (solo superadmin)
  dpa_attested_by uuid, dpa_attested_at timestamptz,   -- el tenant declara tener contrato con el proveedor del CRM
  mapping_version_id uuid,
  created_by uuid, created_at timestamptz default now()
);

create table integration_mapping_versions (     -- inmutables al publicarse, como playbooks
  id uuid primary key default gen_random_uuid(), tenant_id uuid not null, destination_id uuid not null,
  version integer not null, status text not null default 'draft', definition jsonb not null,
  published_by uuid, published_at timestamptz, unique (destination_id, version)
);

create table integration_events (               -- bandeja de salida; la escriben disparadores
  id bigserial primary key, tenant_id uuid not null,
  kind text not null, entity text not null, entity_id uuid not null,
  occurred_at timestamptz not null default now(), dispatched_at timestamptz
);

create table integration_deliveries (
  id uuid primary key default gen_random_uuid(), tenant_id uuid not null, destination_id uuid not null,
  entity text not null, entity_id uuid not null, action text not null check (action in ('upsert','delete','restrict')),
  status text not null default 'pending' check (status in ('pending','in_flight','delivered','failed','dead','skipped')),
  skip_reason text,                        -- 'no_consent', 'not_active', 'out_of_scope'
  attempts integer not null default 0, next_attempt_at timestamptz, last_error text, last_status_code integer,
  payload_hash text,                       -- para no reenviar lo idéntico y para reconciliar
  due_on date,                             -- para supresiones y rectificaciones (Plan 2)
  created_at timestamptz default now(), delivered_at timestamptz,
  unique (destination_id, entity, entity_id) -- una fila viva por entidad: se coalesce
);

create table integration_links (                -- entidad ↔ id externo
  tenant_id uuid not null, destination_id uuid not null, entity text not null, entity_id uuid not null,
  external_id text not null, external_url text, last_synced_hash text, last_synced_at timestamptz,
  primary key (destination_id, entity, entity_id)
);

create table api_keys (                          -- API pública (CRM-3)
  id uuid primary key default gen_random_uuid(), tenant_id uuid not null, name text not null,
  key_prefix text not null, key_hash text not null,   -- como los tokens de autoservicio: solo el hash
  scopes text[] not null, created_by uuid, created_at timestamptz default now(),
  last_used_at timestamptz, revoked_at timestamptz, expires_at timestamptz
);
```

**Secretos.** En **Supabase Vault** (`vault.secrets`). Se escriben con
`set_integration_secret(p_destination_id, p_secret jsonb)` (`security definer`,
`tenant_admin` con MFA, auditado sin el valor) y se leen solo con
`integration_secret(p_destination_id)` (`service_role`). La pantalla solo muestra
"Configurado ✓" y la fecha.

**Disparadores** que escriben `integration_events` en la misma transacción que el
cambio: `client_profiles.version` sube (Plan 3), `clients.processing_state`
cambia (Plan 2), `applications.status` cambia, `case_decisions` recibe una fila,
`consent_records` recibe una revocación. Un tenant sin destinos activos no
genera eventos (el disparador lo comprueba con un índice parcial).

**RLS.** El personal de un tenant no lee nada de integraciones salvo
`tenant_admin` (destinos, mapeos, entregas y enlaces de su tenant, **sin**
`secret_ref` ni `key_hash`, por privilegio de columna). Ningún rol de usuario
escribe; solo funciones. `anon`, nada.

---

## 7. Motor de sincronización (`ai-orchestrator/src/integrations/`)

1. **`integration.dispatch`** (cada minuto y al despertar): reclama eventos con
   `SKIP LOCKED`, calcula los destinos que coinciden (`integration_targets()` en la
   base: alcance, productos, segmento, eventos) y hace *upsert* de la fila de
   `integration_deliveries` de cada uno. Un evento de `person.erased` o
   `consent.revoked` crea una entrega `delete` o `restrict` con `due_on` = hoy + 5
   días hábiles (`add_business_days`, Plan 2).
2. **`integration.deliver`** (una cola, llave única por destino y entidad):
   - pide `integration_payload()`; si devuelve `skipped` (sin consentimiento, no
     activo, fuera de alcance) marca la entrega `skipped` con el motivo y, si
     antes se había enviado, encola un `restrict` o `delete` según la política
     del destino;
   - si `payload_hash` es igual al último enviado, no hace nada;
   - llama al adaptador; guarda `external_id` en `integration_links`; escribe
     `data_transfers` (Plan 2) con el destino, el país y las categorías enviadas.
3. **Errores**, por clase:

   | Clase | Ejemplos | Qué pasa |
   | --- | --- | --- |
   | Autenticación | 401, token revocado | Destino a `error`, se pausa, se avisa al administrador; las entregas esperan |
   | Validación | 400 de propiedad inexistente, valor inválido | `dead` con el mensaje del CRM; no se reintenta; se ve en la bitácora |
   | Límite de tasa | 429 | Respeta `Retry-After`; el limitador baja el ritmo |
   | Transitorio | 5xx, tiempo agotado | Reintento con espera exponencial (30 s … 6 h) hasta 24 h; después `dead` |

4. **Limitador de tasa y cortacircuitos** por destino, con los límites del § 8.
5. **Reconciliación** nocturna: compara el hash del estado actual con
   `last_synced_hash` y reencola lo que difiere (corrige eventos perdidos).
6. **Propagación con plazo** (Plan 2): las entregas `delete` y `restrict` llenan
   `dsr_propagations`; el vigilante avisa si alguna se acerca a su `due_on`.
7. **Salud**: `/health/queue` incluye las colas de integración; el panel de cada
   destino muestra entregadas, fallidas, atraso y último error.

**Interfaz común de los adaptadores**

```ts
export interface CrmAdapter {
  readonly kind: "webhook" | "hubspot" | "dynamics" | "odoo" | "salesforce";
  /** Comprueba credenciales y permisos; lo usa el asistente. */
  verify(dest: Destination, secret: Secret): Promise<VerifyResult>;
  /** Campos del destino para el editor de mapeos (propiedades de HubSpot, columnas de Dataverse, campos de Odoo). */
  describe(dest: Destination, secret: Secret, object: string): Promise<TargetField[]>;
  /** Crea lo que el destino necesita: propiedades personalizadas, clave alternativa, grupo "Tramiq". */
  provision?(dest: Destination, secret: Secret): Promise<ProvisionResult>;
  upsert(req: UpsertRequest, signal: AbortSignal): Promise<UpsertResult>;         // idempotente
  remove(req: RemoveRequest, signal: AbortSignal): Promise<RemoveResult>;         // supresión o archivo
  restrict?(req: RestrictRequest, signal: AbortSignal): Promise<void>;            // marca "tratamiento limitado"
  readonly limits: { perSecond?: number; perTenSeconds?: number; perDay?: number; batchSize: number };
}
```

**Mapeos** (`integration_mapping_versions.definition`), datos y no código:

```jsonc
{ "objects": {
    "person": { "target": "contacts", "id_property": "tramiq_client_id",
      "fields": [
        { "from": "identity.full_name", "to": "firstname+lastname", "transform": "split_name" },
        { "from": "contact.email",      "to": "email" },
        { "from": "contact.phone",      "to": "phone", "transform": "phone_e164" },
        { "from": "employment.employer_name", "to": "company" },
        { "from": "income.band",        "to": "tramiq_income_band" } ] },
    "application": { "target": "deals", "id_property": "tramiq_application_id",
      "associate_to": "person",
      "fields": [
        { "from": "product.name", "to": "dealname", "transform": "template:Solicitud N.º {number} — {product.name}" },
        { "from": "status", "to": "dealstage", "transform": "enum_map",
          "map": { "submitted": "appointmentscheduled", "manual_review": "qualifiedtobuy",
                   "approved": "closedwon", "declined": "closedlost", "withdrawn": "closedlost" } },
        { "from": "form.coverage_amount", "to": "amount" } ] } } }
```

Transformaciones disponibles: `date_iso`, `date_epoch_ms`, `enum_map`, `template`,
`split_name`, `phone_e164`, `money_number`, `uppercase`, `constant`. Cada versión
se valida contra lo que `describe()` devuelve antes de publicarse.

---

## 8. Conectores

### 8.1 HubSpot (`CRM-5`)

| Tema | Decisión |
| --- | --- |
| Autenticación | v1: **token de app de una sola cuenta** (app privada / *static auth*) que el administrador pega, con los permisos de contactos, negocios y esquemas. v2: app pública con **OAuth 2.0** (tokens de refresco en Vault), necesaria para el marketplace |
| Objetos | Contactos (persona), Negocios (solicitud) con asociación contacto↔negocio, Notas para la decisión. Objetos personalizados solo en Enterprise: no se usan |
| Upsert | `POST …/objects/contacts/batch/upsert` con `idProperty` = propiedad personalizada **de valor único** `tramiq_client_id` (con correo como llave no se admiten *upserts* parciales). Hasta 100 registros por lote |
| Aprovisionamiento | Crea el grupo de propiedades "Tramiq" y las propiedades (`tramiq_client_id` con valores únicos, `tramiq_application_id`, `tramiq_income_band`, `tramiq_en_rectificacion`…) con la API de propiedades |
| Etapas | El asistente lista los *pipelines* y etapas de negocios del portal y propone el mapeo de estados |
| Supresión | Borrado definitivo del contacto (endpoint de borrado por privacidad de HubSpot) cuando el Plan 2 ejecuta una supresión; archivar no basta porque queda en la papelera |
| Límites | Según el plan del portal: del orden de 100–190 solicitudes por 10 s por app y topes diarios; la búsqueda tiene límites más estrictos (usar lotes y `integration_links`, no búsquedas) |
| Versiones | HubSpot publica rutas con fecha (p. ej. `2026-03`, `2026-09`) junto a `v3`. Fijar una versión con fecha en `config` y revisarla cada semestre |

### 8.2 Microsoft Dynamics 365 / Dataverse (`CRM-6`)

| Tema | Decisión |
| --- | --- |
| Autenticación | **Microsoft Entra ID**, flujo de credenciales de cliente (servidor a servidor): el cliente registra una app (o consiente la app multi-inquilino de Tramiq) y crea un **usuario de aplicación** en su entorno con un rol de seguridad mínimo. Secreto o certificado en Vault |
| API | Web API OData de Dataverse, `https://<org>.crm.dynamics.com/api/data/v9.2/` |
| Objetos | `contact` (persona); `opportunity` o `lead` (solicitud, a elección del cliente); `annotation` (nota de decisión). Alternativa: tabla personalizada `tramiq_application` |
| Upsert | `PATCH contacts(tramiq_clientid='<uuid>')` usando una **clave alternativa** sobre una columna personalizada; `If-Match: *` o `If-None-Match: *` cuando se quiere solo actualizar o solo crear |
| Aprovisionamiento | Se entrega una **solución de Dataverse** (paquete con prefijo de editor `tramiq_`) con las columnas y la clave alternativa, que el administrador del cliente importa. Es lo habitual en clientes Microsoft y evita pedir permisos de personalización |
| Lotes | `$batch` para agrupar |
| Supresión | `DELETE contacts(<guid>)` |
| Límites | Protección del servicio en ventana deslizante de 5 minutos por usuario y por servidor (del orden de 6 000 solicitudes, más límites de tiempo de ejecución y concurrencia); responde 429 con `Retry-After`. Respetarlo en el limitador |

### 8.3 Odoo (`CRM-7`)

| Tema | Decisión |
| --- | --- |
| Versiones | Odoo 19+ trae la **API externa JSON-2** (`POST /json/2/<modelo>/<método>`, llave de API como *bearer*, encabezado de base de datos). XML-RPC y JSON-RPC están **obsoletos** y su retiro está anunciado para Odoo 22 (otoño 2028) y Odoo Online 21.1. El adaptador usa JSON-2 y cae a XML-RPC (`execute_kw`) para Odoo 17–18 |
| Requisito comercial | En Odoo Online la API externa requiere un plan que la incluya (no el gratuito ni el estándar): preguntarlo en `CRM-0` |
| Autenticación | Usuario técnico con llave de API (se genera en las preferencias del usuario, se ve una vez), URL de la instancia y nombre de la base |
| Objetos | `res.partner` (persona), `crm.lead` con `type = 'opportunity'` (solicitud), `message_post` para la nota de decisión |
| Upsert | No hay *upsert* nativo: buscar por `x_tramiq_client_id` (o el id guardado en `integration_links`) y luego `write` o `create` |
| Aprovisionamiento | En instalaciones propias, un **módulo de Odoo `tramiq_connector`** con los campos `x_tramiq_*` y la vista; en Odoo Online, campos creados con Studio o por API (`ir.model.fields`) si el plan lo permite |
| Supresión | `unlink` del contacto (o `active = False` si el cliente lo prefiere y el abogado lo acepta como supresión — en principio no) |
| Límites | Sin límite formal en instalaciones propias; uso razonable en Odoo Online. Limitador conservador por defecto |

### 8.4 Genéricos (`CRM-2`, `CRM-3`)

- **Webhooks**: firma HMAC-SHA256 según *Standard Webhooks* (`webhook-id`,
  `webhook-timestamp`, `webhook-signature`), secreto por destino con rotación sin
  corte (dos secretos válidos durante 24 h), reintentos 24 h, reenvío manual desde
  la bitácora, catálogo de eventos documentado. Solo URL `https`; se rechazan
  direcciones privadas, de enlace local y de metadatos de nube (protección SSRF,
  resolviendo el DNS antes de conectar).
- **API REST v1** (rutas de `web`, `/api/v1/...`): `GET /persons`, `/persons/{id}`,
  `/applications`, `/applications/{id}`, `/events?after=<cursor>` (para quien
  prefiere tirar en vez de recibir). Llave por tenant (`tq_live_…`, guardada como
  hash), permisos (`read:persons`, `read:applications`, `read:decisions`), límite de
  tasa, especificación OpenAPI 3.1 publicada. Cada respuesta pasa por
  `integration_payload()` con un destino de tipo `api_pull`, así las reglas de
  privacidad son las mismas, y cada lectura escribe `data_transfers`.
- **Archivos**: CSV/XLSX con las columnas de las plantillas de importación de
  HubSpot, Dynamics, Odoo y Salesforce, desde una lista o un segmento (Plan 3).
  Programable por SFTP si un cliente lo pide.
- **iPaaS**: con webhooks + API + OpenAPI, el tenant conecta Zapier, Make, n8n (que
  puede autoalojar, lo mejor para privacidad) o Power Automate (conector
  personalizado desde el OpenAPI). Se documentan recetas para Salesforce, Zoho y
  Pipedrive.

### 8.5 Salesforce y otros (`CRM-10`, opcional)

Salesforce admite *upsert* por campo de id externo (`PATCH
/sobjects/Contact/Tramiq_Client_Id__c/<valor>`), API compuesta y Bulk 2.0;
autenticación con una app externa del cliente. Zoho CRM tiene *upsert* con campos
de verificación de duplicados; Pipedrive no tiene *upsert* nativo. Construirlos
solo con un cliente que los pida; mientras tanto, la capa genérica los cubre.

---

## 9. Qué se exporta por defecto (y qué no)

| Dato | Por defecto | Notas |
| --- | --- | --- |
| Nombre, correo, teléfono, municipio | Sí | Categoría `contact` / `identity` no sensible |
| DUI | **No** | Activable por el tenant (es identificador; minimización) |
| Patrono, cargo, banda de ingreso | Sí | |
| Ingreso exacto | No | Activable |
| Producto, estado, número de solicitud, suma solicitada | Sí | |
| Decisión, condiciones, códigos de motivo | Sí | |
| Puntaje, tier, narrativa de IA, señales | **No** | Datos inferidos; activarlo exige marcarlo en el alcance, y la narrativa y las señales de fraude nunca |
| Salud, biometría | **Nunca** (tope en la base) | Solo `sensitive_approved` por un superadmin con fundamento registrado |
| Archivos de documentos, URL firmadas | **Nunca** | Enlace al expediente en Tramiq, con sesión |

---

## 10. Interfaz (`web`)

**Configuración → Integraciones** (`tenant_admin`, MFA):

1. **Catálogo**: Webhook, API, Exportación de archivos, HubSpot, Dynamics 365,
   Odoo; "Salesforce, Zoho y otros: vía webhook/API" con la receta.
2. **Asistente** por destino:
   1. *Conectar*: credenciales u OAuth; `verify()` dice qué permisos faltan.
   2. *Qué enviar*: entidades, productos, estados o un segmento (Plan 3), eventos.
   3. *Alcance de datos*: lista de atributos con su categoría y sensibilidad (los
      sensibles deshabilitados), el aviso de que el destino se agregará al aviso de
      privacidad, el país de los datos, y la declaración de que existe contrato con
      el proveedor del CRM.
   4. *Mapeo*: sugerido por defecto para cada CRM; editable con los campos que
      devuelve `describe()`; botón "Crear propiedades en el CRM" (`provision()`).
   5. *Probar*: envía un cliente sintético (marcado como prueba) y muestra el
      resultado y el enlace en el CRM.
   6. *Activar* y, opcional, **sincronización inicial** de los clientes existentes
      que cumplan (en lotes, con estimación de tiempo según los límites).
3. **Página del destino**: estado, métricas, bitácora de entregas (carga útil con
   datos enmascarados), reintentar, pausar, rotar secreto, nueva versión de mapeo,
   desconectar (preguntando si borrar lo enviado del CRM).
4. **Llaves de API** y **webhooks** con su catálogo de eventos y el secreto de firma
   (se ve una vez).
5. En la **ficha del cliente** y la **solicitud**: "Sincronizado con HubSpot ✓ ·
   Ver en HubSpot" con el enlace externo, o el motivo por el que no se envía
   ("sin consentimiento comercial", "tratamiento limitado").

---

## 11. Fases

| Fase | Contenido | Tamaño |
| --- | --- | --- |
| `CRM-0` | Descubrimiento con el primer cliente (cuestionario del § 13). Sin código | 1–2 días |
| `CRM-1` | Modelo canónico, `integration_payload()`, bandeja, disparadores, entregas, enlaces, filtros de privacidad, `data_transfers`, RLS y pruebas | 5–6 días |
| `CRM-2` | Webhooks (firma, reintentos, reenvío, SSRF) y exportación de archivos con plantillas | 4–5 días |
| `CRM-3` | API REST v1 con llaves, permisos, límites y OpenAPI | 4–5 días |
| `CRM-4` | Marco de conectores: interfaz, Vault, limitador, cortacircuitos, motor y editor de mapeos, asistente | 5–6 días |
| `CRM-5` | HubSpot | 4–5 días |
| `CRM-6` | Dynamics 365 + solución de Dataverse | 5–6 días |
| `CRM-7` | Odoo (JSON-2 + XML-RPC) + módulo opcional | 4–5 días |
| `CRM-8` | Propagación de supresiones, rectificaciones, limitaciones y revocaciones con plazo; reconciliación; monitoreo | 3–4 días |
| `CRM-9` (v2) | Entrada desde el CRM: cambios de contacto (con reglas de conflicto: la evidencia documental gana) y "crear solicitud desde un negocio" (crea el borrador y envía el enlace personal de `FUN-11`) | 5–7 días |
| `CRM-10` (opcional) | Salesforce, Zoho, Pipedrive o Nango autoalojado | según demanda |

**Orden sugerido dentro del plan:** `CRM-0` → `CRM-1` → `CRM-2` (ya sirve para
cualquier CRM vía iPaaS) → `CRM-8` (la obligación legal de propagar debe existir
desde el primer envío) → `CRM-4` → el conector del primer cliente → `CRM-3` →
los demás conectores.

---

## 12. Pruebas

- **pgTAP, desde el atacante:** un `agent` o `underwriter` no crea destinos ni
  lee entregas; un `tenant_admin` no lee `secret_ref`, el secreto en Vault ni
  `key_hash`; un tenant no ve destinos, entregas ni enlaces de otro;
  `integration_payload()` nunca devuelve atributos sensibles con
  `non_sensitive`, ni titulares sin consentimiento o no activos, ni de otro tenant;
  ningún rol de usuario escribe en las tablas de integración; `anon`, nada.
- **Contrato por conector**: respuestas grabadas (éxito, 400, 401, 429 con
  `Retry-After`, 5xx) y pruebas de que el adaptador clasifica cada una bien;
  idempotencia (dos *upserts* iguales no crean dos registros).
- **Entornos reales de prueba**: cuenta de desarrollador de HubSpot (portales de
  prueba gratuitos), entorno de prueba de Dataverse, Odoo 19 Community en Docker y
  una prueba de Odoo Online. Nunca con datos reales.
- **Webhooks**: verificación de firma con la librería de referencia del estándar;
  SSRF (IP privada, redirección a IP privada, DNS que cambia).
- **De punta a punta**: un cliente sintético aprobado llega a HubSpot como contacto
  + negocio en "ganado"; una supresión del Plan 2 lo borra en ≤ 5 días hábiles (en
  la prueba, de inmediato) y queda en `dsr_propagations`; el informe de acceso del
  Plan 2 lista el envío.

---

## 13. Preguntas para el primer cliente (`CRM-0`)

1. ¿Qué CRM y qué edición/plan? (HubSpot Free/Pro/Enterprise; Dynamics Sales;
   Odoo Online/Odoo.sh/instalación propia y versión.)
2. ¿Dónde están alojados sus datos (país/región)?
3. ¿Qué objeto representa una solicitud para ellos: negocio, oportunidad, *lead*,
   objeto propio?
4. ¿Qué etapas tienen y cómo se corresponden con nuestros estados?
5. ¿Qué datos quieren ver en el CRM, y para qué? (Esto define la finalidad
   `commercial_management` del aviso.)
6. ¿Solo de Tramiq al CRM, o también al revés? ¿Quieren iniciar solicitudes desde
   el CRM?
7. ¿Cada cuánto? (Tiempo real, cada hora, diario.)
8. ¿Quién administra el CRM y puede crear propiedades, una app o un usuario
   técnico?
9. ¿Tienen contrato de tratamiento de datos con el proveedor del CRM?
10. ¿Ya tienen clientes en el CRM que haya que emparejar (por correo, DUI o su id)?

---

## 14. Riesgos

- **Cambios de las APIs** (versiones con fecha de HubSpot, retiro de XML-RPC en
  Odoo). Mitigación: versión fijada por destino, pruebas de contrato y una revisión
  semestral en el calendario.
- **Datos de más en el CRM.** Mitigación: un solo constructor de carga útil en la
  base, con tope de sensibilidad y alcance; pruebas pgTAP que lo atacan.
- **El CRM queda con datos que el titular pidió borrar.** Mitigación: `CRM-8` antes
  de cualquier conector nativo, con plazo y alerta.
- **Credenciales con mucho poder** (un usuario técnico de Dynamics con un rol
  amplio). Mitigación: el asistente pide el rol mínimo y lo verifica con
  `verify()`.
- **Plan gratuito**: la sincronización se detiene cuando el orquestador duerme.

---

## Fuentes (consultadas el 2026-11-07)

- HubSpot — [Contacts API (docs)](https://developers.hubspot.com/docs/api-reference/latest/crm/objects/contacts/guide); [CRM API v3](https://developers.hubspot.com/docs/api-reference/crm-contacts-v3/guide); [límite del lote en la comunidad](https://community.hubspot.com/t5/APIs-Integrations/Limit-for-contact-batch-API/m-p/1143019); límites por plan según reseñas de terceros ([Farasat](https://www.farasat.me/blog/hubspot-api), [Scopious](https://www.scopiousdigital.com/blog/hubspot-api-rate-limits-production)) — verificar contra la guía oficial de uso de la API
- Microsoft Dataverse — [límites de la API](https://learn.microsoft.com/power-apps/developer/data-platform/api-limits); [resumen de límites](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/api-limits-overview)
- Odoo — [External RPC API (19.4)](https://www.odoo.com/documentation/saas-19.4/es/developer/reference/external_rpc_api.html); [visión general de la API en Odoo 19 (Cybrosys)](https://www.cybrosys.com/blog/overview-of-api-integration-in-odoo-19); [obsolescencia de XML-RPC (Xyphen)](https://xyphen-it.nl/en/knowledge-base/odoo-19-xml-rpc-deprecated)
- *Standard Webhooks* — especificación pública de firma de webhooks (standardwebhooks.com)
