# Module 38: Semantic Caching

## 38.1 What is Semantic Caching?

```
Exact caching:
"What is Python?" → cached
"What's Python?"  → cache miss (different string)

Semantic caching:
"What is Python?" → cached
"What's Python?"  → cache hit (same meaning)
"Tell me about Python" → cache hit (similar meaning)

Key: Cache based on meaning, not exact string
```

## 38.2 Basic Semantic Cache

```python
import numpy as np
from dataclasses import dataclass

@dataclass
class CacheEntry:
    query: str
    embedding: list[float]
    response: str
    timestamp: float

class SemanticCache:
    def __init__(self, similarity_threshold: float = 0.95):
        self.entries: list[CacheEntry] = []
        self.threshold = similarity_threshold

    async def get(self, query: str) -> str | None:
        query_embedding = await self._embed(query)

        for entry in self.entries:
            similarity = self._cosine_similarity(
                query_embedding, entry.embedding
            )
            if similarity >= self.threshold:
                return entry.response

        return None

    async def set(self, query: str, response: str):
        embedding = await self._embed(query)
        self.entries.append(CacheEntry(
            query=query,
            embedding=embedding,
            response=response,
            timestamp=time.time()
        ))

    def _cosine_similarity(self, a: list, b: list) -> float:
        a, b = np.array(a), np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    async def _embed(self, text: str) -> list[float]:
        response = await embedding_client.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
```

## 38.3 Cache with Vector Database

```python
import chromadb

class VectorCache:
    def __init__(self, threshold: float = 0.95):
        self.client = chromadb.Client()
        self.collection = self.client.create_collection(
            "cache",
            metadata={"hnsw:space": "cosine"}
        )
        self.threshold = threshold

    async def get(self, query: str) -> str | None:
        results = self.collection.query(
            query_texts=[query],
            n_results=1,
            include=["documents", "distances"]
        )

        if results["distances"][0]:
            distance = results["distances"][0][0]
            similarity = 1 - distance  # cosine distance to similarity

            if similarity >= self.threshold:
                return results["documents"][0][0]

        return None

    async def set(self, query: str, response: str):
        self.collection.add(
            documents=[response],
            metadatas=[{"query": query, "timestamp": time.time()}],
            ids=[str(uuid.uuid4())]
        )
```

## 38.4 GPTCache Integration

```python
from gptcache import cache
from gptcache.embedding import Onnx
from gptcache.similarity_evaluation.distance import SearchDistanceEvaluation
from gptcache.manager import get_data_manager, CacheBase, VectorBase

# Initialize GPTCache
onnx = Onnx()
cache_base = CacheBase("sqlite")
vector_base = VectorBase("faiss", dimension=onnx.dimension)
data_manager = get_data_manager(cache_base, vector_base)

cache.init(
    embedding_func=onnx.to_embeddings,
    data_manager=data_manager,
    similarity_evaluation=SearchDistanceEvaluation(),
)

# Usage with OpenAI
from gptcache.adapter import openai

response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What is Python?"}]
)
# Automatically cached based on semantic similarity
```

## 38.5 Cache Invalidation

```python
class SemanticCacheWithTTL:
    def __init__(self, threshold: float = 0.95, ttl_seconds: int = 3600):
        self.entries = []
        self.threshold = threshold
        self.ttl = ttl_seconds

    async def get(self, query: str) -> str | None:
        # Clean expired entries
        self._cleanup()

        query_embedding = await self._embed(query)

        for entry in self.entries:
            similarity = self._cosine_similarity(
                query_embedding, entry.embedding
            )
            if similarity >= self.threshold:
                return entry.response

        return None

    def _cleanup(self):
        now = time.time()
        self.entries = [
            e for e in self.entries
            if now - e.timestamp < self.ttl
        ]

    def invalidate_similar(self, query: str):
        """Invalidate cache entries similar to query"""
        query_embedding = self._embed_sync(query)
        self.entries = [
            e for e in self.entries
            if self._cosine_similarity(query_embedding, e.embedding) < 0.8
        ]
```

## 38.6 Context-Aware Caching

```python
class ContextAwareCache:
    """Cache considering both query and context"""

    def __init__(self, threshold: float = 0.92):
        self.entries = []
        self.threshold = threshold

    async def get(self, query: str, context: str = "") -> str | None:
        # Combine query and context for matching
        combined = f"{query}\n\nContext: {context[:500]}"
        combined_embedding = await self._embed(combined)

        for entry in self.entries:
            similarity = self._cosine_similarity(
                combined_embedding, entry.embedding
            )
            if similarity >= self.threshold:
                return entry.response

        return None

    async def set(self, query: str, context: str, response: str):
        combined = f"{query}\n\nContext: {context[:500]}"
        embedding = await self._embed(combined)

        self.entries.append(CacheEntry(
            query=query,
            embedding=embedding,
            response=response,
            timestamp=time.time(),
            metadata={"context_hash": hashlib.md5(context.encode()).hexdigest()}
        ))
```

## 38.7 Tiered Caching

```python
class TieredCache:
    """Exact match → Semantic match → Generate"""

    def __init__(self):
        self.exact_cache = {}  # Fast exact match
        self.semantic_cache = SemanticCache(threshold=0.95)

    async def get_or_generate(self, query: str, generate_fn) -> str:
        # Tier 1: Exact match (fastest)
        query_hash = hashlib.md5(query.encode()).hexdigest()
        if query_hash in self.exact_cache:
            return self.exact_cache[query_hash]

        # Tier 2: Semantic match
        cached = await self.semantic_cache.get(query)
        if cached:
            return cached

        # Tier 3: Generate
        response = await generate_fn(query)

        # Store in both caches
        self.exact_cache[query_hash] = response
        await self.semantic_cache.set(query, response)

        return response
```

## 38.8 Cache Analytics

```python
class CacheAnalytics:
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.hit_similarities = []

    def record_hit(self, similarity: float):
        self.hits += 1
        self.hit_similarities.append(similarity)

    def record_miss(self):
        self.misses += 1

    def get_stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "hit_rate": self.hits / total if total > 0 else 0,
            "total_requests": total,
            "avg_hit_similarity": (
                sum(self.hit_similarities) / len(self.hit_similarities)
                if self.hit_similarities else 0
            ),
            "estimated_savings": self.hits * 0.003  # Rough cost per request
        }
```

## 38.9 Redis-Based Semantic Cache

```python
import redis
import json

class RedisSemanticCache:
    def __init__(self, redis_url: str, threshold: float = 0.95):
        self.redis = redis.from_url(redis_url)
        self.threshold = threshold
        self.index_key = "cache:index"

    async def get(self, query: str) -> str | None:
        query_embedding = await self._embed(query)

        # Get all cached embeddings (for small cache)
        # For large cache, use Redis vector search
        cached = self.redis.hgetall(self.index_key)

        for key, data in cached.items():
            entry = json.loads(data)
            similarity = self._cosine_similarity(
                query_embedding, entry["embedding"]
            )
            if similarity >= self.threshold:
                return entry["response"]

        return None

    async def set(self, query: str, response: str, ttl: int = 3600):
        embedding = await self._embed(query)
        key = str(uuid.uuid4())

        data = json.dumps({
            "query": query,
            "embedding": embedding,
            "response": response
        })

        self.redis.hset(self.index_key, key, data)
        self.redis.expire(f"cache:{key}", ttl)
```

## 38.10 Summary

| Approach | Speed | Accuracy |
|----------|-------|----------|
| Exact match | Fastest | Exact only |
| Semantic (0.95) | Fast | High precision |
| Semantic (0.90) | Fast | More recall |
| Context-aware | Medium | Best for RAG |

**Best practices:**
- Start with high threshold (0.95+)
- Use tiered caching for best performance
- Implement TTL for freshness
- Monitor hit rates and adjust threshold
- Consider context for RAG applications
- Use vector DB for large caches
