-- Migration Script: Fix RLS Policies for Views
-- This migration adds proper Row Level Security policies for views

-- Drop the existing view first
DROP VIEW IF EXISTS user_session_summary;

-- Recreate the view with proper RLS
CREATE VIEW user_session_summary AS
SELECT 
    s.session_id,
    s.user_id,
    s.project_id,
    s.title,
    s.created_at,
    s.updated_at,
    s.last_message_at,
    COUNT(cm.message_id) as message_count,
    d.snapshot_json->>'title' as project_title,
    d.snapshot_json->>'logline' as project_logline
FROM sessions s
LEFT JOIN chat_messages cm ON s.session_id = cm.session_id
LEFT JOIN dossier d ON s.project_id = d.project_id
WHERE s.is_active = true
GROUP BY s.session_id, s.user_id, s.project_id, s.title, s.created_at, s.updated_at, s.last_message_at, d.snapshot_json;

-- Enable RLS on the view
ALTER VIEW user_session_summary SET (security_invoker = true);

-- Create a security definer function for the view that enforces RLS
CREATE OR REPLACE FUNCTION get_user_session_summary(p_user_id UUID)
RETURNS TABLE (
    session_id UUID,
    project_id UUID,
    title TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    message_count BIGINT,
    project_title TEXT,
    project_logline TEXT
) 
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Verify the requesting user matches the requested user_id
    IF auth.uid() != p_user_id THEN
        RAISE EXCEPTION 'Access denied: You can only view your own session summary';
    END IF;
    
    RETURN QUERY
    SELECT 
        s.session_id,
        s.project_id,
        s.title,
        s.created_at,
        s.updated_at,
        s.last_message_at,
        COUNT(cm.message_id) as message_count,
        d.snapshot_json->>'title' as project_title,
        d.snapshot_json->>'logline' as project_logline
    FROM sessions s
    LEFT JOIN chat_messages cm ON s.session_id = cm.session_id
    LEFT JOIN dossier d ON s.project_id = d.project_id
    WHERE s.is_active = true 
      AND s.user_id = p_user_id
    GROUP BY s.session_id, s.project_id, s.title, s.created_at, s.updated_at, s.last_message_at, d.snapshot_json
    ORDER BY s.last_message_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION get_user_session_summary(UUID) TO authenticated;

-- Create a more secure version of the view that uses the function
CREATE OR REPLACE VIEW user_session_summary_secure AS
SELECT * FROM get_user_session_summary(auth.uid());

-- Enable RLS on the secure view
ALTER VIEW user_session_summary_secure SET (security_invoker = true);

-- Create additional security functions for common queries

-- Function to get user's own sessions with proper RLS
CREATE OR REPLACE FUNCTION get_my_sessions(p_limit INTEGER DEFAULT 10)
RETURNS TABLE (
    session_id UUID,
    project_id UUID,
    title TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    message_count BIGINT,
    last_message_preview TEXT,
    project_title TEXT,
    project_logline TEXT
) 
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.session_id,
        s.project_id,
        s.title,
        s.created_at,
        s.updated_at,
        s.last_message_at,
        COUNT(cm.message_id) as message_count,
        (
            SELECT content 
            FROM chat_messages 
            WHERE session_id = s.session_id 
            ORDER BY created_at DESC 
            LIMIT 1
        ) as last_message_preview,
        d.snapshot_json->>'title' as project_title,
        d.snapshot_json->>'logline' as project_logline
    FROM sessions s
    LEFT JOIN chat_messages cm ON s.session_id = cm.session_id
    LEFT JOIN dossier d ON s.project_id = d.project_id
    WHERE s.is_active = true 
      AND s.user_id = auth.uid()
    GROUP BY s.session_id, s.project_id, s.title, s.created_at, s.updated_at, s.last_message_at, d.snapshot_json
    ORDER BY s.last_message_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get session messages with proper RLS
CREATE OR REPLACE FUNCTION get_my_session_messages(
    p_session_id UUID, 
    p_limit INTEGER DEFAULT 50, 
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    message_id UUID,
    role TEXT,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ
) 
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Verify session ownership
    IF NOT EXISTS (
        SELECT 1 FROM sessions 
        WHERE session_id = p_session_id 
          AND user_id = auth.uid() 
          AND is_active = true
    ) THEN
        RAISE EXCEPTION 'Access denied: Session not found or not owned by user';
    END IF;
    
    RETURN QUERY
    SELECT 
        cm.message_id,
        cm.role,
        cm.content,
        cm.metadata,
        cm.created_at
    FROM chat_messages cm
    WHERE cm.session_id = p_session_id
    ORDER BY cm.created_at ASC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION get_my_sessions(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_my_session_messages(UUID, INTEGER, INTEGER) TO authenticated;

-- Add comments for documentation
COMMENT ON FUNCTION get_user_session_summary(UUID) IS 'Get session summary for a specific user (with RLS enforcement)';
COMMENT ON FUNCTION get_my_sessions(INTEGER) IS 'Get current user sessions with message counts and previews';
COMMENT ON FUNCTION get_my_session_messages(UUID, INTEGER, INTEGER) IS 'Get messages for a session owned by current user';
COMMENT ON VIEW user_session_summary_secure IS 'Secure view that only shows current user sessions';

-- Note: RLS policies cannot be created directly on views in PostgreSQL
-- Use the secure functions (get_my_sessions, get_my_session_messages) instead
-- for proper RLS enforcement

-- Update the session service to use the secure functions
-- This will be handled in the application code, but we document it here
COMMENT ON SCHEMA public IS 'Use get_my_sessions() and get_my_session_messages() functions instead of direct view access for better security';
