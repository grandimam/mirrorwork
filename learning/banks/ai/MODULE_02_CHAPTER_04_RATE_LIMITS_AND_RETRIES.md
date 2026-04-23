# Chapter 4: Handling Rate Limits and Retries

## 4.1 Understanding Rate Limits

API providers limit requests to ensure fair usage:

| Limit Type | What It Limits |
|------------|----------------|
| RPM | Requests per minute |
| TPM | Tokens per minute |
| RPD | Requests per day |
| Concurrent | Simultaneous requests |

```python
# Typical limits (vary by tier/plan)
RATE_LIMITS = {
    "anthropic_tier1": {"rpm": 60, "tpm": 40_000},
    "anthropic_tier2": {"rpm": 1000, "tpm": 80_000},
    "openai_tier1": {"rpm": 500, "tpm": 30_000},
}
```

## 4.2 Rate Limit Errors

```python
import anthropic
from anthropic import RateLimitError

try:
    response = client.messages.create(...)
except RateLimitError as e:
    print(f"Rate limited: {e}")
    # e.response.headers may contain:
    # - retry-after: seconds to wait
    # - x-ratelimit-limit-requests
    # - x-ratelimit-remaining-requests
```

## 4.3 Basic Retry with Backoff

```python
import time
import random

def retry_with_backoff(func, max_retries=5, base_delay=1):
    """Exponential backoff with jitter"""
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            # Exponential backoff: 1s, 2s, 4s, 8s...
            delay = base_delay * (2 ** attempt)
            # Add jitter to prevent thundering herd
            delay += random.uniform(0, delay * 0.1)

            print(f"Rate limited, retrying in {delay:.1f}s...")
            time.sleep(delay)

# Usage
response = retry_with_backoff(
    lambda: client.messages.create(model="claude-3-5-sonnet", ...)
)
```

## 4.4 Using Tenacity Library

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import anthropic

@retry(
    retry=retry_if_exception_type(anthropic.RateLimitError),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(5),
)
def call_api(prompt: str):
    return client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

# Async version
@retry(
    retry=retry_if_exception_type(anthropic.RateLimitError),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(5),
)
async def call_api_async(prompt: str):
    return await async_client.messages.create(...)
```

## 4.5 Rate Limiter Implementation

```python
import asyncio
from collections import deque
from time import time

class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.window = 60  # seconds
        self.requests = deque()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = time()
            # Remove old requests
            while self.requests and self.requests[0] < now - self.window:
                self.requests.popleft()

            if len(self.requests) >= self.rpm:
                # Wait until oldest request expires
                wait_time = self.requests[0] + self.window - now
                await asyncio.sleep(wait_time)
                return await self.acquire()

            self.requests.append(now)

# Usage
limiter = RateLimiter(rpm=60)

async def rate_limited_call(prompt: str):
    await limiter.acquire()
    return await client.messages.create(...)
```

## 4.6 Token Bucket Algorithm

```python
import asyncio
import time

class TokenBucket:
    def __init__(self, tokens_per_second: float, max_tokens: int):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(
                self.max_tokens,
                self.tokens + elapsed * self.tokens_per_second
            )
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            wait_time = (tokens - self.tokens) / self.tokens_per_second
            await asyncio.sleep(wait_time)
            self.tokens = 0
            return True

# 60 RPM = 1 request per second
bucket = TokenBucket(tokens_per_second=1, max_tokens=10)
```

## 4.7 Handling Retry-After Header

```python
import anthropic

async def call_with_retry_after(prompt: str):
    while True:
        try:
            return await client.messages.create(
                model="claude-3-5-sonnet",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
        except anthropic.RateLimitError as e:
            retry_after = e.response.headers.get("retry-after")
            if retry_after:
                wait = float(retry_after)
            else:
                wait = 60  # default
            print(f"Rate limited, waiting {wait}s")
            await asyncio.sleep(wait)
```

## 4.8 Batch with Rate Limiting

```python
import asyncio

async def process_batch_with_limits(
    prompts: list,
    rpm_limit: int = 60,
    max_concurrent: int = 10
):
    semaphore = asyncio.Semaphore(max_concurrent)
    limiter = RateLimiter(rpm=rpm_limit)
    results = []

    async def process_one(prompt: str, index: int):
        async with semaphore:
            await limiter.acquire()
            try:
                response = await client.messages.create(
                    model="claude-3-5-sonnet",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                return (index, response.content[0].text, None)
            except Exception as e:
                return (index, None, str(e))

    tasks = [process_one(p, i) for i, p in enumerate(prompts)]
    results = await asyncio.gather(*tasks)

    # Sort by original index
    return sorted(results, key=lambda x: x[0])
```

## 4.9 Circuit Breaker Pattern

```python
import time

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_time=60):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failures = 0
        self.last_failure = None
        self.state = "closed"  # closed, open, half-open

    def can_proceed(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure > self.recovery_time:
                self.state = "half-open"
                return True
            return False
        return True  # half-open allows one request

    def record_success(self):
        self.failures = 0
        self.state = "closed"

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"

breaker = CircuitBreaker()

async def call_with_breaker(prompt: str):
    if not breaker.can_proceed():
        raise Exception("Circuit breaker open - service unavailable")

    try:
        response = await client.messages.create(...)
        breaker.record_success()
        return response
    except RateLimitError:
        breaker.record_failure()
        raise
```

## 4.10 Summary

| Strategy | When to Use |
|----------|-------------|
| Exponential backoff | Simple retry logic |
| Tenacity | Complex retry policies |
| Rate limiter | Proactive limit enforcement |
| Token bucket | Smooth request distribution |
| Circuit breaker | Prevent cascading failures |

**Best practices**:
- Always implement retry with backoff
- Add jitter to prevent thundering herd
- Respect retry-after headers
- Use semaphores to limit concurrency
- Monitor rate limit errors
