# System Architecture: WhatsApp Appointment Notifier

This document outlines the container federation, data directories, workflow orchestration pattern, and data flow topologies of the **WhatsApp Appointment Notifier** system.

---

## 🏗️ 1. Container Federation Diagram

The application runs in a isolated Docker Bridge network consisting of 4 dedicated daemon containers:

```mermaid
graph TD
    subgraph LAN_or_WAN [Public/Private LAN Endpoint]
        Admin[Clinic Staff]
        Patient[Patient Mobile Phone]
    end

    subgraph Docker_Host [Docker Compose Virtual Host Network: notifier-network]
        direction TB

        subgraph Orchestration_Layer [Orchestration Container]
            N8N[notifier-n8n:5678]
        end

        subgraph Messaging_Gateway [Gateway Container]
            Evo[notifier-evolution-api:8080]
        end

        subgraph Datastore_Layer [Persistence Services]
            PG[(notifier-postgres:5432)]
            Redis[(notifier-redis:6379)]
        end

        %% Connections within Host
        N8N -- "REST API (apikey)" --> Evo
        N8N -- "Write Cites/Replies" --> PG
        Evo -- "Post Webhook message.upsert" --> N8N
        Evo -- "Prisma Client (PostgreSQL)" --> PG
        Evo -- "Keys/Caching" --> Redis
    end

    %% External Connections
    Admin -- "Upload CSV/XLS (POST)" --> N8N
    Patient -- "Send WhatsApp Text" --> Evo
    Evo -- "Deliver WhatsApp Text" --> Patient
```

---

## ⚡ 2. Data Flow Topologies

### Flow A: Appointment Processing & Delivery (P1 - MVP)

This sequential flow runs when a staff member uploads an appointment spreadsheet:

1. **Trigger**: Multi-part CSV/XLSX file is POSTed to `http://<host>:5678/webhook/upload-appointments`.
2. **Immediate Reply**: n8n generates a UUID `batchId`, validates the file size under 10MB/1000 rows, and responds syncronously with `{ "batchId": "...", "status": "processing" }` to prevent clinic computer lockups.
3. **Parse & Normalization**:
   - Extraction of spreadsheet sheets using the custom node.
   - Script trims whitespace and parses dates/times.
   - Evaluates prefix condition: If phone lacks country prefix, injects configured `DEFAULT_COUNTRY_CODE`.
4. **Validation Check**: If columns pass checking, they are directed to the Database Write step. If failing, they are logged as a schema rejection reason in the DB and omitted from the send loop.
5. **Database Entry**: Inserts parsed rows into the `appointments` table with state `pending`.
6. **Delivery Loop (Throttle-Controlled)**:
   - For each valid appointment row, formatted reminders are assembled.
   - HTTP request executes to Evolution API `/message/sendText/{instance}` with payload delay of `1200ms`.
   - On delivery timeout or 5xx failures, n8n invokes Exponential Backoff retry strategy (re-queue with multiplier intervals: `5s`, `15s`, `45s`).
7. **Status Update**: Upon termination, database records are adjusted:
   - Success → Set `notification_status = 'sent'`, saving sent timestamp.
   - Failure → Set `notification_status = 'failed'`, saving explicit `error_reason`.
   - Logging results in `notification_records` table.

---

### Flow B: Conversational Reply & Guardrails (P2 - Bot Module)

This asynchronous flow executes when a patient replies to a sent reminder:

```mermaid
sequenceDiagram
    autonumber
    actor Patient as Patient Phone
    participant Evo as Evolution API
    participant N8N as n8n Webhook
    participant DB as Postgres Datastore
    participant LLM as OpenAI GPT-3.5

    Patient->>Evo: Sends: "At what hour is my appointment?"
    Evo->>N8N: Webhook callback (POST json messages.upsert)
    activate N8N
    N8N-->>Evo: HTTP 200 OK (Instant acknowledgment)
    
    rect rgb(200, 220, 240)
        Note over N8N,DB: Initialization & Check Step
        N8N->>DB: Query configuration + current time
        DB-->>N8N: Active status + business hours (09:00 - 18:00)
    end

    alt Message received Outside Business Hours
        N8N->>Patient: Send polite courtesy Holding Message via Evolution API
        N8N->>DB: Log message status 'escalated' (Reason: outside_business_hours)
    else Received inside Business Hours
        N8N->>DB: Look up latest active appointment by patient phone
        DB-->>N8N: Found Appointment ID, Date, Time, Type
        N8N->>DB: Look up/Create PatientProfile & ConversationSession
        DB-->>N8N: Returns level 1 and level 2 memory context
        
        rect rgb(240, 200, 200)
            Note over N8N,LLM: Layer 1 Guardrail: Topic Classification
            N8N->>LLM: Classify intent (Allowed: appointment_time, Location, etc.)
            LLM-->>N8N: Classification: { topic: "appointment_time", confidence: 0.95 }
        end
        
        alt Classification is NOT ALLOWED (e.g. topic is "medical_advice" or confidence < 0.70)
            N8N->>Patient: Send human hand-off holding message
            N8N->>DB: Record Conversation escalated (Reason: medical_advice_requested)
        else Classification is APPROVED
            rect rgb(200, 240, 200)
                Note over N8N,LLM: Layer 2 Guardrail: Constrained Action
                N8N->>LLM: Render system context + memories + patient query
                LLM-->>N8N: Generated: "Su cita de Limpieza es mañana a las 15:00."
            end

            rect rgb(240, 240, 200)
                Note over N8N,N8N: Layer 3 Guardrail: Validation & Post-scan
                Note over N8N: Check chars <= 200 & no terms from medical blocklist
            end

            alt Scan validation FAILS (e.g. contained "anestesia" or "caries")
                N8N->>Patient: Send human hand-off holding message
                N8N->>DB: Record Conversation escalated (Reason: medical_term_detected)
            else Scan validation APPROVED
                N8N->>Patient: Deliver short AI response (Evolution API send text)
                N8N->>DB: Store reply in patient_replies and append to ConversationSession context_window
            end
        end
    end
    deactivate N8N
```

---

## 📂 3. Port Map & Database Directory Allocations

### TCP Port Declarations
* **5678** (n8n Webhook & Configuration Panel)
* **8080** (Evolution API Gateway API)
* **5432** (PostgreSQL Connection Port)
* **6379** (Redis Caching Port)

### Volume Mount Strategies
All datastores store states inside named docker volumes to guarantee state retention across reboots or deployments:

```yaml
volumes:
  notifier-postgres-data:   # Maps /var/lib/postgresql/data inside database container
  notifier-redis-data:      # Maps /data inside Redis container
  notifier-evolution-data:  # Stores Baileys credentials and connection state
  notifier-n8n-data:        # Holds workflow logs and node encryption credentials
```
