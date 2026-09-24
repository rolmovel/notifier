# Tasks: Envío Robusto y Confirmación de Entrega de Mensajes WhatsApp

**Input**: Design documents from `/specs/003-reliable-message-delivery/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Se incluyen tests unitarios para los componentes nuevos de robustez (backoff/jitter, rate limiter, circuit breaker, estados) porque son lógica pura testable sin red. El flujo de entrega real se valida manualmente con un número de prueba (documentado en quickstart.md).

> **⚠️ Envíos reales**: durante las pruebas manuales de envío real, usar **SOLO** los teléfonos **629071739** y **629335570**. Nunca a otros destinos.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `bridge/`, `tests/` at repository root
- Python application code lives in `src/` (models, services, ui)
- Node.js Baileys bridge lives in `bridge/`
- Tests mirror source structure under `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new dependencies; confirm test scaffolding exists

- [ ] T001 Verify `pytest`, `pytest-httpx` are available in `pyproject.toml` dev dependencies (already listed in 002 T004). No new runtime dependencies required — httpx, pydantic, PySide6 already present.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 [P] Ampliar `SendStatus` enum in `src/models/send_result.py` — add `SENDING`, `DELIVERED`, `PENDING`, `FAILED`; keep backward-compat alias so historical `"sent"` maps to `delivered` per data-model.md
- [ ] T003 [P] Add `SendAttempt` model in `src/models/send_attempt.py` — fields: `attempt_number`, `started_at`, `status`, `error_reason`, `message_id` per data-model.md
- [ ] T004 [P] Ampliar `SendResult` in `src/models/send_result.py` — add `message_id`, `delivered_at`, `attempts: list[SendAttempt]`; keep existing fields
- [ ] T005 [P] Ampliar `SendSession` computed properties in `src/models/send_history.py` — add `delivered_count`, `pending_count`, keep `sent_count` as alias of `delivered_count` for backward compat
- [ ] T006 [P] Implement `RateLimiter` in `src/services/rate_limiter.py` — enforce `min_interval_ms` (default 1500) between sends; `async wait_until_ready()` per research.md R-003
- [ ] T007 [P] Implement `CircuitBreaker` in `src/services/circuit_breaker.py` — states `closed/open/half_open`, `threshold` (default 3), `cooldown_s` (default 60), `record_success()/record_error()/allow_send()` per research.md R-004
- [ ] T008 [P] Implement `SendQueue` in `src/services/send_queue.py` — FIFO deque of `SendJob`; `enqueue()/dequeue()`; `SendJob` dataclass `{appointment, rendered_text, attempts, message_id, deadline}`
- [ ] T009 [P] Modificar `bridge/whatsapp-bridge.js` — listen to `sock.ev.on('messages.update')` and populate an in-memory `receiptMap` (`message_id → status/server_ack/delivery_ack/updated_at`) per contracts/whatsapp-bridge-contract.md
- [ ] T010 [P] Modificar `bridge/whatsapp-bridge.js` — change `POST /send` response from `{success:true,...}` to `{accepted:true, message_id, status:"sending", timestamp}`; keep `success` as deprecated alias
- [ ] T011 [P] Modificar `bridge/whatsapp-bridge.js` — add `GET /message/{id}` endpoint returning `{message_id, status, server_ack, delivery_ack, updated_at}` with `404`/`409` errors per contract

**Checkpoint**: Foundation ready — enums, models, rate limiter, circuit breaker, queue, and bridge receipt tracking are in place.

---

## Phase 3: User Story 1 — Estado de envío real y veraz (Priority: P1) 🎯 MVP

**Goal**: The app tells the truth about each message: delivered / pending / failed, based on real Baileys delivery receipts — never marking "enviado" just because the bridge accepted the message.

**Independent Test**: Send a test batch (including one invalid/non-deliverable number) and verify delivered → "entregado", stuck "Enviando..." → "pendiente", and failures → "fallido" with reason.

### Implementation for User Story 1

- [ ] T012 [US1] Modificar `src/services/whatsapp_client.py` — `send_message()` now reads `accepted`+`message_id` from `POST /send` and returns a `SendResult` with status `SENDING` and `message_id` set (no longer `SENT` on HTTP 200); add new `get_message_status(message_id)` method calling `GET /message/{id}`
- [ ] T013 [US1] Implement `DeliveryTracker` in `src/services/delivery_tracker.py` — poll `GET /message/{id}` for in-flight messages until `delivered`/`failed` or `delivery_timeout_s` (default 45) expires; classify `DELIVERY_ACK`/`READ` → delivered, `ERROR`/timeout → failed, `SERVER_ACK`/pending → pending; emit updated `SendResult` per research.md R-002
- [ ] T014 [US1] Modificar `src/ui/results_table.py` — render three states: `DELIVERED` → "✅ Entregado" (green), `PENDING` → "⏳ Pendiente" (orange), `FAILED` → "❌ Fallido" (red); update `get_summary()` to return delivered/pending/failed counts
- [ ] T015 [US1] Modificar `src/ui/main_window.py` — `_on_result_ready` and `_on_send_finished` to show delivered/pending/failed counts in the status bar summary (`Completado: X entregados, Y pendientes, Z fallidos`)
- [ ] T016 [US1] Modificar `src/services/csv_exporter.py` — export new status strings (`delivered`/`pending`/`failed`) and add `message_id`/`delivered_at` columns; keep old columns for compatibility
- [ ] T017 [P] [US1] Add unit tests in `tests/unit/test_send_status.py` — enum values, backward-compat `sent`→`delivered` mapping, SendResult/SendAttempt serialization
- [ ] T018 [P] [US1] Add unit tests in `tests/unit/test_whatsapp_client.py` (pytest-httpx) — `send_message` parses `accepted`+`message_id` into `SENDING`; `get_message_status` maps bridge statuses to SendStatus

**Checkpoint**: User Story 1 functional — the results table and summary reflect real delivery state. This is the MVP fix for the reported bug.

---

## Phase 4: User Story 2 — Envío asíncrono con cola y sin saturar WhatsApp (Priority: P1) 🎯 MVP

**Goal**: Batch sends are queued and dispatched one-by-one in the background with rate limiting, exponential backoff + jitter, and a global circuit breaker — never spamming WhatsApp with aggressive retries.

**Independent Test**: Launch 60 messages; verify UI stays responsive, no send interval below the minimum, injected 429 pauses globally and resumes, and per-message retries never exceed the configured max.

### Implementation for User Story 2

- [ ] T019 [US2] Modificar `src/services/send_worker.py` — replace sequential blocking loop with queue consumption: enqueue all valid appointments, dispatch one-by-one via `RateLimiter`, respect `CircuitBreaker.allow_send()`, call `client.send_message()` (non-blocking accept) then hand off to `DeliveryTracker`; keep progress/result/finished/error signals
- [ ] T020 [US2] Integrate `CircuitBreaker` + backoff/jitter into the dispatch loop in `src/services/send_worker.py` — on retryable errors apply exponential backoff with jitter (base 5000ms) up to `max_retries` (default 3) and a per-message deadline; on `429`/consecutive errors trip the breaker per research.md R-004
- [ ] T021 [US2] Modificar `src/services/whatsapp_client.py` — `send_message()` retry loop now uses backoff+jitter (add `_backoff_with_jitter(base, attempt)` helper) and raises/returns retryable vs permanent errors distinctly for the breaker to record
- [ ] T022 [US2] Add unit tests in `tests/unit/test_rate_limiter.py` — intervals never below minimum; concurrent calls serialized
- [ ] T023 [US2] Add unit tests in `tests/unit/test_circuit_breaker.py` — closed→open at threshold, open blocks sends, half_open→closed on success, half_open→open on error
- [ ] T024 [US2] Add unit tests in `tests/unit/test_backoff.py` — exponential growth + jitter bounds; retry cap and deadline respected

**Checkpoint**: User Story 2 functional — sends are asynchronous, rate-limited, and protected against WhatsApp blocking.

---

## Phase 5: User Story 3 — Reintento de mensajes pendientes (Priority: P2)

**Goal**: The admin can re-send only pending/failed messages without duplicating delivered ones, respecting the same spacing/backoff rules.

**Independent Test**: With a batch where some messages are pending, click "Reintentar pendientes" and verify only pending/failed are re-queued and delivered ones are untouched.

### Implementation for User Story 3

- [ ] T025 [US3] Modificar `src/ui/results_table.py` — track per-row `SendResult` (store object in `Qt.UserRole`), add a method to collect pending/failed results for re-send
- [ ] T026 [US3] Modificar `src/ui/main_window.py` — add "Reintentar pendientes" button (enabled when pending/failed exist); on click, build a new `SendWorker` from only pending/failed appointments and re-run through the same queue
- [ ] T027 [US3] Modificar `src/services/send_worker.py` — ensure re-send skips appointments whose `message_id` already has a `DELIVERED` result (deduplication by `message_id` per data-model.md)

**Checkpoint**: User Story 3 functional — pending/failed can be re-sent safely without duplicating delivered messages.

---

## Phase 6: User Story 4 — Registro de intentos y auditoría (Priority: P2)

**Goal**: Each message keeps a record of every attempt (time, status, reason), and history reflects delivered/pending/failed faithfully; resumable after app restart.

**Independent Test**: After a mixed send, open history and verify each result keeps its final state and attempt list; close mid-send and reopen to verify delivered are not duplicated and pending are re-sendable.

### Implementation for User Story 4

- [ ] T028 [US4] Modificar `src/services/history_store.py` — persist `message_id`, `delivered_at`, `attempts`, and ternary status in session JSON; add backward-compat loader that maps legacy `"sent"` → `delivered`
- [ ] T029 [US4] Modificar `src/ui/history_view.py` — show delivered/pending/failed counts per session in the list label and detail summary
- [ ] T030 [US4] Modificar `src/models/send_history.py` — expose `delivered_count`/`pending_count`/`failed_count` used by history view and main window summary

**Checkpoint**: User Story 4 functional — audit trail and resume-without-duplication are in place.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: User-facing error messages, documentation, and packaging updates

- [ ] T031 [P] Translate new error/state messages to Spanish across `src/services/*` and `src/ui/*` ("entregado", "pendiente", "fallido", "reintentos agotados", "WhatsApp está limitando los envíos, pausando...")
- [ ] T032 [P] Update `specs/003-reliable-message-delivery/quickstart.md` if any defaults changed during implementation
- [ ] T033 Update build/packaging references if `src/services/send_queue.py`, `rate_limiter.py`, `circuit_breaker.py`, `delivery_tracker.py` affect PyInstaller (no change expected — pure Python modules auto-included)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational + US1 (uses `send_message` returning `accepted`/`message_id`, `DeliveryTracker`)
- **User Story 3 (Phase 5)**: Depends on US1 + US2 (re-queue through same worker)
- **User Story 4 (Phase 6)**: Depends on US1 (uses final status/attempts)
- **Polish (Phase 7)**: Depends on all user stories

### User Story Dependencies

- **User Story 1 (P1)**: Start after Foundational — no dependencies on other stories
- **User Story 2 (P1)**: Start after Foundational + US1 (needs `accepted`+`message_id` and `DeliveryTracker`)
- **User Story 3 (P2)**: Start after US1 + US2
- **User Story 4 (P2)**: Start after US1

### Within Each User Story

- Models before services; services before UI; core before integration

### Parallel Opportunities

- Foundational: T002–T011 are mostly independent files — can run in parallel
- US1: T017/T018 (tests) can run in parallel with T012–T016
- US2: T022/T023/T024 (tests) can run in parallel
- US1 and US2 both P1 — after Foundational, US1 first (US2 depends on it)

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 2: Foundational (T002–T011)
2. Complete Phase 3: US1 (T012–T018) — truthful status
3. Complete Phase 4: US2 (T019–T024) — async + anti-saturation
4. **STOP and VALIDATE**: send 60 messages, verify no false "entregado", UI responsive, no rapid retries

### Incremental Delivery

1. Foundational → 2. US1 (truthful status, MVP fix) → 3. US2 (robust async) → 4. US3 (re-send pending) → 5. US4 (audit) → 6. Polish

---

## Notes

- The bridge receipt map is in-memory (volatile); persistent truth lives in client JSON history — see contracts/whatsapp-bridge-contract.md
- "At-least-once" delivery is bounded by `max_retries` and per-message deadline; not a 100% guarantee if the destination is unavailable
- `message_id` is the deduplication key for resume/re-send
- Commit after each task or logical group; stop at any checkpoint to validate independently
