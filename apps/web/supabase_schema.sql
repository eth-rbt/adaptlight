-- Supabase Schema for AdaptLight
-- Run this in your Supabase SQL Editor

-- Drop old tables if they exist (only if you want to start fresh)
DROP TABLE IF EXISTS command_logs;
DROP TABLE IF EXISTS state_logs;

-- Command sessions table - stores each text command with full state machine snapshot
CREATE TABLE IF NOT EXISTS command_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- User identification
    user_id TEXT NOT NULL,

    -- Command and response
    command TEXT NOT NULL,
    response_message TEXT,
    success BOOLEAN DEFAULT true,

    -- Current state after command
    current_state TEXT,
    current_state_data JSONB,

    -- Full state machine snapshot after command
    all_states JSONB DEFAULT '[]'::jsonb,   -- Array of all states
    all_rules JSONB DEFAULT '[]'::jsonb,    -- Array of all rules

    -- Agent execution details (for debugging)
    tool_calls JSONB DEFAULT '[]'::jsonb,
    agent_steps JSONB DEFAULT '[]'::jsonb,
    timing_ms FLOAT,
    run_id TEXT,

    -- User feedback (nullable, submitted separately)
    feedback TEXT,
    feedback_rating INTEGER,  -- Optional: 1-5 rating
    feedback_submitted_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster queries
CREATE INDEX IF NOT EXISTS idx_command_sessions_user_id ON command_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_command_sessions_created_at ON command_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_sessions_has_feedback ON command_sessions(feedback) WHERE feedback IS NOT NULL;

-- Enable Row Level Security
ALTER TABLE command_sessions ENABLE ROW LEVEL SECURITY;

-- Policy to allow all access (for demo purposes)
CREATE POLICY "Allow all access to command_sessions" ON command_sessions
    FOR ALL USING (true) WITH CHECK (true);
