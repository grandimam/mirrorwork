# Module 18: Observability

## 18.1 Structured Logging

```python
import structlog

logger = structlog.get_logger()

class ObservableAgent:
    async def run(self, task: str) -> str:
        request_id = str(uuid.uuid4())

        logger.info("agent_start", request_id=request_id, task=task[:100])

        try:
            result = await self._execute(task)
            logger.info("agent_complete", request_id=request_id, status="success")
            return result
        except Exception as e:
            logger.error("agent_error", request_id=request_id, error=str(e))
            raise

    async def _execute_tool(self, name: str, inputs: dict):
        logger.info("tool_call", tool=name, inputs=inputs)
        start = time.time()

        result = await self.tools[name](**inputs)

        logger.info("tool_result", tool=name, duration_ms=(time.time() - start) * 1000)
        return result
```

## 18.2 Tracing with OpenTelemetry

```python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("agent")

class TracedAgent:
    async def run(self, task: str) -> str:
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("task.length", len(task))

            try:
                result = await self._agent_loop(task)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    async def _call_llm(self, messages: list) -> str:
        with tracer.start_as_current_span("llm.call") as span:
            span.set_attribute("messages.count", len(messages))

            response = await self.client.messages.create(...)

            span.set_attribute("tokens.input", response.usage.input_tokens)
            span.set_attribute("tokens.output", response.usage.output_tokens)
            return response
```

## 18.3 Metrics Collection

```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics
llm_requests = Counter("llm_requests_total", "Total LLM requests", ["model", "status"])
llm_latency = Histogram("llm_latency_seconds", "LLM request latency", ["model"])
llm_tokens = Counter("llm_tokens_total", "Tokens used", ["model", "type"])
active_agents = Gauge("active_agents", "Currently running agents")

class MetricsAgent:
    async def call_llm(self, messages: list) -> str:
        model = "claude-3-5-sonnet"

        with llm_latency.labels(model=model).time():
            try:
                response = await self.client.messages.create(
                    model=model,
                    messages=messages
                )

                llm_requests.labels(model=model, status="success").inc()
                llm_tokens.labels(model=model, type="input").inc(response.usage.input_tokens)
                llm_tokens.labels(model=model, type="output").inc(response.usage.output_tokens)

                return response
            except Exception:
                llm_requests.labels(model=model, status="error").inc()
                raise
```

## 18.4 Conversation Logging

```python
class ConversationLogger:
    def __init__(self, storage_path: str = "conversations"):
        self.storage = Path(storage_path)
        self.storage.mkdir(exist_ok=True)

    def log_turn(self, conversation_id: str, turn: dict):
        path = self.storage / f"{conversation_id}.jsonl"
        with open(path, "a") as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                **turn
            }
            f.write(json.dumps(entry) + "\n")

    def log_user_message(self, conv_id: str, message: str):
        self.log_turn(conv_id, {"role": "user", "content": message})

    def log_assistant_message(self, conv_id: str, message: str, tool_calls: list = None):
        self.log_turn(conv_id, {
            "role": "assistant",
            "content": message,
            "tool_calls": tool_calls
        })

    def log_tool_result(self, conv_id: str, tool: str, result: dict):
        self.log_turn(conv_id, {"role": "tool", "tool": tool, "result": result})
```

## 18.5 Debug Mode

```python
class DebuggableAgent:
    def __init__(self, debug: bool = False):
        self.debug = debug

    async def run(self, task: str) -> str:
        if self.debug:
            print(f"\n{'='*50}")
            print(f"TASK: {task}")
            print(f"{'='*50}\n")

        messages = [{"role": "user", "content": task}]

        for iteration in range(10):
            response = await self.client.messages.create(...)

            if self.debug:
                self._debug_response(iteration, response)

            if response.stop_reason == "end_turn":
                return self._get_text(response)

            # Process tools...

    def _debug_response(self, iteration: int, response):
        print(f"\n--- Iteration {iteration} ---")
        print(f"Stop reason: {response.stop_reason}")
        print(f"Tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")

        for block in response.content:
            if block.type == "text":
                print(f"Text: {block.text[:200]}...")
            elif block.type == "tool_use":
                print(f"Tool: {block.name}({json.dumps(block.input)})")
```

## 18.6 Cost Tracking Dashboard

```python
@dataclass
class UsageRecord:
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost: float

class CostTracker:
    PRICING = {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},  # per 1M tokens
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    }

    def __init__(self):
        self.records: list[UsageRecord] = []

    def record(self, model: str, input_tokens: int, output_tokens: int):
        pricing = self.PRICING.get(model, {"input": 0, "output": 0})
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        self.records.append(UsageRecord(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost
        ))

    def get_summary(self, since: datetime = None) -> dict:
        records = self.records
        if since:
            records = [r for r in records if r.timestamp >= since]

        return {
            "total_cost": sum(r.cost for r in records),
            "total_input_tokens": sum(r.input_tokens for r in records),
            "total_output_tokens": sum(r.output_tokens for r in records),
            "request_count": len(records),
        }
```

## 18.7 Error Tracking

```python
class ErrorTracker:
    def __init__(self):
        self.errors = []

    def capture(self, error: Exception, context: dict = None):
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        })

    def get_error_rate(self, window_minutes: int = 60) -> float:
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent = [e for e in self.errors if datetime.fromisoformat(e["timestamp"]) > cutoff]
        return len(recent) / window_minutes  # errors per minute
```

## 18.8 Summary

| Component | Purpose |
|-----------|---------|
| Logging | Debug and audit trail |
| Tracing | Request flow visualization |
| Metrics | Performance monitoring |
| Cost tracking | Budget management |
| Error tracking | Reliability monitoring |

**Best practices:**
- Log all LLM calls with tokens/cost
- Trace end-to-end request flow
- Alert on error rate spikes
- Track cost per user/feature
- Store conversations for debugging
