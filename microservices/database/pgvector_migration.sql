-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create vectors table for storing embeddings
CREATE TABLE IF NOT EXISTS vectors (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255) NOT NULL,
    content_type VARCHAR(255) NOT NULL,
    embedding vector(1536),
    metadata JSONB
);

-- Create index on content ID and type for faster lookups
CREATE INDEX IF NOT EXISTS idx_vectors_content ON vectors(content_type, content_id);

-- Create lookup tables table for storing shared lookup values
CREATE TABLE IF NOT EXISTS lookup_tables (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    values JSONB NOT NULL
);

-- Create metadata store table for rich entity metadata
CREATE TABLE IF NOT EXISTS metadata_store (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(255) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    metadata JSONB NOT NULL,
    UNIQUE(entity_type, entity_id)
);

-- Create index on entity type and ID for faster lookups
CREATE INDEX IF NOT EXISTS idx_metadata_entity ON metadata_store(entity_type, entity_id);

-- Add a comment to the migration
COMMENT ON EXTENSION vector IS 'vector data type for PostgreSQL used for storing OpenAI embeddings'; 