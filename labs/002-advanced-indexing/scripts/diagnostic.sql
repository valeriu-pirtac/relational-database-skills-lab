-- ============================================================================
-- Index Diagnostics & Performance Analysis
-- ============================================================================
-- This script provides utilities for analyzing index usage, size, and efficiency
-- Run this to understand how PostgreSQL is using (or not using) your indexes

-- ============================================================================
-- 1. List all indexes in the database with their sizes
-- ============================================================================
SELECT
    schemaname,
    relname,
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan AS number_of_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(relname::regclass)) AS table_size
FROM
    pg_stat_user_indexes
ORDER BY
    pg_relation_size(indexrelid) DESC;

-- ============================================================================
-- 2. Find unused indexes (never scanned)
-- ============================================================================
SELECT
    schemaname,
    relname,
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan
FROM
    pg_stat_user_indexes
WHERE
    idx_scan = 0
    AND indexrelid NOT IN (
        SELECT indexrelid FROM pg_index WHERE indisprimary OR indisunique
    )
ORDER BY
    pg_relation_size(indexrelid) DESC;

-- ============================================================================
-- 3. Index type breakdown
-- ============================================================================
SELECT
    i.relname,
    i.indexrelname,
    am.amname AS index_type,
    pg_size_pretty(pg_relation_size(i.indexrelid)) AS index_size,
    i.idx_scan AS scans
FROM
    pg_stat_user_indexes i
    JOIN pg_class c ON c.oid = i.indexrelid
    JOIN pg_am am ON am.oid = c.relam
ORDER BY
    i.relname, i.indexrelname;

-- ============================================================================
-- 4. Detailed index information with columns
-- ============================================================================
SELECT
    t.relname AS table_name,
    i.relname AS index_name,
    am.amname AS index_type,
    array_agg(a.attname ORDER BY a.attnum) AS column_names,
    pg_size_pretty(pg_relation_size(i.oid)) AS index_size,
    idx.indisunique AS is_unique,
    idx.indisprimary AS is_primary
FROM
    pg_index idx
    JOIN pg_class i ON i.oid = idx.indexrelid
    JOIN pg_class t ON t.oid = idx.indrelid
    JOIN pg_am am ON am.oid = i.relam
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(idx.indkey)
WHERE
    t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
GROUP BY
    t.relname, i.relname, am.amname, idx.indisunique, idx.indisprimary, i.oid
ORDER BY
    t.relname, i.relname;

-- ============================================================================
-- 5. Cache hit ratio for indexes
-- ============================================================================
SELECT
    indexrelname AS index_name,
    relname AS table_name,
    idx_blks_read AS disk_reads,
    idx_blks_hit AS cache_hits,
    CASE
        WHEN (idx_blks_hit + idx_blks_read) = 0 THEN 0
        ELSE ROUND(100.0 * idx_blks_hit / (idx_blks_hit + idx_blks_read), 2)
    END AS cache_hit_ratio
FROM
    pg_statio_user_indexes
ORDER BY
    cache_hit_ratio ASC;

-- ============================================================================
-- 6. Bloat estimate for B-Tree indexes
-- ============================================================================
SELECT
    schemaname,
    relname,
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    ROUND(100 * (pg_relation_size(indexrelid)::float / 
        NULLIF(pg_relation_size(relname::regclass), 0)), 2) AS index_to_table_ratio
FROM
    pg_stat_user_indexes
ORDER BY
    pg_relation_size(indexrelid) DESC;
