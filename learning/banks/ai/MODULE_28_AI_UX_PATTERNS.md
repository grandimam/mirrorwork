# Module 28: AI UX Patterns

## 28.1 Streaming Responses

```python
# Backend: FastAPI streaming
from fastapi.responses import StreamingResponse

@app.post("/chat/stream")
async def stream_chat(request: ChatRequest):
    async def generate():
        async with client.messages.stream(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": request.message}]
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# Frontend: JavaScript
async function streamChat(message) {
    const response = await fetch('/chat/stream', {
        method: 'POST',
        body: JSON.stringify({ message }),
        headers: { 'Content-Type': 'application/json' }
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value);
        // Parse SSE and update UI incrementally
        updateUI(text);
    }
}
```

## 28.2 Loading States

```python
# Show appropriate loading states
class LoadingStates:
    THINKING = "thinking"      # Waiting for first token
    GENERATING = "generating"  # Streaming response
    TOOL_USE = "searching"     # Using tools
    COMPLETE = "complete"

@dataclass
class StreamEvent:
    state: str
    content: str = ""
    tool: str = None

async def stream_with_states(prompt: str):
    yield StreamEvent(state=LoadingStates.THINKING)

    async with client.messages.stream(...) as stream:
        first_token = True
        async for event in stream:
            if event.type == "content_block_start":
                if first_token:
                    yield StreamEvent(state=LoadingStates.GENERATING)
                    first_token = False

            if event.type == "tool_use":
                yield StreamEvent(state=LoadingStates.TOOL_USE, tool=event.name)

            if event.type == "text":
                yield StreamEvent(state=LoadingStates.GENERATING, content=event.text)

    yield StreamEvent(state=LoadingStates.COMPLETE)
```

## 28.3 Error Handling UX

```python
class UserFriendlyErrors:
    ERROR_MESSAGES = {
        "rate_limit": "I'm receiving too many requests. Please wait a moment.",
        "context_length": "That's a lot of text! Try breaking it into smaller parts.",
        "content_filter": "I can't help with that type of request.",
        "timeout": "This is taking longer than expected. Please try again.",
        "unknown": "Something went wrong. Please try again."
    }

    @classmethod
    def get_message(cls, error: Exception) -> str:
        if "rate" in str(error).lower():
            return cls.ERROR_MESSAGES["rate_limit"]
        if "context" in str(error).lower() or "token" in str(error).lower():
            return cls.ERROR_MESSAGES["context_length"]
        if "content" in str(error).lower() or "safety" in str(error).lower():
            return cls.ERROR_MESSAGES["content_filter"]
        if "timeout" in str(error).lower():
            return cls.ERROR_MESSAGES["timeout"]
        return cls.ERROR_MESSAGES["unknown"]
```

## 28.4 Typing Indicators

```python
# Simulate natural typing for better UX
import asyncio

async def simulate_typing(text: str, chars_per_second: int = 50):
    """Yield text with natural-feeling delays"""
    delay = 1 / chars_per_second

    for char in text:
        yield char
        await asyncio.sleep(delay)

# Variable speed based on punctuation
async def natural_typing(text: str):
    for char in text:
        yield char
        if char in '.!?':
            await asyncio.sleep(0.3)  # Pause at sentence end
        elif char == ',':
            await asyncio.sleep(0.1)  # Brief pause at comma
        else:
            await asyncio.sleep(0.02)
```

## 28.5 Suggested Prompts

```python
class PromptSuggester:
    async def get_suggestions(self, context: str = None) -> list[str]:
        if not context:
            return self._default_suggestions()

        response = await client.messages.create(
            model="claude-3-haiku",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Based on this conversation, suggest 3 follow-up questions the user might ask:

{context}

Return as JSON array of strings."""
            }]
        )
        return json.loads(response.content[0].text)

    def _default_suggestions(self) -> list[str]:
        return [
            "Help me write an email",
            "Explain a concept to me",
            "Review my code",
            "Help me brainstorm ideas"
        ]
```

## 28.6 Feedback Collection

```python
@dataclass
class Feedback:
    message_id: str
    rating: int  # 1-5 or thumbs up/down
    category: str = None  # helpful, accurate, clear, etc.
    comment: str = None

class FeedbackCollector:
    def __init__(self):
        self.feedback = []

    def collect(self, feedback: Feedback):
        self.feedback.append(feedback)
        # Store for analysis

    def get_stats(self) -> dict:
        if not self.feedback:
            return {}

        return {
            "total": len(self.feedback),
            "avg_rating": sum(f.rating for f in self.feedback) / len(self.feedback),
            "positive_rate": sum(1 for f in self.feedback if f.rating >= 4) / len(self.feedback)
        }

# API endpoint
@app.post("/feedback")
async def submit_feedback(feedback: Feedback):
    collector.collect(feedback)
    return {"status": "received"}
```

## 28.7 Conversation Management UI

```python
class ConversationUI:
    def format_message(self, role: str, content: str) -> dict:
        """Format message for display"""
        return {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }

    def format_tool_use(self, tool: str, status: str, result: str = None) -> dict:
        """Format tool use for display"""
        return {
            "type": "tool",
            "tool": tool,
            "status": status,  # running, complete, error
            "result_preview": result[:100] if result else None
        }

    def truncate_for_display(self, text: str, max_length: int = 500) -> str:
        """Truncate long responses with 'show more'"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
```

## 28.8 Summary

| Pattern | Purpose |
|---------|---------|
| Streaming | Immediate feedback |
| Loading states | Clear status |
| Error messages | User-friendly failures |
| Typing simulation | Natural feel |
| Suggestions | Guide users |
| Feedback | Improve quality |

**Best practices:**
- Always stream for long responses
- Show clear loading indicators
- Provide helpful error messages
- Offer suggested prompts
- Collect user feedback
- Make actions reversible
- Show confidence when uncertain
