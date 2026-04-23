# Module 8: Conversation Management

## 8.1 Conversation State

Conversations need state management: history, context, metadata.

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

@dataclass
class Conversation:
    id: str
    messages: list[Message] = field(default_factory=list)
    system_prompt: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata):
        self.messages.append(Message(role=role, content=content, metadata=metadata))

    def to_api_format(self) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in self.messages]
```

## 8.2 Conversation Manager

```python
class ConversationManager:
    def __init__(self, client, system_prompt: str = None):
        self.client = client
        self.system_prompt = system_prompt
        self.conversations: dict[str, Conversation] = {}

    def create(self, conversation_id: str = None) -> Conversation:
        conv_id = conversation_id or str(uuid.uuid4())
        conv = Conversation(id=conv_id, system_prompt=self.system_prompt)
        self.conversations[conv_id] = conv
        return conv

    def get(self, conversation_id: str) -> Optional[Conversation]:
        return self.conversations.get(conversation_id)

    async def send_message(
        self,
        conversation_id: str,
        user_message: str
    ) -> str:
        conv = self.get(conversation_id)
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Add user message
        conv.add_message("user", user_message)

        # Call LLM
        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            system=conv.system_prompt,
            max_tokens=1024,
            messages=conv.to_api_format()
        )

        assistant_message = response.content[0].text
        conv.add_message("assistant", assistant_message)

        return assistant_message
```

## 8.3 Context Window Management

```python
class ContextWindowManager:
    def __init__(self, max_tokens: int = 100000, reserve_output: int = 4000):
        self.max_tokens = max_tokens
        self.reserve_output = reserve_output

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4 + 1

    def trim_messages(self, messages: list[Message], system_prompt: str = "") -> list[Message]:
        available = self.max_tokens - self.reserve_output
        available -= self.estimate_tokens(system_prompt)

        # Always keep first (oldest context) and recent messages
        if len(messages) <= 2:
            return messages

        # Calculate total tokens
        total = sum(self.estimate_tokens(m.content) for m in messages)

        if total <= available:
            return messages

        # Trim from the middle, keeping first and last
        trimmed = [messages[0]]  # Keep first for context
        remaining = available - self.estimate_tokens(messages[0].content)

        # Add from end until we run out of space
        for msg in reversed(messages[1:]):
            msg_tokens = self.estimate_tokens(msg.content)
            if remaining >= msg_tokens:
                trimmed.insert(1, msg)
                remaining -= msg_tokens
            else:
                break

        return trimmed
```

## 8.4 Summarization for Long Conversations

```python
class SummarizingConversationManager:
    def __init__(self, client, max_messages: int = 20):
        self.client = client
        self.max_messages = max_messages

    async def maybe_summarize(self, conv: Conversation):
        if len(conv.messages) < self.max_messages:
            return

        # Summarize older messages
        old_messages = conv.messages[:-4]  # Keep last 4 intact
        summary = await self.summarize_messages(old_messages)

        # Replace old messages with summary
        conv.messages = [
            Message(role="system", content=f"Previous conversation summary: {summary}"),
            *conv.messages[-4:]
        ]

    async def summarize_messages(self, messages: list[Message]) -> str:
        conversation_text = "\n".join([
            f"{m.role}: {m.content}" for m in messages
        ])

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"Summarize this conversation:\n{conversation_text}"
            }]
        )

        return response.content[0].text
```

## 8.5 Conversation Persistence

```python
import json
from pathlib import Path

class ConversationStore:
    def __init__(self, storage_path: str = "conversations"):
        self.path = Path(storage_path)
        self.path.mkdir(exist_ok=True)

    def save(self, conv: Conversation):
        data = {
            "id": conv.id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata
                }
                for m in conv.messages
            ],
            "system_prompt": conv.system_prompt,
            "created_at": conv.created_at.isoformat(),
            "metadata": conv.metadata
        }

        file_path = self.path / f"{conv.id}.json"
        file_path.write_text(json.dumps(data, indent=2))

    def load(self, conversation_id: str) -> Optional[Conversation]:
        file_path = self.path / f"{conversation_id}.json"
        if not file_path.exists():
            return None

        data = json.loads(file_path.read_text())
        conv = Conversation(
            id=data["id"],
            system_prompt=data.get("system_prompt"),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {})
        )

        for m in data["messages"]:
            conv.messages.append(Message(
                role=m["role"],
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]),
                metadata=m.get("metadata", {})
            ))

        return conv
```

## 8.6 Multi-Turn with Tool Use

```python
async def conversation_with_tools(
    conv: Conversation,
    user_message: str,
    tools: list,
    executor: ToolExecutor
) -> str:
    conv.add_message("user", user_message)

    while True:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            system=conv.system_prompt,
            max_tokens=1024,
            tools=tools,
            messages=conv.to_api_format()
        )

        if response.stop_reason == "end_turn":
            text = next(
                (b.text for b in response.content if b.type == "text"),
                ""
            )
            conv.add_message("assistant", text)
            return text

        if response.stop_reason == "tool_use":
            # Add assistant response with tool calls
            conv.add_message("assistant", response.content, raw=True)

            # Execute tools and add results
            for block in response.content:
                if block.type == "tool_use":
                    result = executor.execute(block.name, block.input)
                    conv.add_message("user", {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    }, raw=True)
```

## 8.7 Conversation Branching

```python
class BranchableConversation:
    def __init__(self, conv: Conversation):
        self.conv = conv
        self.branches: dict[str, Conversation] = {}

    def branch(self, branch_name: str, from_message_index: int = -1) -> Conversation:
        """Create a branch from a specific point"""
        new_conv = Conversation(
            id=f"{self.conv.id}_{branch_name}",
            system_prompt=self.conv.system_prompt,
            metadata={"parent": self.conv.id, "branch": branch_name}
        )

        # Copy messages up to branch point
        new_conv.messages = self.conv.messages[:from_message_index + 1].copy()
        self.branches[branch_name] = new_conv

        return new_conv

    def get_branch(self, branch_name: str) -> Optional[Conversation]:
        return self.branches.get(branch_name)
```

## 8.8 Conversation Search

```python
class ConversationSearch:
    def __init__(self, embedder, vector_store):
        self.embedder = embedder
        self.store = vector_store

    async def index_conversation(self, conv: Conversation):
        """Index conversation messages for search"""
        for i, msg in enumerate(conv.messages):
            if msg.role == "user":  # Index user messages
                embedding = await self.embedder.embed(msg.content)
                self.store.add(
                    id=f"{conv.id}_{i}",
                    embedding=embedding,
                    content=msg.content,
                    metadata={
                        "conversation_id": conv.id,
                        "message_index": i,
                        "timestamp": msg.timestamp.isoformat()
                    }
                )

    async def search_conversations(
        self,
        query: str,
        top_k: int = 5
    ) -> list[dict]:
        """Search across all indexed conversations"""
        query_embedding = await self.embedder.embed(query)
        return self.store.search(query_embedding, top_k=top_k)
```

## 8.9 Session Management

```python
from datetime import timedelta

class SessionManager:
    def __init__(self, timeout: timedelta = timedelta(hours=1)):
        self.timeout = timeout
        self.sessions: dict[str, dict] = {}

    def create_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "user_id": user_id,
            "conversation_id": None,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        session = self.sessions.get(session_id)
        if not session:
            return None

        # Check timeout
        if datetime.now() - session["last_activity"] > self.timeout:
            del self.sessions[session_id]
            return None

        session["last_activity"] = datetime.now()
        return session

    def set_conversation(self, session_id: str, conversation_id: str):
        if session_id in self.sessions:
            self.sessions[session_id]["conversation_id"] = conversation_id
```

## 8.10 Summary

| Component | Purpose |
|-----------|---------|
| Message | Single turn in conversation |
| Conversation | Full conversation state |
| Manager | CRUD operations |
| Context Manager | Handle token limits |
| Store | Persistence |
| Session | User session tracking |

**Best practices:**
- Always manage context window limits
- Persist conversations for continuity
- Summarize long conversations
- Track metadata for analytics
- Implement proper session management
- Index for searchability
