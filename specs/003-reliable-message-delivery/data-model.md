# Data Model: Envío Robusto y Confirmación de Entrega

**Date**: 2026-07-14
**Feature**: 003-reliable-message-delivery

## Overview

Amplía el modelo de datos del feature 002 para soportar estados de entrega verificados (`delivered`/`pending`/`failed`), intentos de envío auditables, y la cola + circuit breaker. Todos los modelos siguen siendo Pydantic `BaseModel`; la persistencia sigue en JSON (sin base de datos), coherente con la decisión del proyecto.

## Cambios sobre el modelo de 002

### 1. SendStatus (enum) — AMPLIADO

```python
class SendStatus(str, Enum):
    SENDING = "sending"      # encolado, esperando acuse (transitorio)
    DELIVERED = "delivered"  # confirmación de entrega recibida
    PENDING = "pending"      # acuse aún no llegado, dentro de plazo
    FAILED = "failed"        # error definitivo o timeout
```

**Migración de datos antiguos**: los `SendResult` históricos con `status == "sent"` se interpretan como `delivered`; `"failed"` se mantiene. Se añade un validador/compat en la lectura del historial para no romper JSON ya guardados.

### 2. SendResult — AMPLIADO

| Campo | Tipo | Req | Descripción |
|-------|------|-----|-------------|
| `appointment` | `Appointment` | Sí | (sin cambios) |
| `status` | `SendStatus` | Sí | estado verificado del mensaje |
| `phone_used` | `str` | Sí | (sin cambios) |
| `message_sent` | `str` | Sí | (sin cambios) |
| `message_id` | `str \| None` | No | id devuelto por el bridge (clave de deduplicación) |
| `sent_at` | `datetime \| None` | No | momento en que se encoló |
| `delivered_at` | `datetime \| None` | No | momento de confirmación de entrega (nuevo) |
| `error_reason` | `str \| None` | No | motivo si `failed` |
| `api_response` | `dict \| None` | No | (sin cambios) |
| `attempts` | `list[SendAttempt]` | No | registro de intentos (nuevo, auditabilidad) |

### 3. SendAttempt (NUEVO)

Registro de un único intento de envío de un mensaje.

| Campo | Tipo | Req | Descripción |
|-------|------|-----|-------------|
| `attempt_number` | `int` | Sí | ordinal del intento (1-based) |
| `started_at` | `datetime` | Sí | cuándo se inició |
| `status` | `SendStatus` | Sí | resultado del intento |
| `error_reason` | `str \| None` | No | motivo del fallo si lo hubo |
| `message_id` | `str \| None` | No | id del bridge (si lo hubo) |

### 4. SendSession — AMPLIADO (propiedades calculadas)

Las propiedades de conteo pasan a reflejar los tres estados:

| Propiedad | Fórmula |
|-----------|---------|
| `delivered_count` | `sum(1 for r in results if r.status == DELIVERED)` |
| `pending_count` | `sum(1 for r in results if r.status == PENDING)` |
| `failed_count` | `sum(1 for r in results if r.status == FAILED)` |

Se conservan `sent_count` (alias de `delivered_count`) por compatibilidad con el histórico y la UI existente.

---

## Componentes de infraestructura (en memoria, no persistidos como JSON)

### 5. SendQueue (NUEVO)

Cola FIFO de mensajes pendientes de despacho. Un único despachador consume de a uno.

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `items` | `deque[SendJob]` | mensajes encolados |
| `enqueue(job)` | método | añade un trabajo |
| `dequeue()` | método | extrae el siguiente trabajo |

`SendJob` = `{ appointment, rendered_text, attempts, message_id, deadline }`.

### 6. RateLimiter (NUEVO)

Garantiza el intervalo mínimo entre envíos.

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `min_interval_ms` | `int` | intervalo mínimo configurable (default 1500) |
| `last_send_at` | `datetime` | timestamp del último despacho |
| `wait_until_ready()` | async | espera hasta que se pueda despachar |

### 7. CircuitBreaker (NUEVO)

Pausa global ante errores transitorios masivos.

| Atributo | Tipo | Descripción |
|----------|------|-------------|
| `state` | `closed \| open \| half_open` | estado del circuito |
| `consecutive_errors` | `int` | contador de errores seguidos |
| `threshold` | `int` | umbral para abrir (default 3) |
| `cooldown_s` | `int` | enfriamiento (default 60) |
| `record_success()/record_error()` | método | actualizan el contador |
| `allow_send()` | método | `False` mientras está abierto |

---

## State Transitions

### SendStatus (por mensaje)

```
                ┌─────────────► delivered ── (DELIVERY_ACK / READ)
sending ────────┤
   ▲            ├─► pending  ── (SERVER_ACK, sin entrega aún)
   │            └─► failed   ── (ERROR / deadline agotado / máx. reintentos)
   └── retry (si pending/failed y quedan reintentos)
```

### CircuitBreaker

```
closed ──(≥threshold errores)──► open ──(cooldown agotado)──► half_open
  ▲                                                              │
  └────────────(éxito)───────────────────────────────────────────┘
  (half_open + error → open de nuevo)
```

---

## Persistencia

El `HistoryStore` sigue guardando `SendSession` en JSON. El `SendResult` ampliado (con `message_id`, `delivered_at`, `attempts`, estado ternario) se serializa con `model_dump(mode="json")` igual que hoy. La **deduplicación** en reanudación usa `message_id`: si ya existe un `SendResult` con ese `message_id` y estado `delivered`, no se reenvía.
