# Chapter 3: Streaming Responses

## 3.1 Why Streaming?

Non-streaming: Wait for entire response before showing anything.
Streaming: Show tokens as they're generated.

```
Non-streaming:
User sends → [waits 3 seconds] → Full response appears

Streaming:
User sends → [200ms] first word → [100ms] next word → ...continues
```

**Benefits**:
- Better perceived performance (user sees immediate activity)
- Earlier error detection
- Can cancel mid-generation
- Required for real-time UX

## 3.2 Basic Streaming

### Anthropic

```python
import anthropic

client = anthropic.Anthropic()

with client.messages.stream(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a short story"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

### OpenAI

```python
from openai import OpenAI

client = OpenAI()

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write a short story"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

## 3.3 Async Streaming

```python
import anthropic

client = anthropic.AsyncAnthropic()

async def stream_response(prompt: str):
    async with client.messages.stream(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            print(text, end="", flush=True)

# Run
await stream_response("Explain quantum computing")
```

## 3.4 Collecting Full Response

```python
async def stream_and_collect(prompt: str) -> str:
    """Stream to user while collecting full response"""
    full_response = []

    async with client.messages.stream(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            print(text, end="", flush=True)
            full_response.append(text)

    return "".join(full_response)

# Get both streaming output and final text
response_text = await stream_and_collect("Write a poem")
# response_text contains the complete response
```

## 3.5 Stream Events

Anthropic provides detailed events:

```python
async with client.messages.stream(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    async for event in stream:
        if event.type == "message_start":
            print(f"Started, input tokens: {event.message.usage.input_tokens}")
        elif event.type == "content_block_delta":
            print(event.delta.text, end="")
        elif event.type == "message_delta":
            print(f"\nStop reason: {event.delta.stop_reason}")
        elif event.type == "message_stop":
            print("Complete")
```

## 3.6 Streaming with Tool Use

```python
async def stream_with_tools(prompt: str, tools: list):
    tool_inputs = {}

    async with client.messages.stream(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        tools=tools
    ) as stream:
        async for event in stream:
            if event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    current_tool = event.content_block.name
                    tool_inputs[current_tool] = ""
            elif event.type == "content_block_delta":
                if hasattr(event.delta, "partial_json"):
                    tool_inputs[current_tool] += event.delta.partial_json
                elif hasattr(event.delta, "text"):
                    print(event.delta.text, end="")

    return tool_inputs
```

## 3.7 Web Server Streaming (FastAPI)

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import anthropic

app = FastAPI()
client = anthropic.AsyncAnthropic()

async def generate_stream(prompt: str):
    async with client.messages.stream(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            yield text

@app.get("/stream")
async def stream_endpoint(prompt: str):
    return StreamingResponse(
        generate_stream(prompt),
        media_type="text/plain"
    )
```

## 3.8 Server-Sent Events (SSE)

```python
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse
import json

async def generate_sse(prompt: str):
    async with client.messages.stream(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        async for text in stream.text_stream:
            yield {"event": "message", "data": json.dumps({"text": text})}
        yield {"event": "done", "data": json.dumps({"status": "complete"})}

@app.get("/sse")
async def sse_endpoint(prompt: str):
    return EventSourceResponse(generate_sse(prompt))
```

## 3.9 Cancellation

```python
import asyncio

async def stream_with_timeout(prompt: str, timeout: float = 30.0):
    try:
        async with asyncio.timeout(timeout):
            async with client.messages.stream(
                model="claude-3-5-sonnet",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                async for text in stream.text_stream:
                    print(text, end="")
    except asyncio.TimeoutError:
        print("\n[Cancelled due to timeout]")
```

## 3.10 Error Handling in Streams

```python
async def safe_stream(prompt: str):
    try:
        async with client.messages.stream(
            model="claude-3-5-sonnet",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            collected = []
            async for text in stream.text_stream:
                collected.append(text)
                yield text

    except anthropic.APIConnectionError:
        yield "\n[Connection lost - partial response above]"
    except anthropic.RateLimitError:
        yield "\n[Rate limited - try again later]"
    except Exception as e:
        yield f"\n[Error: {e}]"
```

## 3.11 Summary

| Method | Use Case |
|--------|----------|
| `stream.text_stream` | Simple text output |
| `stream` iterator | Access all event types |
| Async streaming | Non-blocking in async apps |
| SSE | Web client consumption |

**Best practices**:
- Always use streaming for user-facing responses
- Collect full response if you need to store/process it
- Handle errors gracefully mid-stream
- Use SSE for web frontends
- Set reasonable timeouts
