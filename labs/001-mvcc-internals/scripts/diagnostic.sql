-- =====================================================================
-- POSTGRESQL MVCC & STORAGE DIAGNOSTIC PLAYBOOK
-- =====================================================================
--
-- 1. Inspect Hidden MVCC Metadata & Physical Row Location
-- Queries the physical coordinates (ctid), insertion Tx ID (xmin), and deletion Tx ID (xmax)
SELECT
    xmin    ,
    xmax    ,
    ctid    ,
    id      ,
    username,
    balance
FROM
    users;
--
-- 2. Check Active Transactions and Lock Status
-- Run this when analyzing blocking queries or checking if active transactions are locking rows
SELECT
    pid              ,
    age(backend_xmin),
    query            ,
    state
FROM
    pg_stat_activity
WHERE
    state != 'idle'
ORDER BY
    age(backend_xmin) DESC;
--
-- 3. Query PostgreSQL Statistics Collector for Tuple Counts
-- Note: Run 'ANALYZE users;' before running this to force Postgres to refresh statistics.
SELECT
    relname    ,
    n_live_tup ,
    n_dead_tup ,
    last_vacuum,
    last_autovacuum
FROM
    pg_stat_user_tables
WHERE
    relname = 'users';
--
-- 4. Calculate Physical Storage Sizes of Tables and Indexes
-- This demonstrates physical file sizes on disk
SELECT
    pg_size_pretty(pg_relation_size('users'))       AS table_file_size,
    pg_size_pretty(pg_total_relation_size('users')) AS table_plus_indexes_size;
--
-- 5. Deep Scan Physical Storage Bloat using pgstattuple
-- Note: Requires running 'CREATE EXTENSION IF NOT EXISTS pgstattuple;' first.
-- Shows the exact ratio of live bytes to dead bytes sitting inside the 8KB storage pages.
SELECT
    table_len                                    AS total_file_bytes      ,
    pg_size_pretty(table_len)                    AS total_file_size_pretty,
    tuple_count                                  AS live_tuple_count      ,
    tuple_len                                    AS live_tuple_bytes      ,
    round(tuple_len * 100.0 / table_len, 2)      AS live_data_ratio       ,
    dead_tuple_count                                                      ,
    dead_tuple_len                               AS dead_tuple_bytes      ,
    round(dead_tuple_len * 100.0 / table_len, 2) AS bloat_percentage      ,
    free_space                                   AS empty_page_slack_bytes,
    round(free_space * 100.0 / table_len, 2)     AS empty_space_ratio
FROM
    pgstattuple('users');
--
-- 6. Inspect Autovacuum Settings for a Specific Table
-- Displays both global settings and table-specific overrides
SELECT
    relname,
    reloptions
FROM
    pg_class
WHERE
    relname = 'users';
--
-- 7. Configure Aggressive Custom Autovacuum Thresholds for High-Volume Table
-- Force autovacuum to trigger after 50 dead tuples or 5% row changes instead of the 20% default!
ALTER TABLE users
    SET ( autovacuum_enabled = true, autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_threshold = 50 );