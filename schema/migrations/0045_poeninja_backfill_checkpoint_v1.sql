CREATE TABLE IF NOT EXISTS poe_trade.poeninja_backfill_runs (
    run_id String,
    league String,
    requested_by String,
    chunk_size UInt32,
    total_chunks UInt32,
    created_at DateTime64(3, 'UTC') DEFAULT now(),
    started_at DateTime64(3, 'UTC'),
    finished_at DateTime64(3, 'UTC'),
    status Enum8('pending' = 1, 'running' = 2, 'completed' = 3, 'failed' = 4),
    error_message String,
    notes String
) ENGINE = ReplacingMergeTree(finished_at)
ORDER BY (run_id);

CREATE TABLE IF NOT EXISTS poe_trade.poeninja_backfill_chunks (
    run_id String,
    chunk_index UInt32,
    league String,
    chunk_start String,
    chunk_end_inclusive String,
    status Enum8('pending' = 1, 'running' = 2, 'completed' = 3, 'failed' = 4),
    retries UInt16 DEFAULT 0,
    checksum String,
    inserted_rows UInt64,
    started_at DateTime64(3, 'UTC'),
    finished_at DateTime64(3, 'UTC'),
    error_message String
) ENGINE = ReplacingMergeTree(finished_at)
ORDER BY (run_id, chunk_index);
