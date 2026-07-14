# Bot Guardrails & Safety Architecture: Technical Specification

Operating an automated communication channel in a medical or clinical context demands robust, deterministic guarantees. Unlike standard customer support chatbots, a clinical bot cannot be permitted to hallucinate, offer medical advice, reveal alternative patient records, or modify appointment databases without human approval.

This document details the exact prompt structures, validation schemas, and filtration parameters implementing the **4-Layer Safety Guardrail** in our system.

---

## 🛡️ The 4-Layer Security Pipeline

The system uses a defensive, pipe-and-filter progression when processing an incoming patient message:

```
[Incoming Patient Message]
           │
           ▼
┌──────────────────────────────────────┐
│  Layer 1: Pre-Response Classifier    │ ── (Unallowed Topic / Low Confidence) ──┐
└──────────────────────────────────────┘                                         │
           │                                                                     │
           ▼ (Allowed Topic)                                                     │
┌──────────────────────────────────────┐                                         │
│  Layer 2: Constrained Generator      │                                         │
└──────────────────────────────────────┘                                         │
           │                                                                     │
           ▼ (Raw Generated Reply)                                               │
┌──────────────────────────────────────┐                                         │
│  Layer 3: Post-Generation Filtering  │ ── (Banned Words / Size Overflow) ──────┼──► [Layer 4: Escalation Engine]
└──────────────────────────────────────┘                                         │         │
           │                                                                     │         ├─► Send Handoff Msg
           ▼ (Approved Response)                                                 │         ├─► Update Status = 'escalated'
   [Send Message via WhatsApp]                                                   │         └─► Alert Admin Staff
                                                                                 │
                                                                                 │
   [Hold outside hours] ◄────────────── (Business Hours Violation) ──────────────┘
```

---

## 🏷️ Layer 1: System Classification Prompt Design (Topic Classification)

Implemented as a structured JSON classifier in n8n. The system forces the LLM to output a clean JSON syntax, bypassing free-form dialogue.

### Prompts Definition
```text
System Prompt:
You are an API router designed to classify patient input into discrete routing topics.
Do not engage in pleasantries or free-form reply. You must evaluate the message and output a clean JSON string matching this schema:
{
  "topic": string,
  "confidence": float (0.0 to 1.0)
}

The supported values for "topic" are strictly limited to:
  - "appointment_time": Question about the start hour, duration or timeline of their appointment.
  - "appointment_date": Question about the date, day or weekday of the appointment.
  - "appointment_type": Question asking what dental checkup or procedure has been booked.
  - "clinic_location": Inquiry regarding address, parking, directions, or transit options.
  - "appointment_confirmation": Definite statement confirming they will attend (e.g. "I will be there", "Confirm").
  - "medical_advice": Questions about symptoms, toothaches, pain, swollen gums, medication doses, antibiotic questions, or recovery.
  - "reschedule_request": Request to change the date, cancel the appointment, or push the hour.
  - "other": Topics unrelated to the clinic, gibberish, or generic chat.

Under no circumstances output anything else other than a valid JSON parseable string.
```

*Routing Action:* If `"allowed": true` (topic is in allowed list) **and** `"confidence" >= 0.70`, the system routes to Generation. Otherwise, it triggers immediate Layer 4 Escalation.

---

## 📝 Layer 2: Constrained Generation (AI Prompt Constraint)

If approved by Layer 1, the message is routed to the Generation Prompt. This prompt restricts the AI to the patient's individual data retrieved from the database.

### Generator Prompt Layout
```text
System Prompt:
You are an automated administrative assistant at the clinic. Your name is "Asistente Dental".
You are helping the patient query information about their scheduled appointment.

=== PATIENT APPOINTMENT RECORD ===
Patient Name: {{$json.patientName}}
Appointment Date: {{$json.appointmentDate}}
Appointment Time: {{$json.appointmentTime}}
Appointment Category: {{$json.appointmentType}}
==================================

=== CLINIC CONFIGURATION ===
Clinic Name: Dental Care Clinic
Location: Calle Principal 123, Madrid, España
============================

=== PRIOR INTERACTIONS CONTEXT ===
{History of last 10 messages from ConversationSession}
{Condensed summary from PatientProfile}
===================================

RULES OF ENGAGEMENT:
1. You may ONLY communicate details specified in the Patient Appointment Record and Clinic Configuration.
2. You MUST NOT answer questions about symptoms, medications, recommendations, or pricing.
3. You MUST NOT offer administrative rescheduling options (e.g., "I can move you to Thursday").
4. Under no condition mention, reference, or leak information belonging to any other patient name or phone.
5. All replies must be concise (under 200 characters).
6. Response language: Spanish (es).

Current Patient Message: "{{$json.messageContent}}"
```

---

## 🔍 Layer 3: Post-Generation Filtering (Deterministic Checking)

We do not rely solely on the LLM's adherence to instructions. A JavaScript Node intercepts the generated string and subjects it to deterministic check conditions before it goes to WhatsApp:

1. **Character Length Guard**: If `bot_response.length > 200` characters, block.
2. **Double Patient Leak Check**:
   - Compares the string against the current patient name in the database.
   - If the bot includes any other name or phone number that hasn't been specifically bound to the context, block.
3. **Clinical Blocklist Scan**: Checks if the response contains any medical terms, diagnostic terms, or medication.
   - Banned Terms: `antibiótico, anestesia, caries, conducto, empaste, endodoncia, extracción, gingivitis, implante, inflamación, infección, ortodoncia, periodontitis, prótesis, pulir, rayos x, radiografía, sangrado, tumor, úlcera`
   - *Example Match*: If the bot generates *"No se preocupe por el dolor de caries..."*, the string contains `caries`. The filter blocks the message.

---

## 📢 Layer 4: Escalation Routing & Admin Notifications

When a guardrail fails (Layer 1 block, Layer 2 violation, or Layer 3 filtered out), the system executes a containment workflow:

1. **Patient Notification**: Sends a pre-compiled, polite response:
   > *"Gracias por su mensaje. Un miembro del personal de la clínica se pondrá en contacto con usted en horario de consulta pronto."*
2. **Database State Change**: Inserts a record in the `patient_replies` table with:
   - `escalation_status = 'escalated'`
   - `escalation_reason = 'medical_term_detected' | 'blocked_topic' | 'outside_business_hours'`
3. **Staff Alert**: An admin notifications workflow triggers. It writes a warning log card in PostgreSQL that can be queried by clinic systems or delivers a notifications digest to the clinic staff's Slack or administrative mailboxes.
