-- ==============================================================================
-- ConversationSession, PatientProfile, and PatientReply Schemas
-- ==============================================================================

\c notifier;

-- Create patient_profiles table
CREATE TABLE IF NOT EXISTS patient_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    patient_name VARCHAR(100),
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_appointments INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    cross_appointment_summary JSONB DEFAULT '{}'::jsonb,
    summary_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index on profile phone number
CREATE INDEX IF NOT EXISTS idx_patient_profiles_phone ON patient_profiles(phone_number);

-- Create conversation_sessions table
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id UUID UNIQUE REFERENCES appointments(id) ON DELETE CASCADE,
    patient_phone VARCHAR(20) NOT NULL,
    patient_profile_id UUID NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'closed', 'expired')),
    message_count INTEGER DEFAULT 0,
    context_window JSONB DEFAULT '[]'::jsonb
);

-- Indexes for sessions
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_app ON conversation_sessions(appointment_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_profile ON conversation_sessions(patient_profile_id);
CREATE INDEX IF NOT EXISTS idx_conversation_sessions_status ON conversation_sessions(status);

-- Create patient_replies table
CREATE TABLE IF NOT EXISTS patient_replies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number VARCHAR(20) NOT NULL,
    message_content TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    session_id UUID REFERENCES conversation_sessions(id) ON DELETE SET NULL,
    patient_profile_id UUID REFERENCES patient_profiles(id) ON DELETE CASCADE,
    bot_response TEXT,
    escalation_status VARCHAR(20) NOT NULL DEFAULT 'none' CHECK (escalation_status IN ('none', 'escalated', 'resolved')),
    escalation_reason TEXT,
    conversation_log JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- Indexes for replies
CREATE INDEX IF NOT EXISTS idx_patient_replies_phone ON patient_replies(phone_number);
CREATE INDEX IF NOT EXISTS idx_patient_replies_app ON patient_replies(appointment_id);
CREATE INDEX IF NOT EXISTS idx_patient_replies_session ON patient_replies(session_id);
CREATE INDEX IF NOT EXISTS idx_patient_replies_profile ON patient_replies(patient_profile_id);
