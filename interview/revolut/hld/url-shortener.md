# HLD — URL Shortener

> Layer 3: bit.ly / TinyURL at scale, after the L1 in-memory and L2 SQL versions.

## 1. Requirements

**Functional**
- `POST /shorten { long_url } → { short_url }`
- `GET /{short_url} → 301/302 to long_url`
- Same long URL → same short URL (idempotent dedupe)
- Custom aliases (`POST /shorten { long_url, alias }`)
- Optional expiration (TTL)
- Click analytics: count, timestamps, referrer, geo

**Non-functional**
- 100M URLs created/day (≈ 1.2k QPS write)
- 10B redirects/day (≈ 116k QPS read) — **read:write = 100:1**
- p99 redirect latency < 50 ms (mostly DNS+TLS, not us)
- 99.99% availability for redirect path
- 5-year retention minimum

## 2. API

```
POST /api/v1/shorten
  body:    { long_url, alias?, expires_at?, owner_id? }
  → 201:   { short_url, long_url, expires_at }
  → 409:   alias already taken

GET /{short_url}
  → 301:   Location: <long_url>
  → 404:   not found / expired

DELETE /api/v1/{short_url}     (owner-only)
GET    /api/v1/{short_url}/stats
```

## 3. Estimate

```
100M new URLs/day × 365 × 5 = 180B URLs (5-yr horizon)
Each URL row: ~500 B  → 90 TB total
Plus click events: 10B/day × 200 B × 5y = 3.6 PB (analytics tier)

Write: 100M / 86400 ≈ 1.2k QPS  (peak 5×: 6k)
Read:  10B  / 86400 ≈ 116k QPS  (peak 5×: 580k)
```

## 4. Architecture

```
                              ┌──────────────┐
                       ┌─────►│ ID Generator │ (Snowflake / counter shard)
                       │      └──────────────┘
                       │
   client ──► CDN ──► API GW ──► Write service ──► Postgres (master)
                                                   ──► async ──► Kafka ──► Analytics
                       │
                       │      ┌────────────────┐
                       └─────►│ Read service   │
                              │   ↓            │
                              │ Redis cache    │ (LRU, hot keys)
                              │   ↓ miss       │
                              │ Postgres       │ (read replicas, sharded)
                              └────────────────┘
```

**Key insight:** writes and reads need *different* infrastructure. Write side is a small, careful pipeline (ID gen, dedupe, persist). Read side is a giant cache fronting a sharded DB.

## 5. ID generation strategies

| Strategy | Pros | Cons |
|---|---|---|
| **Counter + base62** (L1) | Short codes, monotonic | Single point — sharded counter or DB sequence per region |
| **Snowflake (64-bit)** | Distributed, time-ordered | 11–12 chars in base62 — longer URLs |
| **Hash(long_url) + collision retry** | Stateless, parallel | Collisions at scale (birthday paradox at √62^N) |
| **Pre-allocated key blocks** | Counter sharding without coordination per request | Each writer claims [N, N+10000) from a coordinator |

**Recommendation:** pre-allocated blocks. Each write-service pod claims a 10k-id range from a coordinator (Postgres `nextval('block_seq') * 10000`), generates locally until exhausted. Survives coordinator brief outages.

## 6. Storage schema (sharded)

```sql
short_urls (
    short_url    TEXT PRIMARY KEY,        -- shard key
    long_url     TEXT NOT NULL,
    owner_id     BIGINT,
    created_at   TIMESTAMPTZ NOT NULL,
    expires_at   TIMESTAMPTZ,
    hits         BIGINT NOT NULL DEFAULT 0
);

-- For dedupe (separate table, sharded on hash(long_url))
long_url_index (
    long_url_hash  BYTEA PRIMARY KEY,     -- sha256(long_url)[:16]
    long_url       TEXT NOT NULL,
    short_url      TEXT NOT NULL
);
```

**Sharding key:** `short_url` for the primary table (lookup is by short URL). Dedupe needs a *different* shard key — `hash(long_url)` — hence the second table. Two-shard write, but writes are 1k QPS so it's fine.

## 7. Cache layer (the read story)

```
Redirect path:
  L1 — Edge cache (CDN, 1-min TTL)        ── 90% hit
  L2 — Redis cluster (1 hr TTL, LRU)      ── 9.9% hit
  L3 — Postgres read replica              ── 0.1%
```

Math: 580k QPS × 0.001 = 580 QPS to DB. Manageable.

**Cache invalidation:** TTL-based. URLs are practically immutable (delete is rare). On `DELETE`, push invalidation to Redis + CDN purge. Rare so cost is low.

**Hot key problem:** one viral URL doing 100k QPS hits one Redis shard. Mitigation: replicate hot keys across shards, or push to in-process LRU on the read service.

## 8. Dedupe under concurrency

Two clients `POST /shorten { long_url: "X" }` simultaneously. Both miss the dedupe lookup, both insert.

**Solution:** unique constraint on `long_url_hash` + `INSERT … ON CONFLICT DO NOTHING RETURNING short_url`. Whoever loses the race reads the winner's short URL.

The L2 SQL version ([url_shortner_sql.py](../../../revolut/src/url_shortner_sql.py)) uses `pg_advisory_xact_lock` — fine for single-instance, doesn't scale. At HLD scale, the unique constraint *is* the lock.

## 9. Click analytics — separate pipeline

```
Read service ──► fire-and-forget ──► Kafka topic "clicks"
                                          │
                                          ▼
                                  ┌──────────────┐
                                  │ Stream        │
                                  │ processor     │  (Flink / KStreams)
                                  │ — aggregate  │
                                  │ — enrich     │ (geo, UA parse)
                                  └──────┬───────┘
                                         ▼
                                  ┌──────────────┐
                                  │ ClickHouse   │  (OLAP)
                                  │ /            │
                                  │ BigQuery     │
                                  └──────────────┘
```

**Why not increment `hits` on every read?** 116k writes/s on the hot table = throughput killer. Async pipeline, batch the increments (`UPDATE ... SET hits = hits + N WHERE short_url = $1`).

## 10. Custom aliases

User-supplied alias must:
- Match `[a-zA-Z0-9_-]{4,20}`
- Not be in reserved namespace (`api`, `admin`, `static`, etc.)
- Be unique → check against the same `short_urls` table

Slot custom aliases into the same keyspace as generated ones. The dedupe path differs slightly: `INSERT … ON CONFLICT (short_url) → 409`.

## 11. Expiration / cleanup

Two patterns:

**Lazy:** check `expires_at > now()` on read. Background job sweeps expired rows nightly.
**Eager:** TTL-aware Redis cache; deleted from cache instantly. Postgres swept later.

**Recommendation:** lazy + nightly partition drop (partition by `created_at` month, drop old partitions).

## 12. Failure modes

| Failure | Mitigation |
|---|---|
| ID coordinator down | Each writer has a 10k-id block buffered — survives ~10 min |
| Postgres master down | Promote replica; writes pause for 30 s; reads keep working from cache |
| Redis cluster down | DB absorbs full read load — temporarily 580 QPS, fine if DB is sized for it |
| Hot URL melts a Redis shard | Replicate hot key across shards; in-process LRU on read services |
| Kafka click pipeline backed up | Drop oldest events (analytics is best-effort) |
| Spam URL submitted | Rate limit per IP/owner; URL safety check (Google Safe Browsing API) |

## 13. Security / abuse

- **Rate limit** writes per owner / per IP (e.g., 100/min)
- **URL safety**: check against Google Safe Browsing or equivalent before shortening — async, mark `pending_review` if uncertain
- **Phishing prevention:** never shorten URLs to known phishing domains; allow user reports
- **Captcha** for anonymous writes
- **Ownership** on URLs so deletes / stats are gated

## 14. Multi-region

Writes go to a primary region; replicate async to others. Reads served from local region (cache + read replica).

For true multi-master writes (low-latency global writes), use:
- **Region prefix** in short URL (`us-AbC1`, `eu-XyZ9`) — eliminates ID conflicts
- **CRDT counters** for `hits` aggregation
- **Conflict resolution rule** for dedupe collisions (deterministic by long_url hash → assigned region)

## 15. What the L2 SQL version does well, and where it tops out

The L2 [url_shortner_sql.py](../../../revolut/src/url_shortner_sql.py) covers:
- Schema + unique constraint on long_url ✓
- `pg_advisory_xact_lock` for capacity check ✓
- LRU eviction via `ORDER BY last_accessed` ✓
- Hit counter via `UPDATE … SET hits = hits + 1` on read ✓

It tops out around **1k QPS read** (every redirect = a write to update hits). To scale past that, the click pipeline (§9) is the unlock — separate the read path from the analytics path.

## 16. Capacity

```
180B URLs × 500 B = 90 TB
Sharded across ~30 Postgres nodes (3 TB each)
Read replicas: 3× per shard for HA + read scale

Redis: 1B hot URLs × 200 B = 200 GB → 5–10 nodes with HA
CDN: handled by provider; budget 90% hit rate

Write services: 6k peak QPS / 200 QPS per pod = 30 pods
Read services: 580k peak QPS / 5k QPS per pod (cache-fronted) = 120 pods
```

## 17. What the interviewer will probe

| Question | Where |
|---|---|
| "How do you guarantee no two long URLs share a short?" | §8 — unique constraint + ON CONFLICT |
| "How do you scale to 100k QPS reads?" | §7 — multi-tier cache (CDN → Redis → DB) |
| "How short can the URL be?" | §5 — base62, log_62(N) — 7 chars covers ~3.5 trillion |
| "What if two people try the same alias at the same time?" | §10 — unique constraint, first wins |
| "How do you track clicks without killing the DB?" | §9 — async pipeline, batch updates |
| "How do you delete a URL?" | TTL + cache invalidation; eager for explicit deletes |
| "How does it work multi-region?" | §14 — region prefix, async replication |
| "How would you handle a viral link?" | §7 hot-key fanout; CDN absorbs most; in-process LRU on read pods |

## 18. Tradeoffs to volunteer

- **Counter vs hash IDs** — counter = short, requires coordination; hash = stateless, longer or risks collision
- **301 vs 302** — 301 is permanent (browser caches forever, kills your analytics); 302 forces re-resolution (more load, accurate stats). Most shorteners pick 302.
- **Sync vs async hit counting** — sync = accurate but slow; async = scalable but eventually consistent
- **Soft vs hard delete** — soft = can recover, but storage grows; hard = clean but irreversible
- **Custom aliases vs generated only** — aliases are user-friendly but introduce an attack surface (squatting, impersonation)
