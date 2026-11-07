# Planes de noviembre de 2026 — orden de implementación

*2026-11-07. Cuatro planes pedidos el mismo día, escritos para implementarse uno a
uno. Cada plan da por hecho lo que construyeron los anteriores **en este orden**, y
dice qué deja listo para los siguientes.*

## Los cuatro pedidos y dónde quedó cada uno

| Pedido | Plan | Orden |
| --- | --- | --- |
| Que los tipos de documento se puedan crear y editar, con requisitos de aceptación por tipo (¿un playbook por documento?) | [`01-tipos-de-documento.md`](01-tipos-de-documento.md) | **1.º** |
| Cumplir la LPDP (D.L. 144) y los derechos ARCO-POL "en todos los sentidos", a partir de la presentación de Technosal | [`02-cumplimiento-lpdp-arco-pol.md`](02-cumplimiento-lpdp-arco-pol.md) | **2.º** (su Fase 0 empieza ya) |
| Acceso a todos los datos de los clientes, incluidos los de los documentos: extraer, clasificar, enriquecer (¿base NoSQL?) | [`03-datos-del-cliente-y-enriquecimiento.md`](03-datos-del-cliente-y-enriquecimiento.md) | **3.º** |
| Arquitectura para exportar a CRM (HubSpot, Dynamics, Odoo y cualquier otro) | [`04-exportacion-a-crm.md`](04-exportacion-a-crm.md) | **4.º** |

## Respuestas cortas

- **¿Un playbook por documento aumenta el costo?** No si se hace como se propone:
  una *definición de tipo de documento* versionada con reglas de aceptación
  evaluadas por el mismo motor de los playbooks, sobre lo que la extracción ya
  leyó. Costo de modelo adicional: US$0. Un playbook completo con su propio
  puntaje de IA por documento sí cuesta (≈ +US$0.01–0.02 por documento, casi
  duplicar el costo por solicitud) y no aporta, porque un documento se acepta o se
  rechaza, no se puntúa. Detalle y tabla de costos en el Plan 1 § 0.
- **¿Base NoSQL para los datos de los documentos?** No por ahora: Postgres con una
  tabla de hechos tipada, un perfil JSONB y búsqueda de texto completo da la misma
  flexibilidad sin abrir un segundo almacén de datos personales que habría que
  aislar, proteger y borrar por separado. Plan 3 § 2 dice cuándo reconsiderarlo.
- **¿Hay que contratar un Delegado de Protección de Datos?** La presentación de
  Technosal dice que sí, pero la reforma **D.L. 659 (17-sep-2026) derogó esa
  obligación para el sector privado**; sus funciones pasaron al propio sujeto
  obligado. Plan 2 § 0. Confirmar con un abogado.
- **¿Cómo se cubre "cualquier otro" CRM?** Con una capa genérica (webhooks
  firmados, API pública, archivos con plantillas de importación) desde el primer
  día; conectores nativos solo para HubSpot, Dynamics y Odoo, y solo el que pida
  el primer cliente primero. Plan 4 § 0.

## Por qué este orden

```text
              ┌──────────────────────────────┐
              │ 1. Tipos de documento (DOC)  │  catálogo de campos con clase, categoría,
              └──────────────┬───────────────┘  sensibilidad y atributo canónico
                             │
              ┌──────────────▼───────────────┐
              │ 2. LPDP / ARCO-POL (LPD)     │  finalidades, consentimientos, estado de
              └──────────────┬───────────────┘  tratamiento, inventario, transferencias
                             │
              ┌──────────────▼───────────────┐
              │ 3. Datos del cliente (DAT)   │  hechos, perfil 360, segmentos
              └──────────────┬───────────────┘
                             │
              ┌──────────────▼───────────────┐
              │ 4. Exportación a CRM (CRM)   │  saca el perfil, con las reglas de privacidad
              └──────────────────────────────┘
```

1. **Tipos de documento primero** porque es el más contenido (no depende de nada,
   no tiene calendario legal) y produce la pieza que los otros tres necesitan: un
   catálogo de campos donde cada dato sabe qué es, de qué categoría y si es
   sensible. Sin él, el Plan 2 tendría que clasificar documentos a mano en código,
   el Plan 3 seguiría extrayendo con llaves que inventa el modelo y el Plan 4 no
   tendría qué ofrecer en el editor de mapeos. Además resuelve un problema operativo
   inmediato (requisitos de aceptación por tipo).
2. **LPDP antes de juntar más datos (Plan 3) y antes de sacarlos (Plan 4).** Los
   planes 3 y 4 multiplican la exposición: uno guarda *todo* lo que dicen los
   documentos y el otro lo envía a terceros. Ambos tienen que nacer con las reglas
   de finalidad, consentimiento, sensibilidad, limitación y propagación ya
   construidas, en lugar de agregárselas después. Y la ley ya está vigente.
3. **Datos del cliente antes que CRM** porque el CRM debe exportar **un** perfil
   consolidado con procedencia, no leer de cinco tablas distintas. Exportar antes de
   tener el perfil obligaría a rehacer los mapeos después.
4. **CRM al final** porque es el que más depende de los demás, y porque
   `product-gap-analysis.md` (`NEG-6`) pide no construir integraciones sin un
   cliente que las pida: llegar a él con los otros tres hechos da tiempo para
   hacer esa pregunta.

**Excepción al orden:** la **Fase 0 del Plan 2** (abogado, contratos y arreglos
de seguridad conocidos) empieza **ya**, en paralelo con el Plan 1. Es calendario,
no ingeniería, y varios arreglos son de horas: rotar la contraseña de la base de
datos impresa el 2026-11-02, apagar los inicios de sesión anónimos, encender la
protección de contraseñas filtradas, exigir MFA en ambos tenants.

## Antes de empezar el Plan 1

1. **Desplegar la ronda 2 de la auditoría del 2026-11-05.** Está en `develop` en
   los cinco repos, sin desplegar (`STATUS.md`, encabezado del 2026-11-06), y los
   planes se apoyan en lo que trae (`field_reviews`, `required_documents_for()`,
   `content_sha256`, MFA del personal, `close_unreadable_document()`). Sus tres
   migraciones necesitan el ensayo en transacción revertida antes de aplicarse.
2. **Un segundo proyecto de Supabase para desarrollo (`BLK-4`).** Los cuatro planes
   suman unas 15 migraciones grandes. Ensayarlas solo en producción, dentro de una
   transacción que se revierte, funcionó hasta ahora pero no escala a este volumen.
3. **Planes pagados antes de datos reales.** Los planes 2, 3 y 4 agregan trabajos
   programados que deben correr aunque nadie abra la aplicación (retención, plazos
   ARCO-POL, transcripción, sincronización con CRM), respaldos diarios (Plan 2) y
   más volumen de base (Plan 3). El plan gratuito de Render duerme a los 15 minutos
   y el de Supabase tiene 500 MB y no tiene respaldos.

## Estimación total

| Plan | Núcleo | Opcional |
| --- | --- | --- |
| 1. Tipos de documento | 20–23 días | — |
| 2. LPDP / ARCO-POL | 35–45 días + calendario legal | — |
| 3. Datos del cliente | 25–30 días | +7–8 días (búsqueda semántica, réplica analítica) |
| 4. CRM | ≈ 30 días (base genérica + un conector + propagación) | +4–6 días por conector adicional |
| **Total** | **≈ 110–130 días de una persona** (5–6 meses) | |

Cada plan se puede entregar por fases; los identificadores (`DOC-n`, `LPD-n`,
`DAT-n`, `CRM-n`) sirven para referirse a cada fase en commits y en
`STATUS.md`, como ya se hace con `BLK-n`, `SEC-n`, `FUN-n`.

## Invariantes nuevos que estos planes introducen

Cuando cada uno se implemente, agregarlo a la lista de invariantes del
`CLAUDE.md` del workspace:

1. **Los tipos de documento son datos**, versionados e inmutables al publicarse,
   como los playbooks; cada documento registra la versión con que se leyó y se
   aceptó (Plan 1).
2. **Ninguna tabla con datos personales entra sin su registro en
   `personal_data_stores`**, con una prueba pgTAP que lo exige (Plan 2).
3. **Sin consentimiento de `ai_processing` no hay llamada al modelo** para ese
   titular; falla cerrado a revisión manual (Plan 2).
4. **Un titular que no está `active` no se procesa, no se busca, no se segmenta y no
   se exporta** (Plan 2, aplicado en los planes 3 y 4).
5. **Lo que sale hacia un tercero lo decide una sola función en la base de
   datos** (`integration_payload()`), con un tope de sensibilidad que la pantalla no
   puede saltar; cada salida queda en `data_transfers` (Plan 4).

## Lo que estos planes cierran del análisis de brechas

`SEC-2` (registro de accesos, completo), `SEC-6` (retención y supresión),
`SEC-9`/`SEC-10` (la parte técnica; la legal es la Fase 0 del Plan 2), parte de
`SEC-8` (MFA obligatorio) y de `SEC-11` (secretos en Vault), parte de `CAL-1`
(precisión por campo y versión), y parte de `NEG-6` (integraciones).
