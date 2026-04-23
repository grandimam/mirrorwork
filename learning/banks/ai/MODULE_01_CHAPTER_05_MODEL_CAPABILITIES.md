# Chapter 5: Model Capabilities and Limitations

## 5.1 What Models Are Good At

LLMs excel at tasks involving pattern recognition and generation in language:

| Capability | Examples |
|------------|----------|
| **Text Generation** | Writing, summarization, expansion |
| **Code Generation** | Writing, explaining, debugging code |
| **Analysis** | Sentiment, classification, extraction |
| **Transformation** | Translation, reformatting, conversion |
| **Reasoning** | Step-by-step problem solving |
| **Conversation** | Q&A, chat, roleplay |

```python
# Good use cases
tasks_llms_excel_at = [
    "Write a function that parses JSON",
    "Summarize this article in 3 bullet points",
    "Extract all email addresses from this text",
    "Translate this to Spanish",
    "Explain this code to a junior developer",
    "Classify this support ticket by urgency",
]
```

## 5.2 What Models Are Bad At

```python
# Tasks LLMs struggle with
tasks_llms_fail_at = [
    "What is 47832 * 9284?",           # Precise math
    "Count the words in this text",     # Counting
    "What happened yesterday?",         # Real-time knowledge
    "Generate a truly random number",   # True randomness
    "Remember what I said last week",   # Long-term memory
    "Access my database",               # External systems (without tools)
]
```

| Limitation | Why | Workaround |
|------------|-----|------------|
| **Math** | Predicts "likely" answers, doesn't compute | Use code interpreter tools |
| **Counting** | Tokenization obscures character/word boundaries | Use code or explicit enumeration |
| **Real-time data** | Training data has cutoff | Use search/retrieval tools |
| **Memory** | No state between calls | Pass conversation history |
| **External access** | Isolated by default | Provide tools |

## 5.3 Hallucinations

Models confidently generate false information:

```python
# Hallucination examples
prompt = "What is the paper 'Attention Is All You Need' about?"
# Model might: cite correct info

prompt = "What is the paper 'Attention Is Mostly What You Need' about?"
# Model might: invent a plausible-sounding but fake paper

prompt = "What methods are in the Python 'flibbertigibbet' library?"
# Model might: invent fake but plausible method names
```

**Why hallucinations happen**:
- Model predicts "plausible" text, not "true" text
- Training data contains errors
- Model interpolates between patterns

**Mitigation strategies**:

```python
# 1. Ask for citations
prompt = "List 3 benefits of exercise. Cite specific studies."
# Then verify the citations exist

# 2. Use retrieval (RAG)
context = retrieve_relevant_documents(query)
prompt = f"Based ONLY on this context: {context}\nAnswer: {query}"

# 3. Ask for confidence
prompt = "Answer this question. If unsure, say 'I don't know': ..."

# 4. Verify with tools
# Let model write code to verify facts
```

## 5.4 Knowledge Cutoff

Models only know information from their training data:

```python
# Check model knowledge cutoff
knowledge_cutoffs = {
    "gpt-4o": "October 2023",
    "claude-3-5-sonnet": "April 2024",
    "claude-3-opus": "August 2023",
}

# For recent information, use tools
async def answer_with_search(query: str, client, search_tool):
    # First, check if search is needed
    needs_search = await client.messages.create(
        messages=[{
            "role": "user",
            "content": f"Does answering '{query}' require information after your knowledge cutoff? Reply YES or NO only."
        }]
    )

    if "YES" in needs_search.content:
        search_results = await search_tool.search(query)
        return await answer_with_context(query, search_results, client)
    else:
        return await answer_directly(query, client)
```

## 5.5 Context Limitations

Models can lose track in long contexts:

```python
# "Lost in the middle" phenomenon
# Models pay more attention to beginning and end of context

# Bad: important info buried in middle
prompt = f"""
Here are 50 documents:
{doc1}
{doc2}
...
{doc25}  # Important info here - might be missed!
...
{doc50}

Answer the question.
"""

# Better: highlight important info
prompt = f"""
KEY INFORMATION (most relevant):
{doc25}

Supporting documents:
{other_docs}

Based on the KEY INFORMATION above, answer...
"""
```

## 5.6 Instruction Following Limits

Complex or contradictory instructions cause failures:

```python
# Too many constraints
prompt = """
Write a story that:
- Is exactly 500 words
- Uses no adjectives
- Includes the word "serendipity" exactly 3 times
- Has a twist ending
- Is written from second person POV
- Contains no dialogue
- Uses only present tense
"""
# Model will likely fail some constraints

# Better: prioritize constraints
prompt = """
Write a short story (approximately 500 words) with a twist ending.
Use second person POV and present tense.
"""
```

## 5.7 Capability by Model Size

Larger models handle more complex tasks:

```
Task Complexity vs Model Size

Simple Tasks (Small models OK):
├── Text classification
├── Simple extraction
├── Basic summarization
└── Formatting/conversion

Medium Tasks (Medium models):
├── Code generation
├── Multi-step reasoning
├── Nuanced analysis
└── Creative writing

Complex Tasks (Large models needed):
├── Complex code architecture
├── Subtle reasoning
├── Expert-level analysis
└── Multi-constraint problems
```

```python
def select_model_for_task(task_complexity: str) -> str:
    models = {
        "simple": "claude-3-haiku",      # Fast, cheap
        "medium": "claude-3-5-sonnet",    # Balanced
        "complex": "claude-3-opus",       # Most capable
    }
    return models.get(task_complexity, "claude-3-5-sonnet")
```

## 5.8 Testing Capabilities

Before relying on a capability, test it:

```python
def test_model_capability(client, capability_test: dict) -> bool:
    """Test if model can handle a specific capability"""
    response = client.messages.create(
        model=capability_test["model"],
        messages=[{"role": "user", "content": capability_test["prompt"]}],
        max_tokens=capability_test.get("max_tokens", 1000),
    )

    # Check if output matches expected pattern
    return capability_test["validator"](response.content)

# Example tests
capability_tests = [
    {
        "name": "json_output",
        "model": "claude-3-5-sonnet",
        "prompt": "Return a JSON object with keys 'name' and 'age'. Nothing else.",
        "validator": lambda x: x.strip().startswith("{") and "name" in x,
    },
    {
        "name": "code_generation",
        "model": "claude-3-5-sonnet",
        "prompt": "Write a Python function to reverse a string.",
        "validator": lambda x: "def " in x and "return" in x,
    },
]
```

## 5.9 Capability Evolution

Model capabilities change with updates:

```python
# Track capability changes
CAPABILITY_NOTES = {
    "claude-3-5-sonnet": {
        "released": "2024-06",
        "strengths": ["code", "analysis", "instruction_following"],
        "context": 200_000,
        "notes": "Significant improvement over claude-3-sonnet",
    },
}

# Re-test capabilities after model updates
async def regression_test_capabilities(client, tests: list):
    results = []
    for test in tests:
        passed = await test_model_capability(client, test)
        results.append({"test": test["name"], "passed": passed})

    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"WARNING: {len(failed)} capability tests failed")
    return results
```

## 5.10 Summary

**LLMs excel at**:
- Text generation and transformation
- Code writing and explanation
- Analysis and classification
- Pattern-based reasoning

**LLMs struggle with**:
- Precise computation (use tools)
- Real-time information (use search)
- Counting and exact constraints
- Long-term memory (you must provide context)
- Guaranteed factual accuracy (verify outputs)

**Best practices**:
- Test capabilities before relying on them
- Use tools to extend capabilities (math, search, code execution)
- Verify critical outputs
- Match model size to task complexity
- Re-test after model updates
