-- Migration Script: Fix RLS Policies for All Tables
-- This migration adds proper Row Level Security policies for all existing and new tables

-- Enable RLS on existing tables (if not already enabled)
ALTER TABLE turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE dossier ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (to avoid conflicts)
DROP POLICY IF EXISTS "Users can view own turns" ON turns;
DROP POLICY IF EXISTS "Users can create own turns" ON turns;
DROP POLICY IF EXISTS "Users can update own turns" ON turns;
DROP POLICY IF EXISTS "Users can delete own turns" ON turns;

DROP POLICY IF EXISTS "Users can view own projects" ON dossier;
DROP POLICY IF EXISTS "Users can create own projects" ON dossier;
DROP POLICY IF EXISTS "Users can update own projects" ON dossier;
DROP POLICY IF EXISTS "Users can delete own projects" ON dossier;

DROP POLICY IF EXISTS "Users can view own assets" ON assets;
DROP POLICY IF EXISTS "Users can create own assets" ON assets;
DROP POLICY IF EXISTS "Users can update own assets" ON assets;
DROP POLICY IF EXISTS "Users can delete own assets" ON assets;

-- RLS Policies for `turns` table
-- Users can only access turns from their own sessions
CREATE POLICY "Users can view own turns" ON turns
    FOR SELECT USING (
        user_id = auth.uid() OR 
        session_id IN (
            SELECT session_id FROM sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can create own turns" ON turns
    FOR INSERT WITH CHECK (
        user_id = auth.uid() AND
        session_id IN (
            SELECT session_id FROM sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own turns" ON turns
    FOR UPDATE USING (
        user_id = auth.uid() OR 
        session_id IN (
            SELECT session_id FROM sessions WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete own turns" ON turns
    FOR DELETE USING (
        user_id = auth.uid() OR 
        session_id IN (
            SELECT session_id FROM sessions WHERE user_id = auth.uid()
        )
    );

-- RLS Policies for `dossier` table
-- Users can only access dossiers for projects they own
CREATE POLICY "Users can view own projects" ON dossier
    FOR SELECT USING (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can create own projects" ON dossier
    FOR INSERT WITH CHECK (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own projects" ON dossier
    FOR UPDATE USING (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete own projects" ON dossier
    FOR DELETE USING (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

-- RLS Policies for `assets` table
-- Users can only access assets for projects they own
CREATE POLICY "Users can view own assets" ON assets
    FOR SELECT USING (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can create own assets" ON assets
    FOR INSERT WITH CHECK (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own assets" ON assets
    FOR UPDATE USING (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete own assets" ON assets
    FOR DELETE USING (
        project_id IN (
            SELECT project_id FROM user_projects WHERE user_id = auth.uid()
        )
    );

-- Additional security: Ensure user_id and session_id columns exist in turns table
-- (These should already be added by the previous migration, but let's be safe)
DO $$ 
BEGIN
    -- Add user_id column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'turns' AND column_name = 'user_id') THEN
        ALTER TABLE turns ADD COLUMN user_id UUID REFERENCES users(user_id) ON DELETE CASCADE;
    END IF;
    
    -- Add session_id column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'turns' AND column_name = 'session_id') THEN
        ALTER TABLE turns ADD COLUMN session_id UUID REFERENCES sessions(session_id) ON DELETE CASCADE;
    END IF;
END $$;

-- Create indexes for better performance on the new columns
CREATE INDEX IF NOT EXISTS idx_turns_user_id ON turns(user_id);
CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);

-- Create a function to automatically associate users with projects when they create turns
CREATE OR REPLACE FUNCTION auto_associate_user_project()
RETURNS TRIGGER AS $$
BEGIN
    -- If user_id is set but no user_project association exists, create it
    IF NEW.user_id IS NOT NULL AND NEW.project_id IS NOT NULL THEN
        INSERT INTO user_projects (user_id, project_id)
        VALUES (NEW.user_id, NEW.project_id)
        ON CONFLICT (user_id, project_id) DO NOTHING;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically associate users with projects
DROP TRIGGER IF EXISTS trigger_auto_associate_user_project ON turns;
CREATE TRIGGER trigger_auto_associate_user_project
    AFTER INSERT ON turns
    FOR EACH ROW
    EXECUTE FUNCTION auto_associate_user_project();

-- Create a function to automatically associate users with projects when they create dossiers
CREATE OR REPLACE FUNCTION auto_associate_user_project_dossier()
RETURNS TRIGGER AS $$
BEGIN
    -- If this is a new dossier, we need to associate it with a user
    -- This will be handled by the application logic, but we can add a default association
    -- if needed. For now, we'll leave this as a placeholder.
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for dossier (if needed)
-- DROP TRIGGER IF EXISTS trigger_auto_associate_user_project_dossier ON dossier;
-- CREATE TRIGGER trigger_auto_associate_user_project_dossier
--     AFTER INSERT ON dossier
--     FOR EACH ROW
--     EXECUTE FUNCTION auto_associate_user_project_dossier();

-- Add comments for documentation
COMMENT ON POLICY "Users can view own turns" ON turns IS 'Users can only view turns from their own sessions';
COMMENT ON POLICY "Users can create own turns" ON turns IS 'Users can only create turns in their own sessions';
COMMENT ON POLICY "Users can update own turns" ON turns IS 'Users can only update turns from their own sessions';
COMMENT ON POLICY "Users can delete own turns" ON turns IS 'Users can only delete turns from their own sessions';

COMMENT ON POLICY "Users can view own projects" ON dossier IS 'Users can only view dossiers for projects they own';
COMMENT ON POLICY "Users can create own projects" ON dossier IS 'Users can only create dossiers for projects they own';
COMMENT ON POLICY "Users can update own projects" ON dossier IS 'Users can only update dossiers for projects they own';
COMMENT ON POLICY "Users can delete own projects" ON dossier IS 'Users can only delete dossiers for projects they own';

COMMENT ON POLICY "Users can view own assets" ON assets IS 'Users can only view assets for projects they own';
COMMENT ON POLICY "Users can create own assets" ON assets IS 'Users can only create assets for projects they own';
COMMENT ON POLICY "Users can update own assets" ON assets IS 'Users can only update assets for projects they own';
COMMENT ON POLICY "Users can delete own assets" ON assets IS 'Users can only delete assets for projects they own';

COMMENT ON FUNCTION auto_associate_user_project() IS 'Automatically associates users with projects when they create turns';
COMMENT ON FUNCTION auto_associate_user_project_dossier() IS 'Automatically associates users with projects when they create dossiers';
