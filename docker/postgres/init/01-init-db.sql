-- ==============================================================================
-- PostgreSQL Initial Database Setup
-- Run on first boot of PostgreSQL container to prepare schemas for services
-- ==============================================================================

-- Create n8n database
CREATE DATABASE n8n;

-- Create Evolution API database
CREATE DATABASE evolution;

-- Connect to the main notifier database
-- Note: the standard POSTGRES_DB (notifier) is created automatically by the entrypoint.

-- Grant permissions (if custom users are initialized later, but with POSTGRES_USER they are owners by default)
GRANT ALL PRIVILEGES ON DATABASE n8n TO postgres;
GRANT ALL PRIVILEGES ON DATABASE evolution TO postgres;
