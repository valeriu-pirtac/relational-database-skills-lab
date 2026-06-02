#!/bin/sh
set -e

echo "Setting up replication user and configuration on Primary..."

# Create replication user using environment variables
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER $REPLICATION_USER WITH REPLICATION ENCRYPTED PASSWORD '$REPLICATION_PASSWORD';
EOSQL

# Allow replication connections in pg_hba.conf using environment variable
echo "host replication $REPLICATION_USER 0.0.0.0/0 md5" >> "$PGDATA/pg_hba.conf"

echo "Primary setup completed."
