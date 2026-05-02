# Module 26: Application Patterns

## 26.1 Chatbot Pattern

```python
class Chatbot:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.history = []

    async def chat(self, user_message: str) -> str:
        self.history.append({"role": "user", "content": user_message})

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history
        ]

        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            system=self.system_prompt,
            messages=self.history
        )

        assistant_message = response.content[0].text
        self.history.append({"role": "assistant", "content": assistant_message})

        return assistant_message

    def reset(self):
        self.history = []
```

## 26.2 Q&A over Documents

```python
class DocumentQA:
    def __init__(self, vector_store, embedder):
        self.vector_store = vector_store
        self.embedder = embedder

    async def answer(self, question: str) -> dict:
        # 1. Embed question
        query_embedding = await self.embedder.embed(question)

        # 2. Retrieve relevant chunks
        chunks = await self.vector_store.search(query_embedding, k=5)

        # 3. Generate answer
        context = "\n\n".join([c.text for c in chunks])

        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Answer based on this context:

{context}

Question: {question}

If the context doesn't contain the answer, say "I don't have information about that."
"""
            }]
        )

        return {
            "answer": response.content[0].text,
            "sources": [c.metadata["source"] for c in chunks]
        }
```

## 26.3 Content Generation

```python
class ContentGenerator:
    async def generate_blog_post(self, topic: str, style: str = "professional") -> dict:
        # Generate outline first
        outline = await self._generate_outline(topic)

        # Generate each section
        sections = []
        for section in outline:
            content = await self._generate_section(topic, section, style)
            sections.append({"title": section, "content": content})

        return {
            "title": f"Guide to {topic}",
            "sections": sections
        }

    async def _generate_outline(self, topic: str) -> list[str]:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"Create a 5-section outline for a blog post about: {topic}\nReturn as a JSON array of section titles."
            }]
        )
        return json.loads(response.content[0].text)

    async def _generate_section(self, topic: str, section: str, style: str) -> str:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"Write the '{section}' section for a {style} blog post about {topic}. 2-3 paragraphs."
            }]
        )
        return response.content[0].text
```

## 26.4 Data Extraction

```python
class DataExtractor:
    async def extract_entities(self, text: str, entity_types: list[str]) -> dict:
        schema = {
            "type": "object",
            "properties": {
                entity: {"type": "array", "items": {"type": "string"}}
                for entity in entity_types
            }
        }

        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Extract {', '.join(entity_types)} from this text:

{text}

Return as JSON matching this schema: {json.dumps(schema)}"""
            }]
        )
        return json.loads(response.content[0].text)

# Usage
result = await extractor.extract_entities(
    "John Smith works at Acme Corp in New York.",
    ["people", "companies", "locations"]
)
# {"people": ["John Smith"], "companies": ["Acme Corp"], "locations": ["New York"]}
```

## 26.5 Code Assistant

```python
class CodeAssistant:
    async def explain_code(self, code: str) -> str:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"Explain this code in simple terms:\n\n```\n{code}\n```"
            }]
        )
        return response.content[0].text

    async def review_code(self, code: str) -> dict:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Review this code for issues. Return JSON:
{{"issues": [{{"line": N, "severity": "high/medium/low", "description": "..."}}], "suggestions": ["..."]}}

Code:
```
{code}
```"""
            }]
        )
        return json.loads(response.content[0].text)

    async def generate_tests(self, code: str) -> str:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": f"Write pytest tests for this code:\n\n```python\n{code}\n```"
            }]
        )
        return response.content[0].text
```

## 26.6 Summarization

```python
class Summarizer:
    async def summarize(self, text: str, style: str = "brief") -> str:
        prompts = {
            "brief": "Summarize in 1-2 sentences:",
            "bullet": "Summarize as bullet points:",
            "detailed": "Provide a detailed summary:",
            "eli5": "Explain like I'm 5:"
        }

        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"{prompts[style]}\n\n{text}"
            }]
        )
        return response.content[0].text

    async def summarize_long(self, text: str, chunk_size: int = 10000) -> str:
        """Hierarchical summarization for long documents"""
        # Split into chunks
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

        # Summarize each chunk
        summaries = []
        for chunk in chunks:
            summary = await self.summarize(chunk, "brief")
            summaries.append(summary)

        # Combine and summarize again
        combined = "\n".join(summaries)
        return await self.summarize(combined, "detailed")
```

## 26.7 Classification

```python
class Classifier:
    async def classify(self, text: str, categories: list[str]) -> dict:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": f"""Classify this text into one of: {', '.join(categories)}

Text: {text}

Return JSON: {{"category": "...", "confidence": 0.0-1.0}}"""
            }]
        )
        return json.loads(response.content[0].text)

    async def sentiment(self, text: str) -> dict:
        return await self.classify(text, ["positive", "negative", "neutral"])

    async def intent(self, text: str, intents: list[str]) -> dict:
        return await self.classify(text, intents)
```

## 26.8 Summary

| Pattern | Use Case |
|---------|----------|
| Chatbot | Interactive conversation |
| Document Q&A | Knowledge base queries |
| Content generation | Blogs, emails, copy |
| Data extraction | Structured data from text |
| Code assistant | Explain, review, generate |
| Summarization | Condense long content |
| Classification | Categorize text |

**Best practices:**
- Choose pattern based on use case
- Combine patterns (e.g., RAG + Chatbot)
- Add guardrails for production
- Cache repeated queries
- Monitor quality and cost
