# Module 16: Agent Reliability

## 16.1 Retry Strategies

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class ReliableAgent:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10)
    )
    async def call_llm(self, messages: list) -> str:
        return await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=4096,
            messages=messages
        )

    async def run_with_retry(self, task: str) -> str:
        try:
            return await self.call_llm([{"role": "user", "content": task}])
        except Exception as e:
            return f"Failed after retries: {e}"
```

## 16.2 Fallback Models

```python
class FallbackAgent:
    def __init__(self):
        self.models = [
            "claude-3-5-sonnet",   # Primary
            "claude-3-sonnet",     # Fallback 1
            "claude-3-haiku",      # Fallback 2
        ]

    async def run(self, task: str) -> str:
        for model in self.models:
            try:
                response = await self.client.messages.create(
                    model=model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": task}]
                )
                return response.content[0].text
            except Exception as e:
                print(f"Model {model} failed: {e}")
                continue

        raise Exception("All models failed")
```

## 16.3 Graceful Degradation

```python
class DegradingAgent:
    async def run(self, task: str) -> str:
        # Try full capability
        try:
            return await self._run_with_tools(task)
        except ToolExecutionError:
            pass

        # Fallback: no tools
        try:
            return await self._run_without_tools(task)
        except Exception:
            pass

        # Final fallback: simple response
        return "I'm having trouble processing this request. Please try again."

    async def _run_with_tools(self, task: str) -> str:
        # Full agent with tools
        pass

    async def _run_without_tools(self, task: str) -> str:
        # Simple LLM call without tools
        prompt = f"Answer this without using any tools: {task}"
        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

## 16.4 Idempotency

```python
class IdempotentAgent:
    def __init__(self):
        self.executed_tasks = {}  # task_hash -> result

    async def run(self, task: str, idempotency_key: str = None) -> str:
        key = idempotency_key or hashlib.md5(task.encode()).hexdigest()

        # Check if already executed
        if key in self.executed_tasks:
            return self.executed_tasks[key]

        # Execute and cache
        result = await self._execute(task)
        self.executed_tasks[key] = result

        return result
```

## 16.5 Checkpointing

```python
@dataclass
class Checkpoint:
    task: str
    step: int
    state: dict
    timestamp: datetime

class CheckpointingAgent:
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

    async def run(self, task: str, resume_from: str = None) -> str:
        if resume_from:
            checkpoint = self._load_checkpoint(resume_from)
            state = checkpoint.state
            start_step = checkpoint.step
        else:
            state = {"messages": [{"role": "user", "content": task}]}
            start_step = 0

        for step in range(start_step, 10):
            try:
                result = await self._execute_step(state)

                if result.get("done"):
                    return result["answer"]

                state = result["state"]

                # Save checkpoint
                self._save_checkpoint(task, step, state)

            except Exception as e:
                # Save checkpoint before failing
                self._save_checkpoint(task, step, state)
                raise

    def _save_checkpoint(self, task: str, step: int, state: dict):
        checkpoint = Checkpoint(
            task=task,
            step=step,
            state=state,
            timestamp=datetime.now()
        )
        path = self.checkpoint_dir / f"{hashlib.md5(task.encode()).hexdigest()}.json"
        path.write_text(json.dumps(asdict(checkpoint), default=str))

    def _load_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        path = self.checkpoint_dir / f"{checkpoint_id}.json"
        data = json.loads(path.read_text())
        return Checkpoint(**data)
```

## 16.6 Timeout Handling

```python
class TimeoutAgent:
    def __init__(self, timeout_seconds: float = 60):
        self.timeout = timeout_seconds

    async def run(self, task: str) -> str:
        try:
            async with asyncio.timeout(self.timeout):
                return await self._execute(task)
        except asyncio.TimeoutError:
            return await self._handle_timeout(task)

    async def _handle_timeout(self, task: str) -> str:
        # Try to gracefully recover
        return "The task is taking longer than expected. Here's what I found so far..."
```

## 16.7 Circuit Breaker

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 60):
        self.failures = 0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure = None
        self.state = "closed"  # closed, open, half-open

    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure > self.reset_timeout:
                self.state = "half-open"
                return True
            return False
        return True  # half-open

    def record_success(self):
        self.failures = 0
        self.state = "closed"

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.threshold:
            self.state = "open"

class CircuitBreakerAgent:
    def __init__(self):
        self.breaker = CircuitBreaker()

    async def run(self, task: str) -> str:
        if not self.breaker.can_execute():
            return "Service temporarily unavailable. Please try again later."

        try:
            result = await self._execute(task)
            self.breaker.record_success()
            return result
        except Exception as e:
            self.breaker.record_failure()
            raise
```

## 16.8 Summary

| Strategy | When to Use |
|----------|-------------|
| Retry | Transient failures |
| Fallback | Model-specific issues |
| Degradation | Partial functionality ok |
| Idempotency | Prevent duplicate work |
| Checkpointing | Long-running tasks |
| Timeout | Prevent hangs |
| Circuit breaker | Systemic issues |

**Best practices:**
- Always have retry logic
- Implement fallback chains
- Checkpoint long operations
- Set reasonable timeouts
- Use circuit breakers for external services
