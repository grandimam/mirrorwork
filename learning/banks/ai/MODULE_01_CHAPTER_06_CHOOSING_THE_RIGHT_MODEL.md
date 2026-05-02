# Chapter 6: Choosing the Right Model

## 6.1 Model Selection Factors

| Factor | Consideration |
|--------|---------------|
| **Capability** | Can it do the task well? |
| **Cost** | Price per token (input/output) |
| **Latency** | Time to first token, total response time |
| **Context** | How much input can it handle? |
| **Rate Limits** | Requests per minute, tokens per minute |

## 6.2 Major Model Providers

```python
MODEL_PROVIDERS = {
    "anthropic": {
        "models": ["claude-3-opus", "claude-3-5-sonnet", "claude-3-haiku"],
        "strengths": ["instruction_following", "safety", "long_context"],
    },
    "openai": {
        "models": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        "strengths": ["ecosystem", "multimodal", "function_calling"],
    },
    "google": {
        "models": ["gemini-1.5-pro", "gemini-1.5-flash"],
        "strengths": ["long_context", "multimodal"],
    },
    "local": {
        "models": ["llama-3", "mistral", "mixtral"],
        "strengths": ["privacy", "cost", "customization"],
    },
}
```

## 6.3 Cost Comparison

```python
# Approximate pricing (always check current prices)
PRICING_PER_1M_TOKENS = {
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING_PER_1M_TOKENS.get(model)
    if not pricing:
        return 0.0
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

# Example: 10K input, 2K output
cost = estimate_cost("claude-3-5-sonnet", 10_000, 2_000)
# = (10000/1M * 3) + (2000/1M * 15) = 0.03 + 0.03 = $0.06
```

## 6.4 Model Tiers

```
┌─────────────────────────────────────────────────────────┐
│  FLAGSHIP (Best quality, highest cost)                  │
│  claude-3-opus, gpt-4-turbo                            │
│  Use for: Complex reasoning, critical tasks             │
├─────────────────────────────────────────────────────────┤
│  BALANCED (Good quality, reasonable cost)               │
│  claude-3-5-sonnet, gpt-4o                             │
│  Use for: Most production workloads                     │
├─────────────────────────────────────────────────────────┤
│  FAST/CHEAP (Lower quality, low cost)                   │
│  claude-3-haiku, gpt-3.5-turbo                         │
│  Use for: Simple tasks, high volume, low latency        │
└─────────────────────────────────────────────────────────┘
```

## 6.5 Task-Based Selection

```python
def select_model(task_type: str, constraints: dict = None) -> str:
    constraints = constraints or {}

    task_models = {
        # Simple tasks - use cheap/fast
        "classification": "claude-3-haiku",
        "extraction": "claude-3-haiku",
        "formatting": "claude-3-haiku",

        # Standard tasks - use balanced
        "summarization": "claude-3-5-sonnet",
        "code_generation": "claude-3-5-sonnet",
        "conversation": "claude-3-5-sonnet",
        "analysis": "claude-3-5-sonnet",

        # Complex tasks - use flagship
        "complex_reasoning": "claude-3-opus",
        "research": "claude-3-opus",
        "architecture": "claude-3-opus",
    }

    model = task_models.get(task_type, "claude-3-5-sonnet")

    # Override based on constraints
    if constraints.get("min_latency"):
        model = "claude-3-haiku"
    if constraints.get("max_quality"):
        model = "claude-3-opus"
    if constraints.get("max_budget") and constraints["max_budget"] < 0.01:
        model = "claude-3-haiku"

    return model
```

## 6.6 Latency Considerations

```python
# Typical latency ranges (varies by load, region, input size)
LATENCY_ESTIMATES = {
    "claude-3-haiku": {"ttft": "200-500ms", "tps": "100-150"},
    "claude-3-5-sonnet": {"ttft": "500-1000ms", "tps": "50-80"},
    "claude-3-opus": {"ttft": "1000-2000ms", "tps": "30-50"},
}
# ttft = time to first token
# tps = tokens per second

# For real-time chat: prefer faster models
# For batch processing: latency matters less
```

## 6.7 Multi-Model Architecture

Use different models for different parts of your system:

```python
class ModelRouter:
    def __init__(self, clients: dict):
        self.clients = clients

    async def route(self, task: str, content: str) -> str:
        # Route to appropriate model based on task
        routing_table = {
            "classify": ("haiku", 100),      # model, max_tokens
            "extract": ("haiku", 500),
            "summarize": ("sonnet", 1000),
            "generate_code": ("sonnet", 2000),
            "complex_analysis": ("opus", 4000),
        }

        model_key, max_tokens = routing_table.get(task, ("sonnet", 1000))

        return await self.clients[model_key].messages.create(
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}]
        )

# Example: Use cheap model for classification, better model for generation
router = ModelRouter({
    "haiku": haiku_client,
    "sonnet": sonnet_client,
    "opus": opus_client,
})

# Classify with haiku (fast, cheap)
category = await router.route("classify", user_input)

# Generate response with sonnet (better quality)
response = await router.route("generate_code", user_input)
```

## 6.8 Fallback Strategies

```python
class ModelWithFallback:
    def __init__(self, primary: str, fallback: str):
        self.primary = primary
        self.fallback = fallback

    async def generate(self, messages: list, **kwargs):
        try:
            return await self._call_model(self.primary, messages, **kwargs)
        except RateLimitError:
            print(f"Rate limited on {self.primary}, falling back")
            return await self._call_model(self.fallback, messages, **kwargs)
        except ModelOverloadedError:
            print(f"{self.primary} overloaded, falling back")
            return await self._call_model(self.fallback, messages, **kwargs)

# Use opus with sonnet fallback
client = ModelWithFallback(
    primary="claude-3-opus",
    fallback="claude-3-5-sonnet"
)
```

## 6.9 Decision Matrix

| Scenario | Recommended Model | Reason |
|----------|-------------------|--------|
| High-volume classification | Haiku/3.5-turbo | Cost, speed |
| User-facing chat | Sonnet/GPT-4o | Balance |
| Code review | Sonnet/GPT-4o | Good code understanding |
| Complex research | Opus/GPT-4-turbo | Best reasoning |
| Real-time autocomplete | Haiku | Lowest latency |
| Document analysis | Sonnet with long context | Context + capability |
| Privacy-sensitive | Local (Llama/Mistral) | No data leaves your infra |

## 6.10 Evaluation Before Choosing

```python
async def evaluate_models_for_task(task_prompts: list, models: list):
    """Run same prompts through multiple models, compare results"""
    results = {}

    for model in models:
        model_results = []
        total_cost = 0
        total_latency = 0

        for prompt in task_prompts:
            start = time.time()
            response = await call_model(model, prompt)
            latency = time.time() - start

            model_results.append({
                "prompt": prompt,
                "response": response.content,
                "latency": latency,
                "tokens": response.usage,
            })

            total_cost += estimate_cost(model, response.usage)
            total_latency += latency

        results[model] = {
            "responses": model_results,
            "avg_latency": total_latency / len(task_prompts),
            "total_cost": total_cost,
        }

    return results

# Then manually review quality or use LLM-as-judge
```

## 6.11 Summary

**Selection process**:
1. Define task requirements (quality, speed, cost)
2. Start with balanced model (Sonnet/GPT-4o)
3. Test if cheaper model works for simple tasks
4. Upgrade to flagship only if needed
5. Implement fallbacks for reliability

**Cost optimization**:
- Route simple tasks to cheap models
- Use expensive models only for complex reasoning
- Cache responses where possible
- Monitor and alert on unexpected costs

**Quality assurance**:
- Evaluate models on your specific tasks
- Re-evaluate when models update
- Track quality metrics in production
