-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schema for travel platform
CREATE SCHEMA IF NOT EXISTS travel;

-- Set search path
SET search_path TO travel, public;
