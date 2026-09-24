# Contract: Baileys Bridge — Envío Robusto y Acuse de Entrega

**Date**: 2026-07-14
**Feature**: 003-reliable-message-delivery

## Overview

Este contrato **extiende** el bridge existente (`bridge/whatsapp-bridge.js`, ver `specs/002-whatsapp-desktop-utility/contracts/whatsapp-bridge-contract.md`) para dar confirmación real de entrega. El cambio fundamental: `POST /send` deja de significar "entregado" y pasa a significar "aceptado en cola"; el estado real se obtiene correlacionando el `message_id` con los acuses de Baileys (`messages.update`).

## Cambios respecto al contrato de 002

| Aspecto | Antes (002) | Ahora (003) |
|---------|-------------|-------------|
| Semántica de `POST /send` 200 | "enviado" (`success: true`) | "aceptado en cola" (`accepted: true` + `message_id`) |
| Estado real del mensaje | No disponible | `GET /message/{id}` |
| Acuses de Baileys | No escuchados | Escuchados (`messages.update`) y almacenados en memoria |
| Estados del mensaje | binario | `sending` / `delivered` / `pending` / `failed` |

---

## Endpoints (nuevos / modificados)

### 1. Enviar mensaje (MODIFICADO) — `POST /send`

**Request Body** (sin cambios):
```json
{ "number": "+34612345678", "text": "Hola Juan, ..." }
```

**Response** (200 OK, semántica nueva):
```json
{
  "accepted": true,
  "message_id": "3EB0XXXXXXX",
  "status": "sending",
  "timestamp": 1720886400
}
```

> `accepted: true` significa que el mensaje fue **encolado** por Baileys. NO significa entregado. El campo `success` se elimina o se mantiene como alias obsoleto de `accepted`.

**Error Responses** (sin cambios): `400` inválido, `409` no conectado, `500` error Baileys.

---

### 2. Consultar estado de un mensaje (NUEVO) — `GET /message/{id}`

Devuelve el estado real de un `message_id` según los acuses recibidos.

```
GET /message/3EB0XXXXXXX
```

**Response** (200 OK):
```json
{
  "message_id": "3EB0XXXXXXX",
  "status": "delivered",     // sending | delivered | pending | failed
  "server_ack": true,
  "delivery_ack": true,
  "updated_at": 1720886405
}
```

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `status` | string | Estado agregado del mensaje |
| `server_ack` | bool | El servidor de WhatsApp lo recibió |
| `delivery_ack` | bool | Entregado en el dispositivo destino |
| `updated_at` | int | Timestamp del último acuse |

**Estados agregados**:
| `status` | Significado | Acuse Baileys subyacente |
|----------|-------------|--------------------------|
| `sending` | encolado, sin acuse de servidor | `PENDING` |
| `pending` | servidor lo recibió, aún no entregado | `SERVER_ACK` |
| `delivered` | entregado | `DELIVERY_ACK` (o `READ`) |
| `failed` | error de envío | `ERROR` |

**Error Responses**: `404` si el `message_id` no está registrado; `409` si el bridge no está conectado.

---

## Registro interno de acuses (nuevo en el bridge)

El bridge mantiene en memoria un mapa `message_id → { status, server_ack, delivery_ack, updated_at }` alimentado por:

```javascript
sock.ev.on('messages.update', (updates) => {
    for (const { key, status, update } of updates) {
        if (!key || !key.id) continue;
        receiptMap[key.id] = {
            status,
            server_ack: receiptMap[key.id]?.server_ack || status === 'SERVER_ACK',
            delivery_ack: receiptMap[key.id]?.delivery_ack || status === 'DELIVERY_ACK' || status === 'READ',
            updated_at: Math.floor(Date.now() / 1000),
        };
    }
});
```

> **Limitación conocida**: el mapa es en memoria y se pierde al reiniciar el bridge. Los mensajes encolados cuyo acuse aún no llegó y el bridge se reinicia quedarán sin resolver en el cliente (se tratarán como `pending` y reenviables por `message_id`). La persistencia definitiva del estado vive en el cliente (historial JSON), no en el bridge.

---

## Flujo de envío (cliente → bridge → WhatsApp → acuse)

```
Cliente Python                     Bridge (Node/Baileys)                WhatsApp
     │                                    │                               │
     │  POST /send {number,text}          │                               │
     ├───────────────────────────────────►│  sock.sendMessage()  (encola) │
     │                                    ├──────────────────────────────►│
     │  ← 200 {accepted, message_id,      │                               │
     │         status:"sending"}          │                               │
     │                                    │   ...acuse llega después...   │
     │  GET /message/{id}  (poll)         │                               │
     ├───────────────────────────────────►│  ← messages.update DELIVERY_ACK
     │  ← {status:"delivered"}            │                               │
     │                                    │                               │
```

El cliente **no espera el acuse en la misma petición**: encola, sigue con el siguiente mensaje (respetando el intervalo mínimo), y un verificador en segundo plano consulta `GET /message/{id}` hasta `delivered`, `failed` o deadline.

---

## Referencia

- Eventos Baileys: [Events - Baileys](https://baileys.wiki/concepts/events)
- Ejemplo oficial de correlación envío→acuse: [WhiskeySockets/Baileys PR #2428](https://github.com/WhiskeySockets/Baileys/pull/2428)
