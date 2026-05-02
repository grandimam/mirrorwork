# Module 47: Infrastructure and Scalability

## 47.1 LLM Infrastructure Challenges

```
Unique challenges of LLM applications:

1. Latency: LLM calls take 1-30+ seconds
2. Cost: $0.01-$0.10+ per request
3. Rate limits: Provider-imposed throttling
4. Memory: Large context windows = large memory
5. Reliability: External API dependencies
6. Scaling: Non-linear cost with traffic

Traditional web apps: millisecond responses, predictable resources
LLM apps: second+ responses, variable token costs
```

## 47.2 Load Balancing Across Providers

```python
from dataclasses import dataclass
from enum import Enum
import asyncio
import random

class Provider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    BEDROCK = "bedrock"

@dataclass
class ProviderConfig:
    name: Provider
    client: any
    model: str
    weight: float = 1.0
    max_rpm: int = 1000
    cost_per_1k_tokens: float = 0.01
    is_healthy: bool = True
    current_rpm: int = 0

class LoadBalancer:
    def __init__(self, providers: list[ProviderConfig]):
        self.providers = {p.name: p for p in providers}
        self.request_counts: dict[Provider, int] = {p.name: 0 for p in providers}

    def select_provider(self, strategy: str = "weighted") -> ProviderConfig:
        healthy = [p for p in self.providers.values() if p.is_healthy]
        if not healthy:
            raise RuntimeError("No healthy providers available")

        if strategy == "weighted":
            return self._weighted_selection(healthy)
        elif strategy == "round_robin":
            return self._round_robin(healthy)
        elif strategy == "least_cost":
            return self._least_cost(healthy)
        elif strategy == "least_loaded":
            return self._least_loaded(healthy)

        return random.choice(healthy)

    def _weighted_selection(self, providers: list[ProviderConfig]) -> ProviderConfig:
        total_weight = sum(p.weight for p in providers)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for provider in providers:
            cumulative += provider.weight
            if r <= cumulative:
                return provider
        return providers[-1]

    def _round_robin(self, providers: list[ProviderConfig]) -> ProviderConfig:
        min_count = min(self.request_counts[p.name] for p in providers)
        for provider in providers:
            if self.request_counts[provider.name] == min_count:
                self.request_counts[provider.name] += 1
                return provider
        return providers[0]

    def _least_cost(self, providers: list[ProviderConfig]) -> ProviderConfig:
        return min(providers, key=lambda p: p.cost_per_1k_tokens)

    def _least_loaded(self, providers: list[ProviderConfig]) -> ProviderConfig:
        return min(providers, key=lambda p: p.current_rpm / p.max_rpm)

    def mark_unhealthy(self, provider: Provider):
        if provider in self.providers:
            self.providers[provider].is_healthy = False

    def mark_healthy(self, provider: Provider):
        if provider in self.providers:
            self.providers[provider].is_healthy = True


class MultiProviderClient:
    def __init__(self, load_balancer: LoadBalancer):
        self.load_balancer = load_balancer
        self.fallback_order = [Provider.ANTHROPIC, Provider.OPENAI, Provider.AZURE]

    async def generate(self, prompt: str, **kwargs) -> str:
        errors = []

        for attempt, provider_enum in enumerate(self.fallback_order):
            try:
                provider = self.load_balancer.providers.get(provider_enum)
                if not provider or not provider.is_healthy:
                    continue

                response = await self._call_provider(provider, prompt, **kwargs)
                return response

            except RateLimitError as e:
                errors.append((provider_enum, e))
                self.load_balancer.mark_unhealthy(provider_enum)
                asyncio.create_task(self._health_check_later(provider_enum, 60))

            except Exception as e:
                errors.append((provider_enum, e))

        raise RuntimeError(f"All providers failed: {errors}")

    async def _call_provider(self, provider: ProviderConfig, prompt: str, **kwargs) -> str:
        # Normalize API call across providers
        if provider.name == Provider.ANTHROPIC:
            response = await provider.client.messages.create(
                model=provider.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.content[0].text

        elif provider.name == Provider.OPENAI:
            response = await provider.client.chat.completions.create(
                model=provider.model,
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content

    async def _health_check_later(self, provider: Provider, delay: int):
        await asyncio.sleep(delay)
        self.load_balancer.mark_healthy(provider)
```

## 47.3 Rate Limiting and Throttling

```python
import time
from collections import deque
from asyncio import Semaphore, Lock

class TokenBucketRateLimiter:
    """Token bucket algorithm for rate limiting"""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_and_acquire(self, tokens: int = 1):
        while not await self.acquire(tokens):
            await asyncio.sleep(0.1)


class SlidingWindowRateLimiter:
    """Sliding window rate limiter"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self.lock = Lock()

    async def acquire(self) -> bool:
        async with self.lock:
            now = time.monotonic()

            # Remove old requests
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False

    def time_until_available(self) -> float:
        if not self.requests:
            return 0
        oldest = self.requests[0]
        return max(0, self.window_seconds - (time.monotonic() - oldest))


class AdaptiveRateLimiter:
    """Adjusts rate based on response headers"""

    def __init__(self, initial_rpm: int = 100):
        self.rpm = initial_rpm
        self.limiter = SlidingWindowRateLimiter(initial_rpm, 60)

    async def acquire(self) -> bool:
        return await self.limiter.acquire()

    def update_from_headers(self, headers: dict):
        # Parse rate limit headers (varies by provider)
        remaining = headers.get("x-ratelimit-remaining-requests")
        reset_time = headers.get("x-ratelimit-reset-requests")

        if remaining is not None:
            remaining = int(remaining)
            if remaining < 10:
                # Slow down
                self.rpm = max(10, self.rpm // 2)
                self.limiter = SlidingWindowRateLimiter(self.rpm, 60)


class ConcurrencyLimiter:
    """Limit concurrent requests"""

    def __init__(self, max_concurrent: int):
        self.semaphore = Semaphore(max_concurrent)

    async def __aenter__(self):
        await self.semaphore.acquire()
        return self

    async def __aexit__(self, *args):
        self.semaphore.release()


class CompositeLimiter:
    """Combine multiple limiters"""

    def __init__(
        self,
        requests_per_minute: int,
        tokens_per_minute: int,
        max_concurrent: int
    ):
        self.rpm_limiter = SlidingWindowRateLimiter(requests_per_minute, 60)
        self.tpm_limiter = TokenBucketRateLimiter(tokens_per_minute / 60, tokens_per_minute)
        self.concurrency = ConcurrencyLimiter(max_concurrent)

    async def acquire(self, estimated_tokens: int = 1000):
        # Check all limits
        rpm_ok = await self.rpm_limiter.acquire()
        tpm_ok = await self.tpm_limiter.acquire(estimated_tokens)

        return rpm_ok and tpm_ok
```

## 47.4 Request Queuing and Prioritization

```python
import heapq
from dataclasses import dataclass, field
from typing import Callable, Awaitable
from asyncio import Queue, PriorityQueue

@dataclass(order=True)
class PrioritizedRequest:
    priority: int
    timestamp: float = field(compare=False)
    request_id: str = field(compare=False)
    payload: dict = field(compare=False)
    callback: Callable = field(compare=False)

class PriorityRequestQueue:
    """Priority queue for LLM requests"""

    def __init__(self, max_size: int = 1000):
        self.queue: list[PrioritizedRequest] = []
        self.max_size = max_size
        self.lock = Lock()

    async def enqueue(self, request: PrioritizedRequest) -> bool:
        async with self.lock:
            if len(self.queue) >= self.max_size:
                return False
            heapq.heappush(self.queue, request)
            return True

    async def dequeue(self) -> PrioritizedRequest | None:
        async with self.lock:
            if self.queue:
                return heapq.heappop(self.queue)
            return None

    def size(self) -> int:
        return len(self.queue)


class RequestProcessor:
    """Process queued requests with rate limiting"""

    def __init__(
        self,
        client,
        rate_limiter: CompositeLimiter,
        num_workers: int = 5
    ):
        self.client = client
        self.rate_limiter = rate_limiter
        self.queue = PriorityRequestQueue()
        self.num_workers = num_workers
        self.running = False

    async def submit(self, payload: dict, priority: int = 5) -> asyncio.Future:
        future = asyncio.Future()

        request = PrioritizedRequest(
            priority=priority,
            timestamp=time.time(),
            request_id=str(uuid.uuid4()),
            payload=payload,
            callback=lambda result: future.set_result(result)
        )

        await self.queue.enqueue(request)
        return future

    async def start(self):
        self.running = True
        workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.num_workers)
        ]
        await asyncio.gather(*workers)

    async def _worker(self, worker_id: int):
        while self.running:
            request = await self.queue.dequeue()
            if request is None:
                await asyncio.sleep(0.1)
                continue

            # Wait for rate limit
            await self.rate_limiter.acquire(
                estimated_tokens=request.payload.get("max_tokens", 1000)
            )

            try:
                result = await self.client.generate(**request.payload)
                request.callback({"success": True, "result": result})
            except Exception as e:
                request.callback({"success": False, "error": str(e)})

    def stop(self):
        self.running = False
```

## 47.5 Caching Strategies

```python
import hashlib
from abc import ABC, abstractmethod

class CacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> str | None:
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl: int = 3600):
        pass

    @abstractmethod
    async def delete(self, key: str):
        pass


class RedisCache(CacheBackend):
    def __init__(self, redis_client):
        self.redis = redis_client

    async def get(self, key: str) -> str | None:
        return await self.redis.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600):
        await self.redis.setex(key, ttl, value)

    async def delete(self, key: str):
        await self.redis.delete(key)


class LLMCache:
    """Cache LLM responses"""

    def __init__(self, backend: CacheBackend, embedder=None):
        self.backend = backend
        self.embedder = embedder  # For semantic caching

    def _make_key(self, prompt: str, model: str, **kwargs) -> str:
        # Deterministic key from inputs
        key_data = json.dumps({
            "prompt": prompt,
            "model": model,
            **{k: v for k, v in sorted(kwargs.items())}
        }, sort_keys=True)
        return hashlib.sha256(key_data.encode()).hexdigest()

    async def get_or_generate(
        self,
        client,
        prompt: str,
        model: str,
        ttl: int = 3600,
        **kwargs
    ) -> tuple[str, bool]:
        """Returns (response, was_cached)"""

        cache_key = self._make_key(prompt, model, **kwargs)

        # Check cache
        cached = await self.backend.get(cache_key)
        if cached:
            return cached, True

        # Generate new response
        response = await client.generate(prompt, model=model, **kwargs)

        # Cache result
        await self.backend.set(cache_key, response, ttl)

        return response, False


class SemanticCache:
    """Cache based on semantic similarity"""

    def __init__(self, embedder, vector_store, similarity_threshold: float = 0.95):
        self.embedder = embedder
        self.vector_store = vector_store
        self.threshold = similarity_threshold

    async def get(self, prompt: str) -> str | None:
        embedding = await self.embedder.embed(prompt)
        results = await self.vector_store.search(embedding, k=1)

        if results and results[0].score >= self.threshold:
            return results[0].metadata.get("response")
        return None

    async def set(self, prompt: str, response: str):
        embedding = await self.embedder.embed(prompt)
        await self.vector_store.add(
            id=hashlib.md5(prompt.encode()).hexdigest(),
            embedding=embedding,
            content=prompt,
            metadata={"response": response}
        )


class TieredCache:
    """Multiple cache layers"""

    def __init__(self, l1_cache: CacheBackend, l2_cache: CacheBackend):
        self.l1 = l1_cache  # Fast (in-memory)
        self.l2 = l2_cache  # Persistent (Redis)

    async def get(self, key: str) -> str | None:
        # Try L1 first
        value = await self.l1.get(key)
        if value:
            return value

        # Try L2
        value = await self.l2.get(key)
        if value:
            # Promote to L1
            await self.l1.set(key, value, ttl=300)
            return value

        return None

    async def set(self, key: str, value: str, ttl: int = 3600):
        # Write to both
        await asyncio.gather(
            self.l1.set(key, value, ttl=min(ttl, 300)),
            self.l2.set(key, value, ttl=ttl)
        )
```

## 47.6 Horizontal Scaling with Workers

```python
from celery import Celery
import redis

# Celery setup
celery_app = Celery(
    "llm_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    task_acks_late=True,  # Retry on worker crash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time (LLM calls are slow)
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_text(self, prompt: str, model: str, **kwargs):
    """Celery task for LLM generation"""
    try:
        client = get_llm_client()
        response = client.generate(prompt, model=model, **kwargs)
        return {"success": True, "response": response}

    except RateLimitError as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except Exception as e:
        return {"success": False, "error": str(e)}


@celery_app.task
def batch_generate(prompts: list[dict]):
    """Process multiple prompts"""
    results = []
    for p in prompts:
        result = generate_text.delay(p["prompt"], p["model"])
        results.append(result.id)
    return results


# FastAPI integration
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()

@app.post("/generate")
async def generate_endpoint(request: GenerateRequest):
    # Submit to Celery
    task = generate_text.delay(request.prompt, request.model)

    return {"task_id": task.id, "status": "queued"}


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    result = celery_app.AsyncResult(task_id)

    if result.ready():
        return {"status": "completed", "result": result.get()}
    else:
        return {"status": "pending"}
```

## 47.7 Database Optimization for RAG

```python
# PostgreSQL with pgvector optimization

CREATE_TABLES_SQL = """
-- Documents table with partitioning
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    namespace VARCHAR(255) NOT NULL
) PARTITION BY LIST (namespace);

-- Create partitions for each namespace
CREATE TABLE documents_default PARTITION OF documents DEFAULT;
CREATE TABLE documents_support PARTITION OF documents FOR VALUES IN ('support');
CREATE TABLE documents_docs PARTITION OF documents FOR VALUES IN ('docs');

-- Optimized indexes
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);  -- Adjust based on data size

CREATE INDEX ON documents USING gin (metadata);
CREATE INDEX ON documents (namespace, created_at DESC);

-- Materialized view for frequent queries
CREATE MATERIALIZED VIEW recent_documents AS
SELECT * FROM documents
WHERE created_at > NOW() - INTERVAL '7 days'
WITH DATA;

CREATE INDEX ON recent_documents USING ivfflat (embedding vector_cosine_ops);
"""


class OptimizedVectorStore:
    def __init__(self, pool):
        self.pool = pool

    async def search(
        self,
        embedding: list[float],
        namespace: str,
        k: int = 10,
        filter_metadata: dict = None
    ) -> list[dict]:
        # Use prepared statement
        query = """
        SELECT id, content, metadata,
               1 - (embedding <=> $1::vector) as similarity
        FROM documents
        WHERE namespace = $2
        """

        params = [embedding, namespace]

        if filter_metadata:
            query += " AND metadata @> $3::jsonb"
            params.append(json.dumps(filter_metadata))

        query += """
        ORDER BY embedding <=> $1::vector
        LIMIT $%d
        """ % (len(params) + 1)
        params.append(k)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            {
                "id": str(row["id"]),
                "content": row["content"],
                "metadata": row["metadata"],
                "similarity": row["similarity"]
            }
            for row in rows
        ]

    async def bulk_insert(self, documents: list[dict], namespace: str):
        """Optimized bulk insert"""
        async with self.pool.acquire() as conn:
            # Use COPY for fastest insert
            await conn.copy_records_to_table(
                "documents",
                records=[
                    (
                        doc.get("id") or str(uuid.uuid4()),
                        doc["content"],
                        doc["embedding"],
                        json.dumps(doc.get("metadata", {})),
                        namespace
                    )
                    for doc in documents
                ],
                columns=["id", "content", "embedding", "metadata", "namespace"]
            )

    async def refresh_materialized_view(self):
        async with self.pool.acquire() as conn:
            await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY recent_documents")
```

## 47.8 Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-api
  template:
    metadata:
      labels:
        app: llm-api
    spec:
      containers:
      - name: api
        image: llm-api:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        env:
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: anthropic-key
        - name: REDIS_URL
          value: "redis://redis-service:6379"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
---
# Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: llm-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: llm-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: requests_queue_length
      target:
        type: AverageValue
        averageValue: "10"
---
# Service
apiVersion: v1
kind: Service
metadata:
  name: llm-api-service
spec:
  selector:
    app: llm-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
# Ingress with rate limiting
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: llm-api-ingress
  annotations:
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: llm-api-service
            port:
              number: 80
```

## 47.9 Monitoring and Observability

```python
from prometheus_client import Counter, Histogram, Gauge
import structlog

# Metrics
llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["model", "provider", "status"]
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM request latency",
    ["model", "provider"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60]
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Total tokens processed",
    ["model", "direction"]  # input/output
)

llm_cost_dollars = Counter(
    "llm_cost_dollars",
    "Estimated cost in dollars",
    ["model", "provider"]
)

active_requests = Gauge(
    "llm_active_requests",
    "Currently processing requests"
)

queue_size = Gauge(
    "llm_queue_size",
    "Pending requests in queue"
)


class InstrumentedLLMClient:
    def __init__(self, client, provider: str):
        self.client = client
        self.provider = provider
        self.logger = structlog.get_logger()

    async def generate(self, prompt: str, model: str, **kwargs) -> str:
        start_time = time.time()
        active_requests.inc()

        try:
            response = await self.client.generate(prompt, model=model, **kwargs)

            # Record metrics
            duration = time.time() - start_time
            llm_latency_seconds.labels(model=model, provider=self.provider).observe(duration)
            llm_requests_total.labels(model=model, provider=self.provider, status="success").inc()

            # Token metrics
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            llm_tokens_total.labels(model=model, direction="input").inc(input_tokens)
            llm_tokens_total.labels(model=model, direction="output").inc(output_tokens)

            # Cost estimation
            cost = self._estimate_cost(model, input_tokens, output_tokens)
            llm_cost_dollars.labels(model=model, provider=self.provider).inc(cost)

            # Structured logging
            self.logger.info(
                "llm_request_completed",
                model=model,
                provider=self.provider,
                duration_seconds=duration,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost
            )

            return response.content[0].text

        except Exception as e:
            llm_requests_total.labels(model=model, provider=self.provider, status="error").inc()
            self.logger.error(
                "llm_request_failed",
                model=model,
                provider=self.provider,
                error=str(e)
            )
            raise

        finally:
            active_requests.dec()

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = {
            "claude-sonnet-4-20250514": (0.003, 0.015),
            "claude-3-haiku-20240307": (0.00025, 0.00125),
        }
        input_rate, output_rate = pricing.get(model, (0.01, 0.03))
        return (input_tokens * input_rate + output_tokens * output_rate) / 1000


# FastAPI middleware for request tracking
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        structlog.get_logger().info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=duration
        )

        response.headers["X-Request-ID"] = request_id
        return response
```

## 47.10 Cost Management

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class UsageBudget:
    daily_limit_usd: float
    monthly_limit_usd: float
    alert_threshold: float = 0.8

class CostManager:
    def __init__(self, redis_client, budget: UsageBudget):
        self.redis = redis_client
        self.budget = budget

    async def record_cost(self, cost_usd: float, user_id: str = None):
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        # Atomic increment
        pipe = self.redis.pipeline()
        pipe.incrbyfloat(f"cost:daily:{today}", cost_usd)
        pipe.incrbyfloat(f"cost:monthly:{month}", cost_usd)
        if user_id:
            pipe.incrbyfloat(f"cost:user:{user_id}:{today}", cost_usd)

        # Set expiry
        pipe.expire(f"cost:daily:{today}", 86400 * 2)
        pipe.expire(f"cost:monthly:{month}", 86400 * 35)

        await pipe.execute()

    async def check_budget(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        daily_cost = float(await self.redis.get(f"cost:daily:{today}") or 0)
        monthly_cost = float(await self.redis.get(f"cost:monthly:{month}") or 0)

        return {
            "daily_cost": daily_cost,
            "daily_limit": self.budget.daily_limit_usd,
            "daily_remaining": max(0, self.budget.daily_limit_usd - daily_cost),
            "daily_exceeded": daily_cost >= self.budget.daily_limit_usd,
            "monthly_cost": monthly_cost,
            "monthly_limit": self.budget.monthly_limit_usd,
            "monthly_remaining": max(0, self.budget.monthly_limit_usd - monthly_cost),
            "monthly_exceeded": monthly_cost >= self.budget.monthly_limit_usd,
            "alert": (
                daily_cost >= self.budget.daily_limit_usd * self.budget.alert_threshold or
                monthly_cost >= self.budget.monthly_limit_usd * self.budget.alert_threshold
            )
        }

    async def can_proceed(self) -> bool:
        status = await self.check_budget()
        return not status["daily_exceeded"] and not status["monthly_exceeded"]


class CostAwareRouter:
    """Route to cheaper models when approaching budget"""

    def __init__(self, cost_manager: CostManager):
        self.cost_manager = cost_manager
        self.model_costs = {
            "claude-sonnet-4-20250514": 0.02,    # per 1k tokens avg
            "claude-3-haiku-20240307": 0.001,
        }

    async def select_model(self, preferred_model: str, required_quality: str = "high") -> str:
        budget = await self.cost_manager.check_budget()

        # If under 50% of daily budget, use preferred
        if budget["daily_remaining"] > budget["daily_limit"] * 0.5:
            return preferred_model

        # If between 20-50%, use cheaper for low-priority
        if budget["daily_remaining"] > budget["daily_limit"] * 0.2:
            if required_quality == "low":
                return "claude-3-haiku-20240307"
            return preferred_model

        # If under 20%, always use cheapest
        return "claude-3-haiku-20240307"
```

## 47.11 Summary

| Component | Tool/Strategy | Purpose |
|-----------|---------------|---------|
| Load Balancing | Multi-provider, weighted | Reliability, cost optimization |
| Rate Limiting | Token bucket, sliding window | Stay within limits |
| Queuing | Priority queue, Celery | Handle traffic spikes |
| Caching | Redis, semantic cache | Reduce costs, latency |
| Scaling | K8s HPA, workers | Handle load |
| Database | pgvector, partitioning | Fast retrieval |
| Monitoring | Prometheus, structured logs | Visibility |
| Cost | Budgets, routing | Control spending |

**Scaling guidelines:**
- Start with single provider, add fallbacks
- Cache aggressively (exact + semantic)
- Queue non-urgent requests
- Monitor tokens and costs closely
- Scale workers, not just API pods
- Partition data by namespace/tenant

**Cost optimization priorities:**
1. Cache identical requests
2. Use smaller models for simple tasks
3. Reduce unnecessary tokens in prompts
4. Batch when possible
5. Set hard budget limits
