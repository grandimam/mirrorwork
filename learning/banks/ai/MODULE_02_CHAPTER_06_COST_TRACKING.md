# Chapter 6: Cost Tracking and Budgeting

## 6.1 Understanding API Costs

LLM APIs charge per token:

```python
# Typical pricing structure (check current prices)
PRICING = {
    "claude-3-opus": {"input": 15.0, "output": 75.0},      # per 1M tokens
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING.get(model, {"input": 0, "output": 0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost
```

## 6.2 Extracting Usage from Responses

```python
# Anthropic
response = client.messages.create(...)
usage = response.usage
print(f"Input: {usage.input_tokens}, Output: {usage.output_tokens}")

# OpenAI
response = client.chat.completions.create(...)
usage = response.usage
print(f"Input: {usage.prompt_tokens}, Output: {usage.completion_tokens}")
```

## 6.3 Cost Tracker Class

```python
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

@dataclass
class UsageRecord:
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost: float

class CostTracker:
    def __init__(self):
        self.records: list[UsageRecord] = []
        self.by_model: dict[str, float] = defaultdict(float)
        self.total_cost: float = 0.0

    def record(self, model: str, input_tokens: int, output_tokens: int):
        cost = calculate_cost(model, input_tokens, output_tokens)
        record = UsageRecord(
            timestamp=datetime.now(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost
        )
        self.records.append(record)
        self.by_model[model] += cost
        self.total_cost += cost
        return cost

    def get_summary(self) -> dict:
        return {
            "total_cost": round(self.total_cost, 4),
            "by_model": dict(self.by_model),
            "request_count": len(self.records),
        }

# Usage
tracker = CostTracker()

response = client.messages.create(...)
cost = tracker.record(
    model="claude-3-5-sonnet",
    input_tokens=response.usage.input_tokens,
    output_tokens=response.usage.output_tokens
)
print(f"This request: ${cost:.4f}")
print(f"Total: ${tracker.total_cost:.4f}")
```

## 6.4 Budget Enforcement

```python
class BudgetExceededError(Exception):
    pass

class BudgetedClient:
    def __init__(self, client, budget: float):
        self.client = client
        self.budget = budget
        self.spent = 0.0

    async def create(self, **kwargs) -> tuple:
        # Estimate cost before calling
        estimated = self._estimate_cost(kwargs)
        if self.spent + estimated > self.budget:
            raise BudgetExceededError(
                f"Budget ${self.budget} would be exceeded. Spent: ${self.spent:.2f}"
            )

        response = await self.client.messages.create(**kwargs)

        # Track actual cost
        actual_cost = calculate_cost(
            kwargs["model"],
            response.usage.input_tokens,
            response.usage.output_tokens
        )
        self.spent += actual_cost

        return response

    def _estimate_cost(self, kwargs) -> float:
        # Rough estimate based on input length
        model = kwargs["model"]
        input_chars = sum(len(m["content"]) for m in kwargs["messages"])
        estimated_input = input_chars // 4
        estimated_output = kwargs.get("max_tokens", 1000)
        return calculate_cost(model, estimated_input, estimated_output)

# Usage
budgeted = BudgetedClient(client, budget=1.00)  # $1 budget
try:
    response = await budgeted.create(model="claude-3-5-sonnet", ...)
except BudgetExceededError as e:
    print(f"Budget exceeded: {e}")
```

## 6.5 Per-User Cost Tracking

```python
class UserCostTracker:
    def __init__(self):
        self.user_costs: dict[str, float] = defaultdict(float)
        self.user_limits: dict[str, float] = {}

    def set_limit(self, user_id: str, limit: float):
        self.user_limits[user_id] = limit

    def can_proceed(self, user_id: str, estimated_cost: float) -> bool:
        limit = self.user_limits.get(user_id, float("inf"))
        return self.user_costs[user_id] + estimated_cost <= limit

    def record(self, user_id: str, cost: float):
        self.user_costs[user_id] += cost

    def get_remaining(self, user_id: str) -> float:
        limit = self.user_limits.get(user_id, float("inf"))
        return limit - self.user_costs[user_id]

# Usage
tracker = UserCostTracker()
tracker.set_limit("user123", 10.00)  # $10/month limit

if tracker.can_proceed("user123", estimated_cost=0.05):
    response = await client.messages.create(...)
    tracker.record("user123", actual_cost)
else:
    raise Exception("Monthly limit reached")
```

## 6.6 Cost Alerts

```python
import asyncio

class CostMonitor:
    def __init__(self, alert_threshold: float, alert_callback):
        self.threshold = alert_threshold
        self.callback = alert_callback
        self.total = 0.0
        self.alerted = False

    def record(self, cost: float):
        self.total += cost
        if self.total >= self.threshold and not self.alerted:
            self.alerted = True
            asyncio.create_task(self.callback(self.total))

async def send_alert(total: float):
    print(f"ALERT: Costs reached ${total:.2f}")
    # Send email, Slack, etc.

monitor = CostMonitor(alert_threshold=100.0, alert_callback=send_alert)
```

## 6.7 Cost Optimization Strategies

```python
# 1. Use cheaper models for simple tasks
def select_model_by_complexity(task: str) -> str:
    simple_tasks = ["classify", "extract", "format"]
    if any(t in task.lower() for t in simple_tasks):
        return "claude-3-haiku"  # ~60x cheaper than opus
    return "claude-3-5-sonnet"

# 2. Reduce token usage
def optimize_prompt(prompt: str) -> str:
    # Remove unnecessary whitespace
    prompt = " ".join(prompt.split())
    # Truncate if too long
    if len(prompt) > 10000:
        prompt = prompt[:10000] + "..."
    return prompt

# 3. Cache responses
from functools import lru_cache
import hashlib

response_cache = {}

def get_cached_or_call(prompt: str, model: str):
    cache_key = hashlib.md5(f"{model}:{prompt}".encode()).hexdigest()
    if cache_key in response_cache:
        return response_cache[cache_key]
    response = client.messages.create(...)
    response_cache[cache_key] = response.content[0].text
    return response_cache[cache_key]
```

## 6.8 Cost Reporting

```python
from datetime import datetime, timedelta

class CostReporter:
    def __init__(self, tracker: CostTracker):
        self.tracker = tracker

    def daily_report(self, date: datetime = None) -> dict:
        date = date or datetime.now()
        start = date.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)

        records = [
            r for r in self.tracker.records
            if start <= r.timestamp < end
        ]

        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_cost": sum(r.cost for r in records),
            "request_count": len(records),
            "by_model": self._group_by_model(records),
        }

    def _group_by_model(self, records) -> dict:
        by_model = defaultdict(lambda: {"cost": 0, "requests": 0})
        for r in records:
            by_model[r.model]["cost"] += r.cost
            by_model[r.model]["requests"] += 1
        return dict(by_model)
```

## 6.9 Summary

| Strategy | Impact |
|----------|--------|
| Use cheaper models | Up to 60x savings |
| Reduce prompt size | Linear savings |
| Cache responses | 100% savings on hits |
| Set budgets | Prevent overruns |
| Monitor costs | Early warning |

**Best practices**:
- Track every API call
- Set per-user and global budgets
- Alert before limits are reached
- Route simple tasks to cheap models
- Cache deterministic responses
- Review costs regularly
