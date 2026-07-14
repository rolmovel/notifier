# Feature Specification: WhatsApp Appointment Notifier

**Feature Branch**: `001-whatsapp-appointment-notifier`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "quisiera una aplicacion para automatizar el envio de notificaciones de whatsapp con las citas pendientes. Tendre que de alguna manera subir un fichero con las citas y automatizar su envio. Ademas, podre tener un robot respondiendo a estos whatsapps. Teniendo en cuenta que es para una clinica, las respuestas, si se configuran tendran que pasar por guardarailes estrictos. De cara al plan, como arquitectura usaremos n8n y evolution API para whatsapp. Tendre todo empaquetado para docker. Crea scripts para automatizacion de empaquetados"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload Appointment File & Send Notifications (Priority: P1)

A clinic staff member uploads a file containing pending appointment data (patient name, phone number, appointment date/time, appointment type). The system processes the file, validates the data, and automatically sends personalized WhatsApp notification messages to each patient reminding them of their upcoming appointment. The staff member can see a summary of how many notifications were sent successfully and which ones failed.

**Why this priority**: This is the core value proposition of the system — automating the manual, time-consuming task of calling or messaging patients to remind them of appointments. Without this, there is no MVP.

**Independent Test**: Upload a sample file with 5 appointment entries, trigger the notification process, and verify that 5 WhatsApp messages are sent to the corresponding phone numbers with the correct appointment details.

**Acceptance Scenarios**:

1. **Given** a valid appointment file has been uploaded, **When** the staff member triggers the notification sending process, **Then** each patient in the file receives a WhatsApp message with their appointment details (date, time, type) within a configurable time window.
2. **Given** an appointment file is uploaded with some invalid entries (e.g., missing phone number, invalid date format), **When** the sending process runs, **Then** valid entries are sent successfully and invalid entries are reported in an error summary with reasons for failure.
3. **Given** the notification process has completed, **When** the staff member views the results, **Then** they see a report showing total appointments processed, messages sent successfully, messages failed, and messages pending.
4. **Given** an appointment file is uploaded, **When** the file format is not recognized or is corrupted, **Then** the system rejects the file with a clear error message indicating the expected format.

---

### User Story 2 - Automated WhatsApp Response Bot with Guardrails (Priority: P2)

After a patient receives an appointment notification, they may reply to the WhatsApp message with questions (e.g., "Can I reschedule?", "What time is my appointment?", "Where is the clinic?"). An automated bot can be configured to respond to these replies. Because this is a medical clinic, all bot responses must pass through strict guardrails: the bot must never provide medical advice, must never share other patients' information, must only respond to appointment-related topics, and must escalate to a human staff member when it cannot safely answer.

**Why this priority**: Enhances the notification system by reducing follow-up phone calls from patients, but the core notification capability (P1) must exist first. Guardrails are critical for a clinical context to prevent liability and privacy issues.

**Independent Test**: Send a WhatsApp reply to a notification message asking "What time is my appointment?" and verify the bot responds with the appointment time. Send a reply asking "What medication should I take?" and verify the bot refuses to answer and escalates to a human.

**Acceptance Scenarios**:

1. **Given** a patient has received an appointment notification and the bot is enabled, **When** the patient replies asking about their appointment time or date, **Then** the bot responds with the correct appointment details from the uploaded data.
2. **Given** the bot is enabled and a patient replies asking a medical question (e.g., symptoms, medication, diagnosis), **When** the bot processes the reply, **Then** it does not provide medical advice and instead responds with a message directing the patient to contact clinic staff directly.
3. **Given** the bot is enabled and a patient requests to reschedule or cancel, **When** the bot processes the request, **Then** it does not make changes automatically and instead notifies clinic staff to handle the request manually.
4. **Given** the bot is enabled but cannot confidently answer a patient's question, **When** the bot evaluates the reply, **Then** it escalates the conversation to a human staff member and informs the patient that someone will contact them shortly.
5. **Given** the bot is disabled by clinic staff, **When** a patient replies to a notification, **Then** no automated response is sent and the message is simply logged for staff review.

---

### User Story 3 - Packaging & Deployment Automation (Priority: P3)

The clinic's technical administrator can package the entire system (notification engine, bot, and all dependencies) into a self-contained deployment artifact using automation scripts. The packaged system can be deployed on any environment that supports container-based deployment, with a single command to build and a single command to start all services.

**Why this priority**: Enables reproducible deployments and easy setup, but the system must function first (P1) before packaging matters. This ensures the solution is portable and maintainable.

**Independent Test**: Run the packaging script, verify a complete deployment artifact is produced, deploy it on a clean environment, and confirm all services start and the notification system is operational.

**Acceptance Scenarios**:

1. **Given** the system source code is available, **When** the administrator runs the packaging script, **Then** a complete, self-contained deployment artifact is produced containing all necessary components.
2. **Given** the deployment artifact has been produced, **When** the administrator starts the system on a target environment, **Then** all services start and are healthy within a reasonable startup time.
3. **Given** the system is running, **When** the administrator needs to update or reconfigure the system, **Then** they can do so by modifying configuration files and restarting without rebuilding the entire artifact.

---

### Edge Cases

- What happens when a patient's phone number is not a valid WhatsApp number? The system should mark the notification as failed and include it in the error report.
- What happens when the appointment file is empty (contains headers but no data rows)? The system should report zero appointments to process and not send any notifications.
- What happens when the WhatsApp sending service is temporarily unavailable? The system should retry with backoff and eventually mark unsent messages as failed with a clear reason.
- What happens when a patient replies outside of business hours? The bot should acknowledge receipt and inform the patient when to expect a response, or queue the message for staff review.
- What happens when two appointment files are uploaded with overlapping patients? The system should process them independently and send separate notifications, or deduplicate based on a configurable strategy.
- What happens when the bot encounters a message in a language it does not support? The bot should respond with a default message in the clinic's primary language and escalate to staff.
- What happens when the appointment file exceeds a maximum size? The system should reject it with a clear message about the size limit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow clinic staff to upload an appointment file containing patient appointment data (patient name, phone number, appointment date, appointment time, and appointment type at minimum).
- **FR-002**: System MUST validate uploaded appointment files and reject files with unrecognized formats, corrupted content, or missing required fields, providing a clear error message.
- **FR-003**: System MUST parse appointment data from the uploaded file and extract individual appointment records for processing.
- **FR-004**: System MUST send personalized WhatsApp notification messages to each patient's phone number, including their appointment date, time, and type.
- **FR-005**: System MUST generate a notification results report showing total appointments processed, successfully sent, failed, and pending notifications.
- **FR-006**: System MUST allow clinic staff to trigger the notification sending process manually after file upload.
- **FR-007**: System MUST handle invalid individual appointment records (missing phone, invalid date) without failing the entire batch, and include them in the error report.
- **FR-008**: System MUST retry failed WhatsApp deliveries with an exponential backoff strategy before marking them as permanently failed.
- **FR-009**: System MUST support at least one common file format for appointment data upload (e.g., CSV, Excel/XLSX).
- **FR-010**: System MUST allow clinic staff to enable or disable the automated WhatsApp response bot.
- **FR-011**: When the bot is enabled, system MUST analyze incoming patient replies and respond to appointment-related questions using the patient's appointment data from the uploaded file.
- **FR-012**: When the bot is enabled, system MUST NOT provide medical advice, diagnoses, medication recommendations, or any clinical guidance under any circumstances.
- **FR-013**: When the bot is enabled, system MUST NOT share, confirm, or reveal any other patient's information beyond the individual patient who sent the message.
- **FR-014**: When the bot is enabled, system MUST restrict responses to appointment-related topics only (appointment time, date, location, type, rescheduling requests).
- **FR-015**: When the bot is enabled, system MUST escalate to a human staff member when it cannot confidently or safely answer a patient's question, and inform the patient that someone will contact them.
- **FR-016**: When the bot is enabled, system MUST NOT automatically reschedule, cancel, or modify appointments; it MUST route such requests to clinic staff.
- **FR-017**: System MUST log all bot conversations for audit and review purposes by clinic staff.
- **FR-018**: System MUST provide automation scripts to package the entire system into a self-contained, deployable artifact.
- **FR-019**: System MUST be deployable as a complete package that starts all required services with a single command.
- **FR-020**: System MUST allow configuration changes (e.g., notification message templates, bot behavior settings) without requiring a full rebuild of the deployment artifact.
- **FR-021**: System MUST support configurable notification message templates so clinics can customize the wording of appointment reminders.
- **FR-022**: System MUST allow clinic staff to configure the notification sending schedule (e.g., send reminders X hours/days before the appointment).

### Key Entities *(include if feature involves data)*

- **Appointment**: Represents a scheduled patient appointment. Key attributes: patient name, patient phone number, appointment date, appointment time, appointment type/procedure, and notification status (pending, sent, failed).
- **Notification Record**: Represents the outcome of sending a WhatsApp notification for a specific appointment. Key attributes: appointment reference, phone number, message content, send status (success, failed, pending), timestamp, and error reason if applicable.
- **Patient Reply**: Represents an incoming WhatsApp message from a patient in response to a notification. Key attributes: patient phone number, message content, timestamp, bot response (if any), and escalation status.
- **Bot Configuration**: Represents the configurable settings for the automated response bot. Key attributes: enabled/disabled state, allowed topics, escalation rules, and business hours.
- **Notification Template**: Represents a customizable message template for appointment reminders. Key attributes: template text with placeholders for patient name, date, time, and appointment type.
- **Deployment Package**: Represents the packaged, self-contained system artifact. Key attributes: version, included components, and configuration files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Clinic staff can upload an appointment file and send WhatsApp notifications to all patients within 5 minutes for a batch of up to 100 appointments.
- **SC-002**: At least 95% of valid appointment records in an uploaded file result in successfully delivered WhatsApp notifications.
- **SC-003**: The automated bot correctly identifies and refuses 100% of medical advice requests, directing patients to contact clinic staff instead.
- **SC-004**: The automated bot correctly answers at least 90% of appointment-related questions (time, date, type) using the patient's appointment data.
- **SC-005**: The automated bot escalates to human staff 100% of conversations it cannot confidently or safely handle, without leaving any patient message unanswered.
- **SC-006**: The packaging script produces a complete deployment artifact in under 10 minutes, and the deployed system starts all services and becomes operational within 5 minutes on a clean environment.
- **SC-007**: Clinic staff can enable or disable the bot, modify notification templates, and adjust sending schedules through configuration without technical assistance.
- **SC-008**: The notification results report accurately reflects the status of every appointment record (sent, failed, pending) with zero discrepancies.

## Assumptions

- The clinic has a WhatsApp Business account or equivalent service capable of sending and receiving messages programmatically. (User has specified Evolution API as the WhatsApp integration.)
- The clinic staff member operating the system has basic computer literacy (can upload files, read reports, toggle settings) but is not a technical administrator.
- The automated bot will use an AI language model capable of understanding natural language in the clinic's primary language (assumed Spanish, based on the feature request language).
- The system will be deployed in an environment that supports container-based deployment. (User has specified Docker as the packaging/deployment mechanism.)
- The system will use a workflow automation engine as its core orchestration layer. (User has specified n8n as the automation tool.)
- Appointment files will be provided by the clinic's existing scheduling/management system in a standard spreadsheet format (CSV or Excel).
- The clinic operates during standard business hours; bot responses outside business hours will acknowledge receipt and inform patients of expected response times.
- Phone numbers in appointment files are in a format compatible with WhatsApp (international format with country code). The system will attempt to normalize numbers but may require consistent input format.
- A single clinic location is the primary use case; multi-clinic or multi-tenant support is out of scope for the initial version.
- The bot's guardrails will be enforced through a combination of topic classification, content filtering, and response validation rules configured at the workflow level.
- The user-provided architecture decisions (n8n, Evolution API, Docker, packaging scripts) are documented here as constraints for the planning phase and do not appear in the functional requirements, which remain focused on user and business needs.
