# Module 39: Long Context Strategies

## 39.1 The Long Context Challenge

```
Problem:
- Documents can be millions of tokens
- Context windows are limited (128k-200k typical)
- Performance degrades with length
- "Lost in the middle" phenomenon
- Cost increases with context size

Solutions:
- Chunking and retrieval (RAG)
- Hierarchical summarization
- Map-reduce patterns
- Sliding window
- Selective context
```

## 39.2 Hierarchical Summarization

```python
class HierarchicalSummarizer:
    def __init__(self, chunk_size: int = 4000, summary_ratio: float = 0.2):
        self.chunk_size = chunk_size
        self.summary_ratio = summary_ratio

    async def summarize(self, text: str) -> str:
        # Split into chunks
        chunks = self._chunk(text)

        if len(chunks) == 1:
            return await self._summarize_chunk(chunks[0])

        # Level 1: Summarize each chunk
        summaries = []
        for chunk in chunks:
            summary = await self._summarize_chunk(chunk)
            summaries.append(summary)

        # Combine summaries
        combined = "\n\n".join(summaries)

        # Recursively summarize if still too long
        if len(combined.split()) > self.chunk_size:
            return await self.summarize(combined)

        # Final summary
        return await self._final_summary(combined)

    def _chunk(self, text: str) -> list[str]:
        words = text.split()
        return [
            " ".join(words[i:i + self.chunk_size])
            for i in range(0, len(words), self.chunk_size)
        ]

    async def _summarize_chunk(self, chunk: str) -> str:
        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=int(len(chunk.split()) * self.summary_ratio),
            messages=[{
                "role": "user",
                "content": f"Summarize this text concisely:\n\n{chunk}"
            }]
        )
        return response.content[0].text
```

## 39.3 Map-Reduce Pattern

```python
class MapReduce:
    async def process(self, documents: list[str], question: str) -> str:
        # Map: Process each document
        mapped_results = await asyncio.gather(*[
            self._map(doc, question) for doc in documents
        ])

        # Reduce: Combine results
        return await self._reduce(mapped_results, question)

    async def _map(self, document: str, question: str) -> str:
        prompt = f"""
Extract information relevant to this question from the document.

Question: {question}

Document:
{document}

Relevant information (if any):
"""
        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def _reduce(self, results: list[str], question: str) -> str:
        combined = "\n\n---\n\n".join([
            f"Source {i+1}:\n{r}" for i, r in enumerate(results) if r.strip()
        ])

        prompt = f"""
Based on these extracted pieces of information, answer the question.

Question: {question}

Information:
{combined}

Answer:
"""
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

## 39.4 Sliding Window

```python
class SlidingWindowProcessor:
    def __init__(self, window_size: int = 10000, overlap: int = 1000):
        self.window_size = window_size
        self.overlap = overlap

    async def process(self, text: str, instruction: str) -> list[str]:
        windows = self._create_windows(text)
        results = []

        for i, window in enumerate(windows):
            prompt = f"""
{instruction}

Text (part {i+1} of {len(windows)}):
{window}
"""
            response = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            results.append(response.content[0].text)

        return results

    def _create_windows(self, text: str) -> list[str]:
        words = text.split()
        windows = []
        start = 0

        while start < len(words):
            end = start + self.window_size
            windows.append(" ".join(words[start:end]))
            start = end - self.overlap

        return windows
```

## 39.5 Selective Context

```python
class SelectiveContext:
    """Select most relevant parts of long document"""

    async def select(
        self,
        document: str,
        query: str,
        max_tokens: int = 10000
    ) -> str:
        # Split into sections
        sections = self._split_sections(document)

        # Score each section
        scored = []
        for section in sections:
            score = await self._relevance_score(section, query)
            scored.append((section, score))

        # Sort by relevance
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select top sections within budget
        selected = []
        total_tokens = 0

        for section, score in scored:
            section_tokens = len(section.split()) * 1.3
            if total_tokens + section_tokens > max_tokens:
                break
            selected.append(section)
            total_tokens += section_tokens

        return "\n\n".join(selected)

    async def _relevance_score(self, section: str, query: str) -> float:
        # Use embeddings for fast scoring
        section_emb = await self._embed(section[:1000])
        query_emb = await self._embed(query)
        return cosine_similarity(section_emb, query_emb)
```

## 39.6 Context Compression

```python
class ContextCompressor:
    async def compress(self, context: str, query: str, target_ratio: float = 0.3) -> str:
        prompt = f"""
Compress this context while preserving information relevant to the query.
Keep key facts, remove redundancy and filler.

Query: {query}

Context:
{context}

Compressed context (keep most important information):
"""
        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=int(len(context.split()) * target_ratio),
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

class LLMLingua:
    """Simulate LLMLingua-style compression"""

    def compress(self, text: str, ratio: float = 0.5) -> str:
        # Simple heuristic compression
        sentences = text.split('. ')

        # Keep sentences with higher information density
        scored = []
        for sent in sentences:
            # Simple scoring: length and unique words
            score = len(set(sent.lower().split())) / max(len(sent.split()), 1)
            scored.append((sent, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Keep top sentences
        keep = int(len(scored) * ratio)
        kept = [s[0] for s in scored[:keep]]

        # Restore original order
        return '. '.join(kept)
```

## 39.7 Document Sectioning

```python
class DocumentSectioner:
    """Smart document splitting for long context"""

    def section(self, document: str) -> list[dict]:
        sections = []

        # Split by headers
        parts = re.split(r'\n(#{1,3}\s+.+)\n', document)

        current_header = "Introduction"
        current_content = []

        for part in parts:
            if re.match(r'^#{1,3}\s+', part):
                if current_content:
                    sections.append({
                        "header": current_header,
                        "content": "\n".join(current_content)
                    })
                current_header = part.strip()
                current_content = []
            else:
                current_content.append(part)

        if current_content:
            sections.append({
                "header": current_header,
                "content": "\n".join(current_content)
            })

        return sections

    def get_section_by_relevance(
        self,
        sections: list[dict],
        query: str,
        max_sections: int = 5
    ) -> list[dict]:
        # Score and select relevant sections
        scored = []
        for section in sections:
            score = self._quick_relevance(section["content"], query)
            scored.append((section, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:max_sections]]
```

## 39.8 Incremental Processing

```python
class IncrementalProcessor:
    """Process long document maintaining state"""

    def __init__(self):
        self.state = {"facts": [], "entities": set(), "summary": ""}

    async def process_chunk(self, chunk: str, chunk_idx: int) -> dict:
        prompt = f"""
Previous summary: {self.state['summary']}
Known entities: {list(self.state['entities'])[:20]}

New content (chunk {chunk_idx}):
{chunk}

Extract:
1. New important facts
2. New entities mentioned
3. Updated summary

Return JSON: {{"facts": [...], "entities": [...], "summary": "..."}}
"""
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        result = json.loads(response.content[0].text)

        # Update state
        self.state["facts"].extend(result["facts"])
        self.state["entities"].update(result["entities"])
        self.state["summary"] = result["summary"]

        return self.state
```

## 39.9 Lost in the Middle Mitigation

```python
def reorder_for_attention(documents: list[str], query: str) -> list[str]:
    """Put most relevant documents at start and end"""
    # Score documents
    scored = [(doc, relevance_score(doc, query)) for doc in documents]
    scored.sort(key=lambda x: x[1], reverse=True)

    if len(scored) <= 2:
        return [s[0] for s in scored]

    # Reorder: best at start, second-best at end, rest in middle
    result = []
    result.append(scored[0][0])  # Best at start

    # Middle (less important)
    for doc, _ in scored[2:]:
        result.append(doc)

    result.append(scored[1][0])  # Second best at end

    return result
```

## 39.10 Summary

| Strategy | Best For |
|----------|----------|
| Hierarchical summary | Full document understanding |
| Map-reduce | Multi-document analysis |
| Sliding window | Sequential processing |
| Selective context | Question answering |
| Compression | Token budget constraints |

**Best practices:**
- Use RAG for most long-context needs
- Put important info at start/end
- Compress redundant content
- Process incrementally for very long docs
- Match strategy to task type
- Monitor quality vs. context length
