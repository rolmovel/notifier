# Research: Envío Robusto y Confirmación de Entrega de Mensajes WhatsApp

**Date**: 2026-07-14
**Feature**: 003-reliable-message-delivery

## Research Tasks

### R-001: Cómo obtener confirmación real de entrega desde Baileys

**Decision**: Escuchar el evento `messages.update` de Baileys (y complementariamente `message-receipt.update`) para conocer el estado real de cada `message_id`, en lugar de confiar en el retorno de `sock.sendMessage()`.

**Rationale**: El bug raíz es que `sock.sendMessage(jid, { text })` **resuelve cuando el mensaje se encola localmente**, no cuando WhatsApp lo entrega. El bridge actual devuelve `success: true` con HTTP 200 inmediatamente, y el cliente Python lo traduce a "enviado". Para distinguir "entregado" de "pendiente", hay que correlacionar el `key.id` devuelto por `sendMessage()` con los acuses que Baileys emite a través de `sock.ev.on('messages.update', ...)`.

Baileys emite estados de mensaje con `status` del tipo `WAMessageStatus`:
- `PENDING` — el mensaje está en la cola local / pendiente de envío
- `SERVER_ACK` — el servidor de WhatsApp lo recibió (doble tick gris)
- `DELIVERY_ACK` — entregado en el dispositivo destino (doble tick azul) ← **esto es "entregado"**
- `READ` — leído por el destinatario (marca azul) ← NO requerido para "entregado"
- `ERROR` — falló

El patrón está documentado oficialmente en Baileys: [Events - Baileys](https://baileys.wiki/concepts/events) y un PR que añade un ejemplo de "delivery evidence" correlacionando `sendMessage()` con `messages.update` y `message-receipt.update`: [WhiskeySockets/Baileys PR #2428](https://github.com/WhiskeySockets/Baileys/pull/2428).

**Consecuencia para el diseño**:
- El bridge debe mantener un **registro en memoria** `message_id → { status, timestamp, attempts }`, alimentado por `messages.update`.
- Nuevo endpoint `GET /message/{id}/status` (o `GET /status?message_id=`) para que el cliente consulte el estado real.
- El bridge deja de responder `success: true` como sinónimo de "entregado": responde `accepted: true` + `message_id`, y el estado definitivo se consulta/observa después.

**Alternatives considered**:
- Seguir confiando en el retorno de `sendMessage()` — **rechazado**: es la causa del bug (falso "enviado").
- Usar solo `message-receipt.update` — insuficiente por sí solo; conviene combinarlo con `messages.update`, pero ambos son canales válidos de acuse.
- Polling ciego (esperar N segundos y asumir éxito) — **rechazado**: vuelve a mentir.

---

### R-002: Estados de envío a modelar (SendStatus)

**Decision**: Ampliar el enum de `sent|failed` a un modelo de estados con **`delivered` / `pending` / `failed`**, más un estado transitorio interno `sending`.

**Rationale**: La spec (FR-001) exige distinguir entregado / pendiente / fallido. Internamente el mensaje también pasa por `sending` mientras espera el acuse. Estados:

| Estado | Significado | Fuente de verdad |
|--------|-------------|------------------|
| `sending` (transitorio) | encolado/enviado, esperando acuse | retorno `accepted` del bridge |
| `delivered` | confirmación de entrega recibida | `messages.update` → `DELIVERY_ACK` |
| `pending` | acuse aún no llegado, dentro del plazo | ausencia de acuse tras envío |
| `failed` | error definitivo o timeout tras agotar reintentos | error HTTP / `ERROR` / deadline |

**Mapeo de Baileys → SendStatus**:
- `DELIVERY_ACK` → `delivered`
- `SERVER_ACK` → `sending` (aún no entregado)
- `PENDING` → `sending`/`pending`
- `ERROR` → `failed`
- `READ` → `delivered` (ya estaba entregado)

**Compatibilidad hacia atrás**: los `SendResult` antiguos usan `status` con valor `"sent"`/`"failed"`. Se mapea `"sent"` → `delivered` al leer el histórico (o se conserva un alias), sin romper los JSON ya guardados.

---

### R-003: Cola de envío y despachador asíncrono

**Decision**: Sustituir el bucle secuencial bloqueante del `SendWorker` actual por un **despachador con cola**, con `concurrency = 1`, intervalo mínimo entre envíos, y confirmación de entrega **diferida** (no bloqueante).

**Rationale**: El `SendWorker` actual usa `loop.run_until_complete(client.send_message(...))` por mensaje, encadenando cada envío y su espera. Para robustez se necesita:

1. **Cola (SendQueue)**: los mensajes a enviar se encolan; un único despachador consume de a uno.
2. **Espaciado (RateLimiter)**: garantiza el intervalo mínimo entre envíos (hoy 1.2s fijo → configurable).
3. **Confirmación diferida**: tras `POST /send` el mensaje pasa a `sending`; un verificador consulta `GET /message/{id}/status` en segundo plano (sin bloquear la cola) hasta `delivered`, `failed` o deadline.

Esto da semántica *at-least-once* dentro de límites: reintentar los no confirmados, deduplicar por `message_id`, y no encadenar la espera del acuse al envío del siguiente.

**Alternatives considered**:
- Broker externo (Redis/RabbitMQ/Celery) — **rechazado** para ~60 mensajes: sobre-ingeniería; basta cola en memoria + persistencia local del estado.
- Multi-hilo con pool de conexiones — **rechazado**: disparar en paralelo satura WhatsApp y dispara rate limits; el cuello de botella no es CPU sino el ritmo permitido por WhatsApp.
- Mantener el bucle secuencial actual — insuficiente: no separa envío de confirmación y no reintenta de forma controlada.

---

### R-004: Reintento con backoff + jitter y circuit breaker

**Decision**: Backoff exponencial con jitter por mensaje, más un **circuit breaker global** que pausa todos los envíos ante errores transitorios masivos o rate limit (429).

**Rationale**: Para "no saturar WhatsApp" (FR-010 a FR-012) se aplican tres mecanismos:

1. **Backoff exponencial + jitter**: retraso base × 2^attempt, con una variación aleatoria (jitter) para evitar que los reintentos se sincronicen en ráfaga. Límite de reintentos (p.ej. 3) y deadline total por mensaje (p.ej. 60–120s), ambos configurables.
2. **Rate limiting**: intervalo mínimo entre envíos (p.ej. 1.5–3s), aplicado de forma global por el despachador único.
3. **Circuit breaker**: si se acumulan N errores transitorios consecutivos (p.ej. 3) o el servidor responde 429, el circuito se **abre**: se pausa TODO el envío durante un período de enfriamiento (p.ej. 30–60s), y se reanuda progresivamente (half-open → closed). Evita "machacar" WhatsApp reintentando cada mensaje por separado.

**Alternatives considered**:
- Reintento inmediato / en ráfaga — **rechazado**: dispara bloqueo de cuenta.
- Reintento infinito — **rechazado**: riesgo de spam y bucle sin fin.
- Circuit breaker por mensaje (individual) — insuficiente: ante un bloqueo global hay que parar todo, no reintentar cada mensaje en paralelo.

---

### R-005: Persistencia y reanudación idempotente

**Decision**: Persistir el estado de cada mensaje (incluido `message_id` y `status`) en el historial local para permitir reanudar tras un cierre sin duplicar entregas.

**Rationale**: La spec pide (SC-009) no duplicar entregas al reabrir a mitad de envío. Se persiste:
- Por mensaje: `message_id`, `status`, `attempts`, `sent_at`/`delivered_at`, `error_reason`.
- El `HistoryStore` actual ya guarda `SendSession` en JSON; se amplía el `SendResult` con los campos nuevos y se usa `message_id` como clave de deduplicación (si ya existe un resultado `delivered` para ese `message_id`, no se reenvía).

La garantía es *at-least-once* (puede haber reintento), con **deduplicación por `message_id`** para evitar duplicados visibles.

**Alternatives considered**:
- Base de datos (SQLite) — el proyecto rechaza "bases de datos" por decisión explícita del feature 002; se mantiene JSON.
- Reenviar todo sin deduplicar — **rechazado**: duplicaría entregas.

---

### R-006: Parámetros configurables y valores por defecto

**Decision**: Todos los umbrales de robustez son configurables vía `Settings`, con valores por defecto conservadores y documentados.

**Rationale**: La spec deja los números como "configurables". Valores propuestos por defecto (ajustables en planificación):

| Parámetro | Default propuesto | Nota |
|-----------|-------------------|------|
| `send_interval_ms` | 1500 | intervalo mínimo entre envíos |
| `max_retries` | 3 | reintentos por mensaje |
| `retry_backoff_base_ms` | 5000 | base del backoff exponencial |
| `delivery_timeout_s` | 45 | plazo para recibir el acuse de entrega |
| `circuit_break_threshold` | 3 | errores consecutivos para abrir circuito |
| `circuit_cooldown_s` | 60 | período de enfriamiento del circuit breaker |

**Alternatives considered**:
- Valores hardcodeados — **rechazado**: la spec exige configurables.
- Valores agresivos (intervalo <1s, sin jitter) — **rechazado**: riesgo de bloqueo de cuenta.
