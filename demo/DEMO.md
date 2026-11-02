# Demo de Tramiq — guion y lista de preparación

Preparado el 2026-10-16. El guion base está en `docs/mvp-execution-plan.md`
§ "Guion sugerido"; esta versión lo adapta a Tramiq, al posicionamiento más
amplio que solo seguros y a lo que hoy está desplegado. Duración: 12 a 15 minutos.

## Lo que falta antes de la primera demo

Sin estos puntos, la demo puede fallar delante del cliente.

| | Qué | Quién | Estado |
| --- | --- | --- | --- |
| 0 | **Reemplazar la API key de Anthropic.** El 2026-10-17 la extracción falló con `401 invalid x-api-key`: la key del orquestador en Render ya no es válida, y la del archivo de secretos tampoco. Sin ella, ningún documento se lee y nada se puntúa. `/health/queue` no lo detecta: dice `ok` mientras los trabajos reintentan. Crear una key nueva en console.anthropic.com y ponerla en Render → `qualifier-ai-orchestrator` → Environment → `ANTHROPIC_API_KEY`, directamente en el servicio (nunca en un *envVarGroup* con `sync: false`). Actualizar también `qualifier-secrets.env.txt`. | Tú | Hecho en Render el 2026-10-17. Falta actualizar el archivo de secretos |
| 1 | **Correr una solicitud completa de punta a punta** en cada tenant con los documentos de `qa/2026-10-02/` (`BLK-5`), y decidir un caso como analista. Nunca se ha visto la narrativa ni una decisión real en producción. | Claude, con tu sesión iniciada | **Hecho en ambos.** Seguros: 86 *Preferente*, aprobada con nota. Médico: 80 *Riesgo moderado* (revisión manual, como manda su playbook para 65–84), aprobada con nota. Ambas quedaron en la bitácora |
| 2 | **Refrescar las fechas de la cartera de demo** con `demo/refresh-demo-dates.sql`. Corrido el 2026-10-17: 4 casos vencidos y 3 a tiempo, repartidos en ambos tenants. Las fechas vuelven a envejecer: córrelo otra vez el día antes de la demo; se puede repetir sin problema. | Tú, el día antes | Hecho; repetir antes de la demo |
| 3 | **Supabase → Authentication → URL Configuration**: el *Site URL* debe ser `https://qualifier-web.onrender.com`, no `localhost`. Si no, el correo de "olvidé mi contraseña" lleva a un enlace roto. Ahí mismo: activar *leaked password protection* y desactivar *anonymous sign-ins*. | Tú, en el dashboard | Pendiente |
| 4 | **Desplegar la marca Tramiq en la app** (logo, ícono, títulos). `web` `2c25b8e`, en vivo desde el 2026-10-17 a las 03:45 UTC. La URL sigue siendo `qualifier-web.onrender.com` hasta configurar un dominio propio. | — | Hecho |
| 5 | **Grabar un recorrido de 3 minutos** del guion, como respaldo si falla la red. | Tú | Pendiente |

Recomendado: para el mes de la presentación, pasar los servicios de Render a
`starter` y Supabase a Pro. Se quita el arranque en frío y Supabase deja de
pausarse por inactividad (se pausó en septiembre y otra vez antes del 16 de
octubre). Es reversible.

## Preparación

### El día anterior

- [ ] Supabase activo: dashboard → proyecto `qualifier` → estado *Healthy*. Si está
      pausado, *Restore* (los datos se conservan).
- [ ] Correr `demo/refresh-demo-dates.sql`. Al final debe mostrar: solicitud más
      nueva de ~3 horas, unos 4 casos abiertos vencidos y 3 a tiempo.
- [ ] Hacer el recorrido completo una vez, con el mismo navegador y las mismas cuentas.
- [ ] Tener listo un caso **ya procesado** de cada tenant para saltar a él si la
      extracción tarda o falla.

### Una hora antes

Despertar los tres servicios (el primero tarda cerca de un minuto en frío):

```bash
for u in https://qualifier-web.onrender.com/ https://qualifier-grading-engine.onrender.com/health https://qualifier-ai-orchestrator.onrender.com/health; do curl -s -o /dev/null -w "%{http_code} $u\n" -m 120 "$u"; done
```

Confirmar que la cola tiene consumidor (debe responder `"status":"ok"`):

```bash
curl -sS -H "Authorization: Bearer $(grep '^SERVICE_AUTH_TOKEN=' qualifier-secrets.env.txt | cut -d= -f2 | tr -d '\r ')" https://qualifier-ai-orchestrator.onrender.com/health/queue
```

### Cinco minutos antes

Pestañas abiertas, en este orden:

1. La página de Tramiq (para abrir con el problema y cerrar con el piloto).
2. La app, con sesión iniciada como **agente de seguros**.
3. Una ventana privada con sesión de **analista de seguros**.
4. El editor de playbooks de *Seguro de Vida — Plan Estándar* (como administrador de seguros).
5. `/health/queue`, por si algo se atora.

Archivos a mano: `qa/2026-10-02/seguros/` y `qa/2026-10-02/medico/`. Son personas
y documentos inventados. **Nunca uses datos reales**, aunque el prospecto los ofrezca.

## Cuentas

Contraseña: las siete cuentas `@claude.test` comparten una, fijada el 2026-10-17
y guardada en `.env` en la raíz del workspace (fuera de git), junto con las
direcciones. No se escribe aquí porque este archivo puede ir al repo. Para cambiarla,
o para dar una aleatoria a cada cuenta, usa `web/scripts/reset-test-passwords.mjs`
(instrucciones en su encabezado).

| Para | Cuenta |
| --- | --- |
| Registrar, subir, enviar **y** decidir (seguros) | `admin-seguros@claude.test` |
| Lo mismo en el segundo tenant | `admin-medico@claude.test` |
| Solo registrar y subir (seguros), para mostrar que no ve los botones de decisión | `agent-seguros@claude.test` |
| Decidir casos (seguros), el rol pensado para la cola | `underwriter-seguros@claude.test` |
| Vista de todas las empresas (no registra ni decide) | `superadmin@claude.test` |

Quién puede hacer qué: enviar una solicitud lo permite `submit_application()` a
`agent` y `tenant_admin`; decidir lo permite `decide_case()` a `underwriter` y
`tenant_admin`. Por eso una sola cuenta de administrador por tenant alcanza para
todo el guion. Las cuentas `*@seguros.test` y `*@medico.test` del seed también
existen, si conoces sus contraseñas.

## Guion — 8 tiempos

**Mensaje central:** las reglas son de su empresa, la IA hace la lectura y el
contraste, y cada resultado viene con su porqué. La decisión la toma una persona.

| # | Min | Qué mostrar | Qué decir |
| --- | --- | --- | --- |
| 1 | 0:30 | Registrar un cliente (Karla Hernández, datos de `qa/2026-10-02/README.md`) | "La cartera es suya. No hay portal público que mantener: su equipo registra en nombre del cliente." |
| 2 | 1:00 | Registrar la solicitud de *Seguro de Vida — Plan Estándar*. Los campos salen del producto. | "Cada producto define su formulario. Para crédito o proveedores sería otro formulario, mismo sistema." |
| 3 | 1:00 | Subir el DUI y la constancia **de uno en uno**. Mostrar el indicador de documentos requeridos y la vista del documento. | "Si falta un documento o ya venció, el sistema lo dice antes de puntuar." |
| 4 | 2:00 | Mientras procesa, abrir el editor del playbook. La espera es parte del guion. | "Estas son sus reglas, en un editor. Edad, consistencia del ingreso, vigencia de la constancia. Una versión publicada no se puede editar: cada decisión recuerda con qué reglas se tomó." |
| 5 | 3:00 | Abrir el caso puntuado: puntaje, nivel, trazo de reglas, narrativa en español, banderas, documento al lado. | **El corazón de la demo.** "No es un número: es regla por regla, con el valor que usó. Si un dato no se puede leer, el caso no pasa solo; va a revisión." |
| 6 | 3:00 | Cambiar el divisor de ingreso de 3000 a 2500 en un borrador, probarlo con un caso, publicar la versión y volver a puntuar. | "Su equipo cambió el criterio sin pedirle nada a TI, y la versión anterior queda intacta para auditoría." |
| 7 | 2:00 | Como analista: aprobar con una nota. Mostrar la bitácora: quién, qué, cuándo, con qué versión. | "Esto es lo que le muestra a un auditor o a la SSF." |
| 8 | 2:00 | Cambiar a `medico`: otros documentos, otras reglas, otra escala (*Riesgo bajo… No elegible*), otra marca. | "Mismo motor, otro proceso. Seguros fue el primero; crédito u onboarding son otro playbook." |

Cerrar en la página, sección **Piloto**: doce semanas, un proceso, métricas
acordadas desde el primer día.

## Preguntas difíciles — respuestas honestas

- **"¿Qué tan exacto es?"** — "Lo medimos con sus documentos durante el piloto;
  es una de las métricas de la evaluación." No dar una cifra: no existe todavía (`CAL-1`).
- **"¿Cuánto cuesta?"** — "Depende del proceso y del volumen; se lo enviamos en la
  propuesta." Todavía no hay costo por caso medido de punta a punta (`NEG-1`).
- **"¿Dónde están los datos?"** — "Hoy en nube en Estados Unidos; la ubicación se
  acuerda por contrato." No prometer residencia en El Salvador.
- **"¿Se conecta con nuestro core / buró?"** — "Se define y cotiza en el piloto
  según su sistema." No existen integraciones hoy.
- **"¿Tiene doble factor? ¿Antimalware?"** — "Están en preparación para el piloto."
- **"¿Avisa al cliente por correo?"** — No. "Pedir información" queda registrado
  pero no envía correo todavía. Decirlo antes de que lo pregunten.
- **"¿Quién edita las reglas de su lado?"** — Preguntarlo de vuelta: es el supuesto
  sobre el que descansa el producto. Si nadie, la configuración se ofrece como servicio.

## Contingencias

- **La extracción tarda:** seguir con el tiempo 4 (playbook). No improvisar para
  llenar el silencio.
- **La extracción falla:** usar *Reintentar* en la solicitud y saltar al caso ya
  procesado de respaldo.
- **La app no carga:** probablemente Supabase pausado o un servicio frío. Abrir el
  video de respaldo y seguir con la página.
- **Se cae la red:** video de 3 minutos.
- **`/health/queue` responde `stalled`:** el orquestador no está consumiendo.
  Reiniciarlo desde Render toma ~2 minutos; mientras tanto, usar el caso de respaldo.
- **Nada se despliega el día de la demo.** Un despliegue del orquestador a mitad
  de una puntuación deja ese trabajo tomado por la instancia vieja durante 15
  minutos (pasó el 2026-10-17 con la solicitud médica).
- **Una solicitud se queda en "Enviada" sin avanzar:** en el plan gratuito el
  orquestador se duerme tras 15 minutos sin peticiones, aunque tenga trabajos en
  cola. Abrir `/health` del orquestador lo despierta; el trabajo sigue solo.

## Lo que no se dice en la demo

Ninguna cifra de precisión, tiempo de proceso ni costo por caso. Ninguna
certificación (SOC 2, ISO 27001). Ningún logo de cliente ni testimonio. Ninguna
integración existente. Detalle en `audit/2026-10-16-sales-readiness.md` § 2.
