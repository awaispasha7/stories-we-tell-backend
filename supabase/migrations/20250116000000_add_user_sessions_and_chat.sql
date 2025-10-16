-- Migration Script: Add User Sessions and Chat Message Persistence
-- This migration adds support for multi-user chat sessions with message persistence

-- 1. Create `users` Table (if not using Supabase Auth)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    updated_at TIMESTAMPTZ DEFAULT current_timestamp
);

-- 2. Create `sessions` Table for Chat Sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    project_id UUID REFERENCES dossier(project_id) ON DELETE CASCADE,
    title TEXT, -- User-defined session title (e.g., "My Horror Story", "Romance Novel")
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    updated_at TIMESTAMPTZ DEFAULT current_timestamp,
    last_message_at TIMESTAMPTZ DEFAULT current_timestamp,
    is_active BOOLEAN DEFAULT true
);

-- 3. Create `chat_messages` Table for Individual Messages
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(session_id) ON DELETE CASCADE,
    turn_id UUID REFERENCES turns(turn_id) ON DELETE SET NULL, -- Link to existing turn if available
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB, -- Additional message metadata (e.g., typing indicators, error states)
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    updated_at TIMESTAMPTZ DEFAULT current_timestamp
);

-- 4. Create `user_projects` Table for Project Ownership
CREATE TABLE IF NOT EXISTS user_projects (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    project_id UUID REFERENCES dossier(project_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT current_timestamp,
    PRIMARY KEY (user_id, project_id)
);

-- 5. Update existing `turns` table to link with sessions
ALTER TABLE turns ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES sessions(session_id) ON DELETE CASCADE;
ALTER TABLE turns ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(user_id) ON DELETE CASCADE;

-- 6. Create Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_message_at ON sessions(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);
CREATE INDEX IF NOT EXISTS idx_turns_user_id ON turns(user_id);
CREATE INDEX IF NOT EXISTS idx_user_projects_user_id ON user_projects(user_id);
CREATE INDEX IF NOT EXISTS idx_user_projects_project_id ON user_projects(project_id);

-- 7. Create Functions for Session Management
CREATE OR REPLACE FUNCTION update_session_last_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE sessions 
    SET last_message_at = NEW.created_at,
        updated_at = current_timestamp
    WHERE session_id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 8. Create Trigger to Update Session Timestamp
CREATE TRIGGER trigger_update_session_last_message
    AFTER INSERT ON chat_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_session_last_message();

-- 9. Create Function to Get User's Recent Sessions
CREATE OR REPLACE FUNCTION get_user_sessions(p_user_id UUID, p_limit INTEGER DEFAULT 10)
RETURNS TABLE (
    session_id UUID,
    project_id UUID,
    title TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    last_message_at TIMESTAMPTZ,
    message_count BIGINT,
    last_message_preview TEXT
) AS $$
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
        ) as last_message_preview
    FROM sessions s
    LEFT JOIN chat_messages cm ON s.session_id = cm.session_id
    WHERE s.user_id = p_user_id AND s.is_active = true
    GROUP BY s.session_id, s.project_id, s.title, s.created_at, s.updated_at, s.last_message_at
    ORDER BY s.last_message_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- 10. Create Function to Get Session Messages
CREATE OR REPLACE FUNCTION get_session_messages(p_session_id UUID, p_limit INTEGER DEFAULT 50, p_offset INTEGER DEFAULT 0)
RETURNS TABLE (
    message_id UUID,
    role TEXT,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
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

-- 11. Add Row Level Security (RLS) Policies
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_projects ENABLE ROW LEVEL SECURITY;

-- Users can only see their own data
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid() = user_id);

-- Sessions policies
CREATE POLICY "Users can view own sessions" ON sessions
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own sessions" ON sessions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own sessions" ON sessions
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own sessions" ON sessions
    FOR DELETE USING (auth.uid() = user_id);

-- Chat messages policies
CREATE POLICY "Users can view messages in own sessions" ON chat_messages
    FOR SELECT USING (
        session_id IN (
            SELECT session_id FROM sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can create messages in own sessions" ON chat_messages
    FOR INSERT WITH CHECK (
        session_id IN (
            SELECT session_id FROM sessions WHERE user_id = auth.uid()
        )
    );

-- User projects policies
CREATE POLICY "Users can view own projects" ON user_projects
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can create own projects" ON user_projects
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- 12. Create Views for Common Queries
CREATE OR REPLACE VIEW user_session_summary AS
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

-- 13. Add Comments for Documentation
COMMENT ON TABLE users IS 'User profiles and authentication data';
COMMENT ON TABLE sessions IS 'Chat sessions for each user-project combination';
COMMENT ON TABLE chat_messages IS 'Individual chat messages within sessions';
COMMENT ON TABLE user_projects IS 'Many-to-many relationship between users and projects';
COMMENT ON FUNCTION get_user_sessions IS 'Get recent sessions for a user with message counts and previews';
COMMENT ON FUNCTION get_session_messages IS 'Get paginated messages for a specific session';
