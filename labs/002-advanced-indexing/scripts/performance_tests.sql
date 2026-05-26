-- ============================================================================
-- Performance Testing Queries
-- ============================================================================
-- Use these queries with EXPLAIN (ANALYZE, BUFFERS) to compare performance
-- before and after adding indexes

-- ============================================================================
-- PRODUCTS TABLE QUERIES
-- ============================================================================

-- Query 1: Find active products (benefits from partial index)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, price, category
FROM products
WHERE active = true
LIMIT 100;

-- Query 2: Search JSONB attributes (benefits from GIN index)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, attributes
FROM products
WHERE attributes @> '{"color": "red"}';

-- Query 3: Search JSONB with path operation
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, attributes
FROM products
WHERE attributes->>'brand' = 'Sony';

-- Query 4: Complex JSONB query with multiple conditions
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, price, attributes
FROM products
WHERE attributes @> '{"features": ["bluetooth"]}' 
  AND active = true;

-- ============================================================================
-- ARTICLES TABLE QUERIES
-- ============================================================================

-- Query 5: Full-text search (benefits from GIN index on tsvector)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, author
FROM articles
WHERE search_vector @@ to_tsquery('english', 'postgresql & performance');

-- Query 6: Search tags in JSONB array
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, title, tags
FROM articles
WHERE tags ? 'database';

-- ============================================================================
-- SENSOR_READINGS TABLE QUERIES
-- ============================================================================

-- Query 7: Time range query (benefits from BRIN index)
EXPLAIN (ANALYZE, BUFFERS)
SELECT sensor_id, temperature, recorded_at
FROM sensor_readings
WHERE recorded_at >= NOW() - INTERVAL '7 days'
ORDER BY recorded_at DESC
LIMIT 1000;

-- Query 8: Aggregate query over time range
EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    sensor_id,
    AVG(temperature / 100.0) as avg_temp,
    COUNT(*) as reading_count
FROM sensor_readings
WHERE recorded_at >= NOW() - INTERVAL '1 day'
GROUP BY sensor_id;

-- ============================================================================
-- USERS TABLE QUERIES
-- ============================================================================

-- Query 9: Case-insensitive email search (benefits from expression index)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, username, email
FROM users
WHERE LOWER(email) = 'john.doe@example.com';

-- Query 10: Full name search (benefits from expression index)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, email, first_name, last_name
FROM users
WHERE LOWER(first_name || ' ' || last_name) LIKE '%smith%';
