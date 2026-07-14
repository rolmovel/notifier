# Contract: Bot Guardrails

**Date**: 2026-07-13
**Feature**: 001-whatsapp-appointment-notifier

## Overview

Defines the rules, restrictions, and escalation triggers for the automated WhatsApp response bot. These guardrails are non-negotiable due to the clinical context. They are enforced as a multi-layer system within n8n workflows.

## Guardrail Layers

### Layer 1: Topic Classification (Pre-Response)

**Purpose**: Determine if the patient's message is within the bot's allowed scope before generating any response.

**Allowed Topics**:
- Appointment time inquiry (e.g., "What time is my appointment?")
- Appointment date inquiry (e.g., "When is my appointment?")
- Appointment type inquiry (e.g., "What is my appointment for?")
- Clinic location/directions (e.g., "Where is the clinic?")
- Appointment confirmation (e.g., "I confirm I'll be there")

**Blocked Topics (immediate escalation)**:
- Medical symptoms or conditions (e.g., "I have pain in my tooth")
- Medication questions (e.g., "Should I take antibiotics?")
- Diagnosis requests (e.g., "Do I have a cavity?")
- Treatment advice (e.g., "What should I do for my gum pain?")
- Test results (e.g., "What do my X-ray results say?")
- Pricing or billing questions (e.g., "How much does a filling cost?")
- Personal data of other patients (e.g., "When is María's appointment?")
- Requests to modify appointments (e.g., "Can you reschedule me to next week?") — these are escalated, not handled by the bot

**Implementation**: AI Agent node with a classification system prompt. Output: `{ "topic": "appointment_time" | "medical_advice" | "reschedule_request" | ..., "confidence": 0.0-1.0, "allowed": true|false }`

**Action**: If `allowed: false` or `confidence < 0.7`, proceed to escalation.

---

### Layer 2: Response Generation (Constrained AI)

**Purpose**: Generate a response using only the patient's appointment data, with a strict system prompt.

**System Prompt Rules** (enforced via n8n AI Agent node configuration):
1. You may ONLY discuss the patient's own appointment details (date, time, type).
2. You may provide the clinic's address and general contact information.
3. You MUST NOT provide any medical advice, diagnosis, or treatment recommendations.
4. You MUST NOT mention or reference any other patient's information.
5. You MUST NOT reschedule, cancel, or modify appointments.
6. You MUST NOT discuss pricing, billing, or insurance.
7. If the patient asks about anything outside your scope, respond with: "Lo siento, no puedo ayudar con esa consulta. Un miembro del personal de la clínica se pondrá en contacto con usted pronto." and trigger escalation.
8. All responses must be in Spanish (or the configured language).
9. Responses must be concise (max 200 characters).
10. You must be polite and professional at all times.
11. You may use the conversation history to maintain context, but you MUST NOT reference past appointments or sessions beyond what is provided in the patient profile summary.
12. You may acknowledge that the patient has visited before (if the cross-appointment summary indicates so), but only in a general, polite manner (e.g., "Hola de nuevo, Juan").

**Data Available to AI Agent**:
- Patient's name
- Patient's appointment date
- Patient's appointment time
- Patient's appointment type
- Clinic name and address (from configuration)
- **Conversation history** (Level 1 — per-appointment memory): The last N messages (default 10, configurable via `max_context_messages`) from the `ConversationSession.context_window`. This allows the bot to understand follow-up questions like "¿Y para qué es?" after "¿A qué hora es mi cita?".
- **Patient profile summary** (Level 2 — cross-appointment memory, if `enable_cross_appointment_memory` is `true`): A condensed summary from `PatientProfile.cross_appointment_summary` including: last appointment date/type, known preferences (e.g., "prefers morning"), last interaction topics. This allows the bot to greet recurring patients naturally and anticipate common questions.

**Data NOT Available to AI Agent**:
- Any other patient's information
- Medical records or history
- Pricing or billing information
- Staff schedules or availability
- Full raw history of past sessions (only the condensed `cross_appointment_summary` is provided)
- Conversation history from other patients' sessions

---

### Layer 3: Response Validation (Post-Generation)

**Purpose**: Scan the AI-generated response before sending it via Evolution API. This is a programmatic check (not AI-based) to catch any guardrail violations that the AI model might have produced despite instructions.

**Checks**:
1. **Medical term filter**: Scan response for a blocklist of medical terms (stored in `config/guardrails-rules.json`). Blocklist includes: medication names, medical procedures, diagnostic terms, anatomical terms in a clinical context.
2. **Cross-patient data check**: Verify the response does not contain any phone number or name other than the current patient's.
3. **Length check**: Response must not exceed 200 characters.
4. **Format check**: Response must be valid text (no JSON, no code, no URLs except the clinic's address link).

**Action**: If any check fails, block the response, log the violation, and proceed to escalation.

---

### Layer 4: Escalation Routing

**Purpose**: When any guardrail layer triggers, notify clinic staff and inform the patient.

**Escalation Triggers**:
- Layer 1 classification returns `allowed: false`
- Layer 1 confidence below threshold (default: 0.7)
- Layer 2 AI Agent produces a response that fails Layer 3 validation
- Patient explicitly requests to speak to a human
- Patient requests to reschedule or cancel an appointment
- Message received outside of configured business hours (bot acknowledges but escalates for next-day handling)

**Escalation Actions**:
1. Send a message to the patient: "Gracias por su mensaje. Un miembro del personal de la clínica se pondrá en contacto con usted en horario de consulta."
2. Log the conversation with escalation reason in `PatientReply` record (for audit — FR-017).
3. Send a notification to clinic staff (via a separate n8n workflow that can deliver via email, Slack, or another WhatsApp message to a staff number).

**Escalation Status Values**:
- `none`: No escalation needed; bot responded normally.
- `escalated`: Escalation triggered; staff notified.
- `resolved`: Staff has reviewed and resolved the escalated conversation (manual status update).

---

## Guardrail Rules Configuration

Stored in `config/guardrails-rules.json`:

```json
{
  "version": "1.0.0",
  "confidence_threshold": 0.7,
  "max_response_length": 200,
  "blocked_topics": [
    "medical_symptoms",
    "medication",
    "diagnosis",
    "treatment_advice",
    "test_results",
    "pricing_billing",
    "other_patient_data",
    "appointment_modification"
  ],
  "allowed_topics": [
    "appointment_time",
    "appointment_date",
    "appointment_type",
    "clinic_location",
    "appointment_confirmation"
  ],
  "medical_term_blocklist": [
    "antibiótico", "anestesia", "caries", "conducto", "empaste",
    "endodoncia", "extracción", "gingivitis", "implante", "inflamación",
    "infección", "ortodoncia", "periodontitis", "prótesis", "pulir",
    "rayos x", "radiografía", "sangrado", "tumor", "úlcera"
  ],
  "escalation_message": "Gracias por su mensaje. Un miembro del personal de la clínica se pondrá en contacto con usted en horario de consulta.",
  "out_of_hours_message": "Gracias por su mensaje. Nuestro horario de atención es de {{business_hours_start}} a {{business_hours_end}}. Le responderemos en el próximo horario de consulta.",
  "staff_notification_template": "ESCALACIÓN: El paciente {{patient_name}} ({{patient_phone}}) ha enviado un mensaje que requiere atención manual. Motivo: {{escalation_reason}}. Mensaje: {{message_content}}",
  "memory": {
    "session_context_window": 10,
    "enable_cross_appointment_memory": true,
    "profile_memory_retention_days": 90,
    "max_known_preferences": 5,
    "max_last_topics": 5,
    "session_expiry_hours": 72,
    "session_close_after_appointment_hours": 24
  }
}
```

## Audit Requirements

- Every bot conversation must be logged with: patient phone, message content, classification result, AI response (if generated), guardrail check results, escalation status, and timestamp (FR-017).
- Logs are stored in the `PatientReply.conversation_log` JSON field in PostgreSQL.
- Clinic staff can review all conversations through a simple query or a future reporting workflow.
- Logs must be retained for a minimum of 1 year (configurable via `LOG_RETENTION_DAYS` environment variable).
- Conversation sessions (`ConversationSession`) retain the sliding context window for active bot memory; the full history is preserved in `PatientReply.conversation_log` even after messages drop out of the context window.
- Patient profiles (`PatientProfile`) store cross-appointment summaries. Staff can review a patient's full interaction history by querying all `ConversationSession` records linked to a `PatientProfile`.
