# Module 12: Agent Memory

## 12.1 Memory Types

```
Short-term: Current conversation/task
Working: Scratchpad for current reasoning
Long-term: Persisted across sessions
Episodic: Past experiences/interactions
Semantic: Facts and knowledge
```

## 12.2 Short-Term Memory (Conversation)

```python
class ShortTermMemory:
    def __init__(self, max_messages: int = 50):
        self.messages = []
        self.max_messages = max_messages

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_context(self) -> list:
        return self.messages.copy()

    def clear(self):
        self.messages = []
```

## 12.3 Working Memory (Scratchpad)

```python
class WorkingMemory:
    """Temporary storage for current task reasoning"""

    def __init__(self):
        self.scratchpad = {}
        self.notes = []

    def store(self, key: str, value: any):
        self.scratchpad[key] = value

    def retrieve(self, key: str) -> any:
        return self.scratchpad.get(key)

    def add_note(self, note: str):
        self.notes.append({"note": note, "timestamp": datetime.now()})

    def get_scratchpad_summary(self) -> str:
        return "\n".join([f"- {k}: {v}" for k, v in self.scratchpad.items()])

    def clear(self):
        self.scratchpad = {}
        self.notes = []
```

## 12.4 Long-Term Memory (Vector Store)

```python
class LongTermMemory:
    def __init__(self, embedder, vector_store):
        self.embedder = embedder
        self.store = vector_store

    async def remember(self, content: str, metadata: dict = None):
        embedding = await self.embedder.embed(content)
        self.store.add(
            id=str(uuid.uuid4()),
            embedding=embedding,
            content=content,
            metadata=metadata or {}
        )

    async def recall(self, query: str, top_k: int = 5) -> list[str]:
        query_embedding = await self.embedder.embed(query)
        results = self.store.search(query_embedding, top_k=top_k)
        return [r["content"] for r in results]

    async def forget(self, memory_id: str):
        self.store.delete(memory_id)
```

## 12.5 Entity Memory

```python
class EntityMemory:
    """Track entities mentioned in conversations"""

    def __init__(self):
        self.entities = {}  # entity_name -> info

    def update_entity(self, name: str, info: dict):
        if name not in self.entities:
            self.entities[name] = {}
        self.entities[name].update(info)

    def get_entity(self, name: str) -> dict:
        return self.entities.get(name, {})

    def get_summary(self) -> str:
        lines = []
        for name, info in self.entities.items():
            lines.append(f"{name}: {info}")
        return "\n".join(lines)

    async def extract_entities(self, text: str, client) -> list[dict]:
        prompt = f"""
Extract entities from this text:
{text}

Return JSON: [{{"name": "...", "type": "person|place|thing", "info": {{}}}}]"""

        response = await client.messages.create(
            model="claude-3-haiku",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)
```

## 12.6 Memory-Augmented Agent

```python
class MemoryAgent:
    def __init__(self, client, tools):
        self.client = client
        self.tools = tools
        self.short_term = ShortTermMemory()
        self.working = WorkingMemory()
        self.long_term = LongTermMemory(embedder, vector_store)

    async def run(self, task: str) -> str:
        # Recall relevant memories
        memories = await self.long_term.recall(task)
        memory_context = "\n".join(memories) if memories else "No relevant memories."

        # Build prompt with memory
        system = f"""
You are an agent with access to memories.

Relevant memories:
{memory_context}

Working notes:
{self.working.get_scratchpad_summary()}
"""

        # Execute task
        result = await self._execute(task, system)

        # Store important information
        await self._maybe_remember(task, result)

        return result

    async def _maybe_remember(self, task: str, result: str):
        # Ask if this should be remembered
        prompt = f"""
Should this interaction be remembered for future reference?
Task: {task}
Result: {result}

Answer YES or NO."""

        response = await self.client.messages.create(
            model="claude-3-haiku",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        if "YES" in response.content[0].text:
            await self.long_term.remember(
                f"Task: {task}\nResult: {result}",
                {"type": "task_result"}
            )
```

## 12.7 Memory Retrieval Strategies

```python
class MemoryRetriever:
    def __init__(self, long_term: LongTermMemory):
        self.memory = long_term

    async def retrieve_by_relevance(self, query: str, top_k: int = 5):
        return await self.memory.recall(query, top_k)

    async def retrieve_by_recency(self, limit: int = 10):
        # Get most recent memories
        return self.memory.store.query(
            order_by="timestamp",
            descending=True,
            limit=limit
        )

    async def retrieve_by_importance(self, top_k: int = 5):
        # Get highest importance memories
        return self.memory.store.query(
            filter={"importance": {"$gte": 0.8}},
            limit=top_k
        )

    async def combined_retrieval(self, query: str) -> list:
        # Combine strategies
        relevant = await self.retrieve_by_relevance(query, 3)
        recent = await self.retrieve_by_recency(3)
        important = await self.retrieve_by_importance(2)

        # Deduplicate and merge
        seen = set()
        combined = []
        for mem in relevant + recent + important:
            if mem["id"] not in seen:
                seen.add(mem["id"])
                combined.append(mem)
        return combined
```

## 12.8 Memory Consolidation

```python
async def consolidate_memories(memories: list[str], client) -> str:
    """Summarize and consolidate related memories"""
    prompt = f"""
Consolidate these related memories into a single coherent summary:

{chr(10).join(f'- {m}' for m in memories)}

Consolidated summary:"""

    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## 12.9 Summary

| Memory Type | Scope | Storage |
|-------------|-------|---------|
| Short-term | Current conversation | In-memory list |
| Working | Current task | In-memory dict |
| Long-term | Persistent | Vector DB |
| Entity | Tracked entities | In-memory/DB |

**Best practices:**
- Clear short-term memory between tasks
- Use vector search for long-term retrieval
- Consolidate memories to prevent bloat
- Track entities for personalization
- Implement forgetting for relevance
