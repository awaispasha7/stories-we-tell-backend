-- Quick fix: Add synopsis_checklist column to validation_queue table
-- Run this in your Supabase SQL Editor

ALTER TABLE validation_queue 
ADD COLUMN IF NOT EXISTS synopsis_checklist JSONB DEFAULT '{}'::jsonb;

-- Verify the column was added
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'validation_queue' 
AND column_name = 'synopsis_checklist';

