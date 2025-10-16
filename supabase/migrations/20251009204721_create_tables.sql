-- Migration Script: Create `turns`, `dossier`, and `assets` Tables

-- 1. Create `turns` Table
CREATE TABLE IF NOT EXISTS turns (
    turn_id UUID PRIMARY KEY,  -- Unique identifier for the chat turn
    project_id UUID,  -- Project identifier
    raw_text TEXT,  -- Raw text of the user message
    normalized_json JSONB,  -- Structured metadata in JSON format
    created_at TIMESTAMPTZ DEFAULT current_timestamp  -- Timestamp when the record was created
);

-- 2. Create `dossier` Table
CREATE TABLE IF NOT EXISTS dossier (
    project_id UUID PRIMARY KEY,  -- Unique project identifier
    snapshot_json JSONB,  -- Stores the final metadata snapshot in JSON format
    updated_at TIMESTAMPTZ DEFAULT current_timestamp  -- Timestamp when the record was last updated
);

-- 3. Create `assets` Table
CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY,  -- Unique identifier for each asset (photo, video, etc.)
    project_id UUID REFERENCES dossier(project_id),  -- Link to the corresponding project in the `dossier` table
    type TEXT,  -- Type of asset (photo, script, video, etc.)
    uri TEXT,  -- URI pointing to the location of the asset (e.g., Supabase Storage URI)
    notes TEXT,  -- Optional notes about the asset
    vector VECTOR(1536)  -- For embeddings, if you plan to use semantic search
);

-- Optional: Create an index on the `vector` column in the `assets` table for faster semantic search (using pgvector extension)
CREATE INDEX IF NOT EXISTS idx_vector_embedding ON assets USING ivfflat (vector);
