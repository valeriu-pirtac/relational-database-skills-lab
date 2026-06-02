-- Query to check replication lag and sync state. Run this on the Primary database.
SELECT
    client_addr AS replica_ip,
    state,
    sync_state,
    pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn) AS sent_lag_bytes,
    pg_wal_lsn_diff(sent_lsn, write_lsn) AS write_lag_bytes,
    pg_wal_lsn_diff(write_lsn, flush_lsn) AS flush_lag_bytes,
    pg_wal_lsn_diff(flush_lsn, replay_lsn) AS replay_lag_bytes,
    ROUND(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) / 1024.0, 2) AS total_lag_kb
FROM pg_stat_replication;
