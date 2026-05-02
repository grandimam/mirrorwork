# Module 41: Cross-Encoder Reranking

## 41.1 Bi-Encoder vs Cross-Encoder

```
Bi-Encoder (Embeddings):
- Encode query and documents separately
- Fast: O(1) per document after encoding
- Less accurate for fine-grained relevance

Query → [Encoder] → embedding
Doc   → [Encoder] → embedding
similarity = cosine(query_emb, doc_emb)

Cross-Encoder (Reranker):
- Encode query and document together
- Slow: O(n) - must process each pair
- More accurate relevance scoring

[Query + Doc] → [Encoder] → relevance_score

Best practice: Bi-encoder for retrieval, cross-encoder for reranking
```

## 41.2 Reranking Pipeline

```python
class RetrievalPipeline:
    def __init__(self, retriever, reranker, retrieve_k: int = 50, rerank_k: int = 10):
        self.retriever = retriever
        self.reranker = reranker
        self.retrieve_k = retrieve_k
        self.rerank_k = rerank_k

    async def search(self, query: str) -> list[dict]:
        # Stage 1: Fast retrieval with bi-encoder
        candidates = await self.retriever.search(query, k=self.retrieve_k)

        # Stage 2: Precise reranking with cross-encoder
        reranked = await self.reranker.rerank(query, candidates)

        # Return top results
        return reranked[:self.rerank_k]
```

## 41.3 Sentence Transformers Reranker

```python
from sentence_transformers import CrossEncoder

class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, documents: list[dict]) -> list[dict]:
        # Create query-document pairs
        pairs = [(query, doc["content"]) for doc in documents]

        # Score all pairs
        scores = self.model.predict(pairs)

        # Add scores and sort
        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        return sorted(documents, key=lambda x: x["rerank_score"], reverse=True)

# Usage
reranker = CrossEncoderReranker()
results = reranker.rerank(
    "What is machine learning?",
    [{"content": "ML is...", "id": "1"}, {"content": "Python is...", "id": "2"}]
)
```

## 41.4 Cohere Reranker

```python
import cohere

class CohereReranker:
    def __init__(self, api_key: str):
        self.client = cohere.Client(api_key)

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_n: int = 10
    ) -> list[dict]:
        # Extract text content
        texts = [doc["content"] for doc in documents]

        # Call Cohere rerank API
        response = self.client.rerank(
            model="rerank-english-v3.0",
            query=query,
            documents=texts,
            top_n=top_n
        )

        # Map scores back to documents
        reranked = []
        for result in response.results:
            doc = documents[result.index].copy()
            doc["rerank_score"] = result.relevance_score
            reranked.append(doc)

        return reranked

# Usage
reranker = CohereReranker(api_key="...")
results = reranker.rerank("quantum computing basics", documents, top_n=5)
```

## 41.5 Jina Reranker

```python
import requests

class JinaReranker:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.jina.ai/v1/rerank"

    def rerank(self, query: str, documents: list[dict], top_n: int = 10) -> list[dict]:
        response = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "documents": [doc["content"] for doc in documents],
                "top_n": top_n
            }
        )

        results = response.json()["results"]

        reranked = []
        for result in results:
            doc = documents[result["index"]].copy()
            doc["rerank_score"] = result["relevance_score"]
            reranked.append(doc)

        return reranked
```

## 41.6 LLM-as-Reranker

```python
class LLMReranker:
    """Use LLM to rerank (slower but flexible)"""

    async def rerank(self, query: str, documents: list[dict], top_n: int = 5) -> list[dict]:
        # Score each document
        scored = []
        for doc in documents:
            score = await self._score(query, doc["content"])
            scored.append({**doc, "rerank_score": score})

        # Sort and return top
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_n]

    async def _score(self, query: str, document: str) -> float:
        prompt = f"""
Rate the relevance of this document to the query on a scale of 0-10.
Consider: Does it answer the question? Is the information accurate and complete?

Query: {query}

Document: {document[:1000]}

Score (0-10):"""

        response = await client.messages.create(
            model="claude-3-haiku-20241022",
            max_tokens=5,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            return float(response.content[0].text.strip())
        except:
            return 0.0
```

## 41.7 Batch Reranking

```python
class BatchReranker:
    """Efficient batch reranking"""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank_batch(
        self,
        queries: list[str],
        documents_per_query: list[list[dict]],
        batch_size: int = 32
    ) -> list[list[dict]]:
        # Flatten all pairs
        all_pairs = []
        pair_indices = []  # Track which query each pair belongs to

        for q_idx, (query, docs) in enumerate(zip(queries, documents_per_query)):
            for doc in docs:
                all_pairs.append((query, doc["content"]))
                pair_indices.append((q_idx, doc))

        # Score in batches
        all_scores = []
        for i in range(0, len(all_pairs), batch_size):
            batch = all_pairs[i:i + batch_size]
            scores = self.model.predict(batch)
            all_scores.extend(scores)

        # Reconstruct results
        results = [[] for _ in queries]
        for (q_idx, doc), score in zip(pair_indices, all_scores):
            doc_with_score = {**doc, "rerank_score": float(score)}
            results[q_idx].append(doc_with_score)

        # Sort each query's results
        for i in range(len(results)):
            results[i].sort(key=lambda x: x["rerank_score"], reverse=True)

        return results
```

## 41.8 Hybrid Reranking

```python
class HybridReranker:
    """Combine multiple reranking signals"""

    def __init__(self):
        self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def rerank(
        self,
        query: str,
        documents: list[dict],
        weights: dict = None
    ) -> list[dict]:
        weights = weights or {
            "cross_encoder": 0.6,
            "bm25": 0.2,
            "recency": 0.1,
            "popularity": 0.1
        }

        # Cross-encoder scores
        pairs = [(query, doc["content"]) for doc in documents]
        ce_scores = self.model.predict(pairs)

        # Normalize and combine
        for doc, ce_score in zip(documents, ce_scores):
            combined_score = (
                weights["cross_encoder"] * self._normalize(ce_score) +
                weights["bm25"] * self._normalize(doc.get("bm25_score", 0)) +
                weights["recency"] * self._recency_score(doc) +
                weights["popularity"] * self._normalize(doc.get("views", 0))
            )
            doc["combined_score"] = combined_score

        return sorted(documents, key=lambda x: x["combined_score"], reverse=True)

    def _normalize(self, score: float, min_val: float = 0, max_val: float = 10) -> float:
        return (score - min_val) / (max_val - min_val + 1e-10)

    def _recency_score(self, doc: dict) -> float:
        if "date" not in doc:
            return 0.5
        days_old = (datetime.now() - doc["date"]).days
        return max(0, 1 - days_old / 365)  # Decay over a year
```

## 41.9 Reranker Evaluation

```python
class RerankerEvaluator:
    def evaluate(
        self,
        reranker,
        test_cases: list[dict]  # {query, documents, relevant_ids}
    ) -> dict:
        metrics = {"ndcg": [], "mrr": [], "precision_at_5": []}

        for case in test_cases:
            reranked = reranker.rerank(case["query"], case["documents"])
            reranked_ids = [doc["id"] for doc in reranked]
            relevant = set(case["relevant_ids"])

            # NDCG
            metrics["ndcg"].append(self._ndcg(reranked_ids, relevant))

            # MRR
            metrics["mrr"].append(self._mrr(reranked_ids, relevant))

            # P@5
            metrics["precision_at_5"].append(
                len(set(reranked_ids[:5]) & relevant) / 5
            )

        return {k: sum(v) / len(v) for k, v in metrics.items()}

    def _mrr(self, ranked: list, relevant: set) -> float:
        for i, doc_id in enumerate(ranked):
            if doc_id in relevant:
                return 1 / (i + 1)
        return 0

    def _ndcg(self, ranked: list, relevant: set, k: int = 10) -> float:
        # Simplified NDCG
        dcg = sum(1 / np.log2(i + 2) for i, doc_id in enumerate(ranked[:k]) if doc_id in relevant)
        idcg = sum(1 / np.log2(i + 2) for i in range(min(len(relevant), k)))
        return dcg / idcg if idcg > 0 else 0
```

## 41.10 Summary

| Reranker | Speed | Quality | Cost |
|----------|-------|---------|------|
| Cross-encoder (local) | Medium | High | Free |
| Cohere Rerank | Fast | High | API cost |
| Jina Reranker | Fast | High | API cost |
| LLM-as-reranker | Slow | Flexible | High |

**Best practices:**
- Always rerank RAG results
- Retrieve 3-5x more than needed, then rerank
- Use local cross-encoders for cost efficiency
- Batch requests for throughput
- Combine with other signals (recency, popularity)
- Evaluate with NDCG, MRR metrics
