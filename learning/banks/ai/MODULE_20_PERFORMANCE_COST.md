# Module 20: Performance and Cost Optimization

## 20.1 Understanding Costs

```python
# Cost breakdown
COSTS_PER_1M_TOKENS = {
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = COSTS_PER_1M_TOKENS[model]
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
```

## 20.2 Prompt Optimization

```python
# Verbose prompt - expensive
VERBOSE_PROMPT = """
You are a helpful assistant. Your task is to analyze the following text
and provide a comprehensive summary. Please ensure that you capture all
the key points and main ideas. The summary should be clear and concise.

Text to analyze:
{text}

Please provide your summary below:
"""

# Optimized prompt - cheaper
OPTIMIZED_PROMPT = """Summarize this text in 2-3 sentences:

{text}"""

# Token savings: ~50 tokens per request
```

## 20.3 Caching Responses

```python
class ResponseCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.cache = {}
        self.ttl = ttl_seconds

    def _hash(self, messages: list) -> str:
        return hashlib.md5(json.dumps(messages).encode()).hexdigest()

    async def get_or_create(self, messages: list, create_fn: callable) -> str:
        key = self._hash(messages)

        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.ttl:
                return entry["response"]

        response = await create_fn()
        self.cache[key] = {"response": response, "timestamp": time.time()}
        return response

# Usage
cache = ResponseCache()
response = await cache.get_or_create(
    messages,
    lambda: client.messages.create(...)
)
```

## 20.4 Model Routing

```python
class ModelRouter:
    def __init__(self, client):
        self.client = client

    def select_model(self, task: str) -> str:
        # Simple tasks → cheap model
        simple_patterns = ["summarize", "translate", "format", "extract"]
        if any(p in task.lower() for p in simple_patterns):
            return "claude-3-haiku"

        # Complex tasks → powerful model
        complex_patterns = ["analyze", "reason", "code", "debug"]
        if any(p in task.lower() for p in complex_patterns):
            return "claude-3-5-sonnet"

        return "claude-3-haiku"  # Default to cheaper

    async def run(self, task: str) -> str:
        model = self.select_model(task)
        response = await self.client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[{"role": "user", "content": task}]
        )
        return response.content[0].text
```

## 20.5 Streaming for Latency

```python
async def stream_response(client, messages: list):
    """Stream for better perceived latency"""
    first_token_time = None
    start_time = time.time()

    async with client.messages.stream(
        model="claude-3-5-sonnet",
        max_tokens=1000,
        messages=messages
    ) as stream:
        async for text in stream.text_stream:
            if first_token_time is None:
                first_token_time = time.time()
                print(f"Time to first token: {first_token_time - start_time:.2f}s")
            yield text

# Time to first token (TTFT) is key UX metric
```

## 20.6 Batching Requests

```python
class BatchProcessor:
    def __init__(self, client, batch_size: int = 10):
        self.client = client
        self.batch_size = batch_size

    async def process_batch(self, items: list[str]) -> list[str]:
        """Process multiple items in parallel"""
        results = []

        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]

            tasks = [
                self.client.messages.create(
                    model="claude-3-haiku",
                    max_tokens=500,
                    messages=[{"role": "user", "content": item}]
                )
                for item in batch
            ]

            responses = await asyncio.gather(*tasks)
            results.extend([r.content[0].text for r in responses])

        return results
```

## 20.7 Context Window Management

```python
class ContextManager:
    def __init__(self, max_tokens: int = 100000):
        self.max_tokens = max_tokens

    def truncate_messages(self, messages: list, encoding) -> list:
        """Keep most recent messages within limit"""
        total = 0
        kept = []

        # Always keep system message
        system = [m for m in messages if m["role"] == "system"]

        # Process from newest to oldest
        for msg in reversed(messages):
            if msg["role"] == "system":
                continue

            tokens = len(encoding.encode(msg["content"]))
            if total + tokens > self.max_tokens * 0.8:  # 80% limit
                break

            kept.insert(0, msg)
            total += tokens

        return system + kept

    def summarize_old_messages(self, messages: list) -> list:
        """Summarize older messages to save tokens"""
        if len(messages) < 10:
            return messages

        old = messages[:-5]
        recent = messages[-5:]

        summary = f"Previous conversation summary: [Discussed {len(old)} messages about various topics]"

        return [{"role": "system", "content": summary}] + recent
```

## 20.8 Summary

| Optimization | Impact |
|--------------|--------|
| Model routing | 10-50x cost reduction |
| Prompt optimization | 20-50% token savings |
| Caching | Eliminate repeated calls |
| Batching | Better throughput |
| Streaming | Better UX |

**Best practices:**
- Use cheapest model that works
- Cache deterministic queries
- Truncate context intelligently
- Stream for user-facing apps
- Monitor cost per feature
- Set budgets and alerts
