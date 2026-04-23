# Webhook Ingestion Service with ASGI

Webhooks are HTTP callbacks -- POST requests that external services send to your server when events occur. GitHub sends a webhook when someone pushes code. Stripe sends one when a payment succeeds. Slack sends one when a user invokes a slash command. Your job is to receive these payloads, verify their authenticity, acknowledge receipt quickly, and process them reliably.

ASGI is a natural fit for this. The `receive()` callable gives you direct control over how request bodies are read. The async nature of the protocol lets you acknowledge webhooks immediately and defer processing. There is no framework magic between you and the bytes on the wire.

This document builds a complete webhook ingestion service from raw ASGI primitives.

## Table of Contents

1. [What Webhook Ingestion Is](#what-webhook-ingestion-is)
2. [Basic Webhook Receiver](#basic-webhook-receiver)
3. [Reading the Full Request Body](#reading-the-full-request-body)
4. [Signature Verification](#signature-verification)
5. [Routing Webhooks](#routing-webhooks)
6. [Idempotency](#idempotency)
7. [Fast Acknowledgment Pattern](#fast-acknowledgment-pattern)
8. [Payload Parsing and Validation](#payload-parsing-and-validation)
9. [Error Handling](#error-handling)
10. [Dead Letter Queues](#dead-letter-queues)
11. [Webhook Event Logging and Audit Trails](#webhook-event-logging-and-audit-trails)
12. [Rate Limiting Incoming Webhooks](#rate-limiting-incoming-webhooks)
13. [Multi-Tenant Webhook Routing](#multi-tenant-webhook-routing)
14. [Health Check Endpoints](#health-check-endpoints)
15. [Complete Working Implementation](#complete-working-implementation)

---

## What Webhook Ingestion Is

A webhook is a user-defined HTTP callback. When an event occurs in a third-party service, that service makes an HTTP POST request to a URL you have registered. The payload typically contains a JSON description of the event.

The flow looks like this:

```
External Service (GitHub, Stripe, Slack, ...)
    |
    |  POST /webhooks/github
    |  Headers: X-Hub-Signature-256, X-GitHub-Event, X-GitHub-Delivery
    |  Body: {"action": "opened", "pull_request": {...}}
    |
    v
Your ASGI Application
    |
    |-- 1. Read the full request body
    |-- 2. Verify the signature
    |-- 3. Respond 200 OK immediately
    |-- 4. Process the event asynchronously
    v
```

Key requirements for a webhook receiver:

- **Fast response**: Most providers expect a response within 5-30 seconds. If you take too long, they mark delivery as failed and retry.
- **Idempotent processing**: Providers retry on failure. You will receive the same event more than once. Your processing must handle duplicates.
- **Signature verification**: Payloads are not trustworthy unless you verify a cryptographic signature provided in the headers.
- **Reliable processing**: If your processing logic fails after you have already responded 200, you need a way to recover and retry.

---

## Basic Webhook Receiver

The simplest possible webhook receiver accepts a POST request, reads the body, and responds 200.

```python
async def webhook_receiver(scope, receive, send):
    """Accept a POST webhook and respond 200 OK."""
    assert scope["type"] == "http"

    # Only accept POST
    if scope["method"] != "POST":
        await send({
            "type": "http.response.start",
            "status": 405,
            "headers": [
                [b"content-type", b"text/plain"],
                [b"allow", b"POST"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b"Method Not Allowed",
        })
        return

    # Read the body (simplified -- see next section for full version)
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body", False):
            break

    # Respond 200 immediately
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"text/plain"]],
    })
    await send({
        "type": "http.response.body",
        "body": b"OK",
    })
```

This is the skeleton. Every section that follows adds a layer of robustness on top of it.

---

## Reading the Full Request Body

ASGI delivers request bodies in chunks. The `receive()` callable returns `http.request` events, each carrying a `body` bytes field and a `more_body` boolean indicating whether additional chunks follow. You must loop until `more_body` is `False` (or absent) to assemble the complete payload.

### Basic Chunked Assembly

```python
async def read_body(receive):
    """Read the complete HTTP request body from receive()."""
    body = b""
    while True:
        event = await receive()
        body += event.get("body", b"")
        if not event.get("more_body", False):
            break
    return body
```

This works, but repeated concatenation of bytes objects creates a new copy each time. For large payloads, this is inefficient.

### Efficient Assembly with bytearray

```python
async def read_body(receive):
    """Read the complete HTTP request body efficiently."""
    chunks = bytearray()
    while True:
        event = await receive()
        chunk = event.get("body", b"")
        if chunk:
            chunks.extend(chunk)
        if not event.get("more_body", False):
            break
    return bytes(chunks)
```

`bytearray.extend()` amortizes allocation. This matters when webhook payloads are large (some Stripe events can be several kilobytes; GitHub push events with many commits can be tens of kilobytes).

### Assembly with Size Limit

Webhook payloads have reasonable expected sizes. Accepting arbitrarily large bodies is a denial-of-service vector.

```python
class PayloadTooLarge(Exception):
    pass


async def read_body(receive, max_size=1_048_576):
    """Read body with a size cap (default 1 MB)."""
    chunks = bytearray()
    while True:
        event = await receive()
        chunk = event.get("body", b"")
        if chunk:
            chunks.extend(chunk)
        if len(chunks) > max_size:
            raise PayloadTooLarge(
                f"Body exceeds {max_size} bytes"
            )
        if not event.get("more_body", False):
            break
    return bytes(chunks)
```

If the limit is exceeded, the caller catches `PayloadTooLarge` and responds with 413.

### Extracting Headers

Headers in ASGI scope are a list of two-element lists of bytes. A helper to look them up:

```python
def get_header(scope, name):
    """Get a header value by lowercase name. Returns bytes or None."""
    name_lower = name.lower()
    for header_name, header_value in scope.get("headers", []):
        if header_name.decode("latin-1").lower() == name_lower:
            return header_value
    return None
```

Or, more efficiently, building a dict once:

```python
def headers_dict(scope):
    """Build a case-insensitive header lookup dict."""
    return {
        k.decode("latin-1").lower(): v
        for k, v in scope.get("headers", [])
    }
```

---

## Signature Verification

Any publicly reachable URL will receive junk traffic. You must verify that incoming webhooks actually come from the service they claim to come from. Most providers use HMAC-SHA256 signatures.

### HMAC-SHA256 Verification (GitHub Style)

GitHub sends a `X-Hub-Signature-256` header containing `sha256=<hex_digest>`. The digest is computed over the raw request body using a shared secret.

```python
import hashlib
import hmac


def verify_github_signature(body, secret, signature_header):
    """
    Verify a GitHub webhook signature.

    Args:
        body: Raw request body bytes.
        secret: The webhook secret (bytes).
        signature_header: Value of X-Hub-Signature-256 header (bytes).

    Returns:
        True if valid, False otherwise.
    """
    if not signature_header:
        return False

    sig_str = signature_header.decode("utf-8")
    if not sig_str.startswith("sha256="):
        return False

    expected_sig = sig_str[7:]  # Strip "sha256=" prefix

    computed = hmac.new(
        secret,
        body,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison -- critical for security
    return hmac.compare_digest(computed, expected_sig)
```

### HMAC-SHA256 Verification (Stripe Style)

Stripe sends a `Stripe-Signature` header with a structured format: `t=<timestamp>,v1=<signature>`. The signed payload is `<timestamp>.<body>`.

```python
def verify_stripe_signature(body, secret, signature_header, tolerance=300):
    """
    Verify a Stripe webhook signature with timestamp validation.

    Args:
        body: Raw request body bytes.
        secret: The webhook signing secret (bytes).
        signature_header: Value of Stripe-Signature header (bytes).
        tolerance: Maximum age in seconds (default 5 minutes).

    Returns:
        True if valid, False otherwise.
    """
    import time

    if not signature_header:
        return False

    sig_str = signature_header.decode("utf-8")

    # Parse structured header: t=...,v1=...
    elements = {}
    for part in sig_str.split(","):
        key, _, value = part.partition("=")
        elements[key.strip()] = value.strip()

    timestamp = elements.get("t")
    signature = elements.get("v1")

    if not timestamp or not signature:
        return False

    # Timestamp validation -- prevent replay attacks
    try:
        ts = int(timestamp)
    except ValueError:
        return False

    if abs(time.time() - ts) > tolerance:
        return False

    # Stripe signs "<timestamp>.<body>"
    signed_payload = f"{timestamp}.".encode() + body
    computed = hmac.new(
        secret,
        signed_payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, signature)
```

### Timestamp Validation

Timestamp validation prevents replay attacks. Without it, an attacker who intercepts a valid webhook payload can re-send it indefinitely. With it, the window is limited to the tolerance (typically 5 minutes).

```python
import time


def validate_timestamp(timestamp_str, tolerance=300):
    """
    Validate that a timestamp is within the acceptable window.

    Args:
        timestamp_str: Unix timestamp as a string.
        tolerance: Maximum allowed age in seconds.

    Returns:
        True if the timestamp is within tolerance.

    Raises:
        ValueError: If the timestamp is not a valid integer.
    """
    ts = int(timestamp_str)
    now = time.time()
    return abs(now - ts) <= tolerance
```

### Constant-Time Comparison

This deserves emphasis. Never use `==` to compare signatures:

```python
# WRONG -- vulnerable to timing attacks
if computed_signature == provided_signature:
    ...

# RIGHT -- constant-time comparison
import hmac
if hmac.compare_digest(computed_signature, provided_signature):
    ...
```

With `==`, Python short-circuits on the first differing byte. An attacker can measure response times to determine how many leading bytes of their forged signature match the real one, and reconstruct the signature one byte at a time. `hmac.compare_digest()` always compares every byte, taking the same amount of time regardless of how many bytes match.

### Generic Signature Verifier

A reusable verifier that can be configured per provider:

```python
import hashlib
import hmac
import time


class SignatureVerifier:
    def __init__(self, secret, algorithm="sha256", tolerance=None):
        self.secret = secret if isinstance(secret, bytes) else secret.encode()
        self.algorithm = algorithm
        self.tolerance = tolerance  # seconds, or None to skip

    def compute(self, payload):
        return hmac.new(
            self.secret,
            payload,
            getattr(hashlib, self.algorithm),
        ).hexdigest()

    def verify(self, payload, provided_signature, timestamp=None):
        if self.tolerance is not None and timestamp is not None:
            try:
                ts = int(timestamp)
            except (ValueError, TypeError):
                return False
            if abs(time.time() - ts) > self.tolerance:
                return False

        computed = self.compute(payload)
        return hmac.compare_digest(computed, provided_signature)
```

---

## Routing Webhooks

In practice, you receive webhooks from multiple providers at different paths. You need a router.

### Path-Based Routing

```python
async def webhook_router(scope, receive, send):
    """Route webhooks by URL path."""
    assert scope["type"] == "http"

    path = scope["path"]
    routes = {
        "/webhooks/github": handle_github,
        "/webhooks/stripe": handle_stripe,
        "/webhooks/slack": handle_slack,
    }

    handler = routes.get(path)
    if handler is None:
        await send_response(send, 404, b"Not Found")
        return

    await handler(scope, receive, send)


async def send_response(send, status, body, content_type=b"text/plain"):
    """Helper to send a complete HTTP response."""
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [[b"content-type", content_type]],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
```

### Event-Type Routing

Within a single provider, you often want to dispatch by event type. GitHub sends the event type in the `X-GitHub-Event` header. Stripe puts it in the JSON body as `type`.

```python
async def handle_github(scope, receive, send):
    """Route GitHub webhooks by event type."""
    headers = headers_dict(scope)
    event_type = headers.get("x-github-event", b"").decode()

    body = await read_body(receive)

    # Verify signature before doing anything else
    secret = b"your-github-webhook-secret"
    signature = headers.get("x-hub-signature-256")
    if not verify_github_signature(body, secret, signature):
        await send_response(send, 401, b"Invalid signature")
        return

    # Dispatch by event type
    github_handlers = {
        "push": handle_github_push,
        "pull_request": handle_github_pr,
        "issues": handle_github_issues,
        "ping": handle_github_ping,
    }

    handler = github_handlers.get(event_type)
    if handler is None:
        # Accept but ignore unknown event types
        await send_response(send, 200, b"OK (ignored)")
        return

    await handler(body, scope, send)


async def handle_github_ping(body, scope, send):
    """Respond to GitHub ping events (sent when a webhook is first created)."""
    await send_response(send, 200, b"pong")
```

### Prefix-Based Routing with Wildcards

For more flexible routing:

```python
class WebhookRouter:
    def __init__(self):
        self.routes = {}

    def route(self, path_prefix):
        """Decorator to register a handler for a path prefix."""
        def decorator(func):
            self.routes[path_prefix] = func
            return func
        return decorator

    def match(self, path):
        """Find the handler with the longest matching prefix."""
        best_match = None
        best_length = 0
        for prefix, handler in self.routes.items():
            if path.startswith(prefix) and len(prefix) > best_length:
                best_match = handler
                best_length = len(prefix)
        return best_match

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return

        handler = self.match(scope["path"])
        if handler is None:
            await send_response(send, 404, b"Not Found")
            return

        await handler(scope, receive, send)


router = WebhookRouter()


@router.route("/webhooks/github")
async def github_webhook(scope, receive, send):
    ...


@router.route("/webhooks/stripe")
async def stripe_webhook(scope, receive, send):
    ...
```

---

## Idempotency

Webhook providers retry on failure. Some retry even on success if they do not receive your response in time (network issues, load balancer timeouts). You will process the same event more than once unless you handle duplicates.

### Event ID Tracking

Most providers include a unique delivery or event ID in the headers:

| Provider | Header / Field |
|----------|---------------|
| GitHub   | `X-GitHub-Delivery` |
| Stripe   | `Stripe-Webhook-Id` (or `id` in body) |
| Slack    | `X-Slack-Request-Timestamp` + body |

### In-Memory Idempotency Store

For a single-process deployment, a simple set with TTL:

```python
import time
import asyncio


class IdempotencyStore:
    """Track processed event IDs to prevent duplicate processing."""

    def __init__(self, ttl=86400):
        self._seen = {}  # event_id -> timestamp
        self._ttl = ttl
        self._lock = asyncio.Lock()

    async def is_duplicate(self, event_id):
        """Check if we have already processed this event ID."""
        async with self._lock:
            self._cleanup()
            if event_id in self._seen:
                return True
            self._seen[event_id] = time.time()
            return False

    def _cleanup(self):
        """Remove expired entries."""
        cutoff = time.time() - self._ttl
        expired = [
            eid for eid, ts in self._seen.items()
            if ts < cutoff
        ]
        for eid in expired:
            del self._seen[eid]


# Global instance
idempotency_store = IdempotencyStore()
```

### Using the Idempotency Store

```python
async def handle_webhook_with_idempotency(scope, receive, send):
    headers = headers_dict(scope)

    # Extract event ID (GitHub example)
    event_id = headers.get("x-github-delivery", b"").decode()
    if not event_id:
        await send_response(send, 400, b"Missing delivery ID")
        return

    # Check for duplicate
    if await idempotency_store.is_duplicate(event_id):
        # Already processed -- respond 200 so the provider stops retrying
        await send_response(send, 200, b"Already processed")
        return

    body = await read_body(receive)
    # ... verify signature, process event ...
    await send_response(send, 200, b"OK")
```

### Production Idempotency

In-memory stores do not survive restarts and do not work across multiple processes. For production, use Redis:

```python
import redis.asyncio as redis


class RedisIdempotencyStore:
    def __init__(self, redis_url="redis://localhost:6379", ttl=86400):
        self._redis = redis.from_url(redis_url)
        self._ttl = ttl

    async def is_duplicate(self, event_id):
        """Returns True if the event was already seen."""
        # SET with NX: only sets if key does not exist
        # Returns True if key was set (new event), None if it already existed
        was_set = await self._redis.set(
            f"webhook:seen:{event_id}",
            "1",
            nx=True,
            ex=self._ttl,
        )
        return was_set is None  # None means key existed -> duplicate
```

---

## Fast Acknowledgment Pattern

The most important architectural decision in webhook ingestion: respond first, process later.

Webhook providers have tight timeout windows. GitHub gives you 10 seconds. Stripe gives you a bit more but will retry aggressively. If your processing takes longer than the timeout, the provider marks the delivery as failed and sends it again, creating duplicates and wasted work.

The solution is to decouple acknowledgment from processing.

### Using asyncio.create_task()

The simplest approach: fire off a background task and return 200 immediately.

```python
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


async def process_github_event(event_id, event_type, payload):
    """Process a GitHub webhook event (runs in background)."""
    try:
        data = json.loads(payload)
        # ... your actual processing logic ...
        logger.info(f"Processed {event_type} event {event_id}")
    except Exception:
        logger.exception(f"Failed to process {event_type} event {event_id}")
        # In production, push to dead letter queue here


async def handle_github_fast(scope, receive, send):
    """Handle GitHub webhook with fast acknowledgment."""
    headers = headers_dict(scope)
    body = await read_body(receive)

    # Verify signature synchronously -- this is fast
    secret = b"your-secret"
    signature = headers.get("x-hub-signature-256")
    if not verify_github_signature(body, secret, signature):
        await send_response(send, 401, b"Invalid signature")
        return

    event_id = headers.get("x-github-delivery", b"").decode()
    event_type = headers.get("x-github-event", b"").decode()

    # Check idempotency synchronously
    if await idempotency_store.is_duplicate(event_id):
        await send_response(send, 200, b"Already processed")
        return

    # Fire and forget: schedule processing as a background task
    asyncio.create_task(
        process_github_event(event_id, event_type, body)
    )

    # Respond immediately
    await send_response(send, 200, b"Accepted")
```

**Caveat**: `asyncio.create_task()` tasks are not durable. If the process crashes, queued tasks are lost. This is acceptable for non-critical webhooks but not for payment notifications.

### Using a Background Task Queue

For durability, push events to an external queue (Redis, RabbitMQ, SQS) and have workers process them independently.

```python
import asyncio
import json


class WebhookTaskQueue:
    """
    Async-safe in-process queue for webhook processing.
    In production, replace with Redis/RabbitMQ/SQS.
    """

    def __init__(self, max_workers=10):
        self._queue = asyncio.Queue()
        self._max_workers = max_workers
        self._workers = []

    async def start(self):
        """Start worker tasks."""
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker(i))
            self._workers.append(task)

    async def stop(self):
        """Gracefully shut down workers."""
        for _ in self._workers:
            await self._queue.put(None)  # Sentinel
        await asyncio.gather(*self._workers)

    async def enqueue(self, event_id, event_type, payload):
        """Add a webhook event to the processing queue."""
        await self._queue.put({
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
        })

    async def _worker(self, worker_id):
        """Worker loop that processes events from the queue."""
        while True:
            item = await self._queue.get()
            if item is None:
                break
            try:
                await self._process(item)
            except Exception:
                logger.exception(
                    f"Worker {worker_id}: failed to process "
                    f"event {item['event_id']}"
                )
            finally:
                self._queue.task_done()

    async def _process(self, item):
        """Override this or register handlers."""
        data = json.loads(item["payload"])
        # ... dispatch to appropriate handler ...


# Initialize during lifespan
task_queue = WebhookTaskQueue(max_workers=10)
```

### Integrating the Queue with ASGI Lifespan

```python
async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            event = await receive()
            if event["type"] == "lifespan.startup":
                await task_queue.start()
                await send({"type": "lifespan.startup.complete"})
            elif event["type"] == "lifespan.shutdown":
                await task_queue.stop()
                await send({"type": "lifespan.shutdown.complete"})
                return
    elif scope["type"] == "http":
        await webhook_router(scope, receive, send)
```

---

## Payload Parsing and Validation

After receiving and verifying the body, you need to parse it. Webhook payloads are almost always JSON, but not always well-formed.

### Safe JSON Parsing

```python
import json


def parse_json_payload(body):
    """
    Parse a JSON webhook payload.

    Returns:
        Parsed dict on success.

    Raises:
        ValueError: If the body is not valid JSON.
    """
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid JSON payload: {exc}") from exc
```

### Schema Validation

Validate the structure of incoming payloads to catch malformed events early:

```python
def validate_github_push_event(data):
    """
    Validate the structure of a GitHub push event.

    Returns:
        List of error messages (empty if valid).
    """
    errors = []

    if not isinstance(data, dict):
        return ["Payload must be a JSON object"]

    required_fields = ["ref", "repository", "pusher", "commits"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "repository" in data:
        repo = data["repository"]
        if not isinstance(repo, dict):
            errors.append("'repository' must be an object")
        elif "full_name" not in repo:
            errors.append("'repository.full_name' is required")

    return errors


def validate_stripe_event(data):
    """Validate the structure of a Stripe event."""
    errors = []

    if not isinstance(data, dict):
        return ["Payload must be a JSON object"]

    for field in ["id", "type", "data"]:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "data" in data and "object" not in data.get("data", {}):
        errors.append("'data.object' is required")

    return errors
```

### Content-Type Validation

Some providers send `application/x-www-form-urlencoded` instead of JSON (Slack, for example). Handle both:

```python
from urllib.parse import parse_qs


def parse_payload(body, content_type):
    """Parse webhook payload based on Content-Type."""
    if content_type and b"application/json" in content_type:
        return json.loads(body)
    elif content_type and b"application/x-www-form-urlencoded" in content_type:
        decoded = body.decode("utf-8")
        parsed = parse_qs(decoded)
        # Slack sends JSON inside a "payload" form field
        if "payload" in parsed:
            return json.loads(parsed["payload"][0])
        return parsed
    else:
        # Attempt JSON, fall back to raw bytes
        try:
            return json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return body
```

---

## Error Handling

What you return on failure matters. Webhook providers use your HTTP status code to decide whether to retry.

### Status Code Semantics for Webhooks

| Status Code | Meaning to Provider | Provider Behavior |
|-------------|--------------------|--------------------|
| 200-299     | Success            | Mark as delivered, no retry |
| 400         | Bad request        | Varies -- some retry, some don't |
| 401/403     | Auth failure       | Usually no retry (your config is wrong) |
| 404         | Not found          | Usually no retry |
| 410         | Gone               | Permanently disable this webhook |
| 429         | Rate limited       | Retry with backoff |
| 500-599     | Server error       | Retry with backoff |

### Structured Error Responses

```python
import json
import traceback


async def send_json_response(send, status, data):
    """Send a JSON HTTP response."""
    body = json.dumps(data).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", b"application/json"],
            [b"content-length", str(len(body)).encode()],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })


async def safe_webhook_handler(scope, receive, send):
    """Webhook handler with comprehensive error handling."""
    try:
        body = await read_body(receive, max_size=1_048_576)
    except PayloadTooLarge:
        await send_json_response(send, 413, {
            "error": "payload_too_large",
            "message": "Request body exceeds 1 MB limit",
        })
        return

    headers = headers_dict(scope)

    # Signature verification
    try:
        if not verify_signature(body, headers):
            await send_json_response(send, 401, {
                "error": "invalid_signature",
                "message": "Webhook signature verification failed",
            })
            return
    except Exception:
        logger.exception("Signature verification error")
        await send_json_response(send, 500, {
            "error": "verification_error",
            "message": "Internal error during signature verification",
        })
        return

    # Parse payload
    try:
        payload = parse_json_payload(body)
    except ValueError:
        await send_json_response(send, 400, {
            "error": "invalid_payload",
            "message": "Request body is not valid JSON",
        })
        return

    # Acknowledge and process
    try:
        asyncio.create_task(process_event(payload))
        await send_json_response(send, 200, {"status": "accepted"})
    except Exception:
        logger.exception("Failed to enqueue webhook event")
        await send_json_response(send, 500, {
            "error": "processing_error",
            "message": "Failed to accept webhook event",
        })
```

### Returning 410 Gone

If you decommission a webhook endpoint, return 410 so the provider disables the webhook automatically:

```python
DECOMMISSIONED_PATHS = {"/webhooks/old-service"}


async def check_decommissioned(scope, send):
    """Return 410 for decommissioned webhook endpoints."""
    if scope["path"] in DECOMMISSIONED_PATHS:
        await send_json_response(send, 410, {
            "error": "gone",
            "message": "This webhook endpoint has been decommissioned",
        })
        return True
    return False
```

---

## Dead Letter Queues

When background processing fails, you have already responded 200 to the provider. It will not retry. You need to capture the failure and retry on your own.

### In-Memory Dead Letter Queue

```python
import asyncio
import time
import json
import logging

logger = logging.getLogger(__name__)


class DeadLetterQueue:
    """Store failed webhook events for later retry."""

    def __init__(self, max_size=10000):
        self._queue = asyncio.Queue(maxsize=max_size)
        self._retry_task = None

    async def push(self, event_id, event_type, payload, error, attempt=1):
        """Add a failed event to the dead letter queue."""
        entry = {
            "event_id": event_id,
            "event_type": event_type,
            "payload": payload,
            "error": str(error),
            "failed_at": time.time(),
            "attempt": attempt,
        }
        try:
            self._queue.put_nowait(entry)
            logger.warning(
                f"Event {event_id} added to DLQ "
                f"(attempt {attempt}): {error}"
            )
        except asyncio.QueueFull:
            logger.error(
                f"DLQ is full, dropping event {event_id}"
            )

    async def start_retry_loop(self, process_fn, interval=60, max_attempts=5):
        """Periodically retry failed events."""
        self._retry_task = asyncio.create_task(
            self._retry_loop(process_fn, interval, max_attempts)
        )

    async def _retry_loop(self, process_fn, interval, max_attempts):
        while True:
            await asyncio.sleep(interval)
            requeue = []

            while not self._queue.empty():
                try:
                    entry = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                if entry["attempt"] >= max_attempts:
                    logger.error(
                        f"Event {entry['event_id']} exhausted "
                        f"{max_attempts} retry attempts, discarding"
                    )
                    continue

                try:
                    payload = json.loads(entry["payload"])
                    await process_fn(
                        entry["event_id"],
                        entry["event_type"],
                        payload,
                    )
                    logger.info(
                        f"DLQ retry succeeded for {entry['event_id']}"
                    )
                except Exception as exc:
                    entry["attempt"] += 1
                    entry["error"] = str(exc)
                    entry["failed_at"] = time.time()
                    requeue.append(entry)

            for entry in requeue:
                try:
                    self._queue.put_nowait(entry)
                except asyncio.QueueFull:
                    logger.error("DLQ full during requeue")

    @property
    def size(self):
        return self._queue.qsize()


dlq = DeadLetterQueue()
```

### Using the DLQ in Processing

```python
async def process_event_with_dlq(event_id, event_type, body):
    """Process an event, pushing to DLQ on failure."""
    try:
        payload = json.loads(body)
        await dispatch_event(event_type, payload)
    except Exception as exc:
        await dlq.push(event_id, event_type, body, exc)
```

---

## Webhook Event Logging and Audit Trails

Every webhook received should be logged -- both for debugging delivery issues and for compliance. An audit trail lets you answer "did we receive this event?" and "what happened when we processed it?"

### Structured Event Log

```python
import time
import json
import logging
import uuid

audit_logger = logging.getLogger("webhook.audit")


class WebhookAuditLog:
    """Structured audit logging for webhook events."""

    def __init__(self):
        self._entries = []  # In production, write to a database

    def log_received(self, event_id, provider, event_type, headers, body_size):
        """Log that a webhook was received."""
        entry = {
            "log_id": str(uuid.uuid4()),
            "event_id": event_id,
            "provider": provider,
            "event_type": event_type,
            "action": "received",
            "timestamp": time.time(),
            "body_size": body_size,
            "source_ip": None,  # Extract from scope if needed
        }
        self._entries.append(entry)
        audit_logger.info(json.dumps(entry))
        return entry["log_id"]

    def log_verified(self, log_id, success):
        """Log the result of signature verification."""
        entry = {
            "log_id": log_id,
            "action": "signature_verified" if success else "signature_failed",
            "timestamp": time.time(),
        }
        self._entries.append(entry)
        audit_logger.info(json.dumps(entry))

    def log_processed(self, log_id, success, error=None, duration=None):
        """Log the result of event processing."""
        entry = {
            "log_id": log_id,
            "action": "processed" if success else "processing_failed",
            "timestamp": time.time(),
            "duration_ms": round(duration * 1000, 2) if duration else None,
            "error": str(error) if error else None,
        }
        self._entries.append(entry)
        audit_logger.info(json.dumps(entry))

    def log_duplicate(self, event_id, provider):
        """Log that a duplicate delivery was detected."""
        entry = {
            "event_id": event_id,
            "provider": provider,
            "action": "duplicate_detected",
            "timestamp": time.time(),
        }
        self._entries.append(entry)
        audit_logger.info(json.dumps(entry))


audit_log = WebhookAuditLog()
```

### Integrating Audit Logging into the Handler

```python
async def audited_webhook_handler(scope, receive, send):
    """Webhook handler with full audit logging."""
    headers = headers_dict(scope)
    body = await read_body(receive)

    event_id = headers.get("x-github-delivery", b"").decode()
    event_type = headers.get("x-github-event", b"").decode()

    # Log receipt
    log_id = audit_log.log_received(
        event_id=event_id,
        provider="github",
        event_type=event_type,
        headers={k: v.decode() for k, v in headers.items()},
        body_size=len(body),
    )

    # Verify
    secret = b"your-secret"
    sig = headers.get("x-hub-signature-256")
    valid = verify_github_signature(body, secret, sig)
    audit_log.log_verified(log_id, valid)

    if not valid:
        await send_response(send, 401, b"Invalid signature")
        return

    # Check duplicate
    if await idempotency_store.is_duplicate(event_id):
        audit_log.log_duplicate(event_id, "github")
        await send_response(send, 200, b"Already processed")
        return

    # Process in background with audit logging
    async def process_and_log():
        start = time.time()
        try:
            await dispatch_event(event_type, json.loads(body))
            duration = time.time() - start
            audit_log.log_processed(log_id, success=True, duration=duration)
        except Exception as exc:
            duration = time.time() - start
            audit_log.log_processed(
                log_id, success=False, error=exc, duration=duration
            )
            await dlq.push(event_id, event_type, body, exc)

    asyncio.create_task(process_and_log())
    await send_response(send, 200, b"Accepted")
```

---

## Rate Limiting Incoming Webhooks

Even legitimate webhook providers can overwhelm your service during event storms (mass deployments, bulk payment processing). Rate limiting protects your downstream systems.

### Token Bucket Rate Limiter

```python
import time
import asyncio


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.

    Allows `rate` requests per second with bursts up to `capacity`.
    """

    def __init__(self, rate, capacity):
        self.rate = rate          # Tokens added per second
        self.capacity = capacity  # Max tokens (burst size)
        self.tokens = capacity    # Current tokens
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """
        Attempt to acquire a token.

        Returns True if allowed, False if rate limited.
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate,
            )
            self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


class PerProviderRateLimiter:
    """Rate limit webhooks per provider/source."""

    def __init__(self, default_rate=100, default_capacity=200):
        self._limiters = {}
        self._default_rate = default_rate
        self._default_capacity = default_capacity

    def _get_limiter(self, key):
        if key not in self._limiters:
            self._limiters[key] = TokenBucketRateLimiter(
                self._default_rate,
                self._default_capacity,
            )
        return self._limiters[key]

    async def check(self, provider):
        limiter = self._get_limiter(provider)
        return await limiter.acquire()


rate_limiter = PerProviderRateLimiter(rate=100, capacity=200)
```

### Applying Rate Limiting

```python
async def rate_limited_webhook(scope, receive, send):
    """Webhook handler with rate limiting."""
    # Determine provider from path
    path = scope["path"]
    provider = path.split("/")[-1]  # e.g., "github" from "/webhooks/github"

    if not await rate_limiter.check(provider):
        # 429 tells the provider to back off
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [
                [b"content-type", b"text/plain"],
                [b"retry-after", b"60"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b"Rate limit exceeded",
        })
        return

    # Proceed with normal handling
    await webhook_router(scope, receive, send)
```

The `Retry-After` header tells well-behaved providers how long to wait before retrying.

---

## Multi-Tenant Webhook Routing

When your service handles webhooks for multiple customers or tenants, you need to route each webhook to the correct tenant's handler and configuration.

### Tenant Identification Strategies

Tenants can be identified by:

1. **Path segment**: `/webhooks/{tenant_id}/github`
2. **API key in header**: `X-Webhook-Key: tenant_abc_key_123`
3. **Query parameter**: `/webhooks/github?tenant=abc`

### Path-Based Tenant Routing

```python
class TenantConfig:
    def __init__(self, tenant_id, github_secret=None, stripe_secret=None):
        self.tenant_id = tenant_id
        self.github_secret = github_secret
        self.stripe_secret = stripe_secret


# In production, load from a database
TENANTS = {
    "acme": TenantConfig(
        "acme",
        github_secret=b"acme-github-secret",
        stripe_secret=b"acme-stripe-secret",
    ),
    "globex": TenantConfig(
        "globex",
        github_secret=b"globex-github-secret",
        stripe_secret=b"globex-stripe-secret",
    ),
}


def parse_tenant_path(path):
    """
    Parse tenant ID and provider from path.
    Expected format: /webhooks/{tenant_id}/{provider}

    Returns:
        (tenant_id, provider) or (None, None) if not matched.
    """
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "webhooks":
        return parts[1], parts[2]
    return None, None


async def multi_tenant_webhook(scope, receive, send):
    """Route webhooks to the correct tenant handler."""
    tenant_id, provider = parse_tenant_path(scope["path"])

    if tenant_id is None:
        await send_response(send, 404, b"Not Found")
        return

    tenant = TENANTS.get(tenant_id)
    if tenant is None:
        await send_response(send, 404, b"Unknown tenant")
        return

    body = await read_body(receive)
    headers = headers_dict(scope)

    # Verify with tenant-specific secret
    if provider == "github":
        secret = tenant.github_secret
        sig = headers.get("x-hub-signature-256")
        if not secret or not verify_github_signature(body, secret, sig):
            await send_response(send, 401, b"Invalid signature")
            return
    elif provider == "stripe":
        secret = tenant.stripe_secret
        sig = headers.get("stripe-signature")
        if not secret or not verify_stripe_signature(body, secret, sig):
            await send_response(send, 401, b"Invalid signature")
            return
    else:
        await send_response(send, 404, b"Unknown provider")
        return

    # Process with tenant context
    asyncio.create_task(
        process_tenant_event(tenant_id, provider, body)
    )
    await send_response(send, 200, b"Accepted")


async def process_tenant_event(tenant_id, provider, body):
    """Process a webhook event in tenant context."""
    logger.info(f"Processing {provider} event for tenant {tenant_id}")
    payload = json.loads(body)
    # ... tenant-specific logic ...
```

### API-Key-Based Tenant Identification

```python
# Mapping of API keys to tenant IDs
API_KEY_TO_TENANT = {
    b"whk_acme_abc123": "acme",
    b"whk_globex_def456": "globex",
}


async def api_key_tenant_webhook(scope, receive, send):
    """Identify tenant by API key in header."""
    headers = headers_dict(scope)
    api_key = headers.get("x-webhook-key")

    if not api_key:
        await send_json_response(send, 401, {
            "error": "missing_api_key",
            "message": "X-Webhook-Key header is required",
        })
        return

    tenant_id = API_KEY_TO_TENANT.get(api_key)
    if tenant_id is None:
        await send_json_response(send, 401, {
            "error": "invalid_api_key",
            "message": "Unknown API key",
        })
        return

    # Continue with tenant-aware processing
    body = await read_body(receive)
    asyncio.create_task(process_tenant_event(tenant_id, "generic", body))
    await send_response(send, 200, b"Accepted")
```

---

## Health Check Endpoints

Webhook providers often verify that your endpoint is alive before sending events. Some (like Slack) send a challenge request during setup. You need health check endpoints that respond correctly.

### Basic Health Check

```python
async def health_check(scope, receive, send):
    """Simple health check endpoint."""
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            [b"content-type", b"application/json"],
            [b"cache-control", b"no-cache"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": json.dumps({
            "status": "healthy",
            "timestamp": time.time(),
        }).encode(),
    })
```

### Detailed Health Check with Dependency Status

```python
async def detailed_health_check(scope, receive, send):
    """
    Health check that reports the status of dependencies.
    Useful for monitoring and alerting.
    """
    checks = {}

    # Check DLQ size
    dlq_size = dlq.size
    checks["dead_letter_queue"] = {
        "status": "ok" if dlq_size < 1000 else "degraded",
        "pending_items": dlq_size,
    }

    # Check task queue
    checks["task_queue"] = {
        "status": "ok",
        "queue_size": task_queue._queue.qsize(),
    }

    # Overall status
    overall = "healthy"
    if any(c["status"] != "ok" for c in checks.values()):
        overall = "degraded"

    status_code = 200 if overall == "healthy" else 503

    body = json.dumps({
        "status": overall,
        "timestamp": time.time(),
        "checks": checks,
    }).encode()

    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            [b"content-type", b"application/json"],
            [b"cache-control", b"no-cache"],
        ],
    })
    await send({
        "type": "http.response.body",
        "body": body,
    })
```

### Slack URL Verification Challenge

Slack sends a `url_verification` challenge when you first configure a webhook URL. You must echo back the challenge value.

```python
async def handle_slack_challenge(scope, receive, send):
    """Handle Slack URL verification challenge."""
    body = await read_body(receive)
    payload = json.loads(body)

    if payload.get("type") == "url_verification":
        challenge = payload.get("challenge", "")
        response = json.dumps({
            "challenge": challenge,
        }).encode()
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": response,
        })
        return True  # Signal that we handled it

    return False  # Not a challenge, continue normal processing
```

---

## Complete Working Implementation

This section ties every concept together into a single, runnable ASGI application. Save it as a single file and run it with any ASGI server:

```
uvicorn webhook_service:app --host 0.0.0.0 --port 8000
```

```python
"""
Complete Webhook Ingestion Service -- Raw ASGI

A production-grade webhook receiver that handles GitHub, Stripe, and Slack
webhooks with signature verification, idempotency, fast acknowledgment,
background processing, dead letter queues, rate limiting, audit logging,
multi-tenant routing, and health checks.

Run with: uvicorn webhook_service:app --host 0.0.0.0 --port 8000
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from urllib.parse import parse_qs

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("webhook_service")
audit_logger = logging.getLogger("webhook.audit")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PayloadTooLarge(Exception):
    pass


class SignatureVerificationFailed(Exception):
    pass


# ---------------------------------------------------------------------------
# ASGI Helpers
# ---------------------------------------------------------------------------

def get_headers(scope):
    """Build a dict of headers from ASGI scope. Keys are lowercase strings."""
    return {
        k.decode("latin-1").lower(): v
        for k, v in scope.get("headers", [])
    }


async def read_body(receive, max_size=1_048_576):
    """Read the complete HTTP request body with a size limit."""
    chunks = bytearray()
    while True:
        event = await receive()
        chunk = event.get("body", b"")
        if chunk:
            chunks.extend(chunk)
        if len(chunks) > max_size:
            raise PayloadTooLarge(f"Body exceeds {max_size} bytes")
        if not event.get("more_body", False):
            break
    return bytes(chunks)


async def send_response(send, status, body, content_type=b"text/plain", extra_headers=None):
    """Send a complete HTTP response."""
    headers = [[b"content-type", content_type]]
    if extra_headers:
        headers.extend(extra_headers)
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({
        "type": "http.response.body",
        "body": body if isinstance(body, bytes) else body.encode(),
    })


async def send_json(send, status, data, extra_headers=None):
    """Send a JSON HTTP response."""
    body = json.dumps(data).encode("utf-8")
    await send_response(send, status, body, b"application/json", extra_headers)


# ---------------------------------------------------------------------------
# Signature Verification
# ---------------------------------------------------------------------------

class SignatureVerifier:
    """Configurable HMAC signature verifier."""

    def __init__(self, secret, algorithm="sha256", tolerance=None):
        self.secret = secret if isinstance(secret, bytes) else secret.encode()
        self.algorithm = algorithm
        self.tolerance = tolerance

    def _compute(self, payload):
        return hmac.new(
            self.secret,
            payload,
            getattr(hashlib, self.algorithm),
        ).hexdigest()

    def verify(self, payload, signature, timestamp=None):
        if self.tolerance is not None and timestamp is not None:
            try:
                ts = int(timestamp)
            except (ValueError, TypeError):
                return False
            if abs(time.time() - ts) > self.tolerance:
                return False
        computed = self._compute(payload)
        return hmac.compare_digest(computed, signature)


def verify_github_signature(body, secret, signature_header):
    """Verify X-Hub-Signature-256 from GitHub."""
    if not signature_header:
        return False
    sig_str = signature_header.decode("utf-8")
    if not sig_str.startswith("sha256="):
        return False
    verifier = SignatureVerifier(secret)
    return verifier.verify(body, sig_str[7:])


def verify_stripe_signature(body, secret, signature_header, tolerance=300):
    """Verify Stripe-Signature header."""
    if not signature_header:
        return False
    sig_str = signature_header.decode("utf-8")
    elements = {}
    for part in sig_str.split(","):
        key, _, value = part.partition("=")
        elements[key.strip()] = value.strip()
    timestamp = elements.get("t")
    signature = elements.get("v1")
    if not timestamp or not signature:
        return False
    signed_payload = f"{timestamp}.".encode() + body
    verifier = SignatureVerifier(secret, tolerance=tolerance)
    return verifier.verify(signed_payload, signature, timestamp=timestamp)


def verify_slack_signature(body, secret, signature_header, timestamp_header, tolerance=300):
    """Verify X-Slack-Signature header."""
    if not signature_header or not timestamp_header:
        return False
    sig_str = signature_header.decode("utf-8")
    if not sig_str.startswith("v0="):
        return False
    ts = timestamp_header.decode("utf-8")
    try:
        if abs(time.time() - int(ts)) > tolerance:
            return False
    except ValueError:
        return False
    basestring = f"v0:{ts}:".encode() + body
    verifier = SignatureVerifier(secret)
    return verifier.verify(basestring, sig_str[3:])


# ---------------------------------------------------------------------------
# Idempotency Store
# ---------------------------------------------------------------------------

class IdempotencyStore:
    """Track processed event IDs to detect duplicates. TTL-based expiry."""

    def __init__(self, ttl=86400):
        self._seen = {}
        self._ttl = ttl
        self._lock = asyncio.Lock()

    async def is_duplicate(self, event_id):
        async with self._lock:
            self._cleanup()
            if event_id in self._seen:
                return True
            self._seen[event_id] = time.time()
            return False

    def _cleanup(self):
        cutoff = time.time() - self._ttl
        expired = [k for k, v in self._seen.items() if v < cutoff]
        for k in expired:
            del self._seen[k]


# ---------------------------------------------------------------------------
# Dead Letter Queue
# ---------------------------------------------------------------------------

class DeadLetterQueue:
    """Store failed webhook events for retry."""

    def __init__(self, max_size=10000):
        self._queue = asyncio.Queue(maxsize=max_size)
        self._retry_task = None

    @property
    def size(self):
        return self._queue.qsize()

    async def push(self, event_id, event_type, provider, payload, error, attempt=1):
        entry = {
            "event_id": event_id,
            "event_type": event_type,
            "provider": provider,
            "payload": payload if isinstance(payload, str) else payload.decode("utf-8", errors="replace"),
            "error": str(error),
            "failed_at": time.time(),
            "attempt": attempt,
        }
        try:
            self._queue.put_nowait(entry)
            logger.warning(f"DLQ: added event {event_id} (attempt {attempt})")
        except asyncio.QueueFull:
            logger.error(f"DLQ full, dropping event {event_id}")

    async def start_retry_loop(self, process_fn, interval=60, max_attempts=5):
        self._retry_task = asyncio.create_task(
            self._retry_loop(process_fn, interval, max_attempts)
        )

    async def stop(self):
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

    async def _retry_loop(self, process_fn, interval, max_attempts):
        while True:
            await asyncio.sleep(interval)
            requeue = []
            batch_size = self._queue.qsize()

            for _ in range(batch_size):
                try:
                    entry = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                if entry["attempt"] >= max_attempts:
                    logger.error(
                        f"DLQ: event {entry['event_id']} exhausted "
                        f"{max_attempts} attempts, discarding"
                    )
                    continue

                try:
                    await process_fn(
                        entry["event_id"],
                        entry["event_type"],
                        json.loads(entry["payload"]),
                    )
                    logger.info(f"DLQ: retry succeeded for {entry['event_id']}")
                except Exception as exc:
                    entry["attempt"] += 1
                    entry["error"] = str(exc)
                    entry["failed_at"] = time.time()
                    requeue.append(entry)

            for entry in requeue:
                try:
                    self._queue.put_nowait(entry)
                except asyncio.QueueFull:
                    logger.error("DLQ full during requeue")


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLog:
    """Structured audit logging for webhook events."""

    def log_received(self, event_id, provider, event_type, body_size):
        log_id = str(uuid.uuid4())
        entry = {
            "log_id": log_id,
            "event_id": event_id,
            "provider": provider,
            "event_type": event_type,
            "action": "received",
            "timestamp": time.time(),
            "body_size": body_size,
        }
        audit_logger.info(json.dumps(entry))
        return log_id

    def log_verified(self, log_id, success):
        audit_logger.info(json.dumps({
            "log_id": log_id,
            "action": "signature_verified" if success else "signature_failed",
            "timestamp": time.time(),
        }))

    def log_processed(self, log_id, success, error=None, duration=None):
        audit_logger.info(json.dumps({
            "log_id": log_id,
            "action": "processed" if success else "processing_failed",
            "timestamp": time.time(),
            "duration_ms": round(duration * 1000, 2) if duration else None,
            "error": str(error) if error else None,
        }))

    def log_duplicate(self, event_id, provider):
        audit_logger.info(json.dumps({
            "event_id": event_id,
            "provider": provider,
            "action": "duplicate_detected",
            "timestamp": time.time(),
        }))


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class TokenBucketRateLimiter:
    """Token bucket rate limiter with per-key tracking."""

    def __init__(self, rate=100, capacity=200):
        self._limiters = {}
        self._rate = rate
        self._capacity = capacity
        self._lock = asyncio.Lock()

    async def acquire(self, key):
        async with self._lock:
            now = time.monotonic()
            if key not in self._limiters:
                self._limiters[key] = {
                    "tokens": self._capacity,
                    "last_refill": now,
                }

            bucket = self._limiters[key]
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(
                self._capacity,
                bucket["tokens"] + elapsed * self._rate,
            )
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True
            return False


# ---------------------------------------------------------------------------
# Tenant Configuration
# ---------------------------------------------------------------------------

class TenantConfig:
    def __init__(self, tenant_id, secrets=None):
        self.tenant_id = tenant_id
        self.secrets = secrets or {}  # {"github": b"...", "stripe": b"..."}


# Example tenants -- in production, load from a database
TENANTS = {
    "default": TenantConfig("default", {
        "github": b"change-me-github-secret",
        "stripe": b"change-me-stripe-secret",
        "slack": b"change-me-slack-secret",
    }),
}


# ---------------------------------------------------------------------------
# Event Processing (Application Logic)
# ---------------------------------------------------------------------------

async def dispatch_event(provider, event_type, payload):
    """
    Dispatch a verified webhook event to application-specific handlers.
    This is where your business logic goes.
    """
    logger.info(
        f"Processing {provider}/{event_type}: "
        f"{json.dumps(payload)[:200]}..."
    )
    # Simulate processing time
    await asyncio.sleep(0.01)


# ---------------------------------------------------------------------------
# Webhook Service (ties everything together)
# ---------------------------------------------------------------------------

class WebhookIngestionService:
    """
    Complete ASGI webhook ingestion service.

    Handles:
    - Multi-provider routing (GitHub, Stripe, Slack)
    - Signature verification per provider
    - Idempotency via event ID tracking
    - Fast acknowledgment with background processing
    - Dead letter queue for failed events
    - Structured audit logging
    - Per-provider rate limiting
    - Health check endpoints
    - Multi-tenant routing
    """

    def __init__(self):
        self.idempotency = IdempotencyStore(ttl=86400)
        self.dlq = DeadLetterQueue(max_size=10000)
        self.audit = AuditLog()
        self.rate_limiter = TokenBucketRateLimiter(rate=100, capacity=200)

    # -- ASGI entrypoint --

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        elif scope["type"] == "http":
            await self._handle_http(scope, receive, send)

    # -- Lifespan --

    async def _handle_lifespan(self, scope, receive, send):
        while True:
            event = await receive()
            if event["type"] == "lifespan.startup":
                await self.dlq.start_retry_loop(
                    self._retry_process_event,
                    interval=60,
                    max_attempts=5,
                )
                logger.info("Webhook ingestion service started")
                await send({"type": "lifespan.startup.complete"})
            elif event["type"] == "lifespan.shutdown":
                await self.dlq.stop()
                logger.info("Webhook ingestion service stopped")
                await send({"type": "lifespan.shutdown.complete"})
                return

    # -- HTTP Routing --

    async def _handle_http(self, scope, receive, send):
        path = scope["path"]
        method = scope["method"]

        # Health check endpoints (GET only)
        if path == "/health" and method == "GET":
            await self._health_check(scope, receive, send)
            return

        if path == "/health/detailed" and method == "GET":
            await self._detailed_health_check(scope, receive, send)
            return

        # Webhook endpoints (POST only)
        if not path.startswith("/webhooks/"):
            await send_json(send, 404, {"error": "not_found"})
            return

        if method != "POST":
            await send_response(
                send, 405, b"Method Not Allowed",
                extra_headers=[[b"allow", b"POST"]],
            )
            return

        # Parse path: /webhooks/{provider} or /webhooks/{tenant}/{provider}
        parts = path.strip("/").split("/")

        if len(parts) == 2:
            # /webhooks/{provider} -- use default tenant
            tenant_id, provider = "default", parts[1]
        elif len(parts) == 3:
            # /webhooks/{tenant}/{provider}
            tenant_id, provider = parts[1], parts[2]
        else:
            await send_json(send, 404, {"error": "not_found"})
            return

        tenant = TENANTS.get(tenant_id)
        if tenant is None:
            await send_json(send, 404, {"error": "unknown_tenant"})
            return

        if provider not in ("github", "stripe", "slack"):
            await send_json(send, 404, {"error": "unknown_provider"})
            return

        await self._handle_webhook(scope, receive, send, tenant, provider)

    # -- Core Webhook Handler --

    async def _handle_webhook(self, scope, receive, send, tenant, provider):
        headers = get_headers(scope)

        # Rate limiting
        if not await self.rate_limiter.acquire(f"{tenant.tenant_id}:{provider}"):
            await send_response(
                send, 429, b"Rate limit exceeded",
                extra_headers=[[b"retry-after", b"60"]],
            )
            return

        # Read body
        try:
            body = await read_body(receive, max_size=1_048_576)
        except PayloadTooLarge:
            await send_json(send, 413, {
                "error": "payload_too_large",
                "message": "Body exceeds 1 MB",
            })
            return

        # Extract event metadata per provider
        event_id, event_type = self._extract_metadata(provider, headers, body)

        # Audit: received
        log_id = self.audit.log_received(
            event_id, provider, event_type, len(body),
        )

        # Handle Slack URL verification challenge
        if provider == "slack":
            handled = await self._handle_slack_challenge(body, send)
            if handled:
                return

        # Verify signature
        secret = tenant.secrets.get(provider)
        if not secret:
            await send_json(send, 500, {
                "error": "misconfigured",
                "message": f"No secret configured for {provider}",
            })
            return

        verified = self._verify(provider, body, headers, secret)
        self.audit.log_verified(log_id, verified)

        if not verified:
            await send_json(send, 401, {
                "error": "invalid_signature",
                "message": "Signature verification failed",
            })
            return

        # Idempotency check
        if event_id and await self.idempotency.is_duplicate(event_id):
            self.audit.log_duplicate(event_id, provider)
            await send_json(send, 200, {"status": "duplicate"})
            return

        # Fast acknowledgment: respond 200, process in background
        asyncio.create_task(
            self._process_with_audit(
                log_id, event_id, event_type, provider, body,
            )
        )
        await send_json(send, 200, {"status": "accepted"})

    # -- Provider-Specific Methods --

    def _extract_metadata(self, provider, headers, body):
        """Extract event ID and event type from provider-specific locations."""
        if provider == "github":
            event_id = headers.get("x-github-delivery", b"").decode()
            event_type = headers.get("x-github-event", b"").decode()
        elif provider == "stripe":
            event_id = headers.get("stripe-webhook-id", b"").decode()
            # Event type is in the body; we will parse it later
            event_type = ""
            try:
                data = json.loads(body)
                event_type = data.get("type", "")
                if not event_id:
                    event_id = data.get("id", "")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        elif provider == "slack":
            # Slack does not provide a unique delivery ID in headers
            event_id = ""
            event_type = ""
            try:
                data = json.loads(body)
                event_id = data.get("event_id", "")
                event_type = data.get("type", "")
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        else:
            event_id = ""
            event_type = ""

        # Generate a synthetic ID if none provided
        if not event_id:
            event_id = str(uuid.uuid4())

        return event_id, event_type

    def _verify(self, provider, body, headers, secret):
        """Verify the webhook signature for the given provider."""
        if provider == "github":
            sig = headers.get("x-hub-signature-256")
            return verify_github_signature(body, secret, sig)
        elif provider == "stripe":
            sig = headers.get("stripe-signature")
            return verify_stripe_signature(body, secret, sig)
        elif provider == "slack":
            sig = headers.get("x-slack-signature")
            ts = headers.get("x-slack-request-timestamp")
            return verify_slack_signature(body, secret, sig, ts)
        return False

    async def _handle_slack_challenge(self, body, send):
        """Handle Slack url_verification challenge. Returns True if handled."""
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

        if data.get("type") == "url_verification":
            challenge = data.get("challenge", "")
            await send_json(send, 200, {"challenge": challenge})
            return True

        return False

    # -- Background Processing --

    async def _process_with_audit(self, log_id, event_id, event_type, provider, body):
        """Process an event in the background with audit logging and DLQ fallback."""
        start = time.time()
        try:
            payload = json.loads(body)
            await dispatch_event(provider, event_type, payload)
            duration = time.time() - start
            self.audit.log_processed(log_id, success=True, duration=duration)
        except Exception as exc:
            duration = time.time() - start
            self.audit.log_processed(
                log_id, success=False, error=exc, duration=duration,
            )
            await self.dlq.push(
                event_id, event_type, provider, body, exc,
            )

    async def _retry_process_event(self, event_id, event_type, payload):
        """Called by the DLQ retry loop."""
        await dispatch_event("retry", event_type, payload)

    # -- Health Checks --

    async def _health_check(self, scope, receive, send):
        await send_json(send, 200, {
            "status": "healthy",
            "timestamp": time.time(),
        })

    async def _detailed_health_check(self, scope, receive, send):
        checks = {
            "dead_letter_queue": {
                "status": "ok" if self.dlq.size < 1000 else "degraded",
                "pending_items": self.dlq.size,
            },
        }
        overall = "healthy"
        if any(c["status"] != "ok" for c in checks.values()):
            overall = "degraded"

        status_code = 200 if overall == "healthy" else 503
        await send_json(send, status_code, {
            "status": overall,
            "timestamp": time.time(),
            "checks": checks,
        })


# ---------------------------------------------------------------------------
# ASGI Application
# ---------------------------------------------------------------------------

app = WebhookIngestionService()
```

### Testing It

Send a test webhook with curl (signature verification will fail unless you compute a real HMAC, but it demonstrates the flow):

```bash
# Health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed

# GitHub webhook (will fail signature -- use for structure testing)
curl -X POST http://localhost:8000/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: test-delivery-123" \
  -H "X-Hub-Signature-256: sha256=invalid" \
  -d '{"ref": "refs/heads/main", "repository": {"full_name": "user/repo"}}'

# Multi-tenant webhook
curl -X POST http://localhost:8000/webhooks/default/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-GitHub-Delivery: test-delivery-456" \
  -H "X-Hub-Signature-256: sha256=invalid" \
  -d '{"ref": "refs/heads/main"}'
```

To test with a valid signature:

```python
import hashlib
import hmac
import json
import subprocess

secret = b"change-me-github-secret"
body = json.dumps({"ref": "refs/heads/main", "repository": {"full_name": "user/repo"}}).encode()
signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()

subprocess.run([
    "curl", "-X", "POST", "http://localhost:8000/webhooks/github",
    "-H", "Content-Type: application/json",
    "-H", f"X-GitHub-Event: push",
    "-H", f"X-GitHub-Delivery: {uuid.uuid4()}",
    "-H", f"X-Hub-Signature-256: {signature}",
    "-d", body.decode(),
])
```

### Architecture Summary

```
                    Incoming POST
                         |
                    Rate Limiter
                         |
                   Read Body (chunked)
                         |
               Extract Event Metadata
                         |
                  Verify Signature
                    /          \
                 FAIL          PASS
                  |              |
              401 JSON      Idempotency Check
                            /          \
                       DUPLICATE      NEW
                          |              |
                      200 JSON     create_task(process)
                                        |
                                   200 "Accepted"
                                        |
                            [Background Processing]
                               /              \
                           SUCCESS          FAILURE
                              |                |
                         Audit Log       Dead Letter Queue
                                              |
                                       [Retry Loop]
```

Every layer -- body reading, signature verification, idempotency, rate limiting, routing, processing, error recovery -- is built from raw ASGI primitives. No framework required.
