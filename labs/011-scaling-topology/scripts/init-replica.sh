#!/bin/sh
set -e

echo "Starting replica bootstrapper..."

# Wait for primary to accept connections
until pg_isready -h postgres_primary -p 5432 -U "$POSTGRES_USER"; do
  echo "Waiting for primary database to be ready..."
  sleep 1
done

if [ ! -s /var/lib/postgresql/data/PG_VERSION ]; then
  echo "Data directory is empty. Taking base backup from primary..."
  # Clean up directory just in case
  rm -rf /var/lib/postgresql/data/*
  
  # Run pg_basebackup using environment variables
  PGPASSWORD=$REPLICATION_PASSWORD pg_basebackup \
    -h postgres_primary \
    -D /var/lib/postgresql/data \
    -U $REPLICATION_USER \
    -Fp -Xs -P -R
    
  echo "Base backup completed successfully."
fi

echo "Starting replica PostgreSQL..."
# Execute the default entrypoint script
exec docker-entrypoint.sh postgres
