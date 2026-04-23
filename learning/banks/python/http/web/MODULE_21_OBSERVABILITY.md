# Module 21: Observability

## Overview

Observability is the ability to understand your system's internal state from its external outputs. This module covers the three pillars of observability: metrics, logging, and tracing. You'll learn to instrument, collect, and analyze telemetry data.

---

## Learning Objectives

By the end of this module, you will be able to:

1. Implement structured logging
2. Collect and expose metrics
3. Add distributed tracing
4. Build observability into your server
5. Create useful dashboards and alerts

---

## 21.1 The Three Pillars

### Observability Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Observability Stack                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   METRICS   │  │   LOGGING   │  │   TRACING   │         │
│  │             │  │             │  │             │         │
│  │ What's      │  │ What        │  │ How did     │         │
│  │ happening?  │  │ happened?   │  │ it happen?  │         │
│  │             │  │             │  │             │         │
│  │ Aggregated  │  │ Events      │  │ Request     │         │
│  │ numbers     │  │ with        │  │ flow        │         │
│  │             │  │ context     │  │ across      │         │
│  │             │  │             │  │ services    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                  │
│                          ▼                                  │
│                   ┌─────────────┐                           │
│                   │ Dashboards  │                           │
│                   │   Alerts    │                           │
│                   │   Debug     │                           │
│                   └─────────────┘                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### When to Use Each

| Question | Use |
|----------|-----|
| How many requests per second? | Metrics |
| Why did this request fail? | Logging |
| Where did the request spend time? | Tracing |
| Is the system healthy? | Metrics + Health checks |
| What happened at 3:45 AM? | Logging |
| Why is this endpoint slow? | Tracing |

---

## 21.2 Structured Logging

### JSON Logging

```python
import json
import logging
import sys
import time
import traceback
from typing import Any, Optional
from contextvars import ContextVar
from dataclasses import dataclass, field, asdict


# Request context
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')


@dataclass
class LogRecord:
    timestamp: str
    level: str
    message: str
    logger: str
    request_id: str = ''
    user_id: str = ''
    extra: dict = field(default_factory=dict)
    error: Optional[dict] = None

    def to_json(self) -> str:
        data = asdict(self)
        # Remove empty fields
        data = {k: v for k, v in data.items() if v}
        return json.dumps(data)


class JSONFormatter(logging.Formatter):
    """Format logs as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = LogRecord(
            timestamp=self.formatTime(record),
            level=record.levelname,
            message=record.getMessage(),
            logger=record.name,
            request_id=request_id_var.get(),
            user_id=user_id_var.get(),
        )

        # Add extra fields
        if hasattr(record, 'extra'):
            log_record.extra = record.extra

        # Add exception info
        if record.exc_info:
            log_record.error = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }

        return log_record.to_json()


def setup_logging(level: str = 'INFO'):
    """Setup JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    logging.root.handlers = [handler]
    logging.root.setLevel(level)


# Usage
logger = logging.getLogger(__name__)

def log_with_context(**extra):
    """Create log record with extra context."""
    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            kwargs['extra'] = {'extra': self.extra}
            return msg, kwargs

    return ContextAdapter(logger, extra)


# Example usage
async def handle_request(request):
    request_id_var.set(request.id)
    user_id_var.set(request.user_id)

    log = log_with_context(
        path=request.path,
        method=request.method
    )

    log.info("Request started")

    try:
        result = await process(request)
        log.info("Request completed", extra={'extra': {'status': 200}})
        return result
    except Exception as e:
        log.exception("Request failed")
        raise
```

### Log Levels and When to Use Them

```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: Detailed diagnostic info (development only)
logger.debug("Parsing request body", extra={'extra': {'size': len(body)}})

# INFO: Normal operation events
logger.info("Request completed", extra={'extra': {'status': 200, 'latency_ms': 45}})

# WARNING: Unexpected but handled situations
logger.warning("Rate limit approaching", extra={'extra': {'usage': 0.9}})

# ERROR: Errors that affected the request
logger.error("Database query failed", extra={'extra': {'query': query_name}})

# CRITICAL: System-wide failures
logger.critical("Cannot connect to database")
```

### Correlation IDs

```python
import uuid
from contextvars import ContextVar


trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
span_id_var: ContextVar[str] = ContextVar('span_id', default='')


class CorrelationMiddleware:
    """Add correlation IDs to requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Get or generate trace ID
        trace_id = None
        for name, value in scope.get('headers', []):
            if name == b'x-trace-id':
                trace_id = value.decode()
                break

        if not trace_id:
            trace_id = str(uuid.uuid4())

        span_id = str(uuid.uuid4())[:16]

        # Set context
        trace_id_var.set(trace_id)
        span_id_var.set(span_id)

        # Add to response headers
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                headers.append((b'x-trace-id', trace_id.encode()))
                headers.append((b'x-span-id', span_id.encode()))
                message = {**message, 'headers': headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
```

---

## 21.3 Metrics

### Metric Types

```python
from dataclasses import dataclass
from typing import Dict, List
import time
import threading


class Counter:
    """Monotonically increasing counter."""

    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def inc(self, value: float = 1, **label_values):
        """Increment counter."""
        key = tuple(label_values.get(l, '') for l in self.labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value

    def get(self, **label_values) -> float:
        key = tuple(label_values.get(l, '') for l in self.labels)
        return self._values.get(key, 0)


class Gauge:
    """Value that can go up and down."""

    def __init__(self, name: str, description: str, labels: List[str] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._values: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, **label_values):
        """Set gauge value."""
        key = tuple(label_values.get(l, '') for l in self.labels)
        with self._lock:
            self._values[key] = value

    def inc(self, value: float = 1, **label_values):
        key = tuple(label_values.get(l, '') for l in self.labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0) + value

    def dec(self, value: float = 1, **label_values):
        self.inc(-value, **label_values)


class Histogram:
    """Distribution of values."""

    DEFAULT_BUCKETS = [.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]

    def __init__(self, name: str, description: str,
                 labels: List[str] = None, buckets: List[float] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self.buckets = buckets or self.DEFAULT_BUCKETS
        self._counts: Dict[tuple, Dict[float, int]] = {}
        self._sums: Dict[tuple, float] = {}
        self._lock = threading.Lock()

    def observe(self, value: float, **label_values):
        """Record a value."""
        key = tuple(label_values.get(l, '') for l in self.labels)
        with self._lock:
            if key not in self._counts:
                self._counts[key] = {b: 0 for b in self.buckets + [float('inf')]}
                self._sums[key] = 0

            for bucket in self.buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1
            self._counts[key][float('inf')] += 1
            self._sums[key] += value

    def time(self, **label_values):
        """Context manager to time operations."""
        class Timer:
            def __init__(timer_self):
                timer_self.start = None

            def __enter__(timer_self):
                timer_self.start = time.perf_counter()
                return timer_self

            def __exit__(timer_self, *args):
                duration = time.perf_counter() - timer_self.start
                self.observe(duration, **label_values)

        return Timer()


# Metrics registry
class MetricsRegistry:
    """Central registry for all metrics."""

    def __init__(self):
        self.metrics: Dict[str, any] = {}

    def counter(self, name: str, description: str,
                labels: List[str] = None) -> Counter:
        if name not in self.metrics:
            self.metrics[name] = Counter(name, description, labels)
        return self.metrics[name]

    def gauge(self, name: str, description: str,
              labels: List[str] = None) -> Gauge:
        if name not in self.metrics:
            self.metrics[name] = Gauge(name, description, labels)
        return self.metrics[name]

    def histogram(self, name: str, description: str,
                  labels: List[str] = None,
                  buckets: List[float] = None) -> Histogram:
        if name not in self.metrics:
            self.metrics[name] = Histogram(name, description, labels, buckets)
        return self.metrics[name]


# Global registry
metrics = MetricsRegistry()

# Define metrics
REQUEST_COUNT = metrics.counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

REQUEST_LATENCY = metrics.histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'path'],
    buckets=[.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
)

ACTIVE_CONNECTIONS = metrics.gauge(
    'http_connections_active',
    'Active HTTP connections'
)

DB_POOL_SIZE = metrics.gauge(
    'db_pool_connections',
    'Database pool connections',
    ['state']  # active, idle
)
```

### Prometheus Format Export

```python
def prometheus_format(registry: MetricsRegistry) -> str:
    """Export metrics in Prometheus format."""
    lines = []

    for name, metric in registry.metrics.items():
        # Help text
        lines.append(f"# HELP {name} {metric.description}")

        if isinstance(metric, Counter):
            lines.append(f"# TYPE {name} counter")
            for labels, value in metric._values.items():
                label_str = format_labels(metric.labels, labels)
                lines.append(f"{name}{label_str} {value}")

        elif isinstance(metric, Gauge):
            lines.append(f"# TYPE {name} gauge")
            for labels, value in metric._values.items():
                label_str = format_labels(metric.labels, labels)
                lines.append(f"{name}{label_str} {value}")

        elif isinstance(metric, Histogram):
            lines.append(f"# TYPE {name} histogram")
            for labels, buckets in metric._counts.items():
                label_str = format_labels(metric.labels, labels)
                cumulative = 0
                for bucket, count in sorted(buckets.items()):
                    cumulative += count
                    le = '+Inf' if bucket == float('inf') else bucket
                    bucket_labels = f'{label_str[:-1]},le="{le}"}}' if label_str else f'{{le="{le}"}}'
                    lines.append(f"{name}_bucket{bucket_labels} {cumulative}")

                lines.append(f"{name}_sum{label_str} {metric._sums[labels]}")
                lines.append(f"{name}_count{label_str} {buckets[float('inf')]}")

    return '\n'.join(lines)


def format_labels(label_names: List[str], label_values: tuple) -> str:
    if not label_names:
        return ''
    pairs = [f'{n}="{v}"' for n, v in zip(label_names, label_values)]
    return '{' + ','.join(pairs) + '}'


# Metrics endpoint
async def metrics_endpoint(request):
    content = prometheus_format(metrics)
    return Response(
        content,
        content_type='text/plain; charset=utf-8'
    )
```

### Metrics Middleware

```python
class MetricsMiddleware:
    """Collect HTTP metrics."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        method = scope['method']
        path = self._normalize_path(scope['path'])

        ACTIVE_CONNECTIONS.inc()
        start_time = time.perf_counter()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message['type'] == 'http.response.start':
                status_code = message['status']
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = time.perf_counter() - start_time
            ACTIVE_CONNECTIONS.dec()

            REQUEST_COUNT.inc(method=method, path=path, status=str(status_code))
            REQUEST_LATENCY.observe(duration, method=method, path=path)

    def _normalize_path(self, path: str) -> str:
        """Normalize path to avoid high cardinality."""
        # Replace IDs with placeholders
        import re
        path = re.sub(r'/\d+', '/:id', path)
        path = re.sub(r'/[0-9a-f-]{36}', '/:uuid', path)
        return path
```

---

## 21.4 Distributed Tracing

### Trace Context

```python
import uuid
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from contextvars import ContextVar


@dataclass
class Span:
    """Single operation in a trace."""
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "OK"
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict] = field(default_factory=list)

    def finish(self, status: str = None):
        self.end_time = time.time()
        if status:
            self.status = status

    def set_tag(self, key: str, value: str):
        self.tags[key] = value

    def log(self, event: str, **fields):
        self.logs.append({
            'timestamp': time.time(),
            'event': event,
            **fields
        })

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0


# Context for current span
current_span: ContextVar[Optional[Span]] = ContextVar('current_span', default=None)


class Tracer:
    """Simple distributed tracer."""

    def __init__(self):
        self.spans: List[Span] = []

    def start_span(self, operation_name: str,
                   parent: Span = None) -> Span:
        """Start a new span."""
        parent = parent or current_span.get()

        if parent:
            trace_id = parent.trace_id
            parent_id = parent.span_id
        else:
            trace_id = str(uuid.uuid4())
            parent_id = None

        span = Span(
            trace_id=trace_id,
            span_id=str(uuid.uuid4())[:16],
            parent_id=parent_id,
            operation_name=operation_name,
            start_time=time.time()
        )

        self.spans.append(span)
        current_span.set(span)
        return span

    def finish_span(self, span: Span, status: str = None):
        """Finish a span."""
        span.finish(status)

        # Reset to parent span
        parent = self._find_parent(span)
        current_span.set(parent)

    def _find_parent(self, span: Span) -> Optional[Span]:
        if not span.parent_id:
            return None
        for s in self.spans:
            if s.span_id == span.parent_id:
                return s
        return None

    def trace(self, operation_name: str):
        """Decorator/context manager for tracing."""
        tracer = self

        class TraceContext:
            def __init__(self):
                self.span = None

            def __enter__(self):
                self.span = tracer.start_span(operation_name)
                return self.span

            def __exit__(self, exc_type, exc_val, exc_tb):
                status = "ERROR" if exc_type else "OK"
                tracer.finish_span(self.span, status)

            async def __aenter__(self):
                self.span = tracer.start_span(operation_name)
                return self.span

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                status = "ERROR" if exc_type else "OK"
                tracer.finish_span(self.span, status)

        return TraceContext()


# Global tracer
tracer = Tracer()


# Usage
async def handle_request(request):
    async with tracer.trace("handle_request") as span:
        span.set_tag("http.method", request.method)
        span.set_tag("http.url", request.path)

        async with tracer.trace("authenticate"):
            user = await authenticate(request)

        async with tracer.trace("fetch_data") as data_span:
            data_span.set_tag("user_id", user.id)
            data = await fetch_data(user)

        async with tracer.trace("render_response"):
            response = render(data)

        span.set_tag("http.status_code", "200")
        return response
```

### W3C Trace Context

```python
class TraceContextMiddleware:
    """W3C Trace Context propagation."""

    def __init__(self, app, tracer: Tracer):
        self.app = app
        self.tracer = tracer

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)

        # Extract trace context from headers
        trace_id = None
        parent_id = None

        for name, value in scope.get('headers', []):
            if name == b'traceparent':
                trace_id, parent_id = self._parse_traceparent(value.decode())

        # Start root span
        span = self.tracer.start_span(
            f"{scope['method']} {scope['path']}"
        )

        if trace_id:
            span.trace_id = trace_id
            span.parent_id = parent_id

        span.set_tag("http.method", scope['method'])
        span.set_tag("http.url", scope['path'])
        span.set_tag("component", "http")

        try:
            # Inject trace context in response
            async def send_wrapper(message):
                if message['type'] == 'http.response.start':
                    headers = list(message.get('headers', []))
                    headers.append((
                        b'traceparent',
                        self._make_traceparent(span).encode()
                    ))
                    message = {**message, 'headers': headers}
                    span.set_tag("http.status_code", str(message['status']))
                await send(message)

            await self.app(scope, receive, send_wrapper)
            self.tracer.finish_span(span, "OK")

        except Exception as e:
            span.set_tag("error", "true")
            span.log("error", message=str(e))
            self.tracer.finish_span(span, "ERROR")
            raise

    def _parse_traceparent(self, header: str) -> tuple:
        """Parse traceparent header."""
        # Format: version-trace_id-parent_id-flags
        parts = header.split('-')
        if len(parts) >= 3:
            return parts[1], parts[2]
        return None, None

    def _make_traceparent(self, span: Span) -> str:
        """Create traceparent header."""
        return f"00-{span.trace_id}-{span.span_id}-01"
```

---

## 21.5 Observability Integration

### Complete Observability Setup

```python
"""
Complete observability setup for web server.
"""

import logging
from dataclasses import dataclass
from typing import Optional


@dataclass
class ObservabilityConfig:
    service_name: str
    environment: str
    log_level: str = "INFO"
    metrics_path: str = "/metrics"
    enable_tracing: bool = True


class Observability:
    """Unified observability system."""

    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self.logger = self._setup_logging()
        self.metrics = MetricsRegistry()
        self.tracer = Tracer() if config.enable_tracing else None

        # Standard metrics
        self._setup_standard_metrics()

    def _setup_logging(self) -> logging.Logger:
        setup_logging(self.config.log_level)
        logger = logging.getLogger(self.config.service_name)
        return logger

    def _setup_standard_metrics(self):
        """Setup standard metrics."""
        self.request_count = self.metrics.counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'path', 'status']
        )
        self.request_latency = self.metrics.histogram(
            'http_request_duration_seconds',
            'Request latency in seconds',
            ['method', 'path']
        )
        self.active_requests = self.metrics.gauge(
            'http_requests_active',
            'Currently processing requests'
        )
        self.errors = self.metrics.counter(
            'errors_total',
            'Total errors',
            ['type']
        )

    def middleware(self, app):
        """Create observability middleware."""
        obs = self

        async def observability_middleware(scope, receive, send):
            if scope['type'] != 'http':
                return await app(scope, receive, send)

            method = scope['method']
            path = obs._normalize_path(scope['path'])

            # Start span
            span = None
            if obs.tracer:
                span = obs.tracer.start_span(f"{method} {path}")
                span.set_tag("http.method", method)
                span.set_tag("http.url", scope['path'])

            # Update metrics
            obs.active_requests.inc()
            start = time.perf_counter()
            status_code = 500

            async def send_wrapper(message):
                nonlocal status_code
                if message['type'] == 'http.response.start':
                    status_code = message['status']
                    if span:
                        span.set_tag("http.status_code", str(status_code))
                await send(message)

            try:
                await app(scope, receive, send_wrapper)
                if span:
                    obs.tracer.finish_span(span, "OK")
            except Exception as e:
                if span:
                    span.set_tag("error", "true")
                    span.log("error", message=str(e))
                    obs.tracer.finish_span(span, "ERROR")
                obs.errors.inc(type=type(e).__name__)
                raise
            finally:
                duration = time.perf_counter() - start
                obs.active_requests.dec()
                obs.request_count.inc(
                    method=method,
                    path=path,
                    status=str(status_code)
                )
                obs.request_latency.observe(
                    duration,
                    method=method,
                    path=path
                )

                # Log request
                obs.logger.info(
                    "Request completed",
                    extra={'extra': {
                        'method': method,
                        'path': scope['path'],
                        'status': status_code,
                        'duration_ms': round(duration * 1000, 2),
                        'trace_id': span.trace_id if span else None,
                    }}
                )

        return observability_middleware

    def _normalize_path(self, path: str) -> str:
        import re
        path = re.sub(r'/\d+', '/:id', path)
        path = re.sub(r'/[0-9a-f-]{36}', '/:uuid', path)
        return path


# Usage
obs = Observability(ObservabilityConfig(
    service_name="my-api",
    environment="production",
    log_level="INFO"
))

app = obs.middleware(app)
```

---

## 21.6 Alerting

### Alert Rules

```python
from dataclasses import dataclass
from typing import Callable, List, Optional
from enum import Enum
import asyncio


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    name: str
    condition: Callable[[], bool]
    severity: AlertSeverity
    message: str
    cooldown: float = 300  # seconds


class AlertManager:
    """Simple alert manager."""

    def __init__(self):
        self.rules: List[AlertRule] = []
        self.last_fired: dict = {}
        self.handlers: List[Callable] = []

    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)

    def add_handler(self, handler: Callable):
        self.handlers.append(handler)

    async def check(self):
        """Check all alert rules."""
        now = time.time()

        for rule in self.rules:
            # Check cooldown
            if rule.name in self.last_fired:
                if now - self.last_fired[rule.name] < rule.cooldown:
                    continue

            try:
                if rule.condition():
                    await self._fire_alert(rule)
                    self.last_fired[rule.name] = now
            except Exception as e:
                logger.error(f"Alert check failed: {rule.name}", exc_info=True)

    async def _fire_alert(self, rule: AlertRule):
        """Fire alert to all handlers."""
        alert = {
            'name': rule.name,
            'severity': rule.severity.value,
            'message': rule.message,
            'timestamp': time.time()
        }

        for handler in self.handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception:
                pass

    async def run_periodic(self, interval: float = 60):
        """Run alert checks periodically."""
        while True:
            await self.check()
            await asyncio.sleep(interval)


# Define alerts
alerts = AlertManager()

# High error rate
alerts.add_rule(AlertRule(
    name="high_error_rate",
    condition=lambda: (
        REQUEST_COUNT.get(status="500") /
        max(sum(REQUEST_COUNT._values.values()), 1) > 0.05
    ),
    severity=AlertSeverity.CRITICAL,
    message="Error rate exceeds 5%"
))

# High latency
alerts.add_rule(AlertRule(
    name="high_latency",
    condition=lambda: (
        # Check p99 latency
        True  # Implement actual check
    ),
    severity=AlertSeverity.WARNING,
    message="P99 latency exceeds threshold"
))

# Low connection pool
alerts.add_rule(AlertRule(
    name="low_db_connections",
    condition=lambda: DB_POOL_SIZE.get(state="idle") < 2,
    severity=AlertSeverity.WARNING,
    message="Database connection pool nearly exhausted"
))


# Alert handlers
async def slack_handler(alert: dict):
    """Send alert to Slack."""
    async with aiohttp.ClientSession() as session:
        await session.post(
            SLACK_WEBHOOK_URL,
            json={
                "text": f"🚨 [{alert['severity']}] {alert['name']}: {alert['message']}"
            }
        )


async def log_handler(alert: dict):
    """Log alert."""
    logger.warning(
        f"Alert: {alert['name']}",
        extra={'extra': alert}
    )


alerts.add_handler(log_handler)
alerts.add_handler(slack_handler)
```

---

## 21.7 Dashboard Queries

### Key Dashboard Panels

```yaml
# Request Rate
rate(http_requests_total[5m])

# Error Rate
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m]))

# P99 Latency
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Active Connections
http_connections_active

# Request Rate by Endpoint
sum by (path) (rate(http_requests_total[5m]))

# Error Rate by Endpoint
sum by (path) (rate(http_requests_total{status=~"5.."}[5m])) /
sum by (path) (rate(http_requests_total[5m]))
```

### RED Method Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│                     Service Dashboard                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │      Rate       │ │     Errors      │ │   Duration    │ │
│  │                 │ │                 │ │               │ │
│  │   1,234 req/s   │ │     0.5%        │ │  p99: 120ms   │ │
│  │                 │ │                 │ │  p50:  45ms   │ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
│                                                             │
│  Request Rate (5m)              Error Rate (5m)            │
│  ┌─────────────────────────┐   ┌─────────────────────────┐ │
│  │    ╱╲    ╱╲             │   │                         │ │
│  │   ╱  ╲  ╱  ╲   ╱╲      │   │  ─────────────────────  │ │
│  │  ╱    ╲╱    ╲ ╱  ╲     │   │                         │ │
│  │ ╱            ╲    ╲    │   │                         │ │
│  └─────────────────────────┘   └─────────────────────────┘ │
│                                                             │
│  Latency Percentiles           Active Connections          │
│  ┌─────────────────────────┐   ┌─────────────────────────┐ │
│  │ p99 ────────────────    │   │    ╱╲                   │ │
│  │ p95 ─────────────       │   │   ╱  ╲    ╱╲           │ │
│  │ p50 ────────            │   │  ╱    ╲  ╱  ╲          │ │
│  │                         │   │ ╱      ╲╱    ╲         │ │
│  └─────────────────────────┘   └─────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 21.8 Observability Checklist

### Logging

```
□ Structured JSON logging
□ Log levels used appropriately
□ Request ID/trace ID in all logs
□ Sensitive data not logged
□ Error stack traces captured
□ Log aggregation configured
```

### Metrics

```
□ Request rate by endpoint
□ Error rate by endpoint
□ Latency percentiles (p50, p95, p99)
□ Active connections
□ Database pool metrics
□ Cache hit/miss rates
□ External service latencies
```

### Tracing

```
□ Trace ID propagation
□ Spans for key operations
□ Tags for filtering
□ Error marking
□ Sampling configured
```

### Alerting

```
□ Error rate threshold
□ Latency threshold
□ Availability monitoring
□ Resource exhaustion
□ Dependency health
□ On-call rotation
```

---

## Exercises

### Exercise 21.1: Add Structured Logging

Convert your server to use structured JSON logging:
- Request ID in every log
- Performance timing
- Error details with stack traces

### Exercise 21.2: Implement Metrics

Add Prometheus-compatible metrics:
- Request count by method/path/status
- Latency histogram
- Active connections gauge

### Exercise 21.3: Add Tracing

Implement distributed tracing:
- Extract trace context from headers
- Create spans for operations
- Propagate to downstream calls

---

## Summary

Observability fundamentals:

1. **Logging**: Structured, contextual, actionable
2. **Metrics**: RED method (Rate, Errors, Duration)
3. **Tracing**: Request flow across services
4. **Alerting**: Meaningful, actionable alerts
5. **Integration**: All three pillars working together

---

## Next Module

**[Module 22: Middleware Systems →](./MODULE_22_MIDDLEWARE.md)**
