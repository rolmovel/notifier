# Quickstart: Envío Robusto y Confirmación de Entrega

**Date**: 2026-07-14
**Feature**: 003-reliable-message-delivery

## Qué cambia para el usuario

Antes, al terminar un envío todo aparecía "✅ Enviado" aunque el teléfono del paciente siguiera mostrando "Enviando...". Ahora la aplicación distingue **tres estados reales**:

| Estado | Qué significa | Icono en la tabla |
|--------|---------------|-------------------|
| **Entregado** | WhatsApp confirmó la entrega en el destino | ✅ Entregado |
| **Pendiente** | aceptado pero aún no confirmado (reloj/"Enviando...") | ⏳ Pendiente |
| **Fallido** | no se pudo entregar (con motivo) | ❌ Fallido |

Además, el envío es **asíncrono y regulado**: la aplicación encola los mensajes y los despacha de uno en uno con un ritmo controlado, reintenta los fallos transitorios con esperas crecientes, y se **pausa sola** ante un aviso de WhatsApp (rate limit) en lugar de machacar con reintentos.

## Verificación manual del nuevo comportamiento

1. **Conecta WhatsApp** (QR o código de emparejamiento), como hasta ahora.
2. **Carga el Excel** de citas y pulsa "Enviar Recordatorios".
3. **Observa la tabla de resultados en vivo**: cada fila pasa por "⏳ Pendiente" y se convierte en "✅ Entregado" cuando llega el acuse, o "❌ Fallido" con motivo.
4. **Reintento de pendientes**: al final, los que queden "⏳ Pendiente" o "❌ Fallido" se pueden reenviar con un botón dedicado, sin tocar los ya entregados.

> **⚠️ Números de prueba permitidos**: si se realizan envíos reales durante las pruebas, **solo** usar los teléfonos **629071739** y **629335570**. Nunca enviar mensajes reales a otros destinos.

## Verificación técnica del acuse de entrega

### Consultar estado de un mensaje (bridge)

```bash
# Enviar un mensaje
curl -X POST http://127.0.0.1:3001/send \
  -H "Content-Type: application/json" \
  -d '{"number": "+34612345678", "text": "Prueba de entrega"}'
# → {"accepted": true, "message_id": "3EB0...", "status": "sending"}

# Consultar su estado real (usar el message_id devuelto)
curl http://127.0.0.1:3001/message/3EB0...
# → {"message_id":"3EB0...", "status":"delivered", "server_ack":true, "delivery_ack":true}
```

> `accepted: true` ya NO significa "entregado". El estado real es el que devuelve `GET /message/{id}`.

## Parámetros de robustez (Settings)

Todos configurables; valores por defecto conservadores:

| Parámetro | Default | Qué controla |
|-----------|---------|--------------|
| Intervalo entre envíos | 1500 ms | espaciado mínimo entre mensajes |
| Máx. reintentos | 3 | reintentos por mensaje |
| Base de backoff | 5000 ms | espera inicial de reintento (crece exponencialmente) |
| Plazo de entrega | 45 s | tiempo para recibir el acuse antes de marcarlo pendiente/fallido |
| Umbral del circuit breaker | 3 errores | errores seguidos antes de pausar todo |
| Enfriamiento | 60 s | pausa global tras abrir el circuito |

## Prueba de regresión rápida

1. Enviar un lote de 60 mensajes y confirmar que la interfaz no se congela durante el proceso.
2. Inyectar un `429` en el bridge (o desconectar la red un instante) y confirmar que el envío se pausa y reanuda, sin ráfaga de reintentos.
3. Cerrar la app a mitad de envío y reabrir: los entregados no se duplican y los pendientes aparecen como reenviables.

## Referencias

- [spec.md](./spec.md) — historias y requisitos
- [research.md](./research.md) — decisiones técnicas (acuse de Baileys, backoff, circuit breaker)
- [data-model.md](./data-model.md) — modelos ampliados
- [contracts/whatsapp-bridge-contract.md](./contracts/whatsapp-bridge-contract.md) — endpoints nuevos del bridge
