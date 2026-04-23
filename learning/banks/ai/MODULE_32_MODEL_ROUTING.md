# Module 32: Model Routing

## 32.1 Why Route Between Models?

```
Benefits:
- Cost optimization: Use cheaper models for simple tasks
- Latency optimization: Use faster models when speed matters
- Quality optimization: Use best model for complex tasks
- Availability: Fallback when primary model is down

Routing strategies:
- Rule-based: Simple heuristics
- Classifier-based: ML model decides
- Cascade: Try cheap first, escalate if needed
- Dynamic: Adjust based on load/budget
```

## 32.2 Rule-Based Routing

```python
class RuleBasedRouter:
    RULES = [
        {"pattern": r"translate", "model": "claude-3-haiku"},
        {"pattern": r"summarize", "model": "claude-3-haiku"},
        {"pattern": r"(analyze|reason|complex)", "model": "claude-3-5-sonnet"},
        {"pattern": r"(code|debug|review)", "model": "claude-3-5-sonnet"},
    ]

    def route(self, prompt: str) -> str:
        prompt_lower = prompt.lower()

        for rule in self.RULES:
            if re.search(rule["pattern"], prompt_lower):
                return rule["model"]

        # Length-based fallback
        if len(prompt) < 500:
            return "claude-3-haiku"

        return "claude-3-5-sonnet"
```

## 32.3 Classifier-Based Routing

```python
class ClassifierRouter:
    def __init__(self):
        self.classifier = None

    async def train(self, examples: list[dict]):
        """Train classifier on labeled examples"""
        # examples: [{"prompt": "...", "best_model": "..."}]
        # Use sklearn, pytorch, or call LLM for classification
        pass

    async def route(self, prompt: str) -> str:
        # Use small model to classify
        response = await client.messages.create(
            model="claude-3-haiku",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": f"""Classify this prompt complexity:
- SIMPLE: basic questions, translations, formatting
- MEDIUM: summaries, explanations, simple code
- COMPLEX: analysis, reasoning, complex code

Prompt: {prompt[:500]}

Answer SIMPLE, MEDIUM, or COMPLEX only."""
            }]
        )

        complexity = response.content[0].text.strip()
        return {
            "SIMPLE": "claude-3-haiku",
            "MEDIUM": "claude-3-5-sonnet",
            "COMPLEX": "claude-3-5-sonnet",
        }.get(complexity, "claude-3-5-sonnet")
```

## 32.4 Cascade Routing

```python
class CascadeRouter:
    """Try cheaper model first, escalate if needed"""

    def __init__(self):
        self.models = [
            {"name": "claude-3-haiku", "cost": 0.25},
            {"name": "claude-3-5-sonnet", "cost": 3.0},
        ]

    async def generate(self, prompt: str) -> dict:
        for model in self.models:
            response = await client.messages.create(
                model=model["name"],
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            output = response.content[0].text

            # Check if response is good enough
            quality = await self._assess_quality(prompt, output)

            if quality >= 0.8:  # Good enough
                return {
                    "response": output,
                    "model_used": model["name"],
                    "escalated": model != self.models[0]
                }

        # Return last response even if not great
        return {"response": output, "model_used": self.models[-1]["name"]}

    async def _assess_quality(self, prompt: str, response: str) -> float:
        # Quick quality check
        assessment = await client.messages.create(
            model="claude-3-haiku",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": f"Rate response quality 0-10:\nQ: {prompt[:200]}\nA: {response[:200]}\nScore:"
            }]
        )
        try:
            return float(assessment.content[0].text.strip()) / 10
        except:
            return 0.5
```

## 32.5 Budget-Aware Routing

```python
class BudgetAwareRouter:
    def __init__(self, daily_budget: float):
        self.daily_budget = daily_budget
        self.spent_today = 0
        self.last_reset = datetime.now().date()

    def route(self, prompt: str) -> str:
        self._check_reset()

        remaining = self.daily_budget - self.spent_today
        estimated_cost = self._estimate_cost(prompt, "claude-3-5-sonnet")

        if remaining < estimated_cost * 0.5:
            # Low budget, use cheap model
            return "claude-3-haiku"

        return "claude-3-5-sonnet"

    def record_usage(self, model: str, tokens: int):
        costs = {"claude-3-haiku": 0.25, "claude-3-5-sonnet": 3.0}
        self.spent_today += (tokens * costs.get(model, 1.0)) / 1_000_000

    def _estimate_cost(self, prompt: str, model: str) -> float:
        estimated_tokens = len(prompt.split()) * 1.5 + 500  # rough estimate
        costs = {"claude-3-haiku": 0.25, "claude-3-5-sonnet": 3.0}
        return (estimated_tokens * costs.get(model, 1.0)) / 1_000_000

    def _check_reset(self):
        if datetime.now().date() > self.last_reset:
            self.spent_today = 0
            self.last_reset = datetime.now().date()
```

## 32.6 Latency-Based Routing

```python
class LatencyRouter:
    def __init__(self):
        self.latency_stats = {}  # model -> list of latencies

    def route(self, prompt: str, max_latency_ms: float = None) -> str:
        if not max_latency_ms:
            return "claude-3-5-sonnet"

        # Check which models can meet latency requirement
        for model in ["claude-3-haiku", "claude-3-5-sonnet"]:
            avg_latency = self._get_avg_latency(model)
            if avg_latency and avg_latency < max_latency_ms:
                return model

        # Default to fastest
        return "claude-3-haiku"

    def record_latency(self, model: str, latency_ms: float):
        if model not in self.latency_stats:
            self.latency_stats[model] = []
        self.latency_stats[model].append(latency_ms)
        # Keep last 100
        self.latency_stats[model] = self.latency_stats[model][-100:]

    def _get_avg_latency(self, model: str) -> float:
        stats = self.latency_stats.get(model, [])
        return sum(stats) / len(stats) if stats else None
```

## 32.7 Multi-Provider Routing

```python
class MultiProviderRouter:
    def __init__(self):
        self.providers = {
            "anthropic": anthropic.Anthropic(),
            "openai": openai.OpenAI(),
        }
        self.health_status = {p: True for p in self.providers}

    async def generate(self, prompt: str, preferred: str = "anthropic") -> dict:
        # Try preferred provider
        if self.health_status[preferred]:
            try:
                return await self._call(preferred, prompt)
            except Exception as e:
                self.health_status[preferred] = False
                self._schedule_health_check(preferred)

        # Fallback to other providers
        for provider in self.providers:
            if provider != preferred and self.health_status[provider]:
                try:
                    return await self._call(provider, prompt)
                except:
                    self.health_status[provider] = False

        raise Exception("All providers unavailable")

    async def _call(self, provider: str, prompt: str) -> dict:
        if provider == "anthropic":
            response = await self.providers[provider].messages.create(
                model="claude-3-5-sonnet",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return {"response": response.content[0].text, "provider": provider}
        elif provider == "openai":
            response = await self.providers[provider].chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            return {"response": response.choices[0].message.content, "provider": provider}
```

## 32.8 Summary

| Strategy | Best For |
|----------|----------|
| Rule-based | Simple, predictable routing |
| Classifier | Complex task categorization |
| Cascade | Cost optimization |
| Budget-aware | Fixed spending limits |
| Latency-based | Time-sensitive applications |
| Multi-provider | High availability |

**Best practices:**
- Start with simple rules
- Monitor routing decisions
- Track cost/quality per model
- A/B test routing strategies
- Have fallback providers
- Update rules based on data
