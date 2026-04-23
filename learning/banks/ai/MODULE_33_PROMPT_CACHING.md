# Module 33: Prompt Caching

## 33.1 What is Prompt Caching?

```
Without caching:
- Every request processes full prompt from scratch
- Pay full price for repeated context
- Higher latency for long prompts

With caching:
- Repeated prompt prefixes are cached
- 90% cost reduction on cached portions
- Faster time-to-first-token
```

## 33.2 Anthropic Prompt Caching

```python
import anthropic

client = anthropic.Anthropic()

# Mark content for caching with cache_control
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are an expert on the following documentation...",
        },
        {
            "type": "text",
            "text": LARGE_DOCUMENTATION_TEXT,  # Large static content
            "cache_control": {"type": "ephemeral"}  # Cache this
        }
    ],
    messages=[{"role": "user", "content": "What does the API return?"}]
)

# Check cache usage
print(f"Cache read: {response.usage.cache_read_input_tokens}")
print(f"Cache created: {response.usage.cache_creation_input_tokens}")
```

## 33.3 Cache Breakpoints

```python
# Cache works on prefixes - order matters!

# Good: Static content first, then dynamic
system = [
    {"type": "text", "text": STATIC_DOCS, "cache_control": {"type": "ephemeral"}},
    {"type": "text", "text": f"Today is {date}"}  # Dynamic, not cached
]

# Bad: Dynamic content breaks cache
system = [
    {"type": "text", "text": f"Today is {date}"},  # Changes every day
    {"type": "text", "text": STATIC_DOCS}  # Cache invalidated!
]
```

## 33.4 Multi-turn Caching

```python
class CachedConversation:
    def __init__(self, system_prompt: str):
        self.system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ]
        self.messages = []

    async def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        # Cache the conversation history too
        messages_with_cache = self.messages.copy()
        if len(messages_with_cache) > 2:
            # Cache all but last exchange
            messages_with_cache[-3]["content"] = [
                {
                    "type": "text",
                    "text": messages_with_cache[-3]["content"],
                    "cache_control": {"type": "ephemeral"}
                }
            ]

        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=self.system,
            messages=messages_with_cache
        )

        assistant_msg = response.content[0].text
        self.messages.append({"role": "assistant", "content": assistant_msg})
        return assistant_msg
```

## 33.5 RAG with Caching

```python
class CachedRAG:
    def __init__(self, base_context: str):
        # Cache the base instructions
        self.system = [
            {
                "type": "text",
                "text": """You are a helpful assistant. Answer questions
                based only on the provided context.""",
                "cache_control": {"type": "ephemeral"}
            }
        ]
        # Cache frequently used context
        self.base_context = {
            "type": "text",
            "text": base_context,
            "cache_control": {"type": "ephemeral"}
        }

    async def query(self, question: str, additional_context: str = "") -> str:
        messages = [
            {
                "role": "user",
                "content": [
                    self.base_context,  # Cached
                    {"type": "text", "text": additional_context},  # Dynamic
                    {"type": "text", "text": f"\nQuestion: {question}"}
                ]
            }
        ]

        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=self.system,
            messages=messages
        )
        return response.content[0].text
```

## 33.6 OpenAI Caching

```python
from openai import OpenAI

client = OpenAI()

# OpenAI automatically caches identical prompt prefixes
# No explicit cache_control needed

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": LARGE_SYSTEM_PROMPT},
        {"role": "user", "content": "Question here"}
    ]
)

# Check for cached tokens in response
# cached_tokens available in usage
```

## 33.7 Cache Strategy Patterns

```python
# Pattern 1: Static system prompt + dynamic user
CACHED_SYSTEM = {
    "type": "text",
    "text": LARGE_INSTRUCTIONS,
    "cache_control": {"type": "ephemeral"}
}

# Pattern 2: Few-shot examples cached
CACHED_EXAMPLES = {
    "type": "text",
    "text": format_examples(EXAMPLES),
    "cache_control": {"type": "ephemeral"}
}

# Pattern 3: Tool definitions cached
CACHED_TOOLS = {
    "type": "text",
    "text": format_tool_descriptions(TOOLS),
    "cache_control": {"type": "ephemeral"}
}

# Combine in order of most-to-least static
system = [CACHED_SYSTEM, CACHED_EXAMPLES, CACHED_TOOLS]
```

## 33.8 Cost Analysis

```python
# Anthropic pricing (example)
PRICING = {
    "input": 3.00,           # per 1M tokens
    "output": 15.00,
    "cache_write": 3.75,     # 25% more than input
    "cache_read": 0.30,      # 90% less than input
}

def calculate_savings(
    cached_tokens: int,
    requests_per_day: int,
    days: int = 30
) -> dict:
    # Without caching
    no_cache_cost = (cached_tokens * PRICING["input"] / 1_000_000) * requests_per_day * days

    # With caching (1 write + many reads)
    cache_write = cached_tokens * PRICING["cache_write"] / 1_000_000
    cache_reads = (cached_tokens * PRICING["cache_read"] / 1_000_000) * (requests_per_day * days - 1)
    with_cache_cost = cache_write + cache_reads

    return {
        "without_cache": no_cache_cost,
        "with_cache": with_cache_cost,
        "savings": no_cache_cost - with_cache_cost,
        "savings_percent": (1 - with_cache_cost / no_cache_cost) * 100
    }
```

## 33.9 Cache Limitations

```python
# Minimum cacheable size: ~1024 tokens (Anthropic)
# Cache TTL: ~5 minutes of inactivity

# Check if content is large enough to cache
def should_cache(text: str) -> bool:
    estimated_tokens = len(text.split()) * 1.3
    return estimated_tokens >= 1024

# Keep cache warm with periodic requests
async def keep_cache_warm(client, system_prompt: str, interval_seconds: int = 240):
    while True:
        await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": "ping"}]
        )
        await asyncio.sleep(interval_seconds)
```

## 33.10 Summary

| Aspect | Details |
|--------|---------|
| Cost savings | Up to 90% on cached tokens |
| Latency | Faster TTFT for long prompts |
| Min size | ~1024 tokens (Anthropic) |
| TTL | ~5 minutes |
| Best for | Long system prompts, RAG, few-shot |

**Best practices:**
- Put static content first
- Cache system prompts and examples
- Order content most-to-least static
- Monitor cache hit rates
- Keep cache warm for high-traffic apps
