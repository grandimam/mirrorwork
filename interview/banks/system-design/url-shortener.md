# Design a URL Shortener

## Overview

Design a service like bit.ly that takes long URLs and creates short, unique URLs that redirect to the original.

## Requirements to Clarify

### Functional
- Create short URL from long URL
- Redirect short URL to original
- Custom aliases?
- Expiration?
- Analytics (click tracking)?

### Non-Functional
- Scale: How many URLs per day?
- Read vs write ratio?
- URL length constraints?
- Availability requirements?

## Scale Estimates

### Traffic
- 100M new URLs per month (write)
- 10B redirects per month (read)
- Read:Write ratio = 100:1

### Storage
- 500 bytes per URL record
- 100M * 500 bytes = 50GB per month
- 5 years = 3TB

### Bandwidth
- Reads: 10B / (30 * 24 * 3600) = ~4000 QPS
- Peaks: ~40K QPS

## High-Level Components

```
┌─────────┐    ┌──────────────┐    ┌──────────┐
│ Client  │───►│ Load Balancer│───►│ API      │
└─────────┘    └──────────────┘    │ Servers  │
                                   └────┬─────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              ┌──────────┐       ┌──────────┐       ┌──────────┐
              │ URL DB   │       │ Cache    │       │ Key Gen  │
              └──────────┘       └──────────┘       │ Service  │
                                                    └──────────┘
```

## Deep Dive Areas

### Key Generation

**Option A: Hash-based**
- MD5/SHA-256 of long URL
- Take first 6-8 characters
- Problem: Collisions

**Option B: Base62 encoding**
- Use auto-increment ID
- Encode to base62 (a-z, A-Z, 0-9)
- 6 chars = 62^6 = 56B unique URLs

**Option C: Pre-generated keys**
- Generate keys in advance
- Store in separate Key DB
- Mark as used when assigned

### Database Schema

```sql
CREATE TABLE urls (
    short_key VARCHAR(8) PRIMARY KEY,
    long_url TEXT NOT NULL,
    user_id BIGINT,
    created_at TIMESTAMP,
    expires_at TIMESTAMP,
    click_count BIGINT DEFAULT 0
);
```

### Caching Strategy

- Cache hot URLs in Redis
- LRU eviction
- 20% of URLs = 80% of traffic
- Cache size: 20% * 3TB = 600GB

### Read Path (Redirect)

1. Client requests short URL
2. Check cache → hit? return long URL
3. Cache miss → query DB
4. Update cache
5. 301/302 redirect

### Write Path (Create)

1. Validate long URL
2. Check if exists (optional dedup)
3. Generate short key
4. Store in DB
5. Return short URL

## Trade-offs to Discuss

### 301 vs 302 Redirect
- 301: Permanent, browser caches
- 302: Temporary, always hits server
- 302 better for analytics

### SQL vs NoSQL
- SQL: ACID, joins for analytics
- NoSQL: Scale, simple key-value access
- Cassandra/DynamoDB good fit

### Hash vs Counter
- Hash: No coordination, but collisions
- Counter: Coordination needed, no collisions
- Distributed counter: Zookeeper, Redis

## Common Mistakes

- Not considering scale estimates
- Ignoring cache invalidation
- Forgetting analytics requirements
- Not discussing read vs write optimization
- Overlooking security (rate limiting, spam)

## Advanced Topics

- Geo-distributed deployment
- Analytics pipeline
- Abuse prevention
- Custom domains
- A/B testing on redirects
