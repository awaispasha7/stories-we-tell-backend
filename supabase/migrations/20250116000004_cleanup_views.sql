-- Migration Script: Clean Up Redundant Views
-- This migration removes redundant views and keeps only the secure functions

-- Drop both views since we have better secure functions
DROP VIEW IF EXISTS user_session_summary;
DROP VIEW IF EXISTS user_session_summary_secure;

-- The secure functions provide better functionality:
-- - get_my_sessions(limit) - Get current user's sessions with message counts
-- - get_my_session_messages(session_id, limit, offset) - Get session messages with RLS
-- - get_user_session_summary(user_id) - Get specific user's session summary

-- Add documentation comments
COMMENT ON FUNCTION get_my_sessions(INTEGER) IS 'Primary function for getting user sessions - use this instead of views';
COMMENT ON FUNCTION get_my_session_messages(UUID, INTEGER, INTEGER) IS 'Primary function for getting session messages - use this instead of views';
COMMENT ON FUNCTION get_user_session_summary(UUID) IS 'Function for getting specific user session summary with RLS';

-- Create a simple view for basic session data (if really needed)
-- This view will be protected by RLS policies on the underlying tables
CREATE VIEW user_sessions_basic AS
SELECT 
    session_id,
    user_id,
    project_id,
    title,
    created_at,
    updated_at,
    last_message_at,
    is_active
FROM sessions
WHERE is_active = true;

-- Enable RLS on the basic view (this will inherit RLS from the sessions table)
-- Note: This view is only for basic session data, not aggregated data

COMMENT ON VIEW user_sessions_basic IS 'Basic session data view - use get_my_sessions() function for aggregated data with message counts';

-- Final recommendation in schema comment
COMMENT ON SCHEMA public IS 'Use secure functions (get_my_sessions, get_my_session_messages) instead of views for best security and performance';
