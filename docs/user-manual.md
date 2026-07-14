# Manual de Usuario: Sistema de Notificaciones de Citas de WhatsApp

Bienvenido al manual de usuario del **Notificador de Citas de WhatsApp**. Este sistema está diseñado para ayudar a las clínicas a automatizar el envío de recordatorios de citas pendientes y mantener una comunicación fluida y segura con los pacientes mediante inteligencia artificial bajo estrictos parámetros éticos y de seguridad médica.

---

## 📅 1. Introducción al Sistema

El sistema consta de dos módulos principales que automatizan la interacción con los pacientes:
1. **Motor de Envíos Masivos (Citas)**: Permite subir un listado de citas (Excel o CSV) y envía una plantilla personalizada de WhatsApp a cada paciente programando retrasos inteligentes para evitar bloqueos.
2. **Asistente Virtual (Bot Inteligente)**: Responde a las dudas cotidianas de los pacientes sobre su cita (fecha, hora, dirección de la clínica o confirmaciones) y cuenta con **doble capa de memoria** y **guardarraíles de seguridad médica de 4 capas**. Si el paciente pregunta por síntomas o tratamientos, el bot se auto-bloquea y transfiere el caso a humanos.

---

## 🚀 2. Conexión Inicial de WhatsApp (QR Code)

Para que el sistema pueda enviar mensajes en tu nombre, debes conectar tu cuenta de WhatsApp (teléfono de la clínica).

1. Abre tu terminal en el servidor o computadora donde está instalado el sistema.
2. Ejecuta el script de conexión:
   ```bash
   ./scripts/setup-evolution.sh
   ```
3. El sistema devolverá un código de vinculación o un panel con un **Código QR**.
4. En tu teléfono móvil de la clínica:
   - Abre **WhatsApp**.
   - Presiona **Configuración / Ajustes** (icono de engranaje o tres puntos).
   - Selecciona **Dispositivos Vinculados**.
   - Presiona **Vincular un dispositivo** y escanea el código QR que se visualiza en la terminal o interfaz.
5. Una vez terminada la lectura, el estado cambiará a `"open"` (Conectado). ¡Ya puedes enviar mensajes!

---

## 📥 3. Subida de Archivo de Citas (Operación Diaria)

El personal administrativo puede subir las citas del día ó de la semana en un único archivo.

### 📋 Requisitos del Archivo (Excel o CSV)
El archivo debe contener exactamente las siguientes columnas en la primera fila (los nombres de columna no distinguen mayúsculas de minúsculas):

| Nombre de Columna | Formato Exigido | Ejemplo | Descripción |
|-------------------|---|---|---|
| `patient_name` | Texto libre, máx 100 caracteres | `Juan García Pérez` | Nombre completo del paciente |
| `patient_phone` | Con el signo `+` y el código de país | `+34612345678` | Número completo de WhatsApp |
| `appointment_date` | Fecha en formato `AAAA-MM-DD` | `2026-07-20` | Día de la cita médica |
| `appointment_time` | Hora en formato `HH:MM` en 24hs | `14:30` | Hora de la consulta |
| `appointment_type` | Texto libre | `Consulta general` | Motivo de la cita/tratamiento |

*Ejemplo de filas en un CSV:*
```csv
patient_name,patient_phone,appointment_date,appointment_time,appointment_type
María López Fernández,+34698765432,2026-07-20,15:00,Limpieza dental
Carlos Ruiz Gómez,+34655554321,2026-07-21,10:00,Revisión ortodoncia
```

> ⚠️ **IMPORTANTE**: No omitas el prefijo internacional (ej. `+34` para España, `+52` para México). Si no pones el `+` y el código del país, el sistema puede rechazar el registro o mandar el mensaje a un destino erróneo.

### 📤 Cómo subir el archivo
Una vez tengas listo tu archivo Excel (`citas.xlsx`) o CSV (`citas.csv`), puedes enviarlo a n8n usando la interfaz web proveída o mediante un simple comando web en tu red local:

```bash
curl -X POST \
  -H "X-API-Key: tu-n8n-api-key" \
  -F "file=@citas.csv" \
  http://localhost:5678/webhook/upload-appointments
```

El sistema responderá de inmediato dándote un **ID de Lote (Batch ID)** que sirve para revisar el estado del envío:
```json
{
  "batchId": "550e8400-e29b-41d4-a716-446655440000",
  "totalRecords": 50,
  "validRecords": 48,
  "invalidRecords": 2,
  "status": "processing",
  "message": "File received and validated. Sending 48 notifications."
}
```

---

## 📊 4. Seguimiento de Envíos y Errores

Puedes consultar en tiempo real cómo progresan los envíos usando el ID de lote que te entregó el sistema al realizar la subida:

```bash
curl -H "X-API-Key: tu-n8n-api-key" \
  http://localhost:5678/webhook/notification-results/550e8400-e29b-41d4-a716-446655440000
```

### Respuesta del Estado:
El sistema responderá indicando qué mensajes ya salieron y cuáles fallaron con el motivo exacto del fallo (ej: teléfono mal formateado):

```json
{
  "batchId": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "summary": {
    "totalAppointments": 50,
    "sent": 48,
    "failed": 2,
    "pending": 0
  },
  "failedRecords": [
    {
      "patientName": "Ana Martínez",
      "phoneNumber": "644441234",
      "errorReason": "patient_phone: Invalid format. Expected + prefix",
      "retryCount": 0
    }
  ]
}
```

---

## 🤖 5. Comportamiento del Asistente Virtual (Bot)

El asistente virtual asume la carga de responder a las preguntas frecuentes tras enviarse las notificaciones. Se activa/desactiva mediante el archivo de configuración `config/bot-config.json` editando `"enabled": true`.

### 🛡️ Guardarraíles Médicos Estrictos
Debido al ambiente clínico de salud, el bot tiene reglas draconianas programadas en múltiples capas independientes de código:

1. **Temas Permitidos**: El bot **solo** responderá a:
   - Consultas de hora, día o tipo de cita actual.
   - Confirmaciones de asistencia (ej. "Confirmo mi cita").
   - Preguntas sobre la ubicación física u horarios de la clínica.
2. **Bloqueo y Desvío Automático**: Si el paciente pregunta algo fuera de cobertura, como:
   - *"Tengo dolor en una muela, ¿qué tomo?"* (Medicamentos o síntomas)
   - *"¿Cuánto cuesta ponerme un implante?"* (Precios o cotizaciones)
   - *"Por favor, pásame a la tarde"* (Cambio de turnos)
   
   El bot responderá de forma estandarizada y **no intentará diagnosticar**:
   > *"Lo siento, no puedo ayudar con esa consulta de salud. Un miembro del personal de la clínica se pondrá en contacto con usted pronto."*
   
   Y automáticamente enviará una alerta en la base de datos de administración para que un miembro del personal de administración le atienda manualmente.

---

## 🧠 6. Niveles de Memoria de Conversación

Para asegurar una experiencia natural, el bot opera con dos niveles organizados de memoria, asegurando que el paciente no deba repetirse continuamente:

### 💡 Nivel 1: Memoria Contextual de la Cita (Corto Plazo)
Mantiene un registro de los últimos **10 mensajes** correspondientes al tratamiento agendado.
- *Ejemplo de interacción:*
  > **Paciente**: "¿Cuándo tengo mi cita?"
  > **Bot**: "Tiene una cita el 2026-07-20 a las 14:30 para Limpieza dental."
  > **Paciente**: "¿Y dónde es eso?"
  > **Bot**: "Nuestra clínica se encuentra en Calle Principal 123." *(El bot sabe que el paciente se refiere a la ubicación para esa cita específica)*

### 🔍 Nivel 2: Memoria de Perfil de Paciente (Largo Plazo)
Conserva un registro global de los pacientes que asisten regularmente, guardando sus preferencias de comunicación e historial resumido.
- *Ejemplo de interacción:*
  > **Paciente**: "Hola, tengo mi recordatorio"
  > **Bot**: "Hola de nuevo, Juan. Sí, le recordamos su cita el 2026-07-20 a las 14:30. Como en ocasiones anteriores, hemos anotado su preferencia por recibir la información en la mañana."

---

## 🛠️ 7. FAQ - Preguntas Frecuentes

### ¿Qué pasa si el sistema falla a mitad de un lote?
El sistema n8n cuenta con almacenamiento transaccional en PostgreSQL. Si se interrumpe la ejecución, el lote se conserva en estado `pending` y los registros se reanudarán o reportarán de manera transparente sin crear duplicados.

### ¿Cómo cambio las plantillas de los mensajes que se envían?
No requiere cambios internos de programación. Simplemente edita el archivo de texto plano localizado en `config/notification-templates/appointment-reminder.txt` y personaliza el saludo o el cuerpo del mensaje. Las variables se actualizan al vuelo en la próxima subida.

### ¿A qué horas contesta el Bot?
El bot solo contesta dentro de las horas especificadas en `config/bot-config.json`. Si un paciente responde fuera de horas comerciales (ej. 11:00 PM), el sistema detecta que el canal está cerrado y le responde un mensaje configurable de cortesía:
> *"Gracias por su mensaje. Nuestro horario de atención es de 09:00 a 18:00. Le responderemos en el próximo horario de consulta."*

Esto retiene al paciente y detiene la conversación evitando que la IA responda por la noche, dejando el mensaje listo para el chequeo del personal el día siguiente.
