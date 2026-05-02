# HLD — Load Balancer

> Layer 3: how the LB looks at internet-scale, *after* you've coded the L1 in-process version and the L2 SQL version.

## 1. Requirements

**Functional**
- Distribute incoming requests across N backend servers
- Register / deregister servers at runtime (no restart)
- Health checking — eject unhealthy backends within seconds
- Multiple selection policies (round-robin, weighted, least-conn, P2C, consistent-hash)
- Graceful drain — finish in-flight requests before removing a server

**Non-functional**
- p99 selection latency < 1 ms (LB itself, not upstream)
- 99.99% availability — no single point of failure
- 1M+ RPS aggregate, 100k servers in pool max
- Zero-downtime reconfiguration (weights, policy)
- Observability: per-backend latency, error rate, in-flight, ejection events

**Out of scope** (explicitly): TLS termination policy, WAF, DDoS, multi-tenant isolation.

## 2. API

```
POST   /servers          { address, weight }      → 201
DELETE /servers/{addr}                            → 204
POST   /servers/{addr}/heartbeat                  → 200
PATCH  /servers/{addr}   { healthy }              → 200
```

Data plane is implicit — the LB is in the request path; clients don't call it explicitly.

## 3. Estimate

```
1M req/s → 86 B req/day
Each req: ~200 B selection metadata in memory
Backends: 10k–100k
Health checks: every 1s → 100k checks/s if naive (we'll batch)
```

## 4. Architecture

```
                       ┌──────────────────────┐
                       │   Control Plane       │
                       │  (xDS / Consul /      │
                       │   custom service)     │
                       └──────────┬───────────┘
                                  │ membership push
                                  │ (gRPC stream)
                                  ▼
   client ──► ┌────────────┐  ┌────────────┐  ┌────────────┐
              │ LB pod #1  │  │ LB pod #2  │  │ LB pod #N  │
              │ (Envoy /   │  │            │  │            │
              │  custom)   │  │            │  │            │
              └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
                    │               │               │
                    └───────┬───────┴───────┬───────┘
                            │               │
                            ▼               ▼
                       ┌──────────┐    ┌──────────┐
                       │ backend1 │ …  │ backendN │
                       └──────────┘    └──────────┘

       Active health checks (per LB pod, sampled)
       ─────────────────────────────────────────►
```

**Key insight:** the LB is *replicated and stateless*. The selection algorithm is the L1 code; the membership state comes from a control plane (xDS / Consul / etcd / your own).

## 5. Data plane vs control plane

| Concern | Data plane (LB pods) | Control plane |
|---|---|---|
| What | Pick a backend per request | Decide membership, weights, policy |
| Latency | μs | seconds OK |
| Scale | RPS-driven | events-driven |
| State | Local snapshot of membership | Source of truth |
| Tech | Envoy / NGINX / custom Go/Rust | xDS / Consul / etcd |

The L1 Python LB **is** the data-plane algorithm. Wrapping it as a control plane is the architectural move.

## 6. Membership propagation

Two patterns:

**Push (xDS / gRPC stream)** — control plane streams updates to LB pods. Sub-second propagation, no polling. Used by Envoy/Istio.

**Pull (DNS-SD, Consul template, K8s Endpoints API)** — LB pods periodically refresh. Simpler, ~10s lag.

**For Revolut-style internal services:** push via xDS or service mesh sidecar. The L2 SQL LB ([load_balancer_sql.py](../../../revolut/src/load_balancer_sql.py)) plays the *control plane* role here — Postgres is the source of truth, LB pods read from it (or get pushed).

## 7. Health checking — three layers

| Layer | What | Latency to detect |
|---|---|---|
| **Heartbeat** (push) | Backend pings control plane | 5–10 s |
| **Active probe** | LB hits `/healthz` every 1–5 s | 1–5 s |
| **Outlier detection** | Eject on N consecutive 5xx / latency spikes | <1 s |

Envoy's outlier detector is the reference: tracks consecutive errors, ejects for an exponential timeout, automatically un-ejects on recovery. **This is where the L1 `mark_unhealthy` / heartbeat TTL graduate to.**

## 8. Connection draining

When deregistering:
1. Control plane marks server as `DRAINING`
2. LB pods stop sending **new** requests
3. LB pods wait for in-flight count → 0 (or timeout, e.g., 30s)
4. Control plane removes from membership

The L1 `request()` context manager already tracks in-flight; promote that signal to the control plane.

## 9. Locality-aware routing

```
client (eu-west-1a) ──┐
                      │
                      ▼
       ┌────────────────────────┐
       │ LB picks within zone   │  ← prefer same-AZ backends
       │ first (90% weight),    │
       │ leaks 10% cross-AZ for │
       │ resilience             │
       └────────────────────────┘
```

`Server` gains labels: `zone`, `region`, `version`. Strategy considers them. Envoy calls this *locality-weighted load balancing*.

## 10. Consistent hashing for sticky routing

For session stickiness, cache affinity, or stateful upstreams (e.g., websockets, in-memory caches):

- Hash by `client_ip`, `cookie`, or header.
- Use **bounded-load consistent hashing** (Mirkin) — caps any one server at 1.25× average load, prevents hotspots.
- Replication factor 3 — pick top-K, fall back if primary unhealthy.

The L1 `ConsistentHashStrategy` is the algorithm; production-grade adds bounded loads and replication.

## 11. Observability

| Metric | Why |
|---|---|
| `lb_request_total{lb_pod, backend, result}` | Throughput + error rate per backend |
| `lb_request_duration_seconds{backend}` (histogram) | p50/p95/p99 |
| `lb_inflight{backend}` | Saturation |
| `lb_ejections_total{backend, reason}` | Outlier detection events |
| `lb_membership_changes_total{action}` | Control-plane churn |

**Tracing:** propagate W3C `traceparent` header so the upstream call is a child span of the client's trace.

## 12. Failure modes

| Failure | Mitigation |
|---|---|
| Control plane down | LB pods serve from last-known snapshot (cached) — fail-static, not fail-closed |
| All backends unhealthy | Return 503 with `Retry-After`; consider serving cached response |
| Single LB pod crashes | Other pods absorb traffic; client retries |
| Network partition (LB ↔ backend zone) | Locality routing keeps traffic in healthy zone |
| Hot key (consistent hash) | Bounded loads spill over; outlier detector kicks in |
| Thundering herd on backend recovery | Slow-start window: ramp traffic to recovered backend over 60 s |

## 13. Capacity planning

```
1M RPS, 100 µs selection time, 50% safety margin
→ 1M × 100µs / 1s = 100 cores busy on selection alone
→ ~16 LB pods × 8 cores each (with headroom)
```

Memory per LB pod:
```
100k backends × 200 B membership = 20 MB
Plus pool of idle conns, metrics, tracing buffers ≈ 500 MB
```

Negligible. CPU is the constraint.

## 14. Build vs buy

| Build | Buy |
|---|---|
| AWS NLB / GCP TCP LB | L4 only, regional, opaque |
| AWS ALB / GCP HTTPS LB | L7, basic policies, no advanced control plane |
| **Envoy + custom xDS control plane** | Full control, complex policies, you own observability |
| **Service mesh (Istio, Linkerd)** | Sidecar per pod, mTLS, retries, full data plane |
| HAProxy / NGINX | Battle-tested, less programmable |

**Recommendation for Revolut-scale:** Envoy data plane + custom xDS control plane backed by Postgres or etcd. Don't write your own data plane in Python — that's the L1 toy talking. Reuse Envoy and write the *policy* layer.

## 15. Migration path: L1 → L2 → L3

| Stage | Where state lives | Where selection runs | When to move |
|---|---|---|---|
| L1 | In-process dict | Same process | Single-instance services |
| L2 | Postgres | Single Python process | Few-instance, slow-domain (job dispatch) |
| L3 | etcd / Consul + xDS | Envoy pods | Real request-path LB at scale |

The L1 algorithm doesn't disappear at L3 — it gets ported to Envoy's policy plugins (or you stay on Envoy's built-ins, which implement the same algorithms in C++).

## 16. What the interviewer will probe

| Question | Where the answer lives |
|---|---|
| "How do you avoid single-point-of-failure?" | §4 — replicated stateless data plane |
| "How fast do you detect a dead backend?" | §7 — three layers, sub-second via outlier |
| "What if the control plane is down?" | §12 — fail-static from cached snapshot |
| "How do you handle a Black-Friday traffic spike?" | §10 + slow-start in §12 |
| "Why not just use AWS ALB?" | §14 — programmability ceiling |
| "How does consistent hashing avoid hotspots?" | §10 — bounded loads (Mirkin) |
| "How do you roll out a new selection policy?" | xDS push, canary by pod, observe metrics, roll back if regression |

## 17. Tradeoffs to volunteer

- **Push vs pull membership** — push is faster but couples LB pods to control plane availability. Pull is more resilient but laggier.
- **Active vs passive health check** — active catches issues earlier but adds load (100k servers × 1s = 100k probes/s). Passive (outlier) reacts to real traffic — works only when there *is* traffic.
- **Server-side LB vs client-side LB (gRPC-LB)** — server-side adds a hop; client-side scales better but every client needs the algorithm.
- **Sticky sessions vs stateless** — stickiness = cache hit rate ↑, but failover gets messy. Pay the cost only when the upstream is truly stateful.
