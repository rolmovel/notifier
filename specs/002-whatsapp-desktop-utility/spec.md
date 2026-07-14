# Feature Specification: WhatsApp Desktop Utility

**Feature Branch**: `003-whatsapp-desktop-utility`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "Crear una aplicación de escritorio simplificada para enviar recordatorios de citas por WhatsApp sin depender de n8n ni bases de datos. La aplicación leerá un archivo Excel con las columnas: hora de inicio, duración, gabinete, nombre del paciente, tipo de cita, teléfono fijo y teléfono móvil. Enviará los mensajes usando una plantilla configurable y devolverá un listado con los resultados de los WhatsApp enviados y los fallidos."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cargar Excel y Enviar Recordatorios (Priority: P1)

Un administrativo de la clínica selecciona un archivo Excel con las citas del día, la aplicación lo procesa, valida los datos y envía recordatorios personalizados por WhatsApp a cada paciente. Al finalizar, la aplicación muestra un informe claro con los mensajes enviados correctamente y los que fallaron.

**Why this priority**: Es la funcionalidad principal que resuelve el problema del usuario. Sin esta historia no hay producto mínimo viable.

**Independent Test**: Se puede probar cargando un Excel con 5 citas válidas y verificando que la aplicación muestra un informe con 5 mensajes enviados correctamente (o los fallos correspondientes si algún número no es válido).

**Acceptance Scenarios**:

1. **Given** un administrativo tiene un archivo Excel con citas válidas, **When** selecciona el archivo y pulsa "Enviar recordatorios", **Then** la aplicación envía un WhatsApp a cada paciente con los detalles de su cita y muestra un informe con el número de mensajes enviados correctamente.
2. **Given** un archivo Excel contiene filas con datos inválidos (teléfono faltante, formato incorrecto), **When** se procesa el archivo, **Then** la aplicación informa de qué filas tienen errores y por qué, sin enviar mensajes a esos registros.
3. **Given** el proceso de envío ha finalizado, **When** el administrativo ve el informe de resultados, **Then** puede ver una tabla con: paciente, teléfono, fecha/hora de cita, estado del envío (enviado/fallido) y motivo del fallo si lo hubo.
4. **Given** el administrativo selecciona un archivo que no es Excel o está corrupto, **When** la aplicación intenta abrirlo, **Then** muestra un mensaje de error claro indicando que el formato no es válido.

---

### User Story 2 - Configurar Plantilla de Mensaje (Priority: P2)

El administrativo puede personalizar la plantilla del mensaje que se envía a los pacientes, usando variables como el nombre del paciente, fecha, hora, tipo de cita, etc. La plantilla se guarda para usarse en envíos posteriores.

**Why this priority**: Diferentes clínicas pueden querer mensajes con diferente redacción o idioma. Es un valor añadido importante pero el envío básico (P1) funciona sin personalización.

**Independent Test**: Se puede probar modificando la plantilla para incluir el nombre de la clínica y verificar que el mensaje enviado contiene ese texto personalizado.

**Acceptance Scenarios**:

1. **Given** el administrativo abre la configuración de plantilla, **When** modifica el texto de la plantilla usando las variables disponibles, **Then** los siguientes envíos usan la nueva plantilla.
2. **Given** la plantilla contiene una variable que no existe en los datos del Excel, **When** se envía un mensaje, **Then** la aplicación muestra una advertencia pero continúa con el envío omitiendo la variable no resuelta.

---

### User Story 3 - Consultar Historial de Envíos (Priority: P3)

El administrativo puede ver un historial de los envíos realizados anteriormente, almacenado localmente en la aplicación, para consultar resultados pasados.

**Why this priority**: Útil para auditoría y seguimiento, pero no esencial para el funcionamiento diario.

**Independent Test**: Realizar dos envíos con diferentes archivos Excel, cerrar la aplicación, volver a abrirla y verificar que ambos envíos aparecen en el historial.

**Acceptance Scenarios**:

1. **Given** la aplicación tiene envíos previos registrados, **When** el administrativo abre la sección de historial, **Then** puede ver una lista con la fecha de cada envío, número de citas procesadas, enviadas y fallidas.
2. **Given** el administrativo selecciona un envío del historial, **When** hace clic en "Ver detalles", **Then** puede ver el informe completo de ese envío (paciente, teléfono, estado).

---

### Edge Cases

- ¿Qué ocurre si el archivo Excel tiene columnas con nombres diferentes a los esperados? La aplicación debe detectar las columnas por nombre y mostrar un error si falta alguna columna obligatoria.
- ¿Cómo maneja la aplicación números de teléfono con prefijo internacional vs. nacional? Debe normalizar los números al formato E.164 antes de enviar.
- ¿Qué ocurre si no hay conexión a Internet o el bridge de WhatsApp no está disponible? La aplicación debe mostrar un error claro y no perder los datos cargados.
- ¿Qué ocurre si el archivo Excel está vacío (0 filas)? La aplicación debe informar que no hay citas para procesar.
- ¿Qué pasa si la aplicación se cierra durante el envío? Los mensajes ya enviados deben quedar registrados; el usuario debe poder reanudar identificando cuáles quedaron pendientes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La aplicación DEBE permitir seleccionar un archivo Excel (.xlsx) mediante un diálogo de selección de archivos.
- **FR-002**: La aplicación DEBE leer las siguientes columnas del Excel: hora de inicio, duración, gabinete, nombre del paciente, tipo de cita, teléfono fijo y teléfono móvil.
- **FR-003**: La aplicación DEBE dar prioridad al teléfono móvil sobre el fijo para el envío del WhatsApp. Si el móvil no está disponible, DEBE usar el fijo.
- **FR-004**: La aplicación DEBE normalizar los números de teléfono al formato E.164 (con prefijo internacional) antes de enviar.
- **FR-005**: La aplicación DEBE validar que los números de teléfono tengan un formato válido antes de intentar el envío.
- **FR-006**: La aplicación DEBE validar que la fecha y hora de la cita tengan un formato coherente.
- **FR-007**: La aplicación DEBE permitir configurar una plantilla de mensaje con variables: `{{patient_name}}`, `{{appointment_date}}`, `{{appointment_time}}`, `{{appointment_type}}`, `{{gabinete}}`.
- **FR-008**: La aplicación DEBE enviar los mensajes WhatsApp a través de un bridge local de Baileys (HTTP REST en localhost).
- **FR-009**: La aplicación DEBE mostrar un informe de resultados al finalizar el proceso, con: paciente, teléfono, fecha/hora, estado (enviado/fallido) y motivo del fallo.
- **FR-010**: La aplicación DEBE permitir exportar el informe de resultados a un archivo (CSV o Excel).
- **FR-011**: La aplicación DEBE almacenar localmente un historial de envíos realizados (sin usar base de datos externa).
- **FR-012**: La aplicación DEBE funcionar en Windows como mínimo, idealmente también en macOS y Linux.
- **FR-013**: La aplicación DEBE tener una interfaz gráfica de usuario (GUI) intuitiva.
- **FR-014**: La aplicación DEBE permitir configurar el puerto del bridge local y el prefijo de país por defecto.
- **FR-015**: La aplicación DEBE comprobar la conexión con WhatsApp (vía bridge local) antes de intentar enviar mensajes. En el primer arranque, DEBE mostrar un código QR para vincular el dispositivo.

### Key Entities *(include if feature involves data)*

- **Cita (Appointment)**: Representa una cita médica con los atributos: hora de inicio, duración, gabinete, nombre del paciente, tipo de cita, teléfono fijo, teléfono móvil. Es la unidad de datos de entrada.
- **Resultado de Envío (SendResult)**: Representa el resultado del envío de un WhatsApp para una cita. Atributos: datos de la cita, estado (enviado/fallido), timestamp del envío, mensaje de error (si falló).
- **Historial de Envío (SendHistory)**: Representa una sesión de envío completa. Atributos: fecha del envío, número total de citas, enviadas, fallidas, y la lista de resultados individuales.
- **Configuración (Settings)**: Preferencias de la aplicación: puerto del bridge, plantilla de mensaje, prefijo de país por defecto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un administrativo puede completar el proceso completo (cargar Excel, enviar mensajes, ver informe) en menos de 2 minutos para un archivo con 50 citas.
- **SC-002**: La aplicación procesa y envía 100 citas en menos de 5 minutos (dependiendo de la velocidad de la conexión a WhatsApp).
- **SC-003**: El 95% de los envíos con números de teléfono válidos se completan sin errores.
- **SC-004**: Un usuario nuevo puede realizar su primer envío exitoso sin necesidad de leer documentación externa.
- **SC-005**: La aplicación ocupa menos de 100 MB en disco (empaquetada).
- **SC-006**: Los informes de error son lo suficientemente claros para que el administrativo pueda corregir los datos y reenviar sin ayuda técnica.

## Assumptions

- El usuario tiene Node.js 18+ instalado (para desarrollo) o usa la versión empaquetada que lo incluye.
- El usuario escaneará el código QR de WhatsApp en el primer arranque para vincular su dispositivo. La sesión se persiste localmente para usos posteriores.
- El archivo Excel tiene una fila de cabecera con los nombres de columna exactos (o muy similares) a los esperados.
- Los números de teléfono en el Excel pueden estar en formato nacional (sin prefijo) o internacional.
- El prefijo de país por defecto será +34 (España) a menos que se configure otro.
- La aplicación no necesita manejar respuestas entrantes de WhatsApp (eso queda fuera del alcance).
- No se requiere autenticación de usuarios ni permisos dentro de la aplicación.