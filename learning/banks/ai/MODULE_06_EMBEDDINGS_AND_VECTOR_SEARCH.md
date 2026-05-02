# Module 6: Embeddings and Vector Search

## 6.1 What are Embeddings?

Embeddings convert text into numerical vectors that capture semantic meaning.

```python
# Text → Vector
"The cat sat on the mat" → [0.12, -0.34, 0.56, ..., 0.78]  # ~1536 dimensions

# Similar meanings → Similar vectors
"The dog lay on the rug"  → [0.11, -0.32, 0.58, ..., 0.77]  # Close!
"Stock market crashes"    → [-0.45, 0.23, -0.12, ..., 0.01]  # Far
```

## 6.2 Generating Embeddings

```python
# OpenAI
from openai import OpenAI

client = OpenAI()

response = client.embeddings.create(
    model="text-embedding-3-small",
    input="The quick brown fox"
)
embedding = response.data[0].embedding  # List of floats

# Voyage (popular for RAG)
import voyageai

client = voyageai.Client()
result = client.embed(["The quick brown fox"], model="voyage-2")
embedding = result.embeddings[0]
```

## 6.3 Embedding Models

| Model | Dimensions | Use Case |
|-------|------------|----------|
| text-embedding-3-small | 1536 | General, cost-effective |
| text-embedding-3-large | 3072 | Higher quality |
| voyage-2 | 1024 | RAG optimized |
| sentence-transformers | varies | Local/free |

```python
# Local embeddings with sentence-transformers
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode("The quick brown fox")
```

## 6.4 Similarity Metrics

```python
import numpy as np

def cosine_similarity(a: list, b: list) -> float:
    """Most common for text embeddings"""
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def dot_product(a: list, b: list) -> float:
    """Faster, works if vectors are normalized"""
    return np.dot(a, b)

def euclidean_distance(a: list, b: list) -> float:
    """Lower = more similar"""
    return np.linalg.norm(np.array(a) - np.array(b))

# Usage
sim = cosine_similarity(embedding1, embedding2)
# 1.0 = identical, 0.0 = orthogonal, -1.0 = opposite
```

## 6.5 Vector Databases

```python
# pgvector (PostgreSQL)
import psycopg2

conn = psycopg2.connect(...)
cur = conn.cursor()

# Create table with vector column
cur.execute("""
    CREATE TABLE documents (
        id SERIAL PRIMARY KEY,
        content TEXT,
        embedding vector(1536)
    )
""")

# Insert
cur.execute(
    "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
    (text, embedding)
)

# Search
cur.execute("""
    SELECT content, 1 - (embedding <=> %s) as similarity
    FROM documents
    ORDER BY embedding <=> %s
    LIMIT 5
""", (query_embedding, query_embedding))
```

## 6.6 In-Memory Vector Search

```python
import numpy as np

class SimpleVectorStore:
    def __init__(self):
        self.documents = []
        self.embeddings = []

    def add(self, text: str, embedding: list):
        self.documents.append(text)
        self.embeddings.append(embedding)

    def search(self, query_embedding: list, top_k: int = 5) -> list:
        if not self.embeddings:
            return []

        query = np.array(query_embedding)
        embeddings = np.array(self.embeddings)

        # Cosine similarity
        similarities = np.dot(embeddings, query) / (
            np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query)
        )

        top_indices = np.argsort(similarities)[-top_k:][::-1]

        return [
            {"text": self.documents[i], "score": similarities[i]}
            for i in top_indices
        ]
```

## 6.7 Chroma (Simple Vector DB)

```python
import chromadb

client = chromadb.Client()
collection = client.create_collection("documents")

# Add documents (auto-generates embeddings)
collection.add(
    documents=["doc1 content", "doc2 content"],
    ids=["doc1", "doc2"],
    metadatas=[{"source": "file1"}, {"source": "file2"}]
)

# Search
results = collection.query(
    query_texts=["search query"],
    n_results=5
)
```

## 6.8 Pinecone (Managed Vector DB)

```python
from pinecone import Pinecone

pc = Pinecone(api_key="...")
index = pc.Index("my-index")

# Upsert vectors
index.upsert(vectors=[
    {"id": "doc1", "values": embedding1, "metadata": {"source": "file1"}},
    {"id": "doc2", "values": embedding2, "metadata": {"source": "file2"}},
])

# Search
results = index.query(
    vector=query_embedding,
    top_k=5,
    include_metadata=True
)
```

## 6.9 Hybrid Search

Combine vector search with keyword search:

```python
def hybrid_search(
    query: str,
    query_embedding: list,
    documents: list,
    alpha: float = 0.5  # Balance between vector and keyword
) -> list:
    # Vector search scores
    vector_scores = vector_search(query_embedding, documents)

    # Keyword search scores (BM25)
    keyword_scores = bm25_search(query, documents)

    # Combine scores
    combined = {}
    for doc_id, score in vector_scores.items():
        combined[doc_id] = alpha * score

    for doc_id, score in keyword_scores.items():
        combined[doc_id] = combined.get(doc_id, 0) + (1 - alpha) * score

    # Sort by combined score
    return sorted(combined.items(), key=lambda x: x[1], reverse=True)
```

## 6.10 Embedding Best Practices

```python
# 1. Batch embeddings for efficiency
texts = ["doc1", "doc2", "doc3", ...]
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=texts  # Batch, not one at a time
)

# 2. Cache embeddings
import hashlib

def get_embedding_cached(text: str, cache: dict) -> list:
    key = hashlib.md5(text.encode()).hexdigest()
    if key not in cache:
        cache[key] = generate_embedding(text)
    return cache[key]

# 3. Normalize if using dot product
def normalize(embedding: list) -> list:
    norm = np.linalg.norm(embedding)
    return (np.array(embedding) / norm).tolist()

# 4. Truncate long texts
MAX_TOKENS = 8000  # Check model limit
def prepare_for_embedding(text: str) -> str:
    # Rough truncation (proper tokenization is better)
    if len(text) > MAX_TOKENS * 4:
        text = text[:MAX_TOKENS * 4]
    return text
```

## 6.11 Metadata Filtering

```python
# Pinecone with filters
results = index.query(
    vector=query_embedding,
    top_k=10,
    filter={
        "category": {"$eq": "technical"},
        "date": {"$gte": "2024-01-01"}
    }
)

# pgvector with WHERE clause
cur.execute("""
    SELECT content, 1 - (embedding <=> %s) as similarity
    FROM documents
    WHERE category = %s AND created_at >= %s
    ORDER BY embedding <=> %s
    LIMIT 5
""", (query_embedding, "technical", "2024-01-01", query_embedding))
```

## 6.12 Summary

| Component | Options |
|-----------|---------|
| Embedding model | OpenAI, Voyage, sentence-transformers |
| Vector DB | pgvector, Pinecone, Chroma, Weaviate |
| Similarity | Cosine (default), dot product, Euclidean |
| Search type | Vector, keyword, hybrid |

**Best practices:**
- Batch embedding calls
- Cache embeddings (they're deterministic)
- Use appropriate chunk sizes
- Consider hybrid search for better recall
- Filter by metadata when possible
