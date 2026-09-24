# Hallazgos del diagnóstico

**Fecha**: 2026-09-24
**Prueba**: Un único envío controlado a `629071739`

## Evidencia

- `POST /send` respondió HTTP 200.
- `message_id`: `3EB0A3AC5157D955424A83`.
- JID destino: `34629071739@s.whatsapp.net`.
- `fromMe`: `true`.
- `GET /message/{id}` se ejecutó periódicamente cada 2 segundos.
- Todas las respuestas fueron:

```json
{
  "status": "sending",
  "server_ack": false,
  "delivery_ack": false
}
```

- El tracker agotó los 45 segundos y clasificó el mensaje como `pending`.
- En el log del bridge **no apareció ningún** evento `messages.update` para ese `message_id`.
- En el log del bridge **no apareció ningún** evento `message-receipt.update` para ese `message_id`.

## Conclusión provisional

Para este envío concreto, el problema no está en:

- el `DeliveryTracker`;
- las consultas Python al bridge;
- el mapeo de estados Python;
- el refresco de la tabla.

El bridge no recibió ningún acuse de Baileys para ese mensaje. El resultado correcto, con la evidencia disponible, es `sin confirmación`/`pending`; no se debe marcar como `delivered` por inferencia.

## Segunda prueba controlada

Se realizó una segunda prueba autorizada a `629335570`.

- `message_id`: `3EB0570D44A6879C70F433`.
- JID destino: `34629335570@s.whatsapp.net`.
- `fromMe`: `true`, como es normal para cualquier mensaje saliente desde la cuenta conectada.
- No apareció ningún evento `messages.update` para ese `message_id`.
- No apareció ningún evento `message-receipt.update`.
- Todas las respuestas de `GET /message/{id}` fueron `sending`, con `server_ack:false` y `delivery_ack:false`.
- El tracker volvió a agotar los 45 segundos y clasificó el mensaje como `pending`.

## Conclusión actual

El comportamiento se reproduce con dos destinos distintos. Por tanto, no es un caso especial de enviar el mensaje al propio número ni un problema de actualización de la tabla.

La cadena observada es:

```text
sock.sendMessage() → accepted/message_id → ningún acuse Baileys → sending → timeout → pending
```

La aplicación está siendo conservadora correctamente: no marca `delivered` sin acuse. El problema pendiente está en la sesión/flujo de Baileys o en la disponibilidad de acuses del servidor de WhatsApp para estos mensajes salientes.

No se aplicará un workaround que convierta `accepted` en `delivered`, porque reproduciría exactamente el falso positivo original.

## Siguiente investigación técnica

Antes de tocar la UI o el tracker hay que comprobar:

1. El estado de conexión de Baileys realmente permanece `open` durante el envío.
2. Los logs internos de Baileys durante `sock.sendMessage()` y después del envío.
3. Si el mensaje aparece en el dispositivo receptor y si WhatsApp muestra reloj, un tick o dos ticks.
4. Si la sesión enlazada, el número emisor o la versión de WhatsApp permiten recibir acuses de mensajes salientes mediante Baileys.
5. Si hace falta activar/configurar otro mecanismo oficial de receipts o aceptar explícitamente un estado `accepted_without_receipt`.

No se hará otra prueba real hasta decidir cuál de estas hipótesis se puede verificar sin cambiar la semántica de entrega.

## Observación del dispositivo receptor

El usuario confirmó que el segundo mensaje aparece en el teléfono receptor con **dos ticks grises**: entregado, pero no leído.

Esto demuestra que:

- WhatsApp sí entregó el mensaje.
- `sock.sendMessage()` fue aceptado y el flujo de entrega funcionó en WhatsApp.
- La aplicación no recibió ningún evento de acuse de Baileys para poder conocer ese estado.

## Conclusión técnica

El problema ya no es un falso diagnóstico de la UI: existe una pérdida de evidencia entre el servidor/cliente de WhatsApp y los eventos expuestos por Baileys. El sistema actual solo puede afirmar `accepted`/`sending` y no puede deducir legítimamente `delivered` a partir de esos datos.

La solución debe separar explícitamente:

- `accepted`: Baileys aceptó/encoló el mensaje y devolvió `message_id`.
- `delivered_confirmed`: existe un acuse técnico verificable.
- `accepted_without_receipt`: el mensaje fue aceptado, pero Baileys no proporciona acuse observable.

No se debe convertir automáticamente `accepted_without_receipt` en `delivered`, aunque el usuario pueda comprobar visualmente dos ticks grises en el receptor.

## Instrumentación activa

- Bridge: `receipt-diagnostics.jsonl` en el directorio `bridge-auth`.
- Cliente/tracker: logs `Delivery status ...` y `Tracker poll ...` en `notifier.log`.

La instrumentación es temporal y deberá retirarse o convertirse en logging controlado tras cerrar el diagnóstico.
