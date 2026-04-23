# Chapter 25: Backup and Recovery

## Overview

Database backups are your insurance against data loss. PostgreSQL offers multiple backup strategies with different trade-offs in recovery time, point-in-time capability, and operational complexity. Understanding these helps you design appropriate disaster recovery plans.

## Learning Objectives

By the end of this chapter, you will:

- Implement different backup strategies
- Perform point-in-time recovery
- Test recovery procedures
- Design backup policies for different requirements

## Resources

| Resource | Time |
|----------|------|
| Read: PostgreSQL backup documentation | 30 min |
| Hands-on: Practice backup and restore | 45 min |

## Core Concepts

### Backup Types

| Type | Method | Recovery Point | Recovery Time | Use Case |
|------|--------|---------------|---------------|----------|
| Logical (pg_dump) | SQL export | Backup time | Slow (re-import) | Small DBs, migrations |
| Physical (pg_basebackup) | File copy | Backup time | Fast (file restore) | Large DBs |
| Continuous (WAL archiving) | WAL + base | Any point in time | Fast | Production |

### Logical Backup with pg_dump

```bash
# Plain SQL format (human-readable)
pg_dump -h localhost -U postgres mydb > backup.sql

# Custom format (compressed, parallel restore)
pg_dump -h localhost -U postgres -Fc mydb > backup.dump

# Directory format (parallel dump)
pg_dump -h localhost -U postgres -Fd -j 4 mydb -f backup_dir

# Specific tables
pg_dump -h localhost -U postgres -t orders -t users mydb > tables.sql

# Exclude tables
pg_dump -h localhost -U postgres -T logs -T temp_* mydb > backup.sql

# Schema only (no data)
pg_dump -h localhost -U postgres --schema-only mydb > schema.sql

# Data only (no schema)
pg_dump -h localhost -U postgres --data-only mydb > data.sql
```

### Restore from pg_dump

```bash
# Plain SQL format
psql -h localhost -U postgres mydb < backup.sql

# Custom format (supports parallel restore)
pg_restore -h localhost -U postgres -d mydb -j 4 backup.dump

# Create database and restore
createdb -h localhost -U postgres newdb
pg_restore -h localhost -U postgres -d newdb backup.dump

# Restore specific tables
pg_restore -h localhost -U postgres -d mydb -t orders backup.dump

# Clean (drop objects before recreating)
pg_restore -h localhost -U postgres -d mydb --clean backup.dump

# List contents of backup
pg_restore -l backup.dump
```

### Physical Backup with pg_basebackup

```bash
# Basic backup
pg_basebackup -h primary -D /backup/base -U replicator -P

# With compression
pg_basebackup -h primary -D /backup/base -U replicator -P -Z 9

# As tar files
pg_basebackup -h primary -D /backup/base -U replicator -Ft -z

# Include WAL files (self-contained backup)
pg_basebackup -h primary -D /backup/base -U replicator -X stream

# Checkpoint mode (fast vs spread)
pg_basebackup -h primary -D /backup/base -U replicator --checkpoint=fast
```

### Continuous Archiving (WAL)

```ini
# postgresql.conf on primary

# Enable archiving
archive_mode = on
archive_command = 'cp %p /archive/%f'
# Or for cloud: archive_command = 'aws s3 cp %p s3://bucket/wal/%f'

wal_level = replica  # or 'logical' for logical replication
```

```bash
# Restore procedure with WAL

# 1. Stop PostgreSQL
pg_ctl stop -D /var/lib/postgresql/data

# 2. Clear data directory (or move to backup)
rm -rf /var/lib/postgresql/data/*

# 3. Restore base backup
tar -xzf /backup/base.tar.gz -C /var/lib/postgresql/data

# 4. Create recovery configuration (PG 12+)
touch /var/lib/postgresql/data/recovery.signal

# 5. Configure restore in postgresql.conf
# restore_command = 'cp /archive/%f %p'
# recovery_target_time = '2024-01-15 14:30:00'  # optional

# 6. Start PostgreSQL
pg_ctl start -D /var/lib/postgresql/data
# PostgreSQL replays WAL to target point
```

### Point-in-Time Recovery (PITR)

```ini
# postgresql.conf recovery options

# Restore WAL from archive
restore_command = 'cp /archive/%f %p'

# Recovery targets (use one)
recovery_target_time = '2024-01-15 14:30:00 UTC'
# recovery_target_xid = '12345'
# recovery_target_lsn = '0/1000000'
# recovery_target_name = 'my_restore_point'
# recovery_target = 'immediate'  # Stop after consistency point

# What to do after reaching target
recovery_target_action = 'promote'  # or 'pause', 'shutdown'

# Timeline handling
recovery_target_timeline = 'latest'  # or specific timeline ID
```

```sql
-- Create named restore points
SELECT pg_create_restore_point('before_migration');

-- After migration succeeds, can recover to this point if issues found later
```

### Backup Verification

```bash
# Verify pg_dump backup
pg_restore -l backup.dump > /dev/null && echo "Backup valid"

# Test restore to separate instance
createdb test_restore
pg_restore -d test_restore backup.dump
psql -d test_restore -c "SELECT count(*) FROM important_table"
dropdb test_restore

# Verify checksums (if enabled)
pg_checksums -c -D /backup/data
```

### Backup Scheduling

```bash
#!/bin/bash
# backup.sh - Daily backup script

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups
RETENTION_DAYS=7

# Logical backup
pg_dump -h localhost -U postgres -Fc mydb > $BACKUP_DIR/mydb_$DATE.dump

# Remove old backups
find $BACKUP_DIR -name "mydb_*.dump" -mtime +$RETENTION_DAYS -delete

# Verify
if pg_restore -l $BACKUP_DIR/mydb_$DATE.dump > /dev/null 2>&1; then
    echo "Backup successful: mydb_$DATE.dump"
else
    echo "BACKUP VERIFICATION FAILED!" | mail -s "Backup Alert" admin@example.com
fi
```

```bash
# Cron schedule
# Daily at 2 AM
0 2 * * * /opt/scripts/backup.sh >> /var/log/backup.log 2>&1
```

## Key Questions to Understand

- What's the difference between logical and physical backups?
- How do you perform point-in-time recovery?
- How do you verify backups are valid?

## Hands-On Exercises

### Exercise 1: Full Backup and Restore Cycle

```bash
# Create test database with data
psql -c "CREATE DATABASE backup_test"
psql -d backup_test -c "
    CREATE TABLE important_data (id SERIAL, value TEXT, created_at TIMESTAMP DEFAULT NOW());
    INSERT INTO important_data (value) SELECT md5(random()::text) FROM generate_series(1, 10000);
"

# Backup
pg_dump -Fc backup_test > backup_test.dump

# Simulate disaster
psql -c "DROP DATABASE backup_test"

# Restore
createdb backup_test
pg_restore -d backup_test backup_test.dump

# Verify
psql -d backup_test -c "SELECT count(*) FROM important_data"
```

### Exercise 2: Point-in-Time Recovery Setup

```bash
# Enable WAL archiving (requires restart)
# In postgresql.conf:
# archive_mode = on
# archive_command = 'cp %p /archive/%f'

# Take base backup
pg_basebackup -D /backup/base -Ft -z -P

# Make changes
psql -c "INSERT INTO important_data (value) VALUES ('after backup')"

# Create restore point
psql -c "SELECT pg_create_restore_point('before_migration')"

# Make more changes
psql -c "DELETE FROM important_data WHERE id < 1000"

# Now you can recover to 'before_migration' point
```

### Exercise 3: Backup Size Estimation

```sql
-- Estimate backup size
SELECT
    pg_size_pretty(pg_database_size(current_database())) as db_size,
    pg_size_pretty(pg_database_size(current_database()) * 0.3) as estimated_compressed_dump;

-- Per-table sizes
SELECT
    relname as table,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
    pg_size_pretty(pg_relation_size(relid)) as data_size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

## Interview Deep Dive

### Question: "Describe your PostgreSQL backup strategy."

**Answer:**
> "I use a tiered approach: daily pg_dump for quick recovery of specific tables or schemas, plus continuous WAL archiving with weekly base backups for point-in-time recovery.
>
> pg_dump in custom format (-Fc) goes to local storage, then replicated to S3 with 30-day retention. For WAL, I archive to S3 with archive_command, and take pg_basebackup weekly. This gives me PITR capability for the past week.
>
> Critically, I regularly test restores - monthly full restore to a test instance, verifying data integrity with checksums. RPO is minutes (last WAL), RTO is under an hour for full database or minutes for specific tables."

### Question: "How would you perform point-in-time recovery?"

**Answer:**
> "PITR requires continuous archiving enabled beforehand. Steps: 1) Stop PostgreSQL. 2) Clear or move the data directory. 3) Restore the most recent base backup before the target time. 4) Create recovery.signal (PG 12+) or recovery.conf. 5) Set restore_command to fetch archived WAL, and recovery_target_time to the desired point. 6) Start PostgreSQL - it replays WAL up to the target.
>
> After recovery, the database is in a new timeline to prevent confusion with the original. I'd verify data integrity then promote to accept writes, or pause at the recovery point if I need to inspect first."

## Key Takeaways

1. **pg_dump** for logical, portable backups
2. **pg_basebackup** for physical, fast backups
3. **WAL archiving** enables point-in-time recovery
4. **Test restores regularly** - untested backups aren't backups
5. **Document RTO/RPO** and ensure backup strategy meets them

## Self-Assessment Questions

1. What's the difference between pg_dump formats?
2. When would you use pg_basebackup vs pg_dump?
3. What's required for point-in-time recovery?
4. How do you verify a backup is valid?
5. What's a restore point and when would you use it?

## Next Chapter

[Chapter 26: Common Production Issues →](./26_production_issues.md)
