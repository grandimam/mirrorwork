# Module 4: Structured Outputs

## 4.1 Why Structured Outputs?

LLM responses are strings. Applications need structured data.

```python
# Problem: Unstructured response
response = "The sentiment is positive with high confidence"
# How do you extract sentiment? confidence level?

# Solution: Structured response
response = {"sentiment": "positive", "confidence": 0.92}
# Easy to use in code
```

## 4.2 JSON Mode

Request JSON output explicitly:

```python
# Anthropic approach
response = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=500,
    messages=[
        {"role": "user", "content": """
            Analyze this text and return JSON only:
            {"sentiment": "positive|negative|neutral", "confidence": 0.0-1.0}

            Text: Great product!
        """},
        {"role": "assistant", "content": "{"}  # Force JSON start
    ]
)
result = json.loads("{" + response.content[0].text)
```

## 4.3 Schema Definition

Define exact structure expected:

```python
SCHEMA = """
Return a JSON object matching this exact schema:
{
    "summary": string,           // 1-2 sentence summary
    "sentiment": "positive" | "negative" | "neutral",
    "confidence": number,        // between 0.0 and 1.0
    "key_topics": string[],      // array of main topics (max 5)
    "action_items": [
        {
            "task": string,
            "priority": "high" | "medium" | "low"
        }
    ]
}

Important:
- Return ONLY the JSON, no other text
- All fields are required
- Use null for unknown values, not empty strings
"""
```

## 4.4 Pydantic Validation

```python
from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ActionItem(BaseModel):
    task: str
    priority: Priority

class AnalysisResult(BaseModel):
    summary: str
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_topics: list[str] = Field(max_length=5)
    action_items: list[ActionItem] = []

def parse_response(text: str) -> AnalysisResult:
    # Extract JSON from response
    data = extract_json(text)
    return AnalysisResult(**data)
```

## 4.5 Auto-Schema from Pydantic

```python
def pydantic_to_prompt_schema(model: type[BaseModel]) -> str:
    """Generate schema description from Pydantic model"""
    schema = model.model_json_schema()
    return json.dumps(schema, indent=2)

# Usage
schema_text = pydantic_to_prompt_schema(AnalysisResult)
prompt = f"""
Return JSON matching this schema:
{schema_text}

Analyze: {{text}}
"""
```

## 4.6 Robust JSON Extraction

```python
import json
import re

def extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling common issues"""

    # 1. Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Try extracting from code blocks
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # 3. Try finding JSON object/array
    json_patterns = [
        r'(\{[\s\S]*\})',   # Object
        r'(\[[\s\S]*\])',   # Array
    ]
    for pattern in json_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # 4. Try fixing common issues
    fixed = text.strip()
    fixed = re.sub(r',\s*}', '}', fixed)  # Trailing commas
    fixed = re.sub(r',\s*]', ']', fixed)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"Could not extract JSON from: {text[:200]}...")
```

## 4.7 Retry with Feedback

```python
async def get_structured_output(
    prompt: str,
    schema: type[BaseModel],
    max_retries: int = 3
) -> BaseModel:
    """Get structured output with automatic retry on parse failure"""

    messages = [{"role": "user", "content": prompt}]

    for attempt in range(max_retries):
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1500,
            messages=messages
        )

        text = response.content[0].text

        try:
            data = extract_json(text)
            return schema(**data)
        except (ValueError, ValidationError) as e:
            if attempt == max_retries - 1:
                raise

            # Add error feedback for retry
            messages.extend([
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"""
                    Your response had an error: {str(e)}

                    Please provide a corrected JSON response.
                    Remember to match the exact schema provided.
                """}
            ])
```

## 4.8 Typed Function Wrapper

```python
from typing import TypeVar, Type

T = TypeVar('T', bound=BaseModel)

async def structured_call(
    prompt: str,
    response_model: Type[T],
    model: str = "claude-3-5-sonnet"
) -> T:
    """Type-safe structured output call"""

    schema_prompt = f"""
{prompt}

Return your response as JSON matching this schema:
{pydantic_to_prompt_schema(response_model)}

Return ONLY valid JSON, no other text.
"""

    return await get_structured_output(schema_prompt, response_model)

# Usage with full type safety
class SentimentResult(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: float

result = await structured_call(
    "Analyze: Great product!",
    SentimentResult
)
# result is typed as SentimentResult
print(result.sentiment)  # IDE autocomplete works
```

## 4.9 Handling Optional Fields

```python
from typing import Optional

class FlexibleResult(BaseModel):
    required_field: str
    optional_field: Optional[str] = None
    with_default: str = "default value"
    nullable_list: Optional[list[str]] = None

# In prompt
schema_note = """
Optional fields:
- If unknown, use null (not empty string)
- If not applicable, omit the field entirely
"""
```

## 4.10 Arrays and Nested Objects

```python
class Author(BaseModel):
    name: str
    role: str

class Article(BaseModel):
    title: str
    authors: list[Author]
    tags: list[str]
    metadata: dict[str, str]

prompt = """
Extract article information:

{
    "title": "Article title",
    "authors": [
        {"name": "Author name", "role": "Author role"}
    ],
    "tags": ["tag1", "tag2"],
    "metadata": {"key": "value"}
}
"""
```

## 4.11 Enum and Literal Types

```python
from typing import Literal
from enum import Enum

# Using Literal
class StatusResult(BaseModel):
    status: Literal["pending", "approved", "rejected"]

# Using Enum
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class Task(BaseModel):
    name: str
    status: TaskStatus

# In prompt, list valid values explicitly
prompt = """
status must be one of: "pending", "approved", "rejected"
"""
```

## 4.12 Summary

| Technique | Use Case |
|-----------|----------|
| JSON mode | Basic structured output |
| Schema definition | Complex nested structures |
| Pydantic validation | Type safety, auto-validation |
| Retry with feedback | Handle parse failures |
| Prefill response | Force output format |

**Best practices:**
- Always define explicit schema
- Use Pydantic for validation
- Handle parse failures gracefully
- Retry with error feedback
- Keep schemas as simple as possible
- Use enums/literals for constrained values
