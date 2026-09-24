# Plan de diagnóstico determinista del estado de entrega de WhatsApp

## Objetivo

Determinar con evidencia dónde se rompe la cadena:

```text
WhatsApp/Baileys → evento del bridge → receiptMap → GET /message/:id → WhatsAppClient → DeliveryTracker → SendResult → ResultsTable/UI
```

No se harán más cambios de comportamiento ni nuevos envíos hasta identificar el punto exacto del fallo.

## Restricciones

- No realizar envíos reales adicionales durante el diagnóstico inicial.
- Si finalmente hace falta un envío de validación, usar únicamente `629071739` o `629335570`.
- No marcar un mensaje como entregado por inferencia: solo por un acuse verificable.
- Conservar los estados y ficheros de historial actuales para poder comparar.

## Fase 1 — Congelar y documentar el estado actual

1. Confirmar el commit y el estado del working tree.
2. Registrar las versiones exactas de Baileys, Node.js, Python, httpx y PySide6.
3. Guardar copias de los archivos del bridge, cliente, tracker y worker, junto con el último historial afectado.
4. No modificar todavía la lógica de estados.

## Fase 2 — Instrumentar el bridge sin cambiar su comportamiento

Añadir únicamente logging estructurado y temporal en `bridge/whatsapp-bridge.js`:

1. En cada `POST /send`, registrar `message_id`, JID destino, timestamp y una respuesta resumida de `sock.sendMessage()`.
2. En `messages.update`, registrar de forma segura `key.id`, `key.remoteJid`, `key.fromMe`, las claves disponibles de `update`, `update.status` y su tipo JavaScript.
3. En `message-receipt.update`, registrar `key.id`, las claves de `receipt`, timestamps y usuario del acuse.
4. En `GET /message/:id`, registrar exactamente el JSON que se devuelve.
5. Separar los logs de diagnóstico del log general y no registrar el texto del mensaje.

**Resultado esperado:** saber si Baileys emite algún evento para el `message_id` y qué forma exacta tiene.

## Fase 3 — Validar el contrato del bridge de forma aislada

Antes de involucrar la GUI:

1. Arrancar únicamente el bridge.
2. Confirmar `/status` y `/connect`.
3. Consultar el estado de un `message_id` de una prueba existente, si permanece en memoria.
4. Comparar el evento crudo, la entrada de `receiptMap` y la respuesta de `GET /message/:id`.
5. Si `receiptMap` no cambia, el problema está en el listener/evento de Baileys.
6. Si `receiptMap` cambia pero `/message/:id` devuelve otra cosa, el problema está en la agregación del estado.

## Fase 4 — Instrumentar cliente Python y tracker

Añadir logging estructurado en:

1. `WhatsAppClient.send_message()`: JSON recibido de `POST /send` sin exponer el texto.
2. `WhatsAppClient.get_message_status()`: JSON recibido de `GET /message/:id` y estado mapeado a `SendStatus`.
3. `DeliveryTracker.track()`: cada transición y motivo de finalización (`delivered`, `failed` o timeout).
4. `SendWorker`: creación de la tarea tracker, tareas pendientes y finalización.
5. Asegurar que el log diferencia `sending`, `pending`, `delivered` y `failed`.

**Resultado esperado:** determinar si el bridge devuelve `sending`, si el cliente lo transforma mal o si la UI no aplica la actualización.

## Fase 5 — Pruebas controladas sin WhatsApp real

Crear pruebas automatizadas con respuestas simuladas del bridge:

1. `GET /message/:id` devuelve `delivered` → la tabla termina en Entregado.
2. Devuelve `pending` varias veces y luego `delivered` → la fila se actualiza.
3. Devuelve siempre `sending` → termina como Pendiente por timeout.
4. Devuelve `failed` → termina como Fallido.
5. `SendWorker` no cierra el event loop antes de ejecutar el tracker.
6. La UI actualiza la misma fila y no crea una fila duplicada.

Estas pruebas no realizan envíos reales.

## Fase 6 — Comprobar el contrato real de Baileys

Con los logs de la Fase 2, verificar contra Baileys 6.7.24:

1. Si el acuse de mensajes salientes llega por `messages.update`.
2. Si llega por `message-receipt.update`.
3. Si el estado está en `update.status`, `receipt`, `messageStubType` u otra propiedad.
4. Si los mensajes `fromMe` y los mensajes al propio número generan acuse.
5. Si el identificador del evento coincide exactamente con el `message_id` de `sendMessage()`.

No se implementará ningún mapeo adicional hasta capturar un ejemplo real.

## Fase 7 — Una única prueba real controlada

Solo después de completar las fases anteriores:

1. Enviar un único mensaje a uno de los dos teléfonos autorizados.
2. Capturar el `message_id`.
3. Guardar la secuencia temporal completa de eventos y respuestas.
4. Verificar el mensaje en el teléfono receptor.
5. Comparar la evidencia visual con el estado técnico recibido.

Si el mensaje aparece entregado pero WhatsApp no emite un acuse compatible, documentar explícitamente la limitación y separar:

- `accepted_by_server`.
- `delivered_confirmed`.
- `unknown_or_no_receipt`.

## Fase 8 — Aplicar un único arreglo basado en evidencia

Según el punto de fallo:

- Listener incorrecto → corregir solo el listener.
- Evento distinto → suscribirse al evento correcto.
- `message_id` no correlacionable → corregir la correlación.
- Respuesta correcta del bridge pero cliente incorrecto → corregir el mapeo Python.
- Tracker correcto pero UI incorrecta → corregir el upsert de la fila.
- Falta de acuse real → no inventar `delivered`; mostrar `accepted/pending` y documentar la limitación.

## Criterios de salida

El diagnóstico se considerará cerrado cuando exista una traza que permita afirmar una de estas dos cosas:

1. `message_id → evento de entrega → receiptMap → GET /message → tracker → UI Entregado`.
2. WhatsApp no proporciona un acuse de entrega fiable para ese caso, por lo que la aplicación debe mostrar explícitamente `sin confirmación`, nunca `entregado`.

Después del arreglo se repetirán las pruebas automatizadas y una única prueba real autorizada.
