# Chapter 8: Common Prompt Patterns

## 8.1 Classification Pattern

```python
CLASSIFICATION_PROMPT = """
Classify the following text into exactly one category.

Categories:
- bug_report: Issues with existing functionality
- feature_request: Requests for new functionality
- question: Questions about usage
- other: Anything else

Text: {text}

Respond with only the category name, nothing else.
"""

async def classify(text: str) -> str:
    response = await client.messages.create(
        model="claude-3-haiku",  # Fast/cheap model works
        max_tokens=20,
        messages=[{"role": "user", "content": CLASSIFICATION_PROMPT.format(text=text)}]
    )
    return response.content[0].text.strip().lower()
```

## 8.2 Extraction Pattern

```python
EXTRACTION_PROMPT = """
Extract the following information from the text.
If information is not found, use null.

Return JSON only:
{
    "name": string or null,
    "email": string or null,
    "phone": string or null,
    "company": string or null
}

Text: {text}
"""

async def extract_contact(text: str) -> dict:
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=200,
        messages=[
            {"role": "user", "content": EXTRACTION_PROMPT.format(text=text)},
            {"role": "assistant", "content": "{"}
        ]
    )
    return json.loads("{" + response.content[0].text)
```

## 8.3 Transformation Pattern

```python
TRANSFORM_PROMPT = """
Convert the following {source_format} to {target_format}.

Rules:
{rules}

Input:
{input_data}

Output:
"""

async def transform(
    data: str,
    source: str,
    target: str,
    rules: str = ""
) -> str:
    prompt = TRANSFORM_PROMPT.format(
        source_format=source,
        target_format=target,
        rules=rules or "Preserve all information accurately",
        input_data=data
    )
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Usage
sql = await transform(
    data="Get all users who signed up in January",
    source="natural language",
    target="PostgreSQL query",
    rules="Use parameterized queries. Table: users, columns: id, email, created_at"
)
```

## 8.4 Summarization Pattern

```python
SUMMARY_PROMPT = """
Summarize the following content.

Requirements:
- Length: {length}
- Style: {style}
- Focus: {focus}

Content:
{content}

Summary:
"""

SUMMARY_STYLES = {
    "executive": "High-level, business-focused, action-oriented",
    "technical": "Detailed, precise, includes technical terms",
    "simple": "Easy to understand, no jargon, 8th grade level",
}

async def summarize(
    content: str,
    length: str = "2-3 sentences",
    style: str = "executive",
    focus: str = "key points"
) -> str:
    prompt = SUMMARY_PROMPT.format(
        length=length,
        style=SUMMARY_STYLES.get(style, style),
        focus=focus,
        content=content
    )
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## 8.5 Q&A with Context Pattern

```python
QA_PROMPT = """
Answer the question based ONLY on the provided context.
If the answer cannot be found in the context, say "I don't have enough information to answer this."

Context:
{context}

Question: {question}

Answer:
"""

async def answer_with_context(question: str, context: str) -> str:
    prompt = QA_PROMPT.format(context=context, question=question)
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## 8.6 Code Generation Pattern

```python
CODE_PROMPT = """
Write a {language} function with the following specification:

Function name: {name}
Description: {description}
Parameters: {parameters}
Returns: {returns}

Requirements:
- Include type hints
- Add docstring
- Handle edge cases
- Follow {language} best practices

{additional_context}
"""

async def generate_code(
    language: str,
    name: str,
    description: str,
    parameters: str,
    returns: str,
    additional_context: str = ""
) -> str:
    prompt = CODE_PROMPT.format(
        language=language,
        name=name,
        description=description,
        parameters=parameters,
        returns=returns,
        additional_context=additional_context
    )
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## 8.7 Review/Critique Pattern

```python
REVIEW_PROMPT = """
Review the following {artifact_type} and provide constructive feedback.

{artifact}

Provide feedback in this format:
## Strengths
- [list positives]

## Issues
- [SEVERITY: HIGH/MEDIUM/LOW] Description of issue

## Suggestions
- [specific improvement suggestions]

## Overall Assessment
[1-2 sentence summary]
"""

async def review(artifact: str, artifact_type: str) -> str:
    prompt = REVIEW_PROMPT.format(
        artifact_type=artifact_type,
        artifact=artifact
    )
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## 8.8 Comparison Pattern

```python
COMPARE_PROMPT = """
Compare the following options for {context}:

{options}

Provide analysis in this format:

| Criteria | {option_names} |
|----------|{separator}|
| [criteria] | [ratings] |

## Recommendation
[Which option is best for what situation]
"""

async def compare(options: list[dict], context: str) -> str:
    options_text = "\n\n".join(
        f"### Option {i+1}: {opt['name']}\n{opt['description']}"
        for i, opt in enumerate(options)
    )
    option_names = " | ".join(opt["name"] for opt in options)
    separator = " | ".join("---" for _ in options)

    prompt = COMPARE_PROMPT.format(
        context=context,
        options=options_text,
        option_names=option_names,
        separator=separator
    )
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## 8.9 Rewrite/Improve Pattern

```python
REWRITE_PROMPT = """
Rewrite the following {content_type} to be {goal}.

Original:
{original}

Requirements:
{requirements}

Rewritten version:
"""

async def rewrite(
    original: str,
    content_type: str,
    goal: str,
    requirements: list[str] = None
) -> str:
    requirements_text = "\n".join(f"- {r}" for r in (requirements or []))
    prompt = REWRITE_PROMPT.format(
        content_type=content_type,
        goal=goal,
        original=original,
        requirements=requirements_text or "- Preserve the original meaning"
    )
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Usage
improved = await rewrite(
    original="This product is good.",
    content_type="product description",
    goal="more compelling and professional",
    requirements=["Include benefits", "Add call to action", "Keep under 100 words"]
)
```

## 8.10 Multi-Step Pattern

```python
async def multi_step_analysis(document: str) -> dict:
    """Complex analysis broken into steps"""

    # Step 1: Extract key entities
    entities = await extract(document, schema={"people": [], "companies": [], "topics": []})

    # Step 2: Summarize
    summary = await summarize(document, length="3-5 sentences")

    # Step 3: Classify
    category = await classify(document)

    # Step 4: Generate questions
    questions_prompt = f"""
    Based on this summary: {summary}

    Generate 3 clarifying questions that would help understand the document better.
    """
    questions_response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=300,
        messages=[{"role": "user", "content": questions_prompt}]
    )

    return {
        "entities": entities,
        "summary": summary,
        "category": category,
        "questions": questions_response.content[0].text
    }
```

## 8.11 Summary

| Pattern | Use Case | Model Recommendation |
|---------|----------|---------------------|
| Classification | Routing, tagging | Haiku (fast/cheap) |
| Extraction | Data parsing | Sonnet |
| Transformation | Format conversion | Sonnet |
| Summarization | Content condensation | Sonnet |
| Q&A | RAG, support | Sonnet |
| Code Generation | Development | Sonnet/Opus |
| Review | Quality checks | Sonnet |
| Comparison | Decision support | Sonnet |
| Rewrite | Content improvement | Sonnet |
| Multi-step | Complex workflows | Mixed |
