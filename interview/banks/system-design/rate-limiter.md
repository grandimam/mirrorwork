# Design a Rate Limiter

## Overview

Design a rate limiting service that controls the rate of requests a client can make to an API. Critical for preventing abuse and ensuring fair resource usage.

## Requirements to Clarify

### Functional
- Limit by what? (IP, user ID, API key)
- Different limits for different endpoints?
- Hard vs soft limits?
- What response when limited? (429, retry-after)

### Non-Functional
- Latency impact: < 1ms
- High availability
- Distributed across multiple servers
- Accuracy vs performance trade-off

## Scale Estimates

### Traffic
- 1M requests per second across all endpoints
- Rate limit check on every request
- Must be extremely fast (< 1ms)

### Storage
- Per-user state: ~100 bytes
- 10M users = 1GB
- Fits in memory

## Algorithms

### Token Bucket

```
┌─────────────────────────┐
│  Bucket (capacity=10)   │
│  ████████░░              │ (8 tokens)
│                         │
│  Refill: 1 token/sec    │
│  Request takes 1 token  │
└─────────────────────────┘
```

**Pros:** Allows bursts, smooth rate
**Cons:** Memory per bucket

### Sliding Window Log

```
Timeline: ────────────────────►
Requests: │  │    │ │  │    │
          ◄─── 1 minute ────►
Count requests in window
```

**Pros:** Accurate
**Cons:** Memory for timestamps

### Sliding Window Counter

```
Current window: 70% * prev + 100% * current
Approximation, memory efficient
```

**Pros:** Memory efficient
**Cons:** Approximate

### Fixed Window Counter

```
Window 1    Window 2    Window 3
[████]      [██░░]      [░░░░]
  10          5           0
```

**Pros:** Simple, fast
**Cons:** Burst at window edges

## High-Level Architecture

```
┌─────────┐    ┌──────────────┐    ┌──────────────┐
│ Client  │───►│ Rate Limiter │───►│ API Server   │
└─────────┘    │ (middleware) │    └──────────────┘
               └──────┬───────┘
                      │
               ┌──────▼───────┐
               │ Redis Cluster│
               └──────────────┘
```

## Deep Dive Areas

### Distributed Rate Limiting

**Challenge:** Multiple servers need consistent view

**Option A: Sticky sessions**
- Route same client to same server
- Simple but uneven load

**Option B: Centralized store**
- Redis for rate limit state
- Atomic operations (INCR, EXPIRE)
- Single point of failure

**Option C: Local + sync**
- Local rate limit
- Async sync between nodes
- Eventually consistent

### Redis Implementation

```lua
-- Token bucket in Redis
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

-- Refill tokens
local elapsed = now - last_refill
local refill = math.floor(elapsed * rate)
tokens = math.min(capacity, tokens + refill)

-- Check if request allowed
if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)
    return 1  -- allowed
else
    return 0  -- rejected
end
```

### Multi-tier Limiting

```
Tier 1: Global limit (10K RPS total)
    │
Tier 2: Per-service limit (1K RPS per service)
    │
Tier 3: Per-user limit (100 RPS per user)
```

### Response Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1609459200
Retry-After: 30
```

## Trade-offs to Discuss

### Accuracy vs Performance
- More accurate = more storage/compute
- Fixed window faster but less accurate
- Sliding window more accurate but slower

### Local vs Distributed
- Local: Fast, but inconsistent across nodes
- Distributed: Consistent, but network latency
- Hybrid: Best of both

### Hard vs Soft Limits
- Hard: Reject immediately
- Soft: Allow with degraded service
- Depends on use case

## Common Mistakes

- Not considering distributed scenario
- Ignoring race conditions
- Forgetting clock skew
- Over-engineering for simple use case
- Not handling Redis failures gracefully

## Companies That Ask This

- Stripe (API rate limiting)
- Cloudflare (DDoS protection)
- AWS (service limits)
- Any API company

## Advanced Topics

- Rate limiting by cost (expensive ops)
- Dynamic rate limits
- Rate limiting with quotas
- Fair queuing
- Circuit breaker integration
