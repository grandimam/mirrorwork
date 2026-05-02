# Chapter 4: Output Format Control

## 4.1 Why Format Control Matters

Unstructured outputs are hard to parse programmatically:

```python
# Uncontrolled output
"The sentiment is positive and the confidence is about 85%"

# Controlled output
{"sentiment": "positive", "confidence": 0.85}
```

## 4.2 JSON Output

```python
# Method 1: Explicit instruction
prompt = """
Analyze this text and return JSON only:
{"sentiment": "positive|negative|neutral", "confidence": 0.0-1.0}

Text: {text}
"""

# Method 2: Prefill assistant response (Anthropic)
response = client.messages.create(
    model="claude-3-5-sonnet",
    messages=[
        {"role": "user", "content": "Analyze: Great product!"},
        {"role": "assistant", "content": "{"}  # Forces JSON start
    ],
    max_tokens=100
)
```

## 4.3 Structured Output with Schema

```python
schema = """
Return JSON matching this schema:
{
    "summary": string,          // 1-2 sentence summary
    "key_points": string[],     // 3-5 bullet points
    "sentiment": "positive" | "negative" | "neutral",
    "confidence": number,       // 0.0 to 1.0
    "topics": string[]          // main topics discussed
}
"""

prompt = f"""
{schema}

Analyze this article:
{article}
"""
```

## 4.4 Parsing JSON Output

```python
import json
import re

def extract_json(text: str) -> dict:
    """Extract JSON from LLM response"""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in text
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{.*\}',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1) if '```' in pattern else match.group())
            except json.JSONDecodeError:
                continue

    raise ValueError("No valid JSON found in response")
```

## 4.5 Using Pydantic for Validation

```python
from pydantic import BaseModel, Field
from typing import Literal

class SentimentResult(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str

def parse_response(text: str) -> SentimentResult:
    data = extract_json(text)
    return SentimentResult(**data)  # Validates automatically

# Usage
response = client.messages.create(...)
try:
    result = parse_response(response.content[0].text)
    print(f"Sentiment: {result.sentiment}")
except ValidationError as e:
    print(f"Invalid response: {e}")
```

## 4.6 Retry on Format Failure

```python
async def get_structured_output(
    prompt: str,
    schema: type[BaseModel],
    max_retries: int = 3
) -> BaseModel:
    for attempt in range(max_retries):
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            data = extract_json(response.content[0].text)
            return schema(**data)
        except (ValueError, ValidationError) as e:
            if attempt == max_retries - 1:
                raise
            # Ask model to fix
            prompt = f"""
Your previous response had an error: {e}

Please provide a valid JSON response matching the schema.
Previous response: {response.content[0].text}
"""
```

## 4.7 Markdown Output

```python
prompt = """
Write documentation in Markdown format:

# Title
Brief description

## Installation
```bash
installation commands
```

## Usage
```python
code example
```

## API Reference
| Method | Description |
|--------|-------------|
| ... | ... |
"""
```

## 4.8 XML Output

```python
prompt = """
Return the analysis in XML format:

<analysis>
    <summary>...</summary>
    <sentiment>positive|negative|neutral</sentiment>
    <topics>
        <topic>...</topic>
    </topics>
</analysis>

Analyze: {text}
"""

# Parse XML
import xml.etree.ElementTree as ET

def parse_xml_response(text: str):
    # Extract XML from response
    match = re.search(r'<analysis>.*</analysis>', text, re.DOTALL)
    if match:
        root = ET.fromstring(match.group())
        return {
            "summary": root.find("summary").text,
            "sentiment": root.find("sentiment").text,
        }
```

## 4.9 List/Array Output

```python
prompt = """
List exactly 5 suggestions, one per line, numbered:

1. First suggestion
2. Second suggestion
...

Topic: {topic}
"""

def parse_numbered_list(text: str) -> list[str]:
    pattern = r'^\d+\.\s*(.+)$'
    return re.findall(pattern, text, re.MULTILINE)
```

## 4.10 Multiple Outputs

```python
prompt = """
Provide three versions:

## Formal
[formal version]

## Casual
[casual version]

## Technical
[technical version]

Original text: {text}
"""

def parse_sections(text: str) -> dict[str, str]:
    sections = {}
    current = None
    content = []

    for line in text.split('\n'):
        if line.startswith('## '):
            if current:
                sections[current] = '\n'.join(content).strip()
            current = line[3:].strip()
            content = []
        elif current:
            content.append(line)

    if current:
        sections[current] = '\n'.join(content).strip()

    return sections
```

## 4.11 Format Enforcement Techniques

```python
# 1. End prompt with format start
prompt = "List 3 items:\n1."

# 2. Use stop sequences
response = client.messages.create(
    ...,
    stop_sequences=["\n\n", "---"]  # Stop at section breaks
)

# 3. Constrain max_tokens
response = client.messages.create(
    ...,
    max_tokens=50  # Force brevity
)

# 4. Negative instructions
prompt = "Return JSON only. No explanations. No markdown code blocks."
```

## 4.12 Summary

| Format | Use Case | Parsing |
|--------|----------|---------|
| JSON | Structured data | `json.loads` + Pydantic |
| XML | Hierarchical data | ElementTree |
| Markdown | Documentation | Regex sections |
| Numbered list | Ordered items | Regex |

**Best practices:**
- Always specify exact format in prompt
- Provide schema or example
- Use Pydantic for validation
- Implement retry on parse failure
- Prefill assistant response when possible
