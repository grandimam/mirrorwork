# Chapter 2: Messages and Roles

## 2.1 Message Structure

LLM APIs use a conversation format with messages:

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"},
    {"role": "assistant", "content": "Hi! How can I help?"},
    {"role": "user", "content": "What's the weather?"},
]
```

Each message has:
- **role**: Who sent it (system, user, assistant)
- **content**: The message text

## 2.2 Roles Explained

### System Role

Sets behavior, personality, and constraints:

```python
# Anthropic - uses system parameter
response = client.messages.create(
    model="claude-3-5-sonnet",
    system="You are a Python expert. Give concise code examples.",
    messages=[{"role": "user", "content": "How do I read a file?"}]
)

# OpenAI - uses system message
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a Python expert."},
        {"role": "user", "content": "How do I read a file?"}
    ]
)
```

### User Role

Represents human input:

```python
messages = [
    {"role": "user", "content": "Explain recursion simply."}
]
```

### Assistant Role

Represents model output (used for conversation history):

```python
messages = [
    {"role": "user", "content": "What's 2+2?"},
    {"role": "assistant", "content": "4"},
    {"role": "user", "content": "Multiply that by 3"},
]
# Model sees context and responds "12"
```

## 2.3 Conversation History

Build multi-turn conversations by including history:

```python
class Conversation:
    def __init__(self, system_prompt: str = None):
        self.system = system_prompt
        self.messages = []

    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.messages.append({"role": "assistant", "content": content})

    async def send(self, client) -> str:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            system=self.system,
            max_tokens=1024,
            messages=self.messages
        )
        assistant_message = response.content[0].text
        self.add_assistant_message(assistant_message)
        return assistant_message

# Usage
convo = Conversation(system_prompt="You are a helpful tutor.")
convo.add_user_message("Explain Python lists")
response = await convo.send(client)
# Continue conversation
convo.add_user_message("How do I append to one?")
response = await convo.send(client)
```

## 2.4 Message Ordering

Messages must alternate user/assistant (after system):

```python
# Valid
messages = [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello!"},
    {"role": "user", "content": "Help me"},
]

# Invalid - consecutive same role
messages = [
    {"role": "user", "content": "Hi"},
    {"role": "user", "content": "Hello?"},  # Error!
]

# Fix: combine or use proper alternation
messages = [
    {"role": "user", "content": "Hi\n\nHello?"},
]
```

## 2.5 Content Types

### Text Content (Standard)

```python
message = {"role": "user", "content": "Hello"}
```

### Structured Content (Multimodal)

```python
# Anthropic format for images
message = {
    "role": "user",
    "content": [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64_image_data,
            }
        },
        {
            "type": "text",
            "text": "What's in this image?"
        }
    ]
}
```

## 2.6 System Prompt Patterns

### Role Definition

```python
system = """You are a senior software engineer specializing in Python.
- Give concise, production-ready code
- Include error handling
- Follow PEP 8 style"""
```

### Output Format Control

```python
system = """You are a data extraction assistant.
Always respond in JSON format:
{"extracted_data": [...], "confidence": 0.0-1.0}
Never include explanations outside the JSON."""
```

### Behavioral Constraints

```python
system = """You are a customer support agent for Acme Corp.
Rules:
- Never discuss competitor products
- Don't make promises about refunds without manager approval
- Always verify customer identity before sharing account details
- Escalate harassment to human support"""
```

## 2.7 Prefilling Assistant Response

Guide output format by starting the assistant's response:

```python
# Anthropic supports prefilling
response = client.messages.create(
    model="claude-3-5-sonnet",
    messages=[
        {"role": "user", "content": "List 3 colors as JSON"},
        {"role": "assistant", "content": "{"}  # Start the response
    ],
    max_tokens=100
)
# Model continues from "{" ensuring JSON output
```

## 2.8 Tool/Function Results

When using tools, include tool results:

```python
messages = [
    {"role": "user", "content": "What's the weather in Tokyo?"},
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "xyz", "content": '{"temp": 22, "condition": "sunny"}'},
]
```

## 2.9 Best Practices

```python
# 1. Keep system prompts focused
system = "You are a SQL expert. Output only valid SQL queries."

# 2. Don't repeat instructions in every user message
# Bad: "Remember you're an expert. Now, write a query for..."
# Good: "Write a query for..."

# 3. Use assistant messages to maintain context
messages = [
    {"role": "user", "content": "My name is Alice"},
    {"role": "assistant", "content": "Nice to meet you, Alice!"},
    {"role": "user", "content": "What's my name?"},
]
# Model knows: "Alice"

# 4. Clear conversation when context is no longer needed
def start_new_conversation():
    return []  # Fresh messages list
```

## 2.10 Summary

| Role | Purpose | When to Use |
|------|---------|-------------|
| system | Set behavior/rules | Once at start |
| user | Human input | Every user turn |
| assistant | Model output | Include history for context |
| tool | Function results | After tool calls |

**Key points**:
- Include conversation history for multi-turn context
- Alternate user/assistant messages
- Use system prompts for persistent instructions
- Prefill assistant to guide output format
