# Module 21: Deployment Patterns

## 21.1 API Service Architecture

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        response = await agent.run(request.message)
        return ChatResponse(
            response=response,
            conversation_id=request.conversation_id or str(uuid.uuid4())
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 21.2 Streaming Endpoint

```python
from fastapi.responses import StreamingResponse

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        async with client.messages.stream(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": request.message}]
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
```

## 21.3 Background Processing

```python
from celery import Celery

celery_app = Celery("tasks", broker="redis://localhost:6379")

@celery_app.task
def process_document(doc_id: str):
    """Long-running task for document processing"""
    doc = load_document(doc_id)
    chunks = chunk_document(doc)
    embeddings = generate_embeddings(chunks)
    store_embeddings(doc_id, embeddings)
    return {"status": "complete", "chunks": len(chunks)}

# API endpoint
@app.post("/documents/{doc_id}/process")
async def start_processing(doc_id: str):
    task = process_document.delay(doc_id)
    return {"task_id": task.id}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    result = celery_app.AsyncResult(task_id)
    return {"status": result.status, "result": result.result}
```

## 21.4 Queue-Based Architecture

```python
import asyncio
from asyncio import Queue

class AgentWorker:
    def __init__(self, queue: Queue, num_workers: int = 5):
        self.queue = queue
        self.num_workers = num_workers

    async def worker(self, worker_id: int):
        while True:
            task = await self.queue.get()
            try:
                result = await self.process(task)
                task["callback"](result)
            except Exception as e:
                task["error_callback"](e)
            finally:
                self.queue.task_done()

    async def start(self):
        workers = [
            asyncio.create_task(self.worker(i))
            for i in range(self.num_workers)
        ]
        await asyncio.gather(*workers)

    async def process(self, task: dict) -> str:
        return await agent.run(task["message"])
```

## 21.5 Scaling Considerations

```python
# Horizontal scaling with load balancing
"""
                    ┌─────────────┐
                    │   Load      │
                    │  Balancer   │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │   Agent     │ │   Agent     │ │   Agent     │
    │  Instance 1 │ │  Instance 2 │ │  Instance 3 │
    └─────────────┘ └─────────────┘ └─────────────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                    ┌─────────────┐
                    │   Shared    │
                    │   State     │
                    │   (Redis)   │
                    └─────────────┘
"""

# Shared state for scaling
import redis

class SharedState:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)

    def get_conversation(self, conv_id: str) -> list:
        data = self.redis.get(f"conv:{conv_id}")
        return json.loads(data) if data else []

    def save_conversation(self, conv_id: str, messages: list):
        self.redis.set(f"conv:{conv_id}", json.dumps(messages), ex=3600)
```

## 21.6 Health Checks

```python
@app.get("/health")
async def health_check():
    checks = {}

    # Check LLM API
    try:
        await client.messages.create(
            model="claude-3-haiku",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}]
        )
        checks["llm"] = "healthy"
    except Exception as e:
        checks["llm"] = f"unhealthy: {e}"

    # Check vector DB
    try:
        await vector_db.ping()
        checks["vector_db"] = "healthy"
    except Exception as e:
        checks["vector_db"] = f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in checks.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks
    }
```

## 21.7 Configuration Management

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM settings
    anthropic_api_key: str
    default_model: str = "claude-3-5-sonnet"
    max_tokens: int = 4096

    # Rate limiting
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 100000

    # Feature flags
    enable_streaming: bool = True
    enable_caching: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
```

## 21.8 Summary

| Pattern | Use Case |
|---------|----------|
| REST API | Simple request-response |
| Streaming | Real-time responses |
| Background jobs | Long-running tasks |
| Queue | High throughput |
| Serverless | Variable load |

**Best practices:**
- Implement health checks
- Use environment variables
- Plan for horizontal scaling
- Separate compute from state
- Monitor everything
- Set timeouts at every layer
