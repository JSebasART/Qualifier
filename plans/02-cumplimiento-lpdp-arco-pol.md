# Plan 2 — Cumplimiento de la Ley para la Protección de Datos Personales (D.L. 144) y derechos ARCO-POL

*Propuesta, 2026-11-07. Segundo plan del orden recomendado (ver [`README.md`](README.md)).
Identificadores: `LPD-0` … `LPD-13`. No es asesoría legal: cada punto marcado
**[abogado]** necesita confirmación de un profesional antes de darse por cerrado.*

| | |
| --- | --- |
| **Repos** | `db`, `ai-orchestrator`, `web`, `docs`, más trabajo no técnico (contratos, avisos, procesos) |
| **Tamaño** | XL — unos 35–45 días de una persona, más el calendario legal en paralelo |
| **Depende de** | Plan 1 (clasificación por campo y tipos `consent_form`, `dsr_identity`, `power_of_attorney`) |
| **Habilita** | Plan 3 (finalidades, consentimientos y estado de tratamiento que limitan qué se extrae y quién lo ve), Plan 4 (registro de transferencias, propagación de rectificaciones y supresiones a los CRM) |
| **Cierra del análisis de brechas** | `SEC-2` (completo), `SEC-6`, `SEC-9` y `SEC-10` (parte técnica), `SEC-8` (parte), `SEC-11` (parte) |

---

## 0. Resumen

La ley está vigente desde noviembre de 2024 y sus plazos de adecuación ya
vencieron (Art. 60: tres meses para la ACE y tres más para los obligados; Art. 61:
seis meses para tener mecanismos de ejercicio de derechos). Tramiq procesa datos
que la ley trata con la mayor exigencia: **datos de salud** (sensibles, Art. 4
lit. g), **imágenes del DUI**, **datos financieros** y **datos inferidos**
(puntajes y narrativas de IA), y los envía a **proveedores fuera de El Salvador**
(Supabase y Render en EE. UU., Anthropic en EE. UU.).

Lo que el sistema necesita, en una frase por pieza:

1. **Saber qué datos personales guarda, dónde y para qué** (inventario,
   clasificación, registro de actividades de tratamiento).
2. **Probar el consentimiento**, por finalidad, con firma o su equivalente para
   los datos sensibles, también cuando la solicitud la registra el personal
   (hoy ese canal no captura ningún consentimiento).
3. **Atender las siete solicitudes ARCO-POL** en 20 días hábiles, con folio,
   plazos, verificación de identidad, informe de acceso que incluye datos
   inferidos y quién consultó la información, portabilidad, rectificación con
   bloqueo, supresión que respeta las retenciones legales, oposición, limitación y
   revocación, y propagación a quienes recibieron los datos.
4. **Borrar o anonimizar a tiempo** (retención).
5. **Proteger y registrar el acceso** (MFA, acceso por sensibilidad, bitácora de
   consultas con finalidad, minimización de lo que se envía al modelo).
6. **Responder a un incidente en 72 horas** con registro y plantillas.
7. **Documentar transferencias internacionales** y a terceros.
8. **Demostrar todo lo anterior** ante una inspección de la ACE (responsabilidad
   demostrada y carga de la prueba, Arts. 5 lit. i y 54).

### Corrección importante a la presentación de Technosal

La presentación (septiembre de 2026) afirma que nombrar y registrar un
**Delegado de Protección de Datos** es obligatorio y que la ventana de registro
"se está cerrando". **El texto consolidado vigente dice otra cosa**: el Decreto
Legislativo N.º 659 (17-sep-2026, D.O. N.º 173, 18-sep-2026) **derogó los Arts. 15
y 17**, que imponían el Delegado a los sujetos obligados privados. Hoy el
Delegado solo es obligatorio para instituciones públicas (Art. 47 reformado), y la
ACE dejó sin efecto la fecha límite de nombramiento. Las atribuciones que tenía el
Delegado (recibir y resolver solicitudes ARCO-POL, orientar, capacitar, publicar
el aviso) ahora son **obligaciones directas del sujeto obligado** (Art. 16
reformado). Nombrar una persona responsable sigue siendo buena práctica y las
"Políticas de actuación" de la ACE (vigentes desde el 3-sep-2025) lo mencionan;
**[abogado]** confirmar si esas políticas siguen exigiéndolo tras la reforma. El
resto de la presentación (ARCO-POL, 20 días hábiles, 72 horas, aviso,
consentimiento, transferencias, multas) coincide con la ley.

---

## 1. Lo que dice la ley (texto consolidado leído el 2026-11-07)

Fuente: copia de la Corte Suprema de Justicia, con la reforma D.L. 659 marcada
"(1)". Resumen de lo que afecta a Tramiq:

| Tema | Regla | Artículo |
| --- | --- | --- |
| Ámbito | Toda persona natural o jurídica que trate datos personales, manual o automatizadamente, **o a través de terceros** | 2 |
| Exclusión parcial | El historial crediticio regulado por D.L. 695 queda fuera, **salvo** para entidades supervisadas por la SSF respecto de lo que no sea historial crediticio. Las aseguradoras están dentro para todo lo demás | 3 lit. a |
| Datos sensibles | Incluye **salud física y mental, biometría, genética**, situación moral y familiar | 4 lit. g |
| Roles | Responsable (decide fines y medios) y Encargado (trata por cuenta del responsable) | 4 lits. j, p |
| Principios | Exactitud, lealtad, consentimiento y finalidad (con **periodo de almacenamiento**), minimización, transparencia (lenguaje claro, sin letra pequeña), seguridad, licitud (seis bases), **temporalidad**, responsabilidad demostrada, ejercicio progresivo (menores) | 5 |
| Derechos ARCO-POL | Acceso, Rectificación, Cancelación, Oposición, Portabilidad, Olvido, Limitación; también herederos de fallecidos | 4 lit. i, 6–14 |
| Información al recolectar | Finalidad y destinatarios; existencia de la base, **respaldos y sitios de contingencia**; identidad y contacto del responsable **y del encargado**; derechos; medidas de seguridad; quién resguarda, **incluida la nube** | 7 |
| Acceso | Gratuito, claro, sin códigos, con explicación de términos, **quiénes consultaron la información y con qué propósito**, y si hubo intercambio con otras entidades. Nunca revela datos de terceros | 8 |
| Rectificación | 20 días hábiles; **bloqueo** de los datos mientras se verifica | 9 |
| Cancelación | Seis supuestos; no procede si contraviene una obligación legal, datos disociados, defensa de reclamaciones, etc.; **olvido** de datos publicados en internet | 10 |
| Bloqueo | La supresión puede dar lugar a bloqueo: datos solo a disposición de autoridades durante los plazos legales | 11 |
| Oposición | Cese del tratamiento, incluidos **perfiles o clasificaciones** comerciales o de mercadotecnia | 12 |
| Limitación | Mientras se impugna la exactitud, tratamiento ilícito sin supresión, necesidad del titular para reclamaciones, o mientras se resuelve una oposición | 13 |
| Portabilidad | Formato estructurado, de uso común, de lectura mecánica e interoperable, cuando el tratamiento se basa en consentimiento y es automatizado | 14 |
| Obligaciones de trámite | Recibir, tramitar y resolver; asegurar que los datos se entreguen solo al titular o representante acreditado; lineamientos internos; capacitar; publicar el aviso | 16 (reformado) |
| Solicitud | Requisitos (a–g); **una sola prevención** con 10 días hábiles para subsanar; modalidad de entrega elegida por el titular | 18 (reformado) |
| Incompetencia | Devolver la petición en **5 días hábiles** | 19 (reformado) |
| Plazo | **20 días hábiles**, prorrogables otros 20 con causa | 20 (reformado) |
| Entrega | Copias, consulta, documentos electrónicos; avisar a terceros que un dato está en rectificación; notificar rectificación o supresión a **quienes recibieron los datos en 5 días hábiles** | 21 (reformado) |
| Denegación | Ocho causales; puede ser parcial; **resolución motivada** notificada en **3 días hábiles**, por el mismo medio, con las pruebas | 22 (reformado) |
| Costos | Gratuito; solo reproducción o envío; envío electrónico sin costo | 23 |
| Aviso de privacidad | Contenido mínimo a–i (domicilio, datos y cuáles son sensibles, fundamento legal, finalidades distinguiendo las que requieren consentimiento, mecanismos ARCO-POL y de revocación, medios para cambios, contacto del **encargado subcontratado**, cookies); **comunicarlo por escrito al titular al consentir** | 24 |
| Vulneraciones | Notificar a la **ACE, a la Fiscalía y a los titulares** en **72 horas** desde que se conoce; revisión exhaustiva; contenido mínimo; **documentar toda vulneración** | 25 |
| Consentimiento | Expreso y que conste; **datos sensibles: por escrito, firma autógrafa o su equivalente** | 26 |
| Requisitos del consentimiento | Libre, específico, informado, expreso, individualizado | 27 |
| Excepciones | Fuentes públicas, emergencias, disociación, **relación contractual** necesaria, etc. | 28 |
| Revocación | En cualquier momento, gratuita; ejecutar en **5 días hábiles** e informar al encargado en otros 5 | 29–31 |
| Finalidad | Solo para los fines informados; prohibido usar datos para ofrecer otros servicios sin autorización | 32 |
| Procedimientos y proveedores | Documentar procedimientos ARCO-POL; los proveedores con acceso se someten a la ley | 33 |
| Seguridad | Medidas de la ACE; obligatorias también para el **encargado** | 34, 36 |
| Sensibles | Nadie puede ser obligado a darlos; advertir del derecho a no darlos | 37 |
| Transferencia | Con consentimiento previo, informando finalidad y cesionario; **contrato** con el receptor | 40–41 |
| Menores y grupos vulnerables | Interés superior; información adaptada | 42–43 |
| Transferencia internacional | País con nivel adecuado o garantías equivalentes; **"en todo caso deberá mediar el consentimiento previo del titular"**; informar a la ACE del flujo transfronterizo | 44–45 |
| Carga de la prueba | Del consentimiento y de haber comunicado el aviso: **del responsable** | 54 |
| Infracciones | Leves (p. ej. no informar derechos, no publicar contacto del encargado, no notificar vulneraciones), graves (acceso incompleto **"recolectados o inferidos"**, no atender a tiempo, finalidad distinta), muy graves (tratar sin consentimiento, denegar ARCO-POL, transferencias indebidas, ignorar una revocación) | 56 |
| Multas | 1–10, 11–25 y 26–40 salarios mínimos del comercio (US$408.80 en 2026 ⇒ hasta US$16,352 por infracción) | 57 |

**Instrumentos de la ACE.** "Políticas de actuación y manejo de datos personales"
(vigentes desde el 3-sep-2025): contraseñas robustas, **autenticación en dos
pasos**, acceso restringido, **cifrado**, conservación limitada, contratos con
terceros, notificación en 72 horas. "Lineamientos para el Delegado" y "Normativa
del procedimiento sancionador" (D.O. 11-ago-2026). **[abogado]** obtener el
texto completo de las políticas de actuación: el resumen de prensa no cubre
inventario, retención concreta ni nube.

---

## 2. Roles: quién es responsable de qué

| Datos | Responsable | Encargado | Consecuencia para el producto |
| --- | --- | --- | --- |
| Clientes, solicitudes, documentos, puntajes, casos de **cada aseguradora** | La aseguradora (tenant) | **Tramiq** | Tramiq debe dar al responsable las herramientas para cumplir (este plan) y cumplir él mismo como encargado: seguridad (Art. 36), confidencialidad (Art. 34), sometimiento a la ley (Art. 33), ejecutar revocaciones (Art. 30), contrato de encargo |
| Cuentas del personal de la aseguradora | La aseguradora | Tramiq | Igual |
| Cuentas de superadmin, prospectos del sitio, contactos comerciales de Tramiq | **Tramiq** | Sus proveedores | Tramiq necesita su propio aviso de privacidad y su propio procedimiento ARCO-POL |
| Datos que Tramiq envía a Supabase, Render, Anthropic, Resend, Cloudflare, Meta | La aseguradora | Tramiq, y esos proveedores como **subencargados** | Contratos (DPA) con cada uno; listarlos en el aviso (Art. 7, 24 lit. h); evaluar transferencia internacional (Arts. 44–45) |

Consecuencia de diseño: **toda la configuración de privacidad es por tenant** (su
aviso, sus finalidades, sus plazos de retención, su calendario, su portal), y
**ninguna solicitud de un titular a una aseguradora puede revelar datos de otra**,
aunque la misma persona sea cliente de ambas.

---

## 3. Brechas: obligación → estado actual → componente

| Obligación | Artículo | Hoy | Componente |
| --- | --- | --- | --- |
| Inventario y registro de actividades de tratamiento | 5 lit. i, 33, 54 | No existe | `LPD-1` |
| Aviso de privacidad con contenido mínimo | 7, 24 | `consent_texts` existe (versionado, inmutable) pero es texto libre y solo en autoservicio; **ninguna versión publicada en producción** | `LPD-2` |
| Consentimiento probado por finalidad | 5 lit. c, 26, 27, 54 | Autoservicio guarda `consent_text_id` y fecha; **el canal del personal no guarda nada**, que es por donde entran casi todas las solicitudes | `LPD-3` |
| Consentimiento escrito para datos sensibles (salud) | 26 ¶4, 37 | No existe | `LPD-3` |
| Revocación en 5 días hábiles | 29–31 | No existe | `LPD-3`, `LPD-5` |
| Bloqueo, limitación, oposición | 9 ¶4, 11–13 | No existe | `LPD-4` |
| Procedimiento ARCO-POL con plazos | 16, 18–23, 33 | No existe | `LPD-5`, `LPD-6` |
| Acceso con datos inferidos, accesos y transferencias | 8, 56 lit. b.1 | `document.viewed` se registra (`/api/documents/[id]/url`); nada más | `LPD-7`, `LPD-10` |
| Portabilidad | 14 | Exportación CSV de listas, no por titular | `LPD-7` |
| Supresión con excepciones legales | 10, 11 | `delete_client()` borra en duro (sin evaluar retención legal, sin anonimizar bitácoras ni notas) | `LPD-8` |
| Notificar a destinatarios | 21 ¶3 | No existe (y el Plan 4 creará destinatarios) | `LPD-8`, `LPD-12` |
| Temporalidad / retención | 5 lit. h | Solo purga de borradores de autoservicio abandonados | `LPD-9` |
| Medidas de seguridad de la ACE | 36; políticas ACE | MFA por tenant **opcional**; protección de contraseñas filtradas **apagada**; inicios anónimos **encendidos**; contraseña de BD **impresa en una sesión el 2026-11-02 y sin rotar**; sin respaldos (plan gratuito) | `LPD-0`, `LPD-10` |
| Minimización hacia proveedores | 5 lit. d | El agente de consistencia y el narrador reciben `form_data` completo, con contacto | `LPD-10` |
| Vulneraciones en 72 h | 25 | No existe | `LPD-11` |
| Transferencias internacionales | 40–45, 54 | Datos en EE. UU. sin consentimiento específico, sin aviso a la ACE, sin DPA firmados | `LPD-12`, `LPD-0` |
| Responsabilidad demostrada | 5 lit. i, 54 | Bitácora de auditoría sólida para decisiones; nada de privacidad | `LPD-13` |

---

## 4. Riesgos propios de Tramiq

1. **Salud.** El tenant `medico` y los productos de vida piden IMC, padecimientos,
   tabaquismo, laboratorios. Son datos sensibles: consentimiento escrito, nadie
   obligado a darlos (Art. 37), y la prohibición del Art. 59 lit. b de tratarlos
   sin observar el capítulo de sensibles. **[abogado]** ¿Cómo se concilia "nadie
   puede ser obligado" con un seguro de salud que no se puede suscribir sin
   ellos? Probablemente: el consentimiento es libre porque la persona decide
   solicitar el seguro, y se le advierte que sin esos datos no se puede evaluar.
   Debe quedar escrito así en el texto.
2. **Imágenes del DUI.** Contienen fotografía y firma. Mientras Tramiq no haga
   reconocimiento facial, la foto no se trata como biometría en sentido técnico;
   **[abogado]** confirmar. Si algún día se compara una selfie con el DUI, pasa a
   biometría (sensible).
3. **IA en el extranjero.** Cada documento se envía a Anthropic (EE. UU.). Es
   tratamiento por un subencargado y flujo transfronterizo (Arts. 7, 44–45).
4. **Datos inferidos.** Puntaje, tier, recomendación, narrativa, hallazgos de
   consistencia. El Art. 56 lit. b.1 sanciona entregar el acceso incompleto
   "ya sean recolectados o inferidos". Deben estar en el informe de acceso, con la
   salvedad de las señales de fraude (§ `LPD-7`).
5. **Terceros dentro de una solicitud.** Beneficiarios y dependientes (a veces
   menores) aparecen en `form_data`. El informe de acceso no puede revelarlos
   (Art. 8 lit. b) y su tratamiento necesita base legal propia (Arts. 42–43).
6. **Decisiones automatizadas.** La ley no tiene un derecho específico (lo
   confirma también `docs/research/2026-11-06-credit-bureaus-el-salvador.md`),
   pero la oposición del Art. 12 alcanza "perfiles o clasificaciones". El diseño
   actual ayuda: la aprobación automática solo aprueba y nunca rechaza. Debe
   decirse en el aviso, y una oposición debe apagar la aprobación automática y el
   uso de IA para ese titular.
7. **Todo el personal ve todo.** Hoy cualquier rol del tenant lee cualquier
   documento, incluidos los médicos. La minimización pide restringirlo.

---

## 5. Arquitectura de cumplimiento

```text
                    ┌─────────────────────── Configuración por tenant ───────────────────────┐
                    │ privacy_settings · processing_purposes · retention_policies ·           │
                    │ business_holidays · consent_texts (kind) · subprocessors (plataforma)   │
                    └───────────────┬──────────────────────────────┬─────────────────────────┘
                                    │                              │
 Formularios (form_schema          ▼                              ▼
 clasificado) + tipos de    ┌──────────────┐  genera   ┌──────────────────────────┐
 documento (Plan 1) ───────▶│ Inventario   │──────────▶│ RAT · aviso de privacidad│
 + registro de almacenes    │ (LPD-1)      │           │ (LPD-1, LPD-2)           │
                            └──────┬───────┘           └──────────────────────────┘
                                   │ data_subject_footprint()
 Titular ──▶ Portal /privacidad ───┼──▶ data_subject_requests ──▶ cola del personal (LPD-5/6)
            (token + OTP)          │          │
                                   │          ├─▶ informe de acceso / portabilidad (LPD-7)
                                   │          ├─▶ rectificación, supresión, bloqueo (LPD-8)
                                   │          └─▶ estado de tratamiento (LPD-4) ──▶ pipeline,
                                   │                                               exportes, CRM
 Consentimientos ──▶ consent_records (append-only, LPD-3) ──▶ has_consent() ──▶ pipeline, Plan 3, Plan 4
 Accesos ──▶ access_log (LPD-10)        Transferencias ──▶ data_transfers (LPD-12; Plan 4 escribe)
 Retención ──▶ retention.sweep (LPD-9)  Incidentes ──▶ security_incidents (LPD-11)
 Todo ──▶ panel de cumplimiento y paquete de evidencia (LPD-13)
```

**Invariante nuevo, para este plan y los siguientes:** *ninguna tabla nueva que
guarde datos personales entra sin su registro en el inventario.* Una prueba pgTAP
falla si una tabla de `public` tiene una columna `client_id`, `email`, `phone`,
`national_id`, `full_name`, `form_data` o `extracted_data` y no aparece en
`personal_data_stores`. Así los planes 3 y 4 no pueden olvidarlo.

---

## 6. Componentes

### `LPD-0` — Fase 0: legal, contratos y arreglos de seguridad inmediatos (sin código o casi)

Empieza el día uno y corre en paralelo con todo lo demás (es calendario, no
ingeniería — `SEC-9`).

**Arreglos de seguridad ya conocidos (horas, no días):**

1. Rotar la contraseña de la base de datos (impresa en una sesión el 2026-11-02) y
   actualizar `DATABASE_URL` del orquestador y el archivo de secretos.
2. Apagar los inicios de sesión anónimos (Authentication → Providers).
3. Encender la protección contra contraseñas filtradas.
4. Corregir la Site URL de Supabase Auth (`STATUS.md` § 6.5).
5. Borrar `render-blocks.env` a mano.
6. Activar `mfa_required` en ambos tenants (la función `set_mfa_required()` ya
   existe; las políticas de la ACE piden doble factor).
7. Plan pagado de Supabase con respaldos diarios antes de recibir datos reales
   (principio de seguridad: disponibilidad e integridad; `BLK-4`).

**Legal y contractual [abogado]:**

| # | Entregable | Notas |
| --- | --- | --- |
| L1 | Confirmar el estado de la reforma D.L. 659 y de las políticas de la ACE | Ver § 0 |
| L2 | Contrato de encargo (DPA) Tramiq ↔ aseguradora | Instrucciones, confidencialidad, seguridad, subencargados autorizados, transferencias, aviso de vulneración **al responsable en 24 h** (para que llegue a sus 72 h), asistencia ARCO-POL con plazo interno de **2 días hábiles**, devolución y supresión al terminar, auditorías (Arts. 33, 34, 36, 41) |
| L3 | DPA con cada subencargado | Supabase, Render, Anthropic (verificar retención vigente de la API y solicitar *zero data retention*), Resend, Cloudflare (Turnstile), Meta (WhatsApp), el servidor de ClamAV |
| L4 | Base legal por finalidad | Para la tabla de finalidades de `LPD-3` |
| L5 | Texto del consentimiento para datos de salud y forma de la "firma o su equivalente" | ¿Basta OTP + casilla + nombre escrito + firma dibujada? ¿Hace falta firma electrónica certificada (Ley de Firma Electrónica)? |
| L6 | Plazos de retención por clase de dato | Ley de Sociedades de Seguros y normas de la SSF, Código de Comercio (conservación de documentos), Ley contra el Lavado de Dinero y de Activos (registros de clientes), prescripción de acciones. Las cifras de `LPD-9` son propuestas |
| L7 | Transferencia internacional | ¿El uso de subencargados en EE. UU. es "transferencia" del Art. 44? ¿Qué garantías bastan? Comunicación del flujo a la ACE (Art. 45) |
| L8 | Señales de fraude en el informe de acceso | ¿Pueden retenerse como denegación parcial (Art. 22 lits. c, e; deberes de reserva de la ley antilavado)? |
| L9 | Beneficiarios y dependientes menores | Base legal y deber de información |
| L10 | Calendario de días hábiles | Asuetos del Código de Trabajo Art. 190 y fiestas locales; ¿aplica la Ley de Procedimientos Administrativos (supletoria, Art. 62)? |
| L11 | ¿La prevención (Art. 18) suspende el plazo de 20 días? | El diseño asume que el plazo corre desde que la solicitud está completa |
| L12 | Aviso de privacidad y procedimiento ARCO-POL propios de Tramiq | Para sus propios datos (§ 2) |
| L13 | Compromiso de confidencialidad del personal y capacitación | Evidencia que pide la ACE; la presentación de Technosal lo cubre en su fase 3 |

### `LPD-1` — Inventario de datos, clasificación y registro de actividades de tratamiento

**Objetivo.** Saber, en todo momento y de forma generada (no un Excel que envejece),
qué datos personales hay, de qué categoría, si son sensibles, para qué finalidad,
de dónde vienen, a quién van y cuánto se guardan.

**Modelo de datos**

```sql
-- Registro de almacenes de datos personales (plataforma; lo mantienen las migraciones).
create table personal_data_stores (
  table_name     text primary key,
  description    text not null,
  subject_link   text not null,      -- cómo llegar al titular: 'client_id', 'applications.client_id', 'intake_sessions.client_id', 'profiles.id'…
  categories     text[] not null,    -- identity, contact, financial, health, …
  holds_sensitive boolean not null,
  access_handler text not null,      -- include | include_redacted | exclude (con motivo)
  erase_handler  text not null,      -- delete | anonymize | redact_fields | retain_legal
  retention_class text not null      -- clave en retention_policies (LPD-9)
);

-- Clasificación de las preguntas del formulario de cada producto (FUN-10 ya admite objetos).
-- Se agrega a form_schema.fields[]: "category", "sensitive", "purpose".
-- form_schema_valid() valida las nuevas llaves; el linter del editor exige
-- clasificación para publicar un producto con intake activo.

-- Subencargados (plataforma, superadmin).
create table subprocessors (
  id uuid primary key default gen_random_uuid(),
  name text not null, service text not null,           -- "Supabase", "Base de datos y archivos"
  country char(2) not null, region text,                -- 'US', 'us-east-1'
  data_categories text[] not null, receives_sensitive boolean not null,
  purpose text not null, safeguards text,               -- contrato, cláusulas, certificaciones
  dpa_signed_at date, dpa_url text, active boolean not null default true
);
```

**Semilla de `personal_data_stores`** (hoy): `clients`, `applications`
(`form_data`), `documents` (+ objetos de Storage), `scores` (`rationale`,
`ai_summary`, `inputs`), `case_comments`, `case_decisions` (`note`),
`field_reviews`, `intake_sessions`, `intake_info_requests`,
`intake_notifications`, `audit_log` (`metadata`), `profiles` (personal),
`ai_usage` (sin datos personales: `exclude`). Los planes 3 y 4 agregan los suyos.

**Funciones**

- `data_subject_footprint(p_tenant_id, p_client_ids uuid[]) returns jsonb` —
  `security definer`, solo `service_role` y la ruta de servidor de `web` para
  administradores. Recorre los almacenes registrados y devuelve todo lo del
  titular, por almacén. Es la base de `LPD-7` y `LPD-8`.
- `processing_inventory(p_tenant_id) returns jsonb` — une productos, preguntas
  clasificadas, tipos de documento (Plan 1: `category`, `sensitive` por campo),
  finalidades, destinatarios, subencargados y retenciones.

**Registro de actividades de tratamiento (RAT).** Pantalla
**Privacidad → Inventario** y descarga XLSX/PDF, una actividad por producto y
otras fijas (gestión de personal, notificaciones, prevención de fraude):
actividad, finalidad, base legal, categorías de titulares, categorías de datos
(sensibles marcados), origen, destinatarios, transferencias internacionales
(país y garantía), plazo de conservación, medidas de seguridad, sistemas. Es
también un entregable que la presentación de Technosal cotiza; el sistema lo
genera.

**Pruebas pgTAP:** la prueba del invariante (§ 5); `data_subject_footprint` no
devuelve filas de otro tenant aunque el `client_id` sea de otro; ningún rol de
usuario la ejecuta.

### `LPD-2` — Aviso de privacidad estructurado

**Objetivo.** Un aviso que cumpla el Art. 24 (a–i) y el Art. 7, generado desde la
configuración para que no quede desactualizado cuando cambian productos,
proveedores o plazos.

- `privacy_settings` (por tenant): razón social, domicilio, correo y teléfono de
  privacidad, persona responsable (opcional, el antiguo Delegado), URL del portal
  ARCO-POL, medio para comunicar cambios.
- `consent_texts` gana `kind` (`privacy_notice | consent | bureau_authorization`,
  como propone la nota de buró) y `sections jsonb`. Se mantiene: una publicada
  por tenant **y tipo**, inmutable al publicarse.
- **Generador**: arma un borrador en español claro con cada sección mínima: datos
  tratados (con los sensibles señalados, desde `LPD-1`), fundamento legal y
  finalidades (desde `LPD-3`), destinatarios y subencargados (desde
  `subprocessors` y, con el Plan 4, los destinos CRM activos), transferencias
  internacionales, plazos, medidas de seguridad, derechos y cómo ejercerlos,
  revocación, cambios, cookies (la aplicación usa solo cookies de sesión
  necesarias). El administrador edita y publica; **[abogado]** revisa la primera
  versión.
- **Comunicación por escrito al consentir** (Art. 24, último párrafo): cada
  consentimiento envía al titular una copia (PDF o enlace permanente) del aviso y
  del consentimiento, por el canal verificado. Usa la bandeja de salida existente
  (`intake_notifications`, nuevo tipo `consent_copy`).
- **Cambios del aviso** (Art. 24 lit. g): al publicar una versión con cambios en
  finalidades o destinatarios, se encola un aviso a los titulares activos y, si la
  finalidad es nueva, se pide consentimiento nuevo (Art. 7 penúltimo párrafo).
- **Publicación** (Art. 16 lit. g): página pública `/privacidad/<slug>` (y en el
  dominio propio del asegurador, `FUN-11` fase 4) con el aviso vigente y el acceso
  al portal (`LPD-6`).
- **Tramiq** publica el suyo para su sitio y sus cuentas (L12).

### `LPD-3` — Finalidades y consentimiento con evidencia

**Finalidades** (`processing_purposes`, por tenant, sembradas con propuestas):

| `code` | Finalidad | Base legal (Art. 5 lit. g) | ¿Consentimiento? | ¿Puede negarse sin perder el servicio? |
| --- | --- | --- | --- | --- |
| `underwriting` | Evaluar la solicitud y emitir la póliza | Medidas precontractuales (num. 2) | Informado | No |
| `sensitive_health` | Tratar datos de salud para evaluar | Consentimiento escrito (Art. 26 ¶4) | **Sí, escrito** | No para productos que los necesitan **[abogado]** |
| `ai_processing` | Lectura y análisis automatizado por proveedores de IA | Consentimiento **[abogado]** | Sí | **Sí**: la solicitud se evalúa a mano |
| `international_processing` | Tratamiento en servidores fuera de El Salvador | Consentimiento (Art. 44 ¶5) | Sí | **[abogado]** |
| `identity_verification` | Comparar con el DUI y registros | Contrato / interés legítimo | Informado | No |
| `fraud_prevention` | Detectar documentos repetidos o alterados | Interés legítimo (num. 6) | Informado | No |
| `notifications` | Avisar el estado de la solicitud | Contrato | Informado | No |
| `commercial_management` | Gestión comercial en el CRM del asegurador (Plan 4) | Interés legítimo / contrato **[abogado]** | Informado (más `international_processing` si el CRM está fuera) | Oposición |
| `marketing` | Ofertas de otros productos | Consentimiento (Art. 32) | **Sí, opcional** | Sí |
| `profiling_offers` | Perfiles para ofertas, con datos de documentos (Plan 3) | Consentimiento | **Sí, opcional** | Sí |
| `retain_after_decline` | Conservar los datos de una solicitud rechazada para futuras ofertas | Consentimiento | **Sí, opcional** | Sí |
| `bureau_inquiry` | Consulta a buró (D.L. 695; nota de investigación) | Autorización especial | Sí, aparte | Sí (Art. 15 D.L. 695) |

**Registro de consentimientos (append-only)**

```sql
create table consent_records (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id),
  client_id uuid,                 -- puede ser null si aún no hay cliente (autoservicio)
  intake_session_id uuid, application_id uuid,
  purpose_code text not null,
  consent_text_id uuid not null, consent_version integer not null, text_sha256 text not null,
  decision text not null check (decision in ('granted','refused','revoked')),
  channel text not null check (channel in ('self_service','consent_link','staff_signed_form','imported')),
  identity_basis text not null check (identity_basis in
    ('otp_email','otp_whatsapp','personal_link_dob','signed_form_checked','in_person_id_check')),
  signature_kind text check (signature_kind in ('checkbox','typed_name','drawn','scanned_autograph','certified_e_signature')),
  signature_path text,            -- trazo dibujado (PNG) en un bucket privado
  evidence_document_id uuid,      -- documento de tipo consent_form (Plan 1)
  dsr_id uuid,                    -- si la revocación vino de una solicitud
  actor_id uuid,                  -- personal que lo registró, si aplica
  ip inet, user_agent text,       -- revocados a nivel de columna para todo rol de usuario
  created_at timestamptz not null default now(),
  copy_sent_at timestamptz
);
-- Vista security_invoker: el estado vigente por cliente y finalidad.
create view client_consent_state with (security_invoker = true) as …;
```

Nadie inserta directamente; solo las funciones. Ningún `update` ni `delete`.

**Captura por canal**

1. **Autoservicio** (`/s/...`): el paso de consentimiento pasa de "una casilla"
   a una casilla **por finalidad**, con las obligatorias marcadas como tales y las
   opcionales sin marcar por defecto, más el nombre escrito y una firma dibujada
   cuando el producto trata datos sensibles. `intake_submit()` exige el
   consentimiento de las finalidades obligatorias del producto, y
   `intake_record_consents(p_token, p_decisions jsonb, p_signature_path)`
   (`service_role`) graba una fila por finalidad, incluidas las negativas.
2. **Enlace de consentimiento** (nuevo, para solicitudes del personal): el
   personal pulsa "Enviar consentimiento" y el cliente recibe por correo o
   WhatsApp un enlace personal (`/s/c/<token>`, mismo patrón de token con hash
   que `FUN-11`), verifica su fecha de nacimiento o DUI, lee el aviso y firma.
   El personal **no puede marcar la casilla por el cliente**.
3. **Formulario firmado en papel**: el personal sube un documento de tipo
   `consent_form` (plantilla del Plan 1, con la regla `signature_present` y
   campos `full_name`, `national_id`, `signed_at`, `purposes`). Cuando el
   documento queda aceptado, `record_staff_consent()` crea las filas con
   `channel = staff_signed_form`.

**Productos con datos sensibles.** Un producto "trata datos sensibles" si alguna
pregunta de su formulario o algún tipo de documento que su playbook exige tiene
`sensitive: true` (Plan 1). Se deriva, no se configura a mano, para que no se
desincronice. `submit_application()` rechaza (`consent_missing: sensitive_health`)
una solicitud de ese producto sin consentimiento escrito vigente.

**Revocación** (Arts. 29–31): `revoke_consent(p_client_id, p_purpose, p_dsr_id)`
desde el portal o el personal. Efecto en ≤ 5 días hábiles (el sistema lo hace al
instante): las funciones de `LPD-4` dejan de permitir el tratamiento de esa
finalidad, y se encolan los avisos a encargados (Plan 4: destinos CRM).

**Uso del consentimiento en el resto del sistema** — una función:
`has_consent(p_client_id, p_purpose) returns boolean` (`security definer`,
`service_role` y `authenticated` del tenant). Puntos que la consultan:

| Punto | Finalidad | Si falta |
| --- | --- | --- |
| `ai-orchestrator`, antes de **cada** llamada al modelo de un titular | `ai_processing`, `international_processing` | No se llama al modelo. El documento queda "pendiente de revisión manual"; la solicitud se puntúa solo con reglas sobre el formulario y va a revisión manual con `blocked_reason = "ai_processing_not_consented"`. Falla cerrado |
| `submit_application()`, `intake_submit()` | Las obligatorias del producto | Refusa con la lista |
| Plan 3 (perfiles para ofertas, segmentos comerciales) | `profiling_offers`, `marketing` | Excluido |
| Plan 4 (envío al CRM) | `commercial_management` (+ `international_processing`) | No se exporta |
| Retención (`LPD-9`) de solicitudes rechazadas | `retain_after_decline` | Se aplica el plazo corto |

**Pruebas pgTAP:** no se puede insertar, editar ni borrar `consent_records` con JWT;
`ip` y `user_agent` no se pueden leer; el personal no puede registrar un
consentimiento sin documento firmado aceptado ni enlace verificado; un tenant no
registra consentimientos para clientes de otro; `submit_application` rechaza un
producto sensible sin consentimiento escrito; una revocación hace que
`has_consent` devuelva falso al instante.

### `LPD-4` — Estado de tratamiento del titular: limitación, bloqueo, oposición

```sql
alter table clients
  add column processing_state text not null default 'active'
    check (processing_state in ('active','limited','opposed','blocked','erased')),
  add column processing_state_reason text,
  add column processing_state_dsr_id uuid,
  add column processing_state_since timestamptz;

-- Campos concretos bloqueados mientras se rectifican (Art. 9 ¶4, Art. 21 ¶2).
create table field_locks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null, client_id uuid not null,
  field_path text not null,            -- 'clients.annual_income', 'applications.<id>.form_data.monthly_income'
  reason text not null check (reason in ('under_rectification','disputed_accuracy')),
  dsr_id uuid, locked_at timestamptz not null default now(), lifted_at timestamptz
);
```

Las columnas se escriben solo con `set_processing_state()` y las funciones de
`LPD-8` (trigger como el de `field_sources`).

| Estado | Cuándo (artículo) | Qué permite |
| --- | --- | --- |
| `active` | Normal | Todo según consentimientos |
| `limited` | Art. 13 a–d; Art. 9 ¶4 | Conservar y consultar; nada nuevo: ni puntajes, ni IA, ni exportes, ni mercadeo. Las pantallas muestran "Tratamiento limitado: <motivo>" |
| `opposed` | Art. 12 | Igual que `limited` para las finalidades opuestas; la solicitud en curso se retira con aviso |
| `blocked` | Art. 11 (supresión con obligación legal de conservar) | Solo `tenant_admin` y solo para atender autoridades; invisible en listas y búsquedas |
| `erased` | Supresión ejecutada (`LPD-8`) | Nada; la fila queda anonimizada |

**Puntos de control** (todos fallan cerrado): `submit_application()`,
`intake_submit()`, `pipeline_sweep_candidates()` (no devuelve titulares que no
estén `active`), cada job del orquestador antes de llamar al modelo,
`auto_decide_case()`, las vistas de lista (`client_list`, `application_list`
ocultan `blocked` y `erased`), las exportaciones CSV, y los Planes 3 y 4.
`field_locks` hace que la pantalla del cliente muestre "En revisión por
rectificación" junto al dato y que su edición falle, y que un tercero que reciba
ese dato (Plan 4) reciba la marca.

**Oposición a perfiles** (Art. 12): además desactiva la aprobación automática y la
IA para ese titular (riesgo 6 de § 4).

### `LPD-5` — Motor de solicitudes ARCO-POL

**Modelo de datos**

```sql
create table data_subject_requests (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants (id),
  number integer not null,                      -- folio por tenant, como applications.number
  right text not null check (right in ('access','rectification','cancellation','opposition',
                                       'portability','forgetting','limitation','consent_revocation')),
  status text not null default 'received' check (status in
    ('received','identity_pending','prevention_sent','in_review','extended',
     'resolved','returned_incompetent','archived_unanswered')),
  resolution text check (resolution in ('granted','partially_granted','denied')),
  denial_reasons text[],                        -- 'art22_a' … 'art22_h'
  resolution_note text,                         -- resolución motivada
  channel text not null check (channel in ('portal','email','in_person','letter','forwarded_by_processor')),
  requester_kind text not null check (requester_kind in ('subject','representative','heir')),
  subject_full_name text not null, subject_national_id text, subject_birth_date date,
  contact_email text, contact_phone text, notification_medium text not null,
  delivery_modality text check (delivery_modality in ('electronic','simple_copy','certified_copy','consultation')),
  description text, requested_changes jsonb,
  identity_verified_at timestamptz, identity_verified_by uuid, identity_method text,
  received_at timestamptz not null default now(),
  complete_at timestamptz,                      -- desde aquí corre el plazo [abogado L11]
  due_on date, extended_due_on date, extension_reason text,
  prevention_sent_at timestamptz, prevention_due_on date, prevention_answered_at timestamptz,
  decided_at timestamptz, decided_by uuid, decision_notified_at timestamptz,
  recipients_notified_at timestamptz,
  response_path text,                           -- paquete de respuesta en bucket privado
  portal_token_hash text,                       -- no seleccionable por el personal
  assigned_to uuid references profiles (id) on delete set null,
  unique (tenant_id, number)
);
create table dsr_subjects (dsr_id uuid, tenant_id uuid, client_id uuid, matched_by text, primary key (dsr_id, client_id));
create table dsr_events (id bigserial primary key, tenant_id uuid, dsr_id uuid, at timestamptz default now(),
                         actor_id uuid, actor_type text, event text, detail jsonb);   -- append-only
create table business_holidays (id bigserial primary key, country char(2) not null, day date not null,
                                name text not null, tenant_id uuid null);   -- null = nacional
create unique index business_holidays_unique
  on business_holidays (country, day, coalesce(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid));
create function add_business_days(p_from date, p_days int, p_tenant uuid, p_country char(2) default 'SV') returns date;
```

**Calendario.** Semilla de asuetos del Código de Trabajo (Art. 190) para 2026–2028:
1 de enero; jueves, viernes y sábado de Semana Santa (2026: 2–4 de abril; 2027:
25–27 de marzo); 1 y 10 de mayo; 17 de junio; 6 de agosto; 15 de septiembre;
2 de noviembre; 25 de diciembre; más fiestas locales que cada tenant agregue
(3–5 de agosto en San Salvador). Editable por el administrador, porque los
decretos de asueto cambian **[abogado L10]**.

**Plazos que el sistema calcula y vigila**

| Evento | Plazo | Artículo |
| --- | --- | --- |
| Responder | 20 días hábiles desde `complete_at` | 20 |
| Prórroga | +20 días hábiles, con motivo escrito | 20 |
| Subsanar una prevención (una sola vez) | 10 días hábiles para el titular; si no responde, se archiva | 18 |
| Devolver por incompetencia | 5 días hábiles desde la recepción | 19 |
| Notificar una denegación motivada | 3 días hábiles desde la decisión | 22 |
| Notificar a quienes recibieron los datos | 5 días hábiles desde que procede | 21 |
| Ejecutar una revocación e informar al encargado | 5 + 5 días hábiles | 30 |

El vigilante del orquestador (`ops.watchdog`) gana una comprobación: solicitudes a
3 días de vencer, vencidas, y prevenciones vencidas; avisa a los administradores
del tenant por correo y en el panel. El resumen semanal las incluye.

**Flujo**

```text
received ─▶ identity_pending ─▶ (prevention_sent ─▶ …10 d.h.… ─▶ archived_unanswered)
                │                        │ respondida
                ▼                        ▼
           in_review ──(prórroga)──▶ extended
                │
                ▼
           resolved (granted | partially_granted | denied) ─▶ ejecución (LPD-7/8) ─▶ notificación
received ─▶ returned_incompetent  (no es de este responsable: p. ej. otro asegurador)
```

**Funciones** (`security definer`, `tenant_admin` y un rol nuevo opcional
`privacy_officer` — o el permiso como bandera en `profiles` — con MFA y
`audit_log`): `register_dsr()`, `match_dsr_subject()` (busca clientes por DUI,
correo y teléfono **dentro del tenant**), `verify_dsr_identity()`,
`send_dsr_prevention()`, `extend_dsr()`, `assign_dsr()`, `resolve_dsr()`,
`return_dsr_incompetent()`. Las de ejecución están en `LPD-7` y `LPD-8`.

**Solicitudes que llegan a Tramiq** (porque el titular escribió al encargado):
pantalla de superadmin "Recibidas por Tramiq" que las reenvía al tenant
correspondiente (`channel = forwarded_by_processor`) en ≤ 2 días hábiles, sin
contestar el fondo.

**Pantallas** — **Privacidad → Solicitudes**: lista con folio, derecho, titular,
recibida, vence (días hábiles restantes en color), estado, responsable; detalle con
línea de tiempo, verificación de identidad (documentos `dsr_identity` y
`power_of_attorney` del Plan 1 en el visor), vista previa de la huella de datos
(`data_subject_footprint`), acciones según el derecho, plantillas de resolución
(prevención, prórroga, concesión, denegación con las causales del Art. 22
seleccionables, incompetencia) y la casilla de propagación a destinatarios.

**Pruebas pgTAP:** un `agent` o `underwriter` sin permiso no ve ni resuelve
solicitudes; un tenant no ve las de otro; `dsr_events` es append-only;
`portal_token_hash` no es seleccionable; `add_business_days` salta fines de semana
y asuetos; una denegación sin causal ni motivo falla; `match_dsr_subject` nunca
devuelve clientes de otro tenant.

### `LPD-6` — Portal del titular

Página pública por tenant, `/privacidad/<slug>` (y en su dominio propio), con el
**mismo patrón de seguridad que el autoservicio** (`FUN-11`): el titular nunca
tiene credencial de base de datos; un token con hash; funciones `privacy_*`
ejecutables solo por `service_role`, llamadas por `web` después de Turnstile y
límites de tasa.

1. Elegir derecho (lenguaje claro, una línea por derecho, y la revocación).
2. Identificarse: nombre, DUI, fecha de nacimiento, correo o teléfono; si actúa por
   otra persona, su poder o la documentación de heredero.
3. Verificar el contacto con un código (correo o WhatsApp, la misma
   infraestructura de `intake_issue_code`).
4. Describir lo que pide; para rectificación, el dato y el valor correcto con su
   respaldo (Art. 9 ¶2); para acceso, la modalidad de entrega (Art. 18).
5. Recibir folio, fecha límite y un enlace de seguimiento.

**Reglas de seguridad del portal**

- **Nunca revela si hay datos** antes de verificar la identidad: siempre "Recibimos
  su solicitud N.º 12" (evita enumerar clientes).
- La entrega de datos (informe de acceso, portabilidad) solo a un contacto que
  **ya estaba registrado** para ese cliente, o después de que el personal
  verifique el documento de identidad subido (Art. 16 lit. c).
- Descarga con token + código, enlace que expira en 15 días, cada descarga
  registrada en `dsr_events`.
- Formularios modelo de la ACE (Art. 50 lit. q): cuando se publiquen, el portal los
  sigue.

### `LPD-7` — Informe de acceso y portabilidad

**Acceso** (`execute_dsr_access(p_dsr_id)` → orquestador o ruta de servidor de
`web` genera el paquete). Contenido, en español claro y "sin codificaciones" (Art.
8 lit. a), con glosario de términos:

| Sección | Fuente | Notas |
| --- | --- | --- |
| Identificación y contacto | `clients` | Con la procedencia de cada dato (`field_sources`: "tomado de su constancia del 2026-09-28") |
| Solicitudes y respuestas del formulario | `applications.form_data` | **Sin datos de beneficiarios ni dependientes** (Art. 8 lit. b): se indica que existen y que no se incluyen |
| Documentos | `documents` | Lista, fecha, tipo y los datos extraídos de cada uno; copia de los archivos si la modalidad lo pide |
| **Datos inferidos** | `scores`, `case_decisions` | Puntaje, nivel, recomendación, reglas aplicadas con su resultado y la narrativa de IA (Art. 56 lit. b.1). Las señales de fraude y de identidad, **retenidas como denegación parcial motivada** si el abogado lo confirma (L8) |
| Decisiones | `case_decisions` | Qué se decidió, cuándo, con qué condiciones y motivos |
| **Quién consultó y para qué** | `access_log` (`LPD-10`) y `audit_log` | Por persona del personal (nombre y rol) o sistema, fecha y finalidad (Art. 8 lit. a) |
| **Intercambios con otras entidades** | `data_transfers` (`LPD-12`; el Plan 4 escribe ahí) y `subprocessors` | Art. 8, último párrafo |
| Consentimientos | `consent_records` | Qué aceptó o negó, cuándo, versión del texto |
| Estado de tratamiento | `clients.processing_state`, `field_locks` | |
| Datos seudonimizados o disociados | Marcados como tales | Art. 8 lit. b |

Formatos: PDF legible y JSON. Gratis por vía electrónica (Art. 23).

**Portabilidad** (Art. 14): solo lo que el titular **proporcionó** (formulario,
contacto, archivos que subió) y que se trata por consentimiento y en forma
automatizada. JSON con esquema publicado `tramiq.subject-export/v1` (documentado
en `docs/`), CSV para lo tabular y los archivos originales en un ZIP. Si pide
transmitirlo a otro responsable, se envía al correo verificado de ese
responsable y queda en `data_transfers`.

### `LPD-8` — Rectificación, cancelación, olvido y propagación

**Rectificación** (Art. 9):

1. Al registrar la solicitud, `field_locks` bloquea los campos impugnados y el
   cliente pasa a `limited` si el titular lo pide (Art. 13 lit. a).
2. El personal revisa el respaldo y ejecuta `rectify_subject_data(p_dsr_id,
   p_changes jsonb)`: escribe los valores nuevos con procedencia
   `{"source": "dsr", "dsr_id": …}` en `clients.field_sources` (y en los hechos del
   Plan 3 cuando exista), deja una anotación en el documento original —**un
   documento no se edita: es la evidencia de lo que se presentó**— y libera los
   bloqueos.
3. Si la rectificación cambia algo que un puntaje usó, se ofrece "Volver a puntuar"
   (no automático: la decisión ya tomada se registró con lo que había).

**Cancelación** (Arts. 10–11). `execute_dsr_erasure(p_dsr_id)` decide por almacén,
según `personal_data_stores.erase_handler` y las retenciones legales de `LPD-9`:

| Caso | Acción |
| --- | --- |
| No hay obligación legal de conservar (p. ej. borrador o solicitud rechazada fuera de plazo legal) | **Anonimizar**: `clients` sin datos identificables (`full_name` = "Titular eliminado", el resto null), `form_data` vacío, `extracted_data` vacío, archivos borrados de Storage, `content_sha256` borrado, `ai_summary` y `rationale` depurados, comentarios y notas reemplazados por "[eliminado por solicitud N.º X]", contactos de autoservicio y notificaciones depurados. Se conservan los ids, fechas, estados y puntajes numéricos para estadística (dato disociado, Art. 10 lits. d–e) |
| Hay obligación legal (póliza emitida, registros antilavado, reclamos) | **Bloquear** (Art. 11): `processing_state = blocked`, invisible salvo para administradores, y anonimizar cuando venza el plazo legal (lo hace `LPD-9`) |
| `audit_log` | Es append-only. Una función `redact_audit_metadata(p_client_id)` (`service_role`, auditada como `audit.redacted`) reemplaza los datos personales del `metadata` (hoy el trigger de cambios de clientes guarda valores anteriores y nuevos) y conserva la acción, el actor y la fecha. **[abogado]** ¿la bitácora es en sí obligación legal de conservar? |
| Respaldos | Se borran solos al rotar (7 días en Supabase Pro). Se dice en el aviso y en la respuesta |
| Proveedor de IA | Según la retención contratada (L3). Se dice en la respuesta |
| Destinatarios (CRM del Plan 4) | Se encola la supresión en cada destino y se vigila el plazo de 5 días hábiles |

`delete_client()` actual queda para errores administrativos (un cliente
registrado por equivocación), no para atender derechos, y pasa a anonimizar
también la bitácora.

**Olvido** (Art. 10, último párrafo): Tramiq no publica datos en internet. El
procedimiento confirma eso, ejecuta la supresión y pide a los destinatarios que
eliminen copias.

**Propagación** (Art. 21 ¶3, Art. 30): `dsr_propagations (dsr_id, destination_id,
action, due_on, done_at, evidence)`. Sin Plan 4 solo hay destinatarios manuales
(p. ej. "se envió a la reaseguradora X"); con el Plan 4 se llena sola.

### `LPD-9` — Retención y supresión automática

```sql
create table retention_policies (
  tenant_id uuid not null references tenants (id),
  data_class text not null check (data_class in (
    'intake_draft','staff_draft','withdrawn_application','declined_application',
    'approved_application','document_file','extracted_data','case_notes',
    'access_log','consent_record','dsr_record','unconverted_intake_contact','audit_log')),
  retain_days integer not null check (retain_days between 1 and 36500),
  starts_from text not null,            -- 'last_activity' | 'decision' | 'policy_end' | 'created'
  action text not null check (action in ('delete','anonymize','block_then_anonymize')),
  legal_basis text not null,
  approved_by uuid, approved_at timestamptz,
  primary key (tenant_id, data_class)
);
create table legal_holds (
  id uuid primary key default gen_random_uuid(), tenant_id uuid not null,
  client_id uuid, application_id uuid, reason text not null, until date,
  created_by uuid, created_at timestamptz default now(), released_at timestamptz
);
```

**Propuesta de plazos — a validar [abogado L6], no usar sin firma:**

| Clase | Propuesta | Por qué |
| --- | --- | --- |
| Borrador de autoservicio abandonado | 30 días | Ya existe (`intake_purge`) |
| Borrador del personal | 90 días | Sin uso no hay finalidad |
| Solicitud retirada o rechazada | 1–2 años desde la decisión, salvo `retain_after_decline` | Defensa de reclamaciones; prescripción a confirmar |
| Solicitud aprobada (póliza) | Vigencia de la póliza + plazo legal (posiblemente 5 a 10 años) | Normas de seguros, comerciales y antilavado |
| Archivo del documento | Igual que su solicitud | |
| Bitácora de accesos | 2 años | Responder "quién consultó" sin guardarlo para siempre |
| Registros de consentimiento y de solicitudes ARCO-POL | Mientras existan los datos + 5 años | Carga de la prueba (Art. 54) |
| Contacto de autoservicio que nunca se volvió solicitud | 30 días | Minimización |

`retention_candidates(p_limit)` (`service_role`) y un job `privacy.retention`
diario en el orquestador, que borra archivos primero (como `intake.purge`) y luego
aplica la acción, respetando `legal_holds` y el estado `blocked`. Cada ejecución
deja un resumen en `audit_log` (`retention.applied`, con conteos, nunca datos).
Con el plan gratuito de Render el job solo corre cuando el servicio está despierto:
otra razón para un plan pagado antes de datos reales.

### `LPD-10` — Seguridad, acceso por sensibilidad y minimización

1. **MFA obligatorio para todo el personal** (políticas de la ACE): `mfa_required`
   pasa a ser verdadero por defecto y solo un superadmin puede apagarlo, con
   motivo. `require_mfa_if_tenant_requires()` ya protege las funciones críticas;
   se extiende a lecturas de datos sensibles (ver 3).
2. **Bitácora de accesos con finalidad** (`access_log`, append-only, particionada
   por mes): `client.viewed`, `application.viewed`, `case.viewed`,
   `document.viewed` (ya existe en `audit_log`; se mueve aquí), `export.generated`,
   `search.performed` (solo el hecho, no el texto buscado). La finalidad se deduce
   de la pantalla (`underwriting_review`, `customer_service`, `dsr_response`,
   `audit`) y se puede indicar a mano en accesos fuera de lo normal. Es lo que
   alimenta "quién consultó y para qué" (Art. 8). Escrita por las rutas de
   servidor de `web` con la clave de servicio, o por una función `log_access()`
   que deriva el actor de la sesión.
3. **Acceso por sensibilidad** (minimización): los documentos de tipos con campos
   sensibles (Plan 1) y las respuestas sensibles del formulario solo los ven
   `underwriter`, `tenant_admin` y `superadmin`. Un `agent` registra y sube, pero
   después ve "Documento médico — acceso restringido". Política RLS en
   `documents` (`select`), la misma condición en la política del bucket y en la
   ruta de URL firmada; para `form_data`, una vista `application_form_view` que
   enmascara las llaves sensibles según el rol.
4. **Minimización hacia el modelo**: `minimizeForModel()` en el orquestador quita
   del `form_data` que reciben el agente de consistencia, el narrador y las
   preguntas del caso las llaves de categoría `contact` y los identificadores que
   el modelo no necesita (la comparación de identidad es determinista), y nombra al
   titular "el solicitante". La extracción sigue viendo el documento completo (no
   hay alternativa).
5. **Cifrado**: Supabase cifra en reposo (AES-256) y en tránsito. No se propone
   cifrado por columna ahora (impide buscar y complica el Plan 3); se reevalúa si
   el abogado o un cliente lo exige para salud.
6. **Secretos** (`SEC-11`): rotación del token entre servicios y de las claves; las
   credenciales de terceros (Plan 4) en Supabase Vault, nunca en tablas legibles.
7. **Compromiso de confidencialidad del personal**: al primer inicio de sesión y en
   cada versión nueva, el personal acepta un texto (`staff_acknowledgements`).
   Evidencia para la ACE.
8. **Datos reales fuera de producción**: prohibido. Las sesiones de desarrollo y de
   QA usan los fixtures sintéticos (`qa/`), como ya es costumbre; queda escrito en
   `RUNBOOK.md`.

### `LPD-11` — Vulneraciones de seguridad (72 horas)

```sql
create table security_incidents (            -- plataforma, superadmin
  id uuid primary key default gen_random_uuid(),
  detected_at timestamptz not null, known_at timestamptz not null,   -- el reloj corre desde known_at
  nature text not null, data_categories text[] not null, includes_sensitive boolean not null,
  affected_subjects_estimate integer, immediate_actions text, recommendations text,
  root_cause text, corrective_actions text, status text not null default 'open',
  created_by uuid, created_at timestamptz default now()
);
create table incident_tenants (incident_id uuid, tenant_id uuid,
  responsible_notified_at timestamptz,        -- Tramiq → aseguradora (DPA: 24 h)
  ace_notified_at timestamptz, fgr_notified_at timestamptz, subjects_notified_at timestamptz,
  primary key (incident_id, tenant_id));
create table incident_events (… append-only …);
```

- Pantalla de superadmin con el reloj de 72 h y, por tenant afectado, las tres
  notificaciones del Art. 25 con plantillas que ya traen el contenido mínimo
  (a–e para la ACE; a, b, d, e para los titulares).
- Aviso a los titulares por la bandeja de salida (correo y WhatsApp).
- El vigilante del orquestador puede **abrir un incidente en borrador** ante
  señales (accesos masivos, exportes fuera de hora, intentos de lectura entre
  tenants), para que una persona lo confirme o descarte.
- Procedimiento escrito en `RUNBOOK.md` § "Vulneración de datos personales": quién
  decide, cómo se contiene, cómo se notifica.
- Se documenta **toda** vulneración, aunque no se notifique (Art. 25, último
  párrafo).

### `LPD-12` — Transferencias y flujos internacionales

- **`subprocessors`** (`LPD-1`) con país, finalidad, categorías y garantías,
  publicado en el aviso.
- **`data_transfers`**, una fila por envío de datos de un titular a alguien que no
  es el responsable ni Tramiq (append-only): `tenant_id, client_id, recipient_kind
  (crm_destination | reinsurer | bureau | other_controller | authority),
  recipient_id, recipient_name, country, categories, legal_basis, consent_record_id,
  occurred_at, reference`. La escriben el Plan 4 (cada entrega a un CRM), la
  portabilidad y el registro manual. La lee el informe de acceso.
- **Comunicación a la ACE** del flujo transfronterizo (Art. 45) — trámite, no
  código; el inventario de `LPD-1` es el insumo.
- **Opciones de residencia** (para la decisión de negocio de `SEC-10`): (a) seguir
  en EE. UU. con consentimiento, contratos y comunicación a la ACE — recomendado
  mientras el abogado no diga lo contrario; (b) alojar la base y los archivos en un
  centro de datos en El Salvador o la región — costo y operación mucho mayores, y
  el modelo de IA seguiría fuera.

### `LPD-13` — Responsabilidad demostrada

- **Panel de cumplimiento** (Privacidad → Resumen): aviso publicado y su versión;
  % de solicitudes con consentimiento completo por canal; solicitudes ARCO-POL
  abiertas, por vencer y fuera de plazo; tiempo medio de respuesta; retención
  pendiente; MFA del personal; compromisos de confidencialidad aceptados;
  incidentes; subencargados sin DPA; preguntas de formulario y campos sin
  clasificar.
- **Paquete de evidencia** descargable para una inspección: RAT, aviso vigente e
  historial de versiones, procedimiento ARCO-POL, registro de solicitudes con
  plazos, muestra de consentimientos con su evidencia, políticas de retención,
  registro de incidentes, lista de subencargados y DPA, medidas de seguridad.
- **Salida de un tenant** (DPA, devolución o supresión al terminar): exportación
  completa en formato portable y purga verificada, con un acta.

---

## 7. Fases y orden interno

| Fase | Componentes | Tamaño | Notas |
| --- | --- | --- | --- |
| **0** | `LPD-0` | Horas (seguridad) + calendario legal | Empieza ya, aunque el resto espere al Plan 1 |
| **1** | `LPD-1` inventario + `LPD-2` aviso + clasificación de formularios | 6–7 días | Usa la clasificación del Plan 1 |
| **2** | `LPD-3` finalidades y consentimientos (los tres canales) + `has_consent` en el pipeline | 8–10 días | El mayor cambio de comportamiento: **sin consentimiento no hay IA** |
| **3** | `LPD-4` estado de tratamiento + `LPD-5` solicitudes + calendario | 7–8 días | |
| **4** | `LPD-6` portal + `LPD-7` acceso y portabilidad | 6–7 días | |
| **5** | `LPD-8` rectificación, supresión, propagación + `LPD-9` retención | 6–7 días | Ensayar la anonimización sobre una copia |
| **6** | `LPD-10` seguridad y minimización + `LPD-11` incidentes + `LPD-12` transferencias | 5–6 días | |
| **7** | `LPD-13` panel y evidencia | 3 días | |

Cada fase pasa por el ensayo en transacción revertida en producción antes de
`apply_migration`, y por `develop` → `main` como siempre.

---

## 8. Relación con los demás planes

**Usa del Plan 1:** la clasificación `category` / `sensitive` / `pii` de cada
campo (inventario, productos sensibles, acceso por sensibilidad, minimización); los
tipos `consent_form`, `dsr_identity` y `power_of_attorney` con sus reglas de
aceptación (firma presente, identidad legible); el rol `identity_document` para
verificar al titular.

**Deja para el Plan 3:**

- `has_consent()` y las finalidades `profiling_offers` y `marketing`, que limitan
  qué enriquecimiento comercial se puede hacer y con quién;
- `processing_state` y `field_locks`, que la ficha 360 y la búsqueda respetan;
- el invariante de registro en `personal_data_stores` (las tablas de hechos y
  textos del Plan 3 se registran con `erase_handler` y `access_handler`);
- la rectificación, que escribirá hechos con procedencia `dsr`;
- el acceso por sensibilidad, que la ficha 360 aplica campo por campo.

**Deja para el Plan 4:**

- `data_transfers` (cada entrega a un CRM es una fila);
- `has_consent(…, 'commercial_management')` y `international_processing` como
  filtro de exportación;
- `dsr_propagations` y los plazos de 5 días hábiles para rectificaciones,
  supresiones y revocaciones en los CRM;
- `subprocessors` y el generador del aviso, que listarán los destinos CRM activos.

---

## 9. Riesgos

- **El canal del personal pierde fluidez** al exigir consentimiento antes de la
  IA. Mitigación: el enlace de consentimiento se envía al abrir la solicitud
  nueva (cuando ya se despierta el orquestador) y el formulario en papel como
  alternativa.
- **Anonimizar mal es irreversible.** Ensayar en una copia, pruebas con datos
  sintéticos, y un modo "simulación" que muestra qué se borraría.
- **Plazos y bases legales sin confirmar.** Todo valor marcado **[abogado]** se
  configura por tenant y no bloquea la construcción.
- **Volumen de `access_log`.** Particionar por mes y retener 2 años.

---

## Fuentes (consultadas el 2026-11-07)

- D.L. 144, texto con la reforma D.L. 659 — [jurisprudencia.gob.sv](https://www.jurisprudencia.gob.sv/DocumentosBoveda/D/2/2020-2029/2024/11/10660E.PDF)
- D.L. 659 en la Asamblea — [asamblea.gob.sv](https://www.asamblea.gob.sv/sites/default/files/documents/decretos/048D810E-C262-4D9E-8839-B3D26A2F4378.pdf); nota de la Asamblea — [asamblea.gob.sv/node/14116](https://www.asamblea.gob.sv/node/14116)
- Eliminación del delegado para empresas — [Infobae, 17-sep-2026](https://www.infobae.com/el-salvador/2026/09/17/el-salvador-la-asamblea-legislativa-elimina-la-obligacion-del-delegado-de-proteccion-de-datos-para-las-empresas/); [ALTA Legal](https://altalegal.com/comunicacion/reformas-a-la-ley-para-la-proteccion-de-datos-personales/); [Montano & Co.](https://www.montanoandco.net/blog/reforma-sobre-el-delegado-de-proteccion-de-datos-en-el-salvador-que-cambia-para-las-empresas)
- ACE deja sin efecto la fecha de nombramiento — [El Mundo](https://diario.elmundo.sv/politica/ace-deja-sin-efecto-fecha-limite-para-nombrar-delegados-de-proteccion-de-datos); [El Diario de Hoy](https://www.eldiariodehoy.com/noticias/nacionales/sin-fecha-para-nombrar-delegados-de-proteccion-de-datos-personales/93083/2026/)
- Políticas de actuación de la ACE — [El Mundo](https://diario.elmundo.sv/politica/vigentes-politicas-de-actuacion-y-manejo-de-datos-personales-en-el-salvador) (resumen de prensa; falta el texto oficial)
- Lineamientos del Delegado y procedimiento sancionador — [EY](https://www.ey.com/es_ce/technical/tax/tax-alerts/el-salvador-la-agencia-de-ciberseguridad-del-estado-desarrolla-aspectos-relevantes-de-la-ley-de-proteccion-de-datos-personales); [texto en ICNL](https://www.icnl.org/wp-content/uploads/Lineamientos-para-el-delegado-de-proteccion-de-datos-personales.pdf)
- Presentación de Technosal, "Implementación de la Ley de Protección de Datos Personales", septiembre de 2026 (archivo del usuario)
- `docs/research/2026-11-06-credit-bureaus-el-salvador.md` (consentimiento de buró, D.L. 695)
