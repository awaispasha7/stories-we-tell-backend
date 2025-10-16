-- Add password authentication support to users table
-- This migration adds password_hash column and updates RLS policies

-- Add password_hash column to users table
ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Update RLS policies to handle password authentication
-- Users can only see their own password hash (for authentication)
CREATE POLICY IF NOT EXISTS "Users can view own password hash" ON public.users
    FOR SELECT USING (user_id = auth.uid());

-- Users can update their own password hash
CREATE POLICY IF NOT EXISTS "Users can update own password hash" ON public.users
    FOR UPDATE USING (user_id = auth.uid());

-- Create an index on email for faster lookups during authentication
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);

-- Create an index on password_hash for authentication queries
CREATE INDEX IF NOT EXISTS idx_users_password_hash ON public.users(password_hash) WHERE password_hash IS NOT NULL;

-- Add a function to verify user credentials
CREATE OR REPLACE FUNCTION verify_user_credentials(
    user_email TEXT,
    user_password_hash TEXT
) RETURNS TABLE(
    user_id UUID,
    email TEXT,
    display_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        u.user_id,
        u.email,
        u.display_name,
        u.avatar_url,
        u.created_at,
        u.updated_at
    FROM public.users u
    WHERE u.email = user_email 
    AND u.password_hash = user_password_hash
    AND u.password_hash IS NOT NULL;
END;
$$;

-- Grant execute permission on the function
GRANT EXECUTE ON FUNCTION verify_user_credentials(TEXT, TEXT) TO authenticated;

-- Add a function to update user password
CREATE OR REPLACE FUNCTION update_user_password(
    user_id_param UUID,
    new_password_hash TEXT
) RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE public.users 
    SET 
        password_hash = new_password_hash,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = user_id_param;
    
    RETURN FOUND;
END;
$$;

-- Grant execute permission on the function
GRANT EXECUTE ON FUNCTION update_user_password(UUID, TEXT) TO authenticated;

-- Add a function to check if email exists
CREATE OR REPLACE FUNCTION email_exists(user_email TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN EXISTS(
        SELECT 1 FROM public.users 
        WHERE email = user_email
    );
END;
$$;

-- Grant execute permission on the function
GRANT EXECUTE ON FUNCTION email_exists(TEXT) TO authenticated;

-- Add comments for documentation
COMMENT ON COLUMN public.users.password_hash IS 'Hashed password for user authentication';
COMMENT ON FUNCTION verify_user_credentials(TEXT, TEXT) IS 'Verify user credentials for login';
COMMENT ON FUNCTION update_user_password(UUID, TEXT) IS 'Update user password hash';
COMMENT ON FUNCTION email_exists(TEXT) IS 'Check if email address is already registered';
