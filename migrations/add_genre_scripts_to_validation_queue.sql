-- Migration: Add genre_scripts and selected_genre_script columns to validation_queue table
-- Date: 2025-01-XX
-- Description: Adds support for storing multiple genre-specific scripts and tracking selected genre

-- Add genre_scripts column (JSONB) to store array of genre scripts
ALTER TABLE validation_queue 
ADD COLUMN IF NOT EXISTS genre_scripts jsonb DEFAULT '[]'::jsonb;

-- Add selected_genre_script column (TEXT) to track which genre was selected
ALTER TABLE validation_queue 
ADD COLUMN IF NOT EXISTS selected_genre_script text;

-- Add comment for documentation
COMMENT ON COLUMN validation_queue.genre_scripts IS 'Array of genre-specific scripts: [{"genre": str, "script": str, "confidence": float}]';
COMMENT ON COLUMN validation_queue.selected_genre_script IS 'Which genre script was selected (e.g., "Historic Romance")';

