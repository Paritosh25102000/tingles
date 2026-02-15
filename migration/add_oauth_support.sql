-- Migration: Add OAuth support to credentials table
-- This adds auth_provider and oauth_id columns to support Google and LinkedIn login

-- Add auth_provider column (google, linkedin, or email for traditional login)
ALTER TABLE credentials
ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(50) DEFAULT 'email';

-- Add oauth_id column to store the unique ID from OAuth provider
ALTER TABLE credentials
ADD COLUMN IF NOT EXISTS oauth_id VARCHAR(255);

-- Update existing records to have 'email' as auth_provider
UPDATE credentials
SET auth_provider = 'email'
WHERE auth_provider IS NULL;

-- Make password nullable (OAuth users won't have passwords)
ALTER TABLE credentials
ALTER COLUMN password DROP NOT NULL;

-- Create index on oauth_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_credentials_oauth_id ON credentials(oauth_id);

-- Create index on auth_provider for filtering
CREATE INDEX IF NOT EXISTS idx_credentials_auth_provider ON credentials(auth_provider);

-- Add comment to table
COMMENT ON TABLE credentials IS 'User authentication credentials. Supports email/password and OAuth (Google, LinkedIn).';
COMMENT ON COLUMN credentials.auth_provider IS 'Authentication provider: email (traditional), google, or linkedin';
COMMENT ON COLUMN credentials.oauth_id IS 'Unique identifier from OAuth provider (e.g., Google sub claim)';
