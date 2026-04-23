# Module 46: Knowledge Graphs and Graph RAG

## 46.1 What Are Knowledge Graphs?

```
Knowledge Graph: structured representation of entities and relationships

Components:
- Nodes (entities): People, places, concepts, objects
- Edges (relationships): connects entities with typed relations
- Properties: attributes of nodes and edges

Example triple: (Albert Einstein) --[born_in]--> (Ulm, Germany)

Advantages over vector search:
- Explicit relationships (not just similarity)
- Multi-hop reasoning
- Interpretable results
- Structured queries
```

## 46.2 Graph Data Models

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Entity:
    id: str
    type: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = None

@dataclass
class Relationship:
    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any] = field(default_factory=dict)

@dataclass
class Triple:
    subject: Entity
    predicate: str
    object: Entity

    def __str__(self) -> str:
        return f"({self.subject.name}) --[{self.predicate}]--> ({self.object.name})"


class KnowledgeGraph:
    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.relationships: list[Relationship] = []
        self.adjacency: dict[str, list[tuple[str, str]]] = {}  # entity_id -> [(rel_type, target_id)]

    def add_entity(self, entity: Entity):
        self.entities[entity.id] = entity
        if entity.id not in self.adjacency:
            self.adjacency[entity.id] = []

    def add_relationship(self, rel: Relationship):
        self.relationships.append(rel)
        self.adjacency[rel.source_id].append((rel.type, rel.target_id))

    def get_neighbors(self, entity_id: str, rel_type: str = None) -> list[Entity]:
        neighbors = []
        for r_type, target_id in self.adjacency.get(entity_id, []):
            if rel_type is None or r_type == rel_type:
                neighbors.append(self.entities[target_id])
        return neighbors

    def get_triples(self, entity_id: str) -> list[Triple]:
        triples = []
        entity = self.entities[entity_id]
        for r_type, target_id in self.adjacency.get(entity_id, []):
            triples.append(Triple(
                subject=entity,
                predicate=r_type,
                object=self.entities[target_id]
            ))
        return triples
```

## 46.3 Building Knowledge Graphs from Text

```python
class KnowledgeGraphExtractor:
    def __init__(self, client):
        self.client = client
        self.extraction_prompt = """
Extract entities and relationships from the following text.

Output JSON with this structure:
{
  "entities": [
    {"id": "unique_id", "type": "Person|Organization|Location|Concept|Event|Product", "name": "entity name", "properties": {}}
  ],
  "relationships": [
    {"source": "entity_id", "target": "entity_id", "type": "relationship_type", "properties": {}}
  ]
}

Common relationship types:
- works_at, founded, located_in, part_of, created_by
- reports_to, collaborates_with, competed_with
- happened_on, started_at, ended_at
- has_feature, uses, depends_on

Text to analyze:
{text}

Extract all entities and their relationships. Be comprehensive.
"""

    async def extract(self, text: str) -> dict:
        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": self.extraction_prompt.format(text=text)
            }]
        )
        return json.loads(response.content[0].text)

    async def build_graph_from_documents(self, documents: list[str]) -> KnowledgeGraph:
        graph = KnowledgeGraph()
        entity_resolver = EntityResolver()

        for doc in documents:
            # Extract entities and relationships
            extraction = await self.extract(doc)

            # Resolve entities (merge duplicates)
            for entity_data in extraction["entities"]:
                resolved_id = entity_resolver.resolve(entity_data)
                entity = Entity(
                    id=resolved_id,
                    type=entity_data["type"],
                    name=entity_data["name"],
                    properties=entity_data.get("properties", {})
                )
                graph.add_entity(entity)

            # Add relationships
            for rel_data in extraction["relationships"]:
                source_id = entity_resolver.get_resolved_id(rel_data["source"])
                target_id = entity_resolver.get_resolved_id(rel_data["target"])

                rel = Relationship(
                    id=f"{source_id}_{rel_data['type']}_{target_id}",
                    type=rel_data["type"],
                    source_id=source_id,
                    target_id=target_id,
                    properties=rel_data.get("properties", {})
                )
                graph.add_relationship(rel)

        return graph


class EntityResolver:
    """Merge duplicate entities across documents"""

    def __init__(self, similarity_threshold: float = 0.85):
        self.threshold = similarity_threshold
        self.entities: dict[str, Entity] = {}
        self.name_to_id: dict[str, str] = {}

    def resolve(self, entity_data: dict) -> str:
        name_lower = entity_data["name"].lower().strip()

        # Exact match
        if name_lower in self.name_to_id:
            return self.name_to_id[name_lower]

        # Fuzzy match
        for existing_name, existing_id in self.name_to_id.items():
            if self._similar(name_lower, existing_name):
                self.name_to_id[name_lower] = existing_id
                return existing_id

        # New entity
        new_id = f"entity_{len(self.entities)}"
        self.name_to_id[name_lower] = new_id
        return new_id

    def _similar(self, name1: str, name2: str) -> bool:
        # Simple Jaccard similarity on words
        words1 = set(name1.split())
        words2 = set(name2.split())
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union >= self.threshold if union > 0 else False

    def get_resolved_id(self, original_id: str) -> str:
        return self.name_to_id.get(original_id, original_id)
```

## 46.4 Graph Storage with Neo4j

```python
from neo4j import AsyncGraphDatabase

class Neo4jKnowledgeGraph:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self.driver.close()

    async def add_entity(self, entity: Entity):
        query = """
        MERGE (e:{type} {{id: $id}})
        SET e.name = $name, e.properties = $properties
        """.format(type=entity.type)

        async with self.driver.session() as session:
            await session.run(
                query,
                id=entity.id,
                name=entity.name,
                properties=json.dumps(entity.properties)
            )

    async def add_relationship(self, rel: Relationship):
        query = """
        MATCH (a {{id: $source_id}})
        MATCH (b {{id: $target_id}})
        MERGE (a)-[r:{type}]->(b)
        SET r.properties = $properties
        """.format(type=rel.type.upper())

        async with self.driver.session() as session:
            await session.run(
                query,
                source_id=rel.source_id,
                target_id=rel.target_id,
                properties=json.dumps(rel.properties)
            )

    async def query_neighbors(self, entity_name: str, rel_type: str = None, depth: int = 1) -> list[dict]:
        if rel_type:
            query = f"""
            MATCH (e {{name: $name}})-[r:{rel_type}*1..{depth}]-(neighbor)
            RETURN e, r, neighbor
            """
        else:
            query = f"""
            MATCH (e {{name: $name}})-[r*1..{depth}]-(neighbor)
            RETURN e, r, neighbor
            """

        async with self.driver.session() as session:
            result = await session.run(query, name=entity_name)
            return [record.data() async for record in result]

    async def find_path(self, source_name: str, target_name: str, max_depth: int = 5) -> list[dict]:
        query = f"""
        MATCH path = shortestPath(
            (a {{name: $source}})-[*..{max_depth}]-(b {{name: $target}})
        )
        RETURN path
        """

        async with self.driver.session() as session:
            result = await session.run(query, source=source_name, target=target_name)
            return [record.data() async for record in result]

    async def cypher_query(self, query: str, params: dict = None) -> list[dict]:
        async with self.driver.session() as session:
            result = await session.run(query, params or {})
            return [record.data() async for record in result]
```

## 46.5 Graph RAG: Combining Graphs with Retrieval

```python
class GraphRAG:
    """
    Graph RAG: Use knowledge graphs to enhance retrieval

    Flow:
    1. Extract entities from query
    2. Find related entities in graph
    3. Retrieve relevant context from graph structure
    4. Combine with vector search results
    5. Generate response with structured context
    """

    def __init__(self, graph: Neo4jKnowledgeGraph, vector_store, client, embedder):
        self.graph = graph
        self.vector_store = vector_store
        self.client = client
        self.embedder = embedder
        self.entity_extractor = KnowledgeGraphExtractor(client)

    async def query(self, question: str) -> str:
        # Step 1: Extract entities from question
        entities = await self._extract_query_entities(question)

        # Step 2: Retrieve graph context
        graph_context = await self._get_graph_context(entities)

        # Step 3: Vector search for additional context
        vector_context = await self._vector_search(question)

        # Step 4: Combine and generate
        combined_context = self._merge_contexts(graph_context, vector_context)

        return await self._generate_response(question, combined_context)

    async def _extract_query_entities(self, question: str) -> list[str]:
        prompt = f"""
Extract entity names from this question that should be looked up in a knowledge graph.
Return as JSON array of strings.

Question: {question}

Entities:"""

        response = await self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)

    async def _get_graph_context(self, entities: list[str], depth: int = 2) -> dict:
        context = {
            "entities": [],
            "relationships": [],
            "paths": []
        }

        for entity_name in entities:
            # Get entity and neighbors
            neighbors = await self.graph.query_neighbors(entity_name, depth=depth)

            for record in neighbors:
                context["entities"].append({
                    "name": record.get("neighbor", {}).get("name"),
                    "type": record.get("neighbor", {}).get("type"),
                })
                if record.get("r"):
                    context["relationships"].extend(record["r"])

        # Find paths between entities if multiple
        if len(entities) >= 2:
            for i in range(len(entities)):
                for j in range(i + 1, len(entities)):
                    paths = await self.graph.find_path(entities[i], entities[j])
                    context["paths"].extend(paths)

        return context

    async def _vector_search(self, question: str, k: int = 5) -> list[str]:
        embedding = await self.embedder.embed(question)
        results = await self.vector_store.search(embedding, k=k)
        return [r.content for r in results]

    def _merge_contexts(self, graph_context: dict, vector_context: list[str]) -> str:
        sections = []

        # Format graph context
        if graph_context["entities"]:
            entity_list = "\n".join([
                f"- {e['name']} ({e['type']})"
                for e in graph_context["entities"] if e['name']
            ])
            sections.append(f"Related Entities:\n{entity_list}")

        if graph_context["relationships"]:
            rel_list = "\n".join([
                f"- {r}" for r in graph_context["relationships"][:10]
            ])
            sections.append(f"Relationships:\n{rel_list}")

        if graph_context["paths"]:
            sections.append(f"Connection Paths:\n{graph_context['paths']}")

        # Add vector context
        if vector_context:
            doc_list = "\n\n".join([f"Document {i+1}:\n{doc}" for i, doc in enumerate(vector_context)])
            sections.append(f"Retrieved Documents:\n{doc_list}")

        return "\n\n---\n\n".join(sections)

    async def _generate_response(self, question: str, context: str) -> str:
        prompt = f"""
Answer the question using the provided context from our knowledge graph and documents.

Context:
{context}

Question: {question}

Provide a comprehensive answer that leverages the structured knowledge graph relationships
and retrieved documents. Cite specific entities and relationships when relevant.
"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

## 46.6 Community Detection for Summarization

```python
class GraphCommunityRAG:
    """
    Use graph communities for hierarchical summarization
    Based on Microsoft's GraphRAG approach
    """

    def __init__(self, graph: KnowledgeGraph, client):
        self.graph = graph
        self.client = client
        self.communities: list[set[str]] = []
        self.community_summaries: dict[int, str] = {}

    def detect_communities(self, resolution: float = 1.0):
        """Detect communities using Louvain algorithm"""
        import networkx as nx
        from community import community_louvain

        # Build NetworkX graph
        G = nx.Graph()
        for entity_id, entity in self.graph.entities.items():
            G.add_node(entity_id, **{"name": entity.name, "type": entity.type})

        for rel in self.graph.relationships:
            G.add_edge(rel.source_id, rel.target_id, type=rel.type)

        # Detect communities
        partition = community_louvain.best_partition(G, resolution=resolution)

        # Group entities by community
        community_map: dict[int, set[str]] = {}
        for entity_id, community_id in partition.items():
            if community_id not in community_map:
                community_map[community_id] = set()
            community_map[community_id].add(entity_id)

        self.communities = list(community_map.values())
        return self.communities

    async def summarize_communities(self):
        """Generate summaries for each community"""
        for i, community in enumerate(self.communities):
            # Get all triples in community
            triples = []
            for entity_id in community:
                entity_triples = self.graph.get_triples(entity_id)
                triples.extend([str(t) for t in entity_triples])

            if not triples:
                continue

            # Summarize with LLM
            prompt = f"""
Summarize the following knowledge graph triples into a coherent paragraph.
Focus on the main entities and their key relationships.

Triples:
{chr(10).join(triples[:50])}  # Limit for token budget

Summary:"""

            response = await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            self.community_summaries[i] = response.content[0].text

    async def query_with_communities(self, question: str) -> str:
        # Find relevant communities
        question_embedding = await self.embedder.embed(question)

        relevant_summaries = []
        for community_id, summary in self.community_summaries.items():
            summary_embedding = await self.embedder.embed(summary)
            similarity = cosine_similarity(question_embedding, summary_embedding)
            if similarity > 0.5:
                relevant_summaries.append((similarity, summary))

        # Sort by relevance
        relevant_summaries.sort(reverse=True)
        top_summaries = [s for _, s in relevant_summaries[:5]]

        # Generate response
        context = "\n\n".join(top_summaries)

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
            }]
        )

        return response.content[0].text
```

## 46.7 Multi-Hop Reasoning

```python
class MultiHopGraphReasoner:
    """
    Answer complex questions requiring multiple reasoning steps
    """

    def __init__(self, graph: Neo4jKnowledgeGraph, client):
        self.graph = graph
        self.client = client

    async def answer(self, question: str) -> dict:
        # Step 1: Decompose question into sub-questions
        sub_questions = await self._decompose_question(question)

        # Step 2: Answer each sub-question
        intermediate_answers = []
        for sub_q in sub_questions:
            answer = await self._answer_subquestion(sub_q, intermediate_answers)
            intermediate_answers.append({
                "question": sub_q,
                "answer": answer
            })

        # Step 3: Synthesize final answer
        final_answer = await self._synthesize(question, intermediate_answers)

        return {
            "question": question,
            "reasoning_chain": intermediate_answers,
            "answer": final_answer
        }

    async def _decompose_question(self, question: str) -> list[str]:
        prompt = f"""
Break down this complex question into simpler sub-questions that can be answered step by step.
Each sub-question should build on the previous ones.

Question: {question}

Output as JSON array of strings (sub-questions in order):"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)

    async def _answer_subquestion(self, question: str, previous_answers: list[dict]) -> str:
        # Extract entities to query
        entities = await self._extract_entities(question)

        # Query graph for relevant facts
        facts = []
        for entity in entities:
            neighbors = await self.graph.query_neighbors(entity, depth=1)
            for record in neighbors:
                facts.append(str(record))

        # Include previous answers as context
        context = ""
        if previous_answers:
            context = "Previous findings:\n" + "\n".join([
                f"Q: {a['question']}\nA: {a['answer']}"
                for a in previous_answers
            ])

        prompt = f"""
{context}

Graph facts:
{chr(10).join(facts[:20])}

Question: {question}

Answer based on the facts above:"""

        response = await self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def _extract_entities(self, text: str) -> list[str]:
        # Simple NER for entity extraction
        prompt = f"Extract entity names from: {text}\nReturn as JSON array:"
        response = await self.client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)

    async def _synthesize(self, original_question: str, chain: list[dict]) -> str:
        reasoning = "\n".join([
            f"Step {i+1}: {a['question']} → {a['answer']}"
            for i, a in enumerate(chain)
        ])

        prompt = f"""
Original question: {original_question}

Reasoning chain:
{reasoning}

Provide a final, comprehensive answer to the original question:"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

## 46.8 Hybrid Graph-Vector Index

```python
class HybridGraphVectorIndex:
    """
    Combine graph traversal with vector similarity
    """

    def __init__(self, graph: Neo4jKnowledgeGraph, vector_store, embedder):
        self.graph = graph
        self.vector_store = vector_store
        self.embedder = embedder

    async def index_graph_with_embeddings(self):
        """Add embeddings to all entities"""
        # Get all entities
        entities = await self.graph.cypher_query("MATCH (n) RETURN n")

        for record in entities:
            node = record["n"]
            # Create text representation
            text = f"{node.get('name', '')} ({node.get('type', '')})"

            # Generate embedding
            embedding = await self.embedder.embed(text)

            # Store embedding
            await self.vector_store.add(
                id=node.get("id"),
                content=text,
                embedding=embedding,
                metadata={"graph_id": node.get("id")}
            )

    async def search(self, query: str, k: int = 10, expansion_depth: int = 1) -> list[dict]:
        # Vector search for seed entities
        query_embedding = await self.embedder.embed(query)
        vector_results = await self.vector_store.search(query_embedding, k=k)

        # Expand via graph
        expanded_results = []
        seen_ids = set()

        for result in vector_results:
            entity_id = result.metadata.get("graph_id")
            if entity_id and entity_id not in seen_ids:
                seen_ids.add(entity_id)
                expanded_results.append({
                    "entity_id": entity_id,
                    "score": result.score,
                    "source": "vector"
                })

                # Graph expansion
                neighbors = await self.graph.query_neighbors(
                    entity_id,
                    depth=expansion_depth
                )
                for neighbor in neighbors:
                    neighbor_id = neighbor.get("id")
                    if neighbor_id and neighbor_id not in seen_ids:
                        seen_ids.add(neighbor_id)
                        expanded_results.append({
                            "entity_id": neighbor_id,
                            "score": result.score * 0.8,  # Decay
                            "source": "graph_expansion"
                        })

        # Re-rank by combined score
        expanded_results.sort(key=lambda x: x["score"], reverse=True)
        return expanded_results[:k]
```

## 46.9 Graph Query Generation

```python
class NaturalLanguageToGraphQuery:
    """Convert natural language to Cypher queries"""

    def __init__(self, client, schema: str):
        self.client = client
        self.schema = schema

    async def generate_query(self, question: str) -> str:
        prompt = f"""
Convert this natural language question to a Cypher query.

Graph Schema:
{self.schema}

Question: {question}

Rules:
- Use MATCH for pattern matching
- Use WHERE for filtering
- Use RETURN to specify output
- Use LIMIT when appropriate
- Handle relationships with -[:TYPE]-> or -[:TYPE]-

Cypher Query:"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract query from response
        query = response.content[0].text.strip()
        if query.startswith("```"):
            query = query.split("```")[1].strip()
            if query.startswith("cypher"):
                query = query[6:].strip()

        return query

    async def query_and_answer(self, question: str, graph: Neo4jKnowledgeGraph) -> str:
        # Generate Cypher query
        cypher = await self.generate_query(question)

        # Execute query
        try:
            results = await graph.cypher_query(cypher)
        except Exception as e:
            # Fall back to natural language
            return f"Query failed: {e}. Please rephrase your question."

        # Format results
        if not results:
            return "No results found."

        # Generate natural language response
        prompt = f"""
Question: {question}

Query results:
{json.dumps(results[:10], indent=2)}

Provide a natural language answer based on these results:"""

        response = await self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text


# Example schema
EXAMPLE_SCHEMA = """
Node types:
- Person: {name, title, department}
- Company: {name, industry, founded}
- Product: {name, category, price}
- Location: {name, country, type}

Relationship types:
- (Person)-[:WORKS_AT]->(Company)
- (Person)-[:MANAGES]->(Person)
- (Company)-[:LOCATED_IN]->(Location)
- (Company)-[:PRODUCES]->(Product)
- (Person)-[:CREATED]->(Product)
"""
```

## 46.10 Summary

| Approach | Best For | Limitations |
|----------|----------|-------------|
| Pure Vector RAG | Semantic similarity | No explicit relationships |
| Pure Graph | Structured queries | Requires manual construction |
| Graph RAG | Multi-hop reasoning | More complex setup |
| Hybrid | Best of both | Highest complexity |

**When to use Knowledge Graphs:**
- Complex domain with many relationships
- Questions requiring multi-hop reasoning
- Need for explainable results
- Structured data with clear ontology

**Best practices:**
- Start with entity extraction pipeline
- Implement entity resolution for deduplication
- Use community detection for large graphs
- Combine with vector search for semantic matching
- Generate summaries at different granularities
- Cache common query patterns
