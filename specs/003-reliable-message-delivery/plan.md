# Implementation Plan: Envío Robusto y Confirmación de Entrega de Mensajes WhatsApp

**Branch**: `003-reliable-message-delivery` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-reliable-message-delivery/spec.md`

## Summary

Corrige un defecto crítico del envío de recordatorios: hoy **todos los mensajes se marcan "enviado"** en cuanto Baileys los encola, sin verificar jamás la entrega real, por lo que los que se quedan colgados en "Enviando..." (reloj) aparecen igual que los entregados. El fix introduce (1) estados de entrega verificados (**entregado/pendiente/fallido**) basados en el acuse `messages.update` de Baileys, (2) un **envío asíncrono con cola, rate limiting, backoff + jitter y circuit breaker** que no satura WhatsApp, y (3) **persistencia idempotente** para reanudar sin duplicar. Todo sigue sin base de datos externa y sin broker distribuido: cola en memoria + JSON local.

## Technical Context

**Language/Version**: Python 3.11+ (PySide6 GUI), Node.js 18+ (bridge Baileys `@whiskeysockets/baileys`)

**Primary Dependencies**: PySide6, httpx, pydantic (ya presentes); sin dependencias nuevas. Bridge: Baileys ya instalado en `bridge/node_modules`.

**Storage**: Sin base de datos. Estado persistido en JSON vía `HistoryStore` (platformdirs). El registro de acuses del bridge es en memoria (volátil); la fuente de verdad persistente es el historial del cliente.

**Testing**: Tests unitarios con `pytest` para el enum/estados, el backoff/jitter, el rate limiter y el circuit breaker; tests de integración `pytest-httpx` para el cliente contra un bridge simulado; validación manual del acuse real con un número de prueba.

**Target Platform**: Windows (primario), macOS/Linux (secundario).

**Project Type**: Aplicación de escritorio Qt + bridge Node.js local.

**Performance Goals**: Lote de 60 mensajes sin congelar la UI (SC-008), sin bajar del intervalo mínimo entre envíos (SC-006), y clasificación veraz del 100% de los mensajes atascados (SC-001/SC-005).

**Constraints**: No saturar WhatsApp (backoff + jitter + circuit breaker, priorizados sobre velocidad); sin base de datos ni broker externo; compatibilidad con el historial JSON ya guardado.

**Scale/Scope**: Clínica única, ~60 mensajes por lote, un número de WhatsApp, un bridge local.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

La constitución (`.specify/memory/constitution.md`) sigue en forma de plantilla sin principios definidos. No hay principios propios que violar. Se aplican los principios por defecto ya usados en 001/002:

- **Simplicidad (YAGNI)**: No se introduce broker externo ni base de datos; para ~60 mensajes basta cola en memoria + persistencia JSON local. Se rechaza explícitamente Celery/Redis/RabbitMQ.
- **Robustez sobre velocidad**: El espaciado, backoff y circuit breaker se priorizan por encima de la velocidad de envío (anti-bloqueo de cuenta).
- **Compatibilidad**: Los datos históricos (`sent/failed`) se migran/leen sin romper la app.

**Gate evaluation**: PASS (condicional) — sin principios de constitución definidos, se procede con los defaults. Re-evaluar si el propietario define la constitución.

## Project Structure

### Documentation (this feature)

```text
specs/003-reliable-message-delivery/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── whatsapp-bridge-contract.md   # Endpoints nuevos: POST /send (accepted) + GET /message/{id}
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
bridge/
└── whatsapp-bridge.js          # MODIFICAR: escuchar messages.update, endpoint GET /message/{id}, POST /send → accepted
src/
├── models/
│   ├── send_result.py          # MODIFICAR: SendStatus ampliado + message_id, delivered_at, attempts
│   ├── send_attempt.py         # NUEVO: modelo SendAttempt
│   └── send_history.py         # MODIFICAR: delivered/pending/failed_count
├── services/
│   ├── whatsapp_client.py      # MODIFICAR: send_message → accepted+message_id; nuevo get_message_status()
│   ├── send_queue.py           # NUEVO: cola de despacho FIFO
│   ├── rate_limiter.py         # NUEVO: intervalo mínimo entre envíos
│   ├── circuit_breaker.py      # NUEVO: pausa global ante errores masivos
│   ├── delivery_tracker.py     # NUEVO: verifica acuse en segundo plano (poll GET /message/{id})
│   ├── send_worker.py          # MODIFICAR: usar cola + rate limiter + circuit breaker + confirmación diferida
│   └── history_store.py        # MODIFICAR: migrar/leer estados antiguos, deduplicación por message_id
└── ui/
    ├── results_table.py        # MODIFICAR: 3 estados (✅/⏳/❌) + botón "Reintentar pendientes"
    └── main_window.py          # MODIFICAR: cablear reintento de pendientes y estados nuevos
```

**Structure Decision**: Se reutiliza la estructura de 002. Los componentes nuevos de robustez (cola, rate limiter, circuit breaker, delivery tracker) son servicios independientes bajo `src/services/`, testables aisladamente. El bridge solo gana un endpoint y un listener de acuses.

## Complexity Tracking

> Justificación de complejidad añadida (vs. constitution "simplicidad"): el circuit breaker, la cola y el backoff **no** son sobre-ingeniería — son el mínimo necesario para cumplir FR-010/FR-011/FR-012 ("no saturar WhatsApp") sin los cuales el fix de veracidad (US1) provocaría el bloqueo de la cuenta. Se mantiene deliberadamente **sin** broker externo ni base de datos.
