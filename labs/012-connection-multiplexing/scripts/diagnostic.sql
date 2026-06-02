-- ============================================================================
-- Connection Multiplexing Diagnostic Queries
-- ============================================================================

-- 1. Check current connection count by state and client address
-- Run this on the direct PostgreSQL database (port 5440)
SELECT 
    client_addr,
    application_name,
    state,
    count(*) as connection_count
FROM pg_stat_activity
WHERE usename = 'postgres'
GROUP BY client_addr, application_name, state
ORDER BY connection_count DESC;

-- 2. Inspect active queries and their execution duration
-- Helps diagnose if queries are holding locks or taking too long (which pins connections)
SELECT 
    pid,
    now() - query_start AS duration,
    state,
    query
FROM pg_stat_activity
WHERE state != 'idle' AND usename = 'postgres'
ORDER BY duration DESC;

-- 3. Show database setting details related to connections
SHOW max_connections;
SHOW superuser_reserved_connections;

-- ============================================================================
-- PgBouncer Administration Commands
-- Note: These commands cannot be run on standard PostgreSQL.
-- You must connect to the 'pgbouncer' database on the PgBouncer port (6430 or 6431)
-- Example: psql -h localhost -p 6431 -U postgres pgbouncer
-- ============================================================================

-- Show pool configuration and active clients/server connections
-- SHOW POOLS;

-- Show stats about requests, data transferred, and time spent
-- SHOW STATS;

-- Show connected client TCP connections
-- SHOW CLIENTS;

-- Show open server connections to PostgreSQL
-- SHOW SERVERS;
