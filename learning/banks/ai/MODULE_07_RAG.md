# Module 7: RAG (Retrieval-Augmented Generation)

## 7.1 What is RAG?

RAG combines retrieval with generation: find relevant documents, then generate answer using them as context.

```
User: "What's our refund policy?"
            │
            ▼
    ┌───────────────┐
    │   Retrieval   │ → Find relevant docs
    └───────────────┘
            │
            ▼
    ┌───────────────┐
    │  Generation   │ → Answer using docs
    └───────────────┘
            │
            ▼
"According to our policy, refunds are available within 30 days..."
```

## 7.2 Basic RAG Pipeline

```python
class SimpleRAG:
    def __init__(self, llm_client, embedding_client, vector_store):
        self.llm = llm_client
        self.embedder = embedding_client
        self.store = vector_store

    async def query(self, question: str, top_k: int = 5) -> str:
        # 1. Embed the question
        query_embedding = await self.embedder.embed(question)

        # 2. Retrieve relevant documents
        docs = self.store.search(query_embedding, top_k=top_k)

        # 3. Build context
        context = "\n\n".join([
            f"[Source: {doc['metadata']['source']}]\n{doc['content']}"
            for doc in docs
        ])

        # 4. Generate answer
        prompt = f"""
Answer the question based on the following context.
If the answer cannot be found in the context, say "I don't have information about that."

Context:
{context}

Question: {question}

Answer:"""

        response = await self.llm.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text
```

## 7.3 Document Loading

```python
from pathlib import Path

def load_text_file(path: str) -> str:
    return Path(path).read_text()

def load_pdf(path: str) -> str:
    import pypdf
    reader = pypdf.PdfReader(path)
    return "\n".join(page.extract_text() for page in reader.pages)

def load_documents(directory: str) -> list[dict]:
    docs = []
    for path in Path(directory).glob("**/*"):
        if path.suffix == ".txt":
            content = load_text_file(path)
        elif path.suffix == ".pdf":
            content = load_pdf(path)
        elif path.suffix == ".md":
            content = load_text_file(path)
        else:
            continue

        docs.append({
            "content": content,
            "metadata": {"source": str(path), "type": path.suffix}
        })
    return docs
```

## 7.4 Chunking Strategies

```python
def chunk_by_tokens(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Simple token-based chunking"""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks

def chunk_by_paragraphs(text: str, max_chunk_size: int = 1000) -> list[str]:
    """Respect paragraph boundaries"""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_size = 0

    for para in paragraphs:
        para_size = len(para.split())
        if current_size + para_size > max_chunk_size and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_size = 0

        current_chunk.append(para)
        current_size += para_size

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks

def chunk_by_headers(text: str) -> list[dict]:
    """Split by markdown headers"""
    import re
    sections = re.split(r'\n(#{1,3}\s+.+)\n', text)

    chunks = []
    current_header = ""
    for i, section in enumerate(sections):
        if re.match(r'^#{1,3}\s+', section):
            current_header = section.strip()
        elif section.strip():
            chunks.append({
                "header": current_header,
                "content": section.strip()
            })

    return chunks
```

## 7.5 Indexing Pipeline

```python
class RAGIndexer:
    def __init__(self, embedder, vector_store):
        self.embedder = embedder
        self.store = vector_store

    async def index_documents(
        self,
        documents: list[dict],
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        for doc in documents:
            # Chunk the document
            chunks = chunk_by_tokens(
                doc["content"],
                chunk_size=chunk_size,
                overlap=chunk_overlap
            )

            # Embed and store each chunk
            for i, chunk in enumerate(chunks):
                embedding = await self.embedder.embed(chunk)

                self.store.add(
                    id=f"{doc['metadata']['source']}_{i}",
                    embedding=embedding,
                    content=chunk,
                    metadata={
                        **doc["metadata"],
                        "chunk_index": i
                    }
                )
```

## 7.6 Query Processing

```python
async def process_query(query: str, retriever) -> str:
    """Enhance query for better retrieval"""

    # 1. Query expansion (optional)
    expanded = await expand_query(query)

    # 2. Hypothetical document embedding (HyDE)
    # Generate what an ideal answer might look like
    hypothetical = await generate_hypothetical_answer(query)

    # 3. Combine original and hypothetical for search
    query_embedding = await embed(query)
    hyde_embedding = await embed(hypothetical)

    # Average embeddings
    combined = average_embeddings([query_embedding, hyde_embedding])

    return combined
```

## 7.7 Reranking

```python
async def rerank_results(
    query: str,
    results: list[dict],
    top_k: int = 5
) -> list[dict]:
    """Rerank results using LLM for better relevance"""

    # Simple: Use LLM to score relevance
    scored_results = []
    for result in results:
        score = await score_relevance(query, result["content"])
        scored_results.append({**result, "rerank_score": score})

    # Sort by rerank score
    scored_results.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored_results[:top_k]

async def score_relevance(query: str, document: str) -> float:
    """Score document relevance to query"""
    prompt = f"""
Rate the relevance of this document to the query on a scale of 0-10.
Return only the number.

Query: {query}
Document: {document[:500]}

Relevance score:"""

    response = await client.messages.create(
        model="claude-3-haiku",
        max_tokens=5,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        return float(response.content[0].text.strip()) / 10
    except:
        return 0.5
```

## 7.8 Context Assembly

```python
def assemble_context(
    results: list[dict],
    max_tokens: int = 4000
) -> str:
    """Assemble context within token budget"""
    context_parts = []
    total_tokens = 0

    for result in results:
        content = result["content"]
        tokens = len(content.split()) * 1.3  # Rough estimate

        if total_tokens + tokens > max_tokens:
            break

        source = result.get("metadata", {}).get("source", "Unknown")
        context_parts.append(f"[Source: {source}]\n{content}")
        total_tokens += tokens

    return "\n\n---\n\n".join(context_parts)
```

## 7.9 Citation and Attribution

```python
RAG_PROMPT_WITH_CITATIONS = """
Answer the question using the provided sources. Include citations in [1], [2] format.

Sources:
{sources}

Question: {question}

Provide your answer with citations:
"""

def format_sources(results: list[dict]) -> str:
    return "\n\n".join([
        f"[{i+1}] {r['metadata'].get('source', 'Unknown')}\n{r['content']}"
        for i, r in enumerate(results)
    ])

async def query_with_citations(question: str, results: list[dict]) -> str:
    sources = format_sources(results)
    prompt = RAG_PROMPT_WITH_CITATIONS.format(
        sources=sources,
        question=question
    )

    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text
```

## 7.10 Evaluation Metrics

```python
async def evaluate_rag_response(
    question: str,
    response: str,
    retrieved_docs: list[str],
    ground_truth: str = None
) -> dict:
    """Evaluate RAG quality"""

    # 1. Faithfulness: Is response grounded in retrieved docs?
    faithfulness_prompt = f"""
Is this response fully supported by the retrieved documents?
Score 0-10 (10 = fully supported, 0 = hallucinated)

Retrieved documents:
{retrieved_docs}

Response: {response}

Score:"""

    # 2. Relevance: Does response answer the question?
    relevance_prompt = f"""
Does this response adequately answer the question?
Score 0-10.

Question: {question}
Response: {response}

Score:"""

    # 3. If ground truth available: correctness
    # Compare response to ground truth

    return {
        "faithfulness": await get_score(faithfulness_prompt),
        "relevance": await get_score(relevance_prompt),
    }
```

## 7.11 Common RAG Failures

```python
# 1. Retrieval failure: Wrong docs retrieved
# Fix: Better chunking, hybrid search, reranking

# 2. Context stuffing: Too much irrelevant context
# Fix: Better relevance filtering, smaller chunks

# 3. Lost in the middle: Important info ignored
# Fix: Put critical info first/last, use structured prompts

# 4. Hallucination: Answer not in context
# Fix: Explicit grounding instructions, citations

# 5. Outdated information: Stale embeddings
# Fix: Re-index regularly, timestamp filtering
```

## 7.12 Summary

| Stage | Key Decisions |
|-------|---------------|
| Loading | File types, parsing |
| Chunking | Size, overlap, boundaries |
| Embedding | Model, batching |
| Storage | Vector DB choice |
| Retrieval | top_k, filters |
| Reranking | Optional LLM scoring |
| Generation | Context assembly, prompt |

**Best practices:**
- Chunk at semantic boundaries
- Use overlap to preserve context
- Rerank for critical applications
- Require citations
- Test retrieval quality separately
- Monitor and iterate
