#!/bin/bash
# PostgreSQL initialization script
# This script runs when the container is first created

set -e

echo "Initializing PokerKit database..."

# Create additional extensions if needed
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable UUID extension for generating UUIDs
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

    -- Enable pg_trgm for text search optimization
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    GRANT ALL PRIVILEGES ON DATABASE $POSTGRES_DB TO $POSTGRES_USER;

    \echo 'PokerKit database initialized successfully!'
EOSQL
