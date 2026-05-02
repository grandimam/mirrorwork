# HLD — Circuit Breaker

> Layer 3: circuit breaker as a *system pattern*, not just an in-process state machine.

## 1. Requirements

**Functional**
- Trip OPEN when downstream is failing → fail fast, don't pile up
- After cool-down, allow probe requests (HALF-OPEN); close on success
- Per-downstream isolation (one failing dep doesn't trip another)
- Configurable per-route: failure threshold, timeout, success threshold

**Non-functional**
- < 100 µs decision latency (it's on every call)
- Operate per-process (no central coordinator on the hot path)
- Observable: state changes, trip events, half-open probes
- Tunable at runtime without redeploy

## 2. The pattern (recap)

```
            failures ≥ threshold
   CLOSED ──────────────────► OPEN
     ▲                          │
     │                          │ open_timeout elapses
     │ N consecutive            │
     │ successes                ▼
     └────────────────── HALF_OPEN
              ▲                  │
              │       failure    │
              └──────────────────┘
```

The L1 implementation is a **per-process** state machine — see [circuit_breaker.py](../../../revolut/src/circuit_breaker.py).

## 3. Where circuit breakers live

| Location | Pros | Cons |
|---|---|---|
| **Client library** (in caller's process) | Zero hop, fastest, isolates that one client | Every language needs its own; state per-pod |
| **Sidecar proxy** (Envoy / Linkerd) | Language-agnostic, central config | Extra hop (~1 ms); cap policy per upstream |
| **API gateway** | One place to manage | Coarse-grained; can't isolate per-pod |
| **Service mesh data plane** | Best of sidecar + control plane | Operational complexity |

**Recommendation:** sidecar (Envoy) for cross-language polyglot stacks; client library when the call is hot enough that the extra hop matters.

## 4. State scope: per-pod, not global

State is **per-process per-downstream**. A "global" circuit breaker is an anti-pattern:
- Coordination overhead on the hot path
- Single point of failure for the breaker itself
- Different pods might see different views of upstream health (they should!)

If you want global awareness, *aggregate* per-pod state into a dashboard — don't try to coordinate trip decisions.

## 5. Failure detection: count vs rate

| Method | When to use |
|---|---|
| **Consecutive failures** (L1 default) | Simple, latency-friendly; can over-trip on transient bursts |
| **Failure ratio** in a sliding window | Better steady-state behavior; needs a counter / time-bucketed sketch |
| **Latency-based** (e.g., p99 > X for Y seconds) | Catches slow-but-not-failed; harder to tune |
| **Hystrix-style: ratio + min-volume gate** | Industry standard; ignores low-volume noise |

The L1 uses consecutive-failure for simplicity. For prod, use the **ratio + min-volume** approach: trip if `error_rate > 50%` over `min_requests = 20` in last `10s`. Avoids tripping on a burst of 2 failures during low traffic.

## 6. What counts as a "failure"

Define explicitly:
- 5xx HTTP responses ✓
- Timeouts ✓
- Connection errors ✓
- 4xx? **No** — those are caller errors, not upstream failures
- Specific exception types (`ConnectionError`, `psycopg.OperationalError`, etc.)

The L1 code treats *any* exception as failure. For prod, take a `is_failure: Callable[[Exception], bool]` predicate so callers can classify.

## 7. Per-key bulkheading

Often you want isolation per **route**, **tenant**, or **user**. One slow customer shouldn't trip the breaker for everyone.

```python
class CircuitBreakerRegistry:
    _breakers: dict[str, CircuitBreaker] = {}
    def for_key(self, key: str) -> CircuitBreaker: ...
```

Memory: 1 KB per breaker × 10k keys = 10 MB. Trivial. Bound the registry with LRU eviction so a key explosion doesn't OOM.

## 8. Combining with retry, timeout, hedging

Circuit breaker is one tool. Production resilience is layered:

```
incoming request
   ↓
[ deadline ]              — total budget for this request (e.g., 2 s)
   ↓
[ rate limiter ]          — global / per-tenant cap
   ↓
[ circuit breaker ]       — fail fast if downstream is dead
   ↓
[ bulkhead (semaphore) ]  — cap concurrency to upstream
   ↓
[ retry ]                 — bounded, exponential backoff, only on idempotent ops
   ↓
[ timeout ]               — per-attempt
   ↓
upstream call
```

**Order matters:** retry *inside* the breaker (so retries count toward the failure budget); timeout *inside* retry (each attempt has its own deadline).

**Anti-pattern:** retry without circuit breaker — magnifies overload during incidents (retry storms).

## 9. Observability

| Metric | Why |
|---|---|
| `cb_state{key}` (gauge) | Current state per breaker |
| `cb_trip_total{key}` | Trip count — alert on spike |
| `cb_calls_total{key, result}` | Success / failure / blocked breakdown |
| `cb_half_open_probes_total{key, result}` | Recovery progress |
| Trace span attribute `cb.state` | See per-request what the breaker decided |

Alert on:
- Breaker stays open > 5 min (downstream not recovering)
- Trip rate > 1/min sustained (chronic issue)
- Half-open never closes (recovery loop stuck)

## 10. Configuration & rollout

Don't hardcode thresholds. Pull from config service (Consul KV, Spring Cloud Config, AWS App Config) so you can tune without redeploy.

**Default safe values to start:**
- `failure_threshold`: 50% over 20 requests in 10 s
- `open_timeout`: 30 s
- `success_threshold`: 5
- `half_open_max_calls`: 1 (single probe at a time)

Tune from production data, not first principles.

## 11. The "graceful degradation" question

When the breaker is OPEN, you have options:

1. **Fail fast** — return 503 immediately (default in L1)
2. **Fallback** — return cached data, default value, or stale response
3. **Queue** — defer until breaker closes (only for fire-and-forget writes)
4. **Degrade** — serve a simpler version of the page (no recommendations, but core works)

The L1 only does #1. Production usually needs #2 or #4 for user-facing routes.

```python
@cb.fallback(lambda: cached_response)
def get_user_profile(uid): ...
```

## 12. Failure modes of the circuit breaker itself

| Failure | Mitigation |
|---|---|
| Breaker stuck OPEN forever (downstream recovered but no probe traffic) | Bound by `open_timeout`; never permanent OPEN |
| Half-open thundering herd (many concurrent probes when timeout elapses) | `half_open_max_calls` cap (L1 has this) |
| Memory leak from unbounded per-key registry | LRU-bound the registry |
| State diverges across pods | Expected — that's per-pod design. Dashboard aggregation tells the operator |
| Bad config breaks all calls | Config validation + canary roll-out of config changes |

## 13. Testing

The L1 [test_circuit_breaker.py](../../../revolut/tests/test_circuit_breaker.py) uses a **fake clock** — critical pattern. Don't `time.sleep()` in tests:

```python
class FakeClock:
    def __call__(self): return self.t
    def advance(self, dt): self.t += dt

cb = CircuitBreaker(open_timeout=10.0, clock=clock)
```

Fast, deterministic, no flakes.

## 14. What the L1 does well

- Three-state machine, deterministic transitions
- Injectable clock for testable timing
- `guard()` context manager + `call(fn)` — two ergonomic styles
- Half-open concurrent-probe limit (often missed)
- Thread-safe via single Lock
- Custom exception hierarchy

Stops at:
- Consecutive-failure detection only (no ratio + window)
- Treats every exception as failure (no `is_failure` classifier)
- Per-process only (no cross-pod aggregation hooks)
- No fallback mechanism
- No metrics emission

Each is a layer-2/3 graduation.

## 15. What the interviewer will probe

| Question | Where |
|---|---|
| "Why not just retry?" | §8 — retry without breaker → retry storm during outage |
| "Where do you put the breaker?" | §3 — sidecar vs library tradeoffs |
| "How do you tell a transient blip from a real outage?" | §5 — ratio + window, not consecutive-count |
| "What if all your pods trip at once?" | Expected — they all see the same upstream. Operator alert + capacity / dependency check |
| "How do you recover gracefully?" | §11 — fallback / cached response / degraded mode |
| "How do you test the timing logic?" | §13 — fake clock, no real sleeps |
| "What's the difference between bulkhead and circuit breaker?" | Bulkhead = concurrency cap (semaphore); breaker = state machine on observed failures. Composed, not substituted. |
| "How does this interact with the load balancer's outlier detection?" | They overlap. LB outlier = LB ejects bad backend; CB = caller stops calling whole service. CB is finer-grained per-route. |

## 16. Tradeoffs to volunteer

- **Strict count vs rate-window** — count is simple but over-trips on bursts; rate is robust but needs a sliding-window counter
- **Per-pod state vs global state** — per-pod is independent and fast; global is consistent but adds a dependency the breaker is supposed to protect you from
- **Fail-fast vs fallback** — fast is honest but uglier UX; fallback hides outages from users (sometimes good, sometimes "silent failure")
- **Sidecar vs library** — sidecar is polyglot but adds a hop; library is fastest but per-language work
- **Tight thresholds vs loose** — tight = quick to trip (and over-trip); loose = slow to trip but stable. Start loose, tighten with data.
