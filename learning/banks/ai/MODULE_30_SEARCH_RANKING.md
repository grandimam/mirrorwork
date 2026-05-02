# Module 30: Search and Ranking

## 30.1 Hybrid Search

```python
class HybridSearch:
    """Combine keyword and semantic search"""

    def __init__(self, vector_store, keyword_index):
        self.vector_store = vector_store
        self.keyword_index = keyword_index

    async def search(self, query: str, k: int = 10) -> list:
        # Parallel searches
        semantic_results, keyword_results = await asyncio.gather(
            self.vector_store.search(query, k=k),
            self.keyword_index.search(query, k=k)
        )

        # Combine with reciprocal rank fusion
        return self._rrf_fusion(semantic_results, keyword_results, k)

    def _rrf_fusion(self, results1: list, results2: list, k: int) -> list:
        """Reciprocal Rank Fusion"""
        scores = {}
        rrf_k = 60  # Standard RRF constant

        for rank, doc in enumerate(results1):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (rrf_k + rank + 1)

        for rank, doc in enumerate(results2):
            scores[doc.id] = scores.get(doc.id, 0) + 1 / (rrf_k + rank + 1)

        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return sorted_ids[:k]
```

## 30.2 BM25 Keyword Search

```python
from rank_bm25 import BM25Okapi

class BM25Index:
    def __init__(self):
        self.documents = []
        self.index = None

    def add_documents(self, docs: list[dict]):
        self.documents = docs
        tokenized = [self._tokenize(d["content"]) for d in docs]
        self.index = BM25Okapi(tokenized)

    def search(self, query: str, k: int = 10) -> list:
        tokens = self._tokenize(query)
        scores = self.index.get_scores(tokens)

        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        return [
            {"doc": self.documents[i], "score": scores[i]}
            for i in top_indices
        ]

    def _tokenize(self, text: str) -> list[str]:
        return text.lower().split()
```

## 30.3 Reranking

```python
class Reranker:
    """Rerank results using cross-encoder or LLM"""

    async def rerank(self, query: str, results: list, k: int = 5) -> list:
        # Score each result against query
        scored = []

        for result in results:
            score = await self._score_relevance(query, result["content"])
            scored.append({**result, "rerank_score": score})

        # Sort by rerank score
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:k]

    async def _score_relevance(self, query: str, document: str) -> float:
        response = await client.messages.create(
            model="claude-3-haiku",
            max_tokens=10,
            messages=[{
                "role": "user",
                "content": f"""Rate relevance of document to query (0-10):
Query: {query}
Document: {document[:500]}
Score (number only):"""
            }]
        )
        try:
            return float(response.content[0].text.strip())
        except:
            return 0.0
```

## 30.4 Query Expansion

```python
class QueryExpander:
    async def expand(self, query: str) -> list[str]:
        """Generate query variations for better recall"""
        response = await client.messages.create(
            model="claude-3-haiku",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Generate 3 alternative phrasings for this search query:
"{query}"

Return as JSON array of strings."""
            }]
        )
        variations = json.loads(response.content[0].text)
        return [query] + variations

class MultiQuerySearch:
    def __init__(self, search_engine, expander):
        self.search = search_engine
        self.expander = expander

    async def search(self, query: str, k: int = 10) -> list:
        # Expand query
        queries = await self.expander.expand(query)

        # Search with all queries
        all_results = []
        for q in queries:
            results = await self.search.search(q, k=k)
            all_results.extend(results)

        # Deduplicate and rank
        return self._dedupe_and_rank(all_results, k)
```

## 30.5 Faceted Search

```python
class FacetedSearch:
    def __init__(self, search_engine):
        self.search = search_engine

    async def search_with_facets(
        self,
        query: str,
        filters: dict = None,
        facets: list[str] = None
    ) -> dict:
        # Apply filters
        results = await self.search.search(query)

        if filters:
            results = self._apply_filters(results, filters)

        # Compute facets
        facet_counts = {}
        if facets:
            for facet in facets:
                facet_counts[facet] = self._count_facet(results, facet)

        return {
            "results": results,
            "facets": facet_counts,
            "total": len(results)
        }

    def _apply_filters(self, results: list, filters: dict) -> list:
        filtered = []
        for r in results:
            match = all(
                r.get("metadata", {}).get(k) == v
                for k, v in filters.items()
            )
            if match:
                filtered.append(r)
        return filtered

    def _count_facet(self, results: list, facet: str) -> dict:
        counts = {}
        for r in results:
            value = r.get("metadata", {}).get(facet)
            if value:
                counts[value] = counts.get(value, 0) + 1
        return counts
```

## 30.6 Search Analytics

```python
class SearchAnalytics:
    def __init__(self):
        self.queries = []

    def log_search(self, query: str, results: int, clicked: int = None):
        self.queries.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "results_count": results,
            "clicked_position": clicked
        })

    def get_metrics(self) -> dict:
        if not self.queries:
            return {}

        return {
            "total_searches": len(self.queries),
            "avg_results": sum(q["results_count"] for q in self.queries) / len(self.queries),
            "zero_results_rate": sum(1 for q in self.queries if q["results_count"] == 0) / len(self.queries),
            "click_through_rate": sum(1 for q in self.queries if q.get("clicked_position")) / len(self.queries)
        }

    def get_popular_queries(self, n: int = 10) -> list:
        from collections import Counter
        query_counts = Counter(q["query"] for q in self.queries)
        return query_counts.most_common(n)
```

## 30.7 Personalized Ranking

```python
class PersonalizedRanker:
    def __init__(self):
        self.user_preferences = {}  # user_id -> preference vector

    def update_preferences(self, user_id: str, clicked_doc: dict):
        """Update user preferences based on clicks"""
        prefs = self.user_preferences.get(user_id, {})

        for key, value in clicked_doc.get("metadata", {}).items():
            if value:
                prefs[f"{key}:{value}"] = prefs.get(f"{key}:{value}", 0) + 1

        self.user_preferences[user_id] = prefs

    def personalize_results(self, user_id: str, results: list) -> list:
        """Boost results matching user preferences"""
        prefs = self.user_preferences.get(user_id, {})

        if not prefs:
            return results

        for result in results:
            boost = 0
            for key, value in result.get("metadata", {}).items():
                pref_key = f"{key}:{value}"
                boost += prefs.get(pref_key, 0)
            result["personalized_score"] = result.get("score", 0) + boost * 0.1

        return sorted(results, key=lambda x: x["personalized_score"], reverse=True)
```

## 30.8 Summary

| Technique | Purpose |
|-----------|---------|
| Hybrid search | Best of keyword + semantic |
| BM25 | Fast keyword matching |
| Reranking | Improve precision |
| Query expansion | Improve recall |
| Faceted search | Filtering and navigation |
| Personalization | User-specific results |

**Best practices:**
- Combine multiple retrieval methods
- Rerank top results with LLM
- Expand queries for recall
- Track search analytics
- A/B test ranking changes
- Consider user context
