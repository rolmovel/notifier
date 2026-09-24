# Feature Specification: Envío Robusto y Confirmación de Entrega de Mensajes WhatsApp

**Feature Branch**: `003-reliable-message-delivery`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "El envío de mensajes de WhatsApp con ficheros no muy grandes (unos 60 registros) tiene comportamientos raros: algunos mensajes no se envían y otros sí, y sin embargo todos aparecen como enviados. En particular parece que en WhatsApp aparece el mensaje con 'Enviando...' o similar pero no termina de hacerlo. Añadir un sistema más robusto de envío que no sature WhatsApp con reintentos y, en la medida de lo posible, garantice la entrega. Probablemente tenga que ser algo asíncrono."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Estado de envío real y veraz (Priority: P1)

Un administrativo lanza un envío de recordatorios y necesita que la aplicación le diga la VERDAD sobre cada mensaje: cuáles llegaron realmente, cuáles están aún pendientes (reloj / "Enviando...") y cuáles fallaron. Hoy todos aparecen como "enviado" aunque el teléfono siga mostrando "Enviando..." sin llegar a entregarse.

**Why this priority**: Es el núcleo del bug reportado. La confianza en el informe de resultados es la razón de ser de la herramienta: si el informe miente, el administrativo no puede saber a qué pacientes hay que re-enviar, reenviar por otro medio o avisar por teléfono. Sin esto, cualquier otra mejora es irrelevante.

**Independent Test**: Enviar un lote de prueba a números de prueba (incluyendo al menos un número inválido o destino sin entregar), y verificar que: (a) los mensajes realmente entregados aparecen como "entregado", (b) los que quedan colgados en "Enviando..." aparecen como "pendiente" y no como "enviado", y (c) los que fallan aparecen como "fallido" con motivo.

**Acceptance Scenarios**:

1. **Given** se envía un recordatorio a un número válido, **When** WhatsApp confirma la entrega del mensaje, **Then** la aplicación muestra ese registro como "entregado" con la hora real de entrega.
2. **Given** se envía un recordatorio y WhatsApp lo deja en estado "pending" (reloj / "Enviando..."), **When** se consulta el estado, **Then** la aplicación muestra ese registro como "pendiente", NUNCA como "enviado".
3. **Given** algunos mensajes quedan pendientes tras un tiempo límite, **When** finaliza el proceso de envío, **Then** el informe agrupa y muestra claramente entregados / pendientes / fallidos, y el administrativo puede reenviar los pendientes.
4. **Given** un mensaje falla definitivamente (número inexistente, sin conexión), **When** se produce el fallo, **Then** la aplicación muestra "fallido" con el motivo exacto, sin retintarlo indefinidamente.

---

### User Story 2 - Envío asíncrono con cola y sin saturar WhatsApp (Priority: P1)

El administrativo lanza los 60 recordatorios de golpe y la aplicación los **encola** y los va despachando en segundo plano con un ritmo controlado, sin bloquear la interfaz. La aplicación se protege a sí misma y a la cuenta de WhatsApp: nunca dispara todos los mensajes a la vez, espacia los envíos, y ante un pico de errores o una llamada de atención de WhatsApp (rate limit) **se detiene globalmente y espera** en lugar de reintentar agresivamente mensaje a mensaje. El reintento es suave: esperas crecientes con jitter y un tope de reintentos y de tiempo total por mensaje.

**Why this priority**: Es la pieza que hace el sistema "robusto" y evita que el propio fix anti-pérdida de mensajes provoque el efecto contrario: convertir la cuenta en spam y que WhatsApp la bloquee. Sin un envío ordenado, asíncrono y con rate limiting, la garantía de entrega (US1) es inviable y peligrosa.

**Independent Test**: Lanzar un lote de 60 mensajes y verificar que: (a) la interfaz responde durante todo el proceso, (b) ningún intervalo entre envíos baja de un mínimo configurado, (c) al inyectar un error 429 del servidor, el envío global se pausa y reanuda con retraso creciente sin machacar, y (d) cada mensaje reintenta como máximo el número de veces configurado.

**Acceptance Scenarios**:

1. **Given** un lote de 60 recordatorios, **When** se pulsa "Enviar", **Then** los mensajes se encolan y se despachan de uno en uno en segundo plano, con un intervalo mínimo entre envíos, y la interfaz sigue respondiendo.
2. **Given** el servidor devuelve un error transitorio (rate limit 429 o indisponibilidad), **When** se produce, **Then** la aplicación espera un tiempo creciente (backoff exponencial con una variación aleatoria) antes de reintentar, y en ningún caso reintenta el mismo mensaje de forma inmediata o en ráfaga.
3. **Given** se acumulan errores transitorios de forma masiva, **When** se supera un umbral de errores consecutivos, **Then** la aplicación detiene temporalmente TODOS los envíos (pausa global), espera un período de enfriamiento y reanuda progresivamente, en lugar de reintentar cada mensaje en paralelo.
4. **Given** un mensaje concreto falla repetidamente, **When** se alcanza el máximo de reintentos configurado o el tiempo total límite, **Then** se marca como "fallido" definitivo y deja de consumir reenvíos.
5. **Given** la aplicación se cierra con mensajes aún en cola, **When** se reabre, **Then** los mensajes no despachados se pueden reanudar de forma controlada (sin duplicar los ya entregados).

---

### User Story 3 - Reintento de mensajes pendientes (Priority: P2)

Cuando un mensaje queda "pendiente" (el servidor lo aceptó en cola pero no llegó a entregarse), el administrativo debe poder reintentar su envío de forma segura, sin duplicar los que ya se entregaron y sin re-procesar todo el fichero.

**Why this priority**: Una vez que el informe es veraz (US1) y el envío es controlado (US2), la acción natural del usuario es "reenviar lo que faltó". Sin reintento seguro, el administrativo tendría que volver a lanzar el lote completo arriesgándose a duplicar los ya entregados.

**Independent Test**: Con un lote donde algunos mensajes quedaron "pendientes", pulsar "Reintentar pendientes" y verificar que solo se reenvían los pendientes y fallidos, y que los ya entregados no se tocan.

**Acceptance Scenarios**:

1. **Given** un informe muestra mensajes pendientes o fallidos, **When** el administrativo pulsa "Reintentar pendientes", **Then** se reenvían únicamente esos registros, no los ya entregados.
2. **Given** un reintento vuelve a quedar pendiente, **When** se agota un límite de reintentos configurable, **Then** el registro se marca como "fallido" con una nota de reintentos agotados.
3. **Given** el administrativo reintenta los pendientes, **When** el reintento se encola, **Then** respeta las mismas reglas de espaciado y backoff que el envío inicial (no reintenta en ráfaga).

---

### User Story 4 - Registro de intentos y auditoría (Priority: P2)

Para cada mensaje debe quedar constancia de lo que ocurrió en cada intento (hora, estado, motivo), de modo que el histórico refleje fielmente qué se envió, qué se entregó, qué se reintentó y qué falló.

**Why this priority**: Aporta trazabilidad y evita repetir diagnósticos manuales, pero no bloquea la resolución del bug (US1) ni la corrección operativa (US2).

**Independent Test**: Tras un envío con entregados, pendientes y fallidos, abrir el historial y verificar que cada registro conserva su estado final y los intentos realizados correctamente.

**Acceptance Scenarios**:

1. **Given** un mensaje pasó por varios intentos, **When** se consulta el detalle en el historial, **Then** se ven todos los intentos con fecha/hora, estado y motivo.
2. **Given** la aplicación se cierra durante un envío, **When** se reabre, **Then** los registros con estado definitivo (entregado/fallido) se conservan y los pendientes se identifican como reenviables.

---

### Edge Cases

- ¿Qué ocurre si WhatsApp tarda en entregar más del tiempo límite configurado? El mensaje debe marcarse como "pendiente" (o "fallido" tras agotar reintentos), nunca como "enviado".
- ¿Qué ocurre si la conexión se corta justo después de encolar el mensaje pero antes de la confirmación? El mensaje debe quedar "pendiente" y ser verificable al reconectar.
- ¿Qué ocurre si el bridge no informa del estado de entrega (Baileys configurado sin acuses)? El sistema debe documentar esta limitación y, como mínimo, distinguir "enviado (en cola)" de "entregado (confirmado)", sin mentir.
- ¿Qué ocurre si un mensaje queda pendiente indefinidamente (nunca llega acuse ni error)? Debe existir un tiempo límite tras el cual se considera "fallido por timeout" y se permite reintento.
- ¿Qué ocurre con destinos que tienen activada la privacidad sin confirmación de lectura (no marca azul)? La confirmación de ENTREGA (doble tick azul) es distinta de la de LECTURA y debe distinguirse; nunca exigir lectura para considerar entregado.
- ¿Qué ocurre si el servidor devuelve un error transitorio justo en un mensaje concreto? Debe reintentarse con backoff, pero el resto de la cola no debe atascarse ni dispararse en ráfaga.
- ¿Qué ocurre si se acumulan muchos errores transitorios seguidos (posible bloqueo de la cuenta)? El envío global debe pausarse en frío y reanudarse con suavidad, no intensificar los reintentos.
- ¿Qué ocurre si la aplicación se cierra a mitad del envío con mensajes en cola o pendientes? Debe poder reanudarse de forma idempotente sin duplicar entregas ni reintentar sin control.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE distinguir al menos cuatro estados de un mensaje: **entregado**, **pendiente**, **aceptado sin acuse** y **fallido**. El estado "enviado" a secas NO es aceptable si no hay confirmación real de entrega.
- **FR-001A**: Cuando WhatsApp acepta el mensaje pero Baileys no proporciona un acuse verificable dentro del timeout, el sistema DEBE usar `accepted_without_receipt`, no `delivered`, y DEBE permitir confirmación manual explícita.
- **FR-001B**: Un mensaje `accepted_without_receipt` NO DEBE reintentarse automáticamente, porque el reintento puede duplicar un mensaje ya entregado.
- **FR-002**: El sistema NO DEBE marcar un mensaje como entregado basándose únicamente en que el bridge devolvió HTTP 200 tras encolarlo. La confirmación DEBE basarse en una señal de entrega del servidor de WhatsApp.
- **FR-003**: El bridge DEBE exponer un mecanismo para consultar el estado real de un mensaje a partir de su `message_id` (entrega / pendiente / fallido), y DEBE propagar los acuses de Baileys (`messages.update` con `status`) en lugar de responder `success: true` incondicionalmente.
- **FR-004**: El cliente DEBE esperar la confirmación de entrega con un tiempo límite configurable; si se agota, el mensaje se clasifica como pendiente o fallido por timeout, nunca como entregado.
- **FR-005**: El sistema DEBE permitir reintentar únicamente los mensajes pendientes y fallidos, sin volver a enviar los ya entregados.
- **FR-006**: El informe de resultados DEBE mostrar recuentos separados y veraces de entregados, pendientes y fallidos, y en la tabla de resultados el estado de cada registro.
- **FR-007**: El sistema DEBE registrar, por cada mensaje, los intentos realizados (timestamp, estado resultante y motivo), para auditabilidad.
- **FR-008**: El modelo de resultado DEBE incorporar los estados entregado/pendiente/fallido (hoy solo `sent`/`failed`) sin romper los datos ya guardados en el historial.
- **FR-009**: El envío DEBE ejecutarse de forma asíncrona en segundo plano, encolando los mensajes y despachándolos sin bloquear la interfaz de usuario.
- **FR-010**: El sistema DEBE despachar los mensajes de uno en uno con un intervalo mínimo configurable entre envíos, para no saturar a WhatsApp.
- **FR-011**: El sistema DEBE aplicar backoff exponencial con jitter (variación aleatoria) en los reintentos, con un número máximo de reintentos y un tiempo total límite por mensaje, ambos configurables.
- **FR-012**: El sistema DEBE disponer de una pausa global ("circuit breaker") que, ante un umbral de errores transitorios consecutivos o una señal de rate limit, detenga todos los envíos durante un período de enfriamiento y reanude progresivamente, en lugar de reintentar cada mensaje de forma individual y agresiva.
- **FR-013**: El sistema DEBE ofrecer "garantía de entrega en la medida de lo posible": verificar el acuse de entrega, reintentar los fallos transitorios de forma acotada y persistir el estado de cada mensaje para que un cierre o reinicio no pierda ni duplique envíos (semántica *at-least-once* dentro de los límites de reintento, con deduplicación por `message_id`).

### Key Entities *(include if feature involves data)*

- **Estado de Envío (SendStatus)**: Enum ampliado que incluye `delivered`, `pending` y `failed` (hoy solo `sent`/`failed`). Representa el estado verificado de un mensaje.
- **Acuse de Entrega (DeliveryReceipt)**: Señal proveniente de Baileys (`messages.update`) que indica si un `message_id` concreto fue entregado, está pendiente o falló. Es la única fuente de verdad de "entregado".
- **Resultado de Envío (SendResult)**: Se amplía con los nuevos estados, la hora de entrega real, el `message_id`, y la lista de intentos.
- **Intento de Envío (SendAttempt)**: Registro de un único intento de envío de un mensaje (timestamp, resultado, motivo), agrupado bajo su `SendResult`.
- **Cola de Envío (SendQueue)**: Cola de mensajes pendientes de despacho, consumida por un despachador único que respeta el intervalo mínimo entre envíos.
- **Regulador de Ritmo (RateLimiter / CircuitBreaker)**: Componente que garantiza el espaciado mínimo entre envíos y que abre el circuito ante errores transitorios masivos, pausando todo el envío de forma global.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los mensajes que WhatsApp deja en "Enviando..." se muestran como "pendiente" y no como "enviado" en el informe.
- **SC-002**: Menos de un 1% de registros quedan con estado incorrecto en un lote de 60 envíos (falsos "entregados" o falsos "fallidos").
- **SC-003**: Un mensaje realmente entregado aparece como "entregado" en menos de 5 segundos tras la confirmación del servidor.
- **SC-004**: El administrativo puede reenviar los mensajes pendientes de un lote de 60 registros en menos de 1 minuto sin duplicar los ya entregados.
- **SC-005**: El 100% de los mensajes que quedan atascados más allá del tiempo límite configurado terminan clasificados (pendiente o fallido por timeout), sin quedar en estado ambiguo.
- **SC-006**: Un lote de 60 mensajes se envía sin que ningún intervalo entre envíos sea inferior al mínimo configurado, y sin generar más reintentos por mensaje que el máximo configurado.
- **SC-007**: Ante un rate limit (429) o un aluvión de errores transitorios, el envío global se pausa y reanuda sin que se produzca una ráfaga de reintentos (ningún reintento inmediato tras el error).
- **SC-008**: La interfaz de usuario permanece usable (no se congela) durante el envío completo de un lote de 60 mensajes.
- **SC-009**: Tras cerrar y reabrir la aplicación a mitad de un envío, los mensajes entregados no se duplican y los no entregados se identifican como reenviables.

## Assumptions

- El bridge de Baileys es capaz de exponer los acuses de entrega mediante el evento `messages.update` con `status` (`PENDING`, `SERVER_ACK`, `DELIVERY_ACK`, `ERROR`, `READ`). Esto deberá verificarse en la fase de planificación; si Baileys no lo garantiza, la spec registra la limitación explícitamente y el FR-004 exige distinguir "aceptado en cola" de "entregado".
- La confirmación de ENTREGA (`DELIVERY_ACK`, doble tick) es suficiente para marcar "entregado"; NO se requiere confirmación de LECTURA (`READ`, marca azul), que muchos pacientes desactivan.
- El tiempo límite de confirmación será configurable con un valor por defecto razonable (por ejemplo 30–60 segundos) determinado en planificación.
- El alcance se limita al envío de texto 1-a-1 a través del bridge local existente; no cubre grupos, medios ni el flujo de n8n/Evolution API del feature 001.
- Los envíos ya registrados en el historial (con el modelo antiguo `sent/failed`) deben seguir siendo legibles sin romper la aplicación.
- **Valoración de asíncrono**: se adoptan dos niveles de asincronía — (1) envío en segundo plano con cola y despachador único (la UI nunca se bloquea), y (2) confirmación de entrega diferida (encolar, luego verificar acuse de cada `message_id` de forma no bloqueante). No se introduce un sistema distribuido ni un broker externo: para un lote de ~60 mensajes basta una cola en memoria con persistencia local del estado.
- **Garantía de entrega**: se persigue una semántica *at-least-once* (reintento hasta confirmar entrega o agotar el límite) con deduplicación por `message_id`, asumiendo que WhatsApp puede no entregar un mensaje por causas externas (destino sin conexión, bloqueo). La "garantía" queda acotada por esos límites; no se puede prometer entrega al 100% si el destino no está disponible.
- **No saturar WhatsApp**: el reintento es acotado (máx. reintentos y tiempo total por mensaje), con backoff exponencial + jitter y una pausa global ante rate limit/errores masivos. Esto se prioriza por encima de la velocidad de envío.
