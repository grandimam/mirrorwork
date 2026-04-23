# Module 42: Context Engineering

## 42.1 What is Context Engineering?

```
Prompt Engineering: Crafting instructions
Context Engineering: Assembling the right information

Context includes:
- System instructions
- Examples (few-shot)
- Retrieved documents
- Conversation history
- Tool results
- User preferences
- Metadata

Goal: Right information, right order, right amount
```

## 42.2 Context Assembly Pipeline

```python
class ContextAssembler:
    def __init__(self, max_tokens: int = 100000):
        self.max_tokens = max_tokens

    def assemble(
        self,
        query: str,
        system_prompt: str,
        examples: list[dict] = None,
        retrieved_docs: list[str] = None,
        conversation_history: list[dict] = None,
        user_context: dict = None
    ) -> dict:
        budget = self.max_tokens
        components = []

        # Priority 1: System prompt (always include)
        components.append({"type": "system", "content": system_prompt})
        budget -= self._count_tokens(system_prompt)

        # Priority 2: User context/preferences
        if user_context:
            ctx = self._format_user_context(user_context)
            components.append({"type": "user_context", "content": ctx})
            budget -= self._count_tokens(ctx)

        # Priority 3: Retrieved docs (most relevant first)
        if retrieved_docs:
            docs_content = self._fit_documents(retrieved_docs, budget * 0.5)
            components.append({"type": "documents", "content": docs_content})
            budget -= self._count_tokens(docs_content)

        # Priority 4: Examples (if space)
        if examples and budget > 2000:
            examples_content = self._fit_examples(examples, min(budget * 0.2, 4000))
            components.append({"type": "examples", "content": examples_content})
            budget -= self._count_tokens(examples_content)

        # Priority 5: Conversation history (recent first)
        if conversation_history:
            history = self._fit_history(conversation_history, budget * 0.8)
            components.append({"type": "history", "content": history})

        return self._build_messages(components, query)
```

## 42.3 Document Ordering Strategies

```python
class DocumentOrderer:
    """Order documents to maximize attention"""

    def order_for_qa(self, docs: list[dict], query: str) -> list[dict]:
        """Best docs at start and end (avoid lost in middle)"""
        if len(docs) <= 2:
            return docs

        # Sort by relevance
        sorted_docs = sorted(docs, key=lambda x: x.get("score", 0), reverse=True)

        # Reorder: best → worst → second best
        result = [sorted_docs[0]]  # Best at start
        result.extend(sorted_docs[2:])  # Middle (less important)
        result.append(sorted_docs[1])  # Second best at end

        return result

    def order_chronological(self, docs: list[dict]) -> list[dict]:
        """For narrative/timeline questions"""
        return sorted(docs, key=lambda x: x.get("date", ""))

    def order_by_source(self, docs: list[dict]) -> list[dict]:
        """Group by source for clarity"""
        from itertools import groupby

        docs = sorted(docs, key=lambda x: x.get("source", ""))
        grouped = []

        for source, group in groupby(docs, key=lambda x: x.get("source", "")):
            grouped.append(f"\n## Source: {source}\n")
            grouped.extend(list(group))

        return grouped
```

## 42.4 Dynamic Example Selection

```python
class ExampleSelector:
    """Select most relevant few-shot examples"""

    def __init__(self, examples: list[dict]):
        self.examples = examples
        self.embeddings = None

    async def initialize(self):
        """Pre-compute example embeddings"""
        texts = [ex["input"] for ex in self.examples]
        self.embeddings = await batch_embed(texts)

    async def select(self, query: str, k: int = 3) -> list[dict]:
        query_embedding = await embed(query)

        # Find most similar examples
        similarities = [
            cosine_similarity(query_embedding, emb)
            for emb in self.embeddings
        ]

        # Get top-k indices
        top_indices = sorted(
            range(len(similarities)),
            key=lambda i: similarities[i],
            reverse=True
        )[:k]

        return [self.examples[i] for i in top_indices]

    def select_diverse(self, query: str, k: int = 3) -> list[dict]:
        """Select diverse examples (MMR-like)"""
        selected = []
        remaining = list(range(len(self.examples)))

        for _ in range(k):
            if not remaining:
                break

            # Score: relevance - similarity to already selected
            best_idx = None
            best_score = -float("inf")

            for idx in remaining:
                relevance = self._relevance(query, idx)
                diversity = self._diversity(idx, selected)
                score = 0.7 * relevance + 0.3 * diversity

                if score > best_score:
                    best_score = score
                    best_idx = idx

            selected.append(best_idx)
            remaining.remove(best_idx)

        return [self.examples[i] for i in selected]
```

## 42.5 Conversation History Management

```python
class ConversationManager:
    def __init__(self, max_tokens: int = 10000):
        self.max_tokens = max_tokens

    def prepare_history(self, messages: list[dict]) -> list[dict]:
        """Prepare conversation history within token budget"""
        if not messages:
            return []

        # Always keep system message
        system = [m for m in messages if m["role"] == "system"]
        others = [m for m in messages if m["role"] != "system"]

        # Count tokens
        total = sum(self._count_tokens(m["content"]) for m in system)

        # Add messages from newest to oldest
        kept = []
        for msg in reversed(others):
            msg_tokens = self._count_tokens(msg["content"])
            if total + msg_tokens > self.max_tokens:
                break
            kept.insert(0, msg)
            total += msg_tokens

        return system + kept

    def summarize_old_messages(self, messages: list[dict], keep_recent: int = 4) -> list[dict]:
        """Summarize older messages to save tokens"""
        if len(messages) <= keep_recent:
            return messages

        old = messages[:-keep_recent]
        recent = messages[-keep_recent:]

        # Summarize old messages
        summary = self._summarize(old)

        return [
            {"role": "system", "content": f"Previous conversation summary:\n{summary}"}
        ] + recent
```

## 42.6 Context Compression

```python
class ContextCompressor:
    async def compress(self, context: str, query: str, target_tokens: int) -> str:
        current_tokens = self._count_tokens(context)

        if current_tokens <= target_tokens:
            return context

        ratio = target_tokens / current_tokens

        prompt = f"""
Compress this context to approximately {int(ratio * 100)}% of its length.
Preserve information relevant to: {query}
Remove redundancy and filler words.

Context:
{context}

Compressed:"""

        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=target_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    def extractive_compress(self, context: str, query: str, ratio: float = 0.5) -> str:
        """Keep most relevant sentences"""
        sentences = context.split('. ')

        # Score sentences by relevance to query
        scored = []
        query_words = set(query.lower().split())

        for sent in sentences:
            sent_words = set(sent.lower().split())
            overlap = len(query_words & sent_words) / len(query_words)
            scored.append((sent, overlap))

        # Keep top sentences
        scored.sort(key=lambda x: x[1], reverse=True)
        keep_count = int(len(sentences) * ratio)

        # Maintain original order
        kept_sentences = set(s[0] for s in scored[:keep_count])
        return '. '.join(s for s in sentences if s in kept_sentences)
```

## 42.7 Metadata Injection

```python
class MetadataInjector:
    def inject(self, query: str, metadata: dict) -> str:
        """Add relevant metadata to context"""
        parts = []

        # Current time context
        if metadata.get("include_time", True):
            parts.append(f"Current time: {datetime.now().isoformat()}")

        # User preferences
        if "user_preferences" in metadata:
            prefs = metadata["user_preferences"]
            parts.append(f"User preferences: {json.dumps(prefs)}")

        # Domain context
        if "domain" in metadata:
            parts.append(f"Domain: {metadata['domain']}")

        # Session context
        if "session_info" in metadata:
            parts.append(f"Session: {metadata['session_info']}")

        context_header = "\n".join(parts)

        return f"""
Context:
{context_header}

Query: {query}
"""
```

## 42.8 Context Quality Scoring

```python
class ContextScorer:
    async def score(self, context: str, query: str) -> dict:
        """Score context quality"""
        scores = {}

        # Relevance: Does context relate to query?
        scores["relevance"] = await self._score_relevance(context, query)

        # Coverage: Does context cover query aspects?
        scores["coverage"] = await self._score_coverage(context, query)

        # Coherence: Is context well-organized?
        scores["coherence"] = await self._score_coherence(context)

        # Redundancy: How much repetition?
        scores["redundancy"] = self._score_redundancy(context)

        scores["overall"] = (
            0.4 * scores["relevance"] +
            0.3 * scores["coverage"] +
            0.2 * scores["coherence"] +
            0.1 * (1 - scores["redundancy"])
        )

        return scores

    def _score_redundancy(self, context: str) -> float:
        """Measure repetition in context"""
        sentences = context.split('. ')
        if len(sentences) < 2:
            return 0

        # Check for similar sentences
        duplicates = 0
        for i, s1 in enumerate(sentences):
            for s2 in sentences[i+1:]:
                if self._similarity(s1, s2) > 0.8:
                    duplicates += 1

        return duplicates / len(sentences)
```

## 42.9 Context Templates

```python
# Standard context template
QA_CONTEXT_TEMPLATE = """
## Instructions
{system_prompt}

## Reference Documents
{documents}

## Examples
{examples}

## Conversation
{history}

## Current Question
{query}
"""

# RAG-specific template
RAG_TEMPLATE = """
Answer the question using ONLY the information in the provided documents.
If the answer is not in the documents, say "I don't have information about that."

Documents:
{documents}

Question: {query}

Answer (with citations):
"""

# Agent context template
AGENT_TEMPLATE = """
## Your Role
{role_description}

## Available Tools
{tools}

## Previous Actions
{action_history}

## Current Task
{task}

Decide your next action:
"""
```

## 42.10 Summary

| Component | Priority | Strategy |
|-----------|----------|----------|
| System prompt | Highest | Always include |
| User context | High | Personalization |
| Retrieved docs | High | Relevance-ordered |
| Examples | Medium | Dynamic selection |
| History | Medium | Recent + summary |
| Metadata | Low | As needed |

**Best practices:**
- Order by priority and relevance
- Put critical info at start/end
- Compress when over budget
- Select examples dynamically
- Summarize old conversation
- Score and monitor context quality
- Use templates for consistency
