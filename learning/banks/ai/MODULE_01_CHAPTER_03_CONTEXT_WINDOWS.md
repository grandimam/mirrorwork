# Chapter 3: Context Windows and Limits

## 3.1 What is a Context Window?

The context window is the maximum number of tokens a model can process in a single request (input + output combined).

```
┌─────────────────────────────────────────┐
│           Context Window (e.g., 128K)   │
├─────────────────────┬───────────────────┤
│    Input Tokens     │   Output Tokens   │
│   (your prompt +    │   (model's        │
│    conversation)    │    response)      │
└─────────────────────┴───────────────────┘
```

If your input is 100K tokens, you only have 28K left for the response.

## 3.2 Common Context Window Sizes

| Model | Context Window |
|-------|---------------|
| GPT-4o | 128K |
| Claude 3.5 Sonnet | 200K |
| Claude 3 Opus | 200K |
| Gemini 1.5 Pro | 1M+ |
| Llama 3 | 8K - 128K |
| Mistral | 32K |

```python
MODEL_CONTEXT_LIMITS = {
    "gpt-4o": 128_000,
    "gpt-4-turbo": 128_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3-opus": 200_000,
}

def get_available_output_tokens(model: str, input_tokens: int) -> int:
    limit = MODEL_CONTEXT_LIMITS.get(model, 8000)
    return limit - input_tokens
```

## 3.3 Context Window vs Max Output Tokens

Two different limits:

```python
# Context window: total tokens (input + output)
# Max output tokens: cap on response length

response = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=4096,  # Max output tokens (your choice)
    messages=[...]    # Input tokens (your prompt)
)

# If context window is 200K:
# - Input can be up to ~196K (leaving room for output)
# - Output capped at your max_tokens setting
```

## 3.4 What Happens When You Exceed Limits

```python
# Scenario 1: Input exceeds context window
# Result: API error before processing

# Scenario 2: Output would exceed context window
# Result: Response truncated mid-generation

# Scenario 3: Output exceeds max_tokens
# Result: Response truncated at max_tokens
```

```python
# Check for truncation
response = client.messages.create(...)

if response.stop_reason == "max_tokens":
    print("Response was truncated!")
elif response.stop_reason == "end_turn":
    print("Response completed naturally")
```

## 3.5 Managing Conversation History

The most common context management challenge:

```python
class ConversationManager:
    def __init__(self, max_context_tokens: int = 100_000):
        self.messages = []
        self.system_prompt = None
        self.max_context = max_context_tokens
        self.reserved_for_response = 4096

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self._trim_if_needed()

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _get_total_tokens(self) -> int:
        total = 0
        if self.system_prompt:
            total += self._estimate_tokens(self.system_prompt)
        for msg in self.messages:
            total += self._estimate_tokens(msg["content"])
        return total

    def _trim_if_needed(self):
        """Remove oldest messages (except system) to fit context"""
        available = self.max_context - self.reserved_for_response

        while self._get_total_tokens() > available and len(self.messages) > 2:
            # Keep at least the last user message and response
            self.messages.pop(0)

    def get_messages(self) -> list:
        msgs = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(self.messages)
        return msgs
```

## 3.6 Strategies for Long Contexts

**Strategy 1: Sliding Window**

```python
def sliding_window(messages: list, max_messages: int = 20) -> list:
    """Keep only the most recent N messages"""
    if len(messages) <= max_messages:
        return messages
    return messages[-max_messages:]
```

**Strategy 2: Summarization**

```python
async def summarize_and_compress(messages: list, client) -> list:
    """Summarize older messages to save tokens"""
    if len(messages) < 10:
        return messages

    # Summarize older messages
    old_messages = messages[:-4]  # Keep last 4 intact
    recent_messages = messages[-4:]

    summary = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Summarize this conversation briefly:\n{old_messages}"
        }]
    )

    return [
        {"role": "system", "content": f"Previous conversation summary: {summary.content}"},
        *recent_messages
    ]
```

**Strategy 3: RAG for Context**

```python
def rag_based_context(query: str, full_history: list, retriever) -> list:
    """Retrieve only relevant parts of history"""
    # Embed the current query
    relevant_messages = retriever.search(
        query=query,
        documents=full_history,
        top_k=10
    )
    return relevant_messages
```

## 3.7 Large Context Best Practices

**Put important information at the start and end**:

```python
# Models pay more attention to beginning and end
prompt = f"""
CRITICAL INSTRUCTION: {most_important_instruction}

{large_body_of_context}

REMINDER: {most_important_instruction}
"""
```

**Use clear structure for large inputs**:

```python
prompt = """
## TASK
Analyze the following documents.

## DOCUMENT 1: Sales Report
{doc1}

## DOCUMENT 2: Customer Feedback
{doc2}

## DOCUMENT 3: Market Analysis
{doc3}

## INSTRUCTIONS
Based on all documents above, provide:
1. Key insights
2. Recommendations
"""
```

## 3.8 Measuring Context Usage

```python
import tiktoken

class ContextTracker:
    def __init__(self, model: str, max_context: int):
        self.encoder = tiktoken.encoding_for_model(model)
        self.max_context = max_context

    def count_tokens(self, messages: list) -> dict:
        input_tokens = 0
        for msg in messages:
            input_tokens += len(self.encoder.encode(msg["content"]))
            input_tokens += 4  # overhead per message

        return {
            "input_tokens": input_tokens,
            "available_for_output": self.max_context - input_tokens,
            "utilization": input_tokens / self.max_context * 100
        }

# Usage
tracker = ContextTracker("gpt-4", 128_000)
stats = tracker.count_tokens(messages)
print(f"Using {stats['utilization']:.1f}% of context")
```

## 3.9 Common Pitfalls

**Pitfall 1: Not accounting for output tokens**

```python
# Wrong: using full context for input
input_tokens = 127_000  # Leaves only 1K for response!

# Right: reserve space for response
max_input = context_limit - expected_output_tokens
```

**Pitfall 2: Growing conversations without limits**

```python
# Wrong: append forever
conversation.append(new_message)

# Right: manage size
conversation.append(new_message)
conversation = trim_to_limit(conversation, max_tokens)
```

**Pitfall 3: Ignoring truncation**

```python
# Wrong: assume response is complete
result = response.content

# Right: check stop reason
if response.stop_reason == "max_tokens":
    # Handle incomplete response
    result = await continue_generation(response)
```

## 3.10 Summary

- Context window = max total tokens (input + output)
- Always reserve tokens for the expected response
- Implement conversation trimming for chat applications
- Use summarization or RAG for very long histories
- Structure large inputs clearly with sections
- Monitor and log context utilization
- Handle truncation gracefully
