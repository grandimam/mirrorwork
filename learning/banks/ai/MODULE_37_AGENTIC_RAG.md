# Module 37: Agentic RAG

## 37.1 What is Agentic RAG?

```
Basic RAG:
Query → Retrieve → Generate → Done

Agentic RAG:
Query → Reason about what to retrieve
      → Retrieve
      → Evaluate if sufficient
      → Retrieve more if needed
      → Synthesize across sources
      → Self-correct if wrong
      → Generate final answer

Key difference: Agent decides WHAT, WHEN, and HOW MUCH to retrieve
```

## 37.2 Basic vs Agentic RAG

```python
# Basic RAG: Fixed retrieval
async def basic_rag(query: str) -> str:
    docs = await retrieve(query, k=5)  # Always 5 docs
    return await generate(query, docs)

# Agentic RAG: Dynamic retrieval
async def agentic_rag(query: str) -> str:
    # Agent decides retrieval strategy
    plan = await plan_retrieval(query)

    all_docs = []
    for step in plan:
        docs = await retrieve(step["query"], k=step["k"])
        all_docs.extend(docs)

        # Check if we have enough
        if await is_sufficient(query, all_docs):
            break

    return await generate(query, all_docs)
```

## 37.3 Retrieval Planning

```python
class RetrievalPlanner:
    async def plan(self, query: str) -> list[dict]:
        prompt = f"""
Analyze this question and plan retrieval strategy.

Question: {query}

Decide:
1. What specific information do we need?
2. What queries should we run?
3. How many documents per query?

Return JSON:
[{{"query": "...", "k": N, "reason": "..."}}]
"""
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)

# Example output:
# [
#   {"query": "Python async best practices", "k": 3, "reason": "core concepts"},
#   {"query": "asyncio error handling", "k": 2, "reason": "specific topic"},
#   {"query": "async performance optimization", "k": 2, "reason": "advanced"}
# ]
```

## 37.4 Iterative Retrieval

```python
class IterativeRetriever:
    def __init__(self, vector_store, max_iterations: int = 3):
        self.store = vector_store
        self.max_iterations = max_iterations

    async def retrieve(self, query: str) -> list:
        all_docs = []
        seen_ids = set()

        for i in range(self.max_iterations):
            # Generate retrieval query
            if i == 0:
                search_query = query
            else:
                search_query = await self._generate_followup_query(
                    query, all_docs
                )

            # Retrieve
            docs = await self.store.search(search_query, k=5)
            new_docs = [d for d in docs if d["id"] not in seen_ids]

            if not new_docs:
                break

            all_docs.extend(new_docs)
            seen_ids.update(d["id"] for d in new_docs)

            # Check if sufficient
            if await self._is_sufficient(query, all_docs):
                break

        return all_docs

    async def _generate_followup_query(self, original: str, docs: list) -> str:
        prompt = f"""
Original question: {original}

Documents retrieved so far:
{self._summarize_docs(docs)}

What additional information should we search for?
Generate a search query for missing information.
"""
        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    async def _is_sufficient(self, query: str, docs: list) -> bool:
        prompt = f"""
Question: {query}

Retrieved documents cover:
{self._summarize_docs(docs)}

Can we fully answer the question with these documents?
Answer YES or NO.
"""
        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        return "YES" in response.content[0].text.upper()
```

## 37.5 Multi-Source RAG Agent

```python
class MultiSourceRAGAgent:
    def __init__(self):
        self.sources = {
            "docs": DocumentStore(),
            "web": WebSearchTool(),
            "database": DatabaseTool(),
        }

    async def answer(self, query: str) -> dict:
        # Decide which sources to use
        sources_to_use = await self._select_sources(query)

        # Retrieve from each source
        all_results = {}
        for source_name in sources_to_use:
            source = self.sources[source_name]
            results = await source.search(query)
            all_results[source_name] = results

        # Synthesize
        answer = await self._synthesize(query, all_results)

        return {
            "answer": answer,
            "sources_used": sources_to_use,
            "results": all_results
        }

    async def _select_sources(self, query: str) -> list[str]:
        prompt = f"""
Question: {query}

Available sources:
- docs: Internal documentation
- web: Live web search
- database: Company database

Which sources should we query? Return as JSON array.
"""
        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)
```

## 37.6 Self-Correcting RAG

```python
class SelfCorrectingRAG:
    async def answer(self, query: str) -> str:
        # Initial retrieval and generation
        docs = await self.retrieve(query)
        answer = await self.generate(query, docs)

        # Verify answer
        verification = await self._verify(query, answer, docs)

        if not verification["is_correct"]:
            # Retrieve more based on what's wrong
            additional_query = verification["missing_info"]
            more_docs = await self.retrieve(additional_query)

            # Regenerate with more context
            answer = await self.generate(query, docs + more_docs)

        return answer

    async def _verify(self, query: str, answer: str, docs: list) -> dict:
        prompt = f"""
Question: {query}
Answer: {answer}
Sources: {self._format_docs(docs)}

Verify:
1. Is the answer correct based on sources?
2. Is anything missing or wrong?
3. What additional info would help?

Return JSON: {{"is_correct": bool, "issues": [...], "missing_info": "..."}}
"""
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)
```

## 37.7 RAG Agent with Tools

```python
RAG_TOOLS = [
    {
        "name": "search_documents",
        "description": "Search internal documents",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {"type": "object"},
                "k": {"type": "integer", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_web",
        "description": "Search the web for current information",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "get_document",
        "description": "Get full content of a specific document",
        "input_schema": {
            "type": "object",
            "properties": {"doc_id": {"type": "string"}},
            "required": ["doc_id"]
        }
    }
]

async def rag_agent(query: str) -> str:
    system = """You are a research assistant. Use the available tools to find
information and answer questions. Search multiple sources if needed.
Always cite your sources."""

    messages = [{"role": "user", "content": query}]

    while True:
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=system,
            tools=RAG_TOOLS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return extract_text(response)

        # Execute tools and continue
        messages = await process_tool_calls(messages, response)
```

## 37.8 Query Decomposition

```python
class QueryDecomposer:
    async def decompose(self, complex_query: str) -> list[str]:
        """Break complex query into sub-queries"""
        prompt = f"""
Break this complex question into simpler sub-questions that can be answered independently.

Question: {complex_query}

Return JSON array of sub-questions.
"""
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)

class DecomposedRAG:
    async def answer(self, query: str) -> str:
        # Decompose
        sub_queries = await self.decomposer.decompose(query)

        # Answer each sub-query
        sub_answers = []
        for sq in sub_queries:
            docs = await self.retrieve(sq)
            answer = await self.generate(sq, docs)
            sub_answers.append({"query": sq, "answer": answer})

        # Synthesize final answer
        return await self._synthesize(query, sub_answers)
```

## 37.9 Adaptive Retrieval

```python
class AdaptiveRetriever:
    """Adjust retrieval strategy based on query type"""

    async def retrieve(self, query: str) -> list:
        query_type = await self._classify_query(query)

        if query_type == "factual":
            # Precise retrieval, few docs
            return await self.store.search(query, k=3)

        elif query_type == "exploratory":
            # Broad retrieval, more docs
            return await self.store.search(query, k=10)

        elif query_type == "comparative":
            # Multiple targeted searches
            aspects = await self._extract_aspects(query)
            all_docs = []
            for aspect in aspects:
                docs = await self.store.search(aspect, k=3)
                all_docs.extend(docs)
            return all_docs

        elif query_type == "temporal":
            # Filter by date
            return await self.store.search(
                query, k=5,
                filters={"date": {"$gte": "2024-01-01"}}
            )
```

## 37.10 Summary

| Pattern | Use Case |
|---------|----------|
| Iterative retrieval | Complex multi-part questions |
| Multi-source | Questions spanning domains |
| Self-correcting | High accuracy requirements |
| Query decomposition | Complex analytical questions |
| Adaptive | Mixed query types |

**Best practices:**
- Let agent decide retrieval strategy
- Implement sufficiency checking
- Support multiple retrieval rounds
- Verify answers against sources
- Decompose complex queries
- Track retrieval decisions for debugging
