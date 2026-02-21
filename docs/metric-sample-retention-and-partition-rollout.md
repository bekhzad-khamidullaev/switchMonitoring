# Metric Sample Retention and Partition Rollout

## Goal
- Keep `metric_sample` query latency stable for 10k+ hosts.
- Cap table growth with automatic retention.
- Prepare zero-downtime migration path to PostgreSQL native partitioning.

## Phase 1: Retention (implemented)
- Enable scheduled retention:
  - `METRIC_SAMPLE_RETENTION_ENABLED=True`
  - `METRIC_SAMPLE_RETENTION_DAYS=30`
  - `METRIC_SAMPLE_RETENTION_BATCH_SIZE=20000`
  - `METRIC_SAMPLE_RETENTION_MAX_BATCHES=10`
  - `METRIC_SAMPLE_RETENTION_HOUR=2`
  - `METRIC_SAMPLE_RETENTION_MINUTE=20`
- Manual run:
```bash
python manage.py maintain_metric_samples --retention-days 30 --batch-size 20000 --max-batches 10
```
- Safe dry run:
```bash
python manage.py maintain_metric_samples --retention-days 30 --batch-size 20000 --max-batches 10 --dry-run
```

## Phase 2: Partition Preparation (PostgreSQL)
- Confirm engine:
```sql
SHOW server_version;
SELECT current_database();
```
- Baseline check:
```sql
SELECT
  COUNT(*) AS rows_total,
  MIN(ts) AS oldest_ts,
  MAX(ts) AS newest_ts
FROM metric_sample;
```
- Validate API hot-path explain plans:
```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, ts, subscription_id
FROM metric_sample
WHERE subscription_id = 123
ORDER BY ts DESC, id DESC
LIMIT 500;
```

## Phase 3: Zero-Downtime Partition Migration (playbook)
1. Create partitioned table `metric_sample_v2` (RANGE by month on `ts`) with same columns.
2. Add monthly partitions for current month and next 6 months.
3. Add matching indexes on each partition:
   - `(subscription_id, ts DESC, id DESC)`
   - `(quality, ts DESC)`
4. Start dual-write from poller into old+new table (feature flag).
5. Backfill historical data in chunks by month (`INSERT ... SELECT ... WHERE ts BETWEEN ...`).
6. Compare counts and sample checksums per day.
7. Switch reads (`api_device_timeseries`, CSV export) to `metric_sample_v2`.
8. Stop writes to old table and rename tables in one transaction window.
9. Keep old table read-only for rollback window (for example 7 days), then drop.

## Partition Retention Policy
- Drop old partitions instead of row deletes:
```sql
DROP TABLE IF EXISTS metric_sample_2025_01;
```
- Keep a scheduler that:
  - creates next month partition in advance;
  - drops partitions older than retention window.

## Operational SLO Hints
- Track:
  - p95/p99 latency for `/snmp/api/devices/{id}/timeseries`
  - rows inserted per minute
  - rows deleted/dropped per day
  - table and index bloat
