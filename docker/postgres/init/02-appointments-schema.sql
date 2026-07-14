-- ==============================================================================
-- Appointments and Notification Records Schemas
-- ==============================================================================

\c notifier;

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Define notification_status type/constraint or check
CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_name VARCHAR(100) NOT NULL,
    patient_phone VARCHAR(20) NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    appointment_type VARCHAR(200) NOT NULL,
    notification_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (notification_status IN ('pending', 'sent', 'failed')),
    notification_sent_at TIMESTAMP WITH TIME ZONE,
    error_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    batch_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for phone number searches and state transitions
CREATE INDEX IF NOT EXISTS idx_appointments_phone ON appointments(patient_phone);
CREATE INDEX IF NOT EXISTS idx_appointments_batch ON appointments(batch_id);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(notification_status);

-- Create NotificationRecords table
CREATE TABLE IF NOT EXISTS notification_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) NOT NULL,
    message_content TEXT NOT NULL,
    send_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (send_status IN ('success', 'failed', 'pending')),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    error_reason TEXT,
    evolution_api_response JSONB,
    retry_attempt INTEGER DEFAULT 0
);

-- Index for appointment foreign keys
CREATE INDEX IF NOT EXISTS idx_notification_records_appointment ON notification_records(appointment_id);
