# Module 40: Constrained Decoding

## 40.1 What is Constrained Decoding?

```
Standard generation:
- Model outputs any valid tokens
- May not match required format
- Post-processing needed

Constrained decoding:
- Limit valid tokens at each step
- Guarantee format compliance
- No post-processing needed

Constraints:
- JSON schema
- Regex patterns
- Grammar rules
- Enum values
```

## 40.2 JSON Mode (Native)

```python
# OpenAI JSON mode
from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o",
    response_format={"type": "json_object"},
    messages=[{
        "role": "user",
        "content": "List 3 fruits as JSON with name and color fields"
    }]
)

# Guaranteed valid JSON
data = json.loads(response.choices[0].message.content)
```

## 40.3 Structured Outputs with Schema

```python
# OpenAI Structured Outputs
from pydantic import BaseModel

class Fruit(BaseModel):
    name: str
    color: str
    calories: int

class FruitList(BaseModel):
    fruits: list[Fruit]

response = client.beta.chat.completions.parse(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": "List 3 fruits with their colors and calories"
    }],
    response_format=FruitList
)

# Guaranteed to match schema
fruits = response.choices[0].message.parsed
```

## 40.4 Outlines (Grammar-Constrained)

```python
import outlines

# Load model
model = outlines.models.transformers("mistralai/Mistral-7B-v0.1")

# JSON schema constraint
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer", "minimum": 0, "maximum": 150}
    },
    "required": ["name", "age"]
}

generator = outlines.generate.json(model, schema)
result = generator("Create a person profile:")
# Guaranteed valid JSON matching schema

# Regex constraint
phone_pattern = r"\(\d{3}\) \d{3}-\d{4}"
generator = outlines.generate.regex(model, phone_pattern)
phone = generator("Generate a phone number:")
# Output: (555) 123-4567

# Choice constraint
generator = outlines.generate.choice(model, ["yes", "no", "maybe"])
answer = generator("Should I buy this? ")
# Output: one of yes/no/maybe
```

## 40.5 LMQL (Query Language)

```python
import lmql

@lmql.query
async def classify_sentiment(text: str):
    '''lmql
    "Classify the sentiment of: {text}\n"
    "Sentiment: [SENTIMENT]" where SENTIMENT in ["positive", "negative", "neutral"]
    return SENTIMENT
    '''

result = await classify_sentiment("I love this product!")
# Guaranteed to be one of the three options

@lmql.query
async def extract_info(text: str):
    '''lmql
    "Extract information from: {text}\n"
    "Name: [NAME]" where len(NAME) < 50
    "Age: [AGE]" where INT(AGE) and 0 <= int(AGE) <= 120
    return {"name": NAME, "age": int(AGE)}
    '''
```

## 40.6 Guidance Library

```python
from guidance import models, gen, select

# Load model
model = models.Transformers("mistralai/Mistral-7B-v0.1")

# Structured generation
result = model + f"""\
Extract information:
Name: {gen('name', max_tokens=20, stop='\n')}
Category: {select(['electronics', 'clothing', 'food'], name='category')}
Price: ${gen('price', regex=r'\d+\.\d{2}')}
"""

print(result['name'], result['category'], result['price'])

# Complex template
result = model + f"""\
Generate a product review:
Rating: {gen('rating', regex=r'[1-5]')}/5
Pros:
- {gen('pro1', max_tokens=30, stop='\n')}
- {gen('pro2', max_tokens=30, stop='\n')}
Cons:
- {gen('con1', max_tokens=30, stop='\n')}
Summary: {gen('summary', max_tokens=100)}
"""
```

## 40.7 Instructor Library

```python
import instructor
from pydantic import BaseModel, Field
from openai import OpenAI

# Patch OpenAI client
client = instructor.from_openai(OpenAI())

class UserInfo(BaseModel):
    name: str = Field(description="User's full name")
    age: int = Field(ge=0, le=150, description="User's age")
    email: str = Field(pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')

# Extract with validation
user = client.chat.completions.create(
    model="gpt-4o",
    response_model=UserInfo,
    messages=[{
        "role": "user",
        "content": "John Doe is 30 years old, email: john@example.com"
    }]
)

# user is a validated UserInfo instance
print(user.name, user.age, user.email)

# With retries for validation failures
user = client.chat.completions.create(
    model="gpt-4o",
    response_model=UserInfo,
    max_retries=3,  # Retry if validation fails
    messages=[{"role": "user", "content": "Extract: Jane, 25, jane@test.com"}]
)
```

## 40.8 Custom Grammar Constraints

```python
# Using outlines with custom grammar
import outlines

# Define grammar (BNF-like)
grammar = """
start: object
object: "{" pair ("," pair)* "}"
pair: STRING ":" value
value: STRING | NUMBER | "true" | "false" | "null" | array | object
array: "[" value ("," value)* "]" | "[]"
STRING: /"[^"]*"/
NUMBER: /-?[0-9]+(\.[0-9]+)?/
"""

model = outlines.models.transformers("...")
generator = outlines.generate.cfg(model, grammar)

result = generator("Generate a JSON config:")
# Output follows the grammar exactly
```

## 40.9 Enum and Choice Constraints

```python
from enum import Enum
from pydantic import BaseModel
import instructor

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Status(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class Task(BaseModel):
    title: str
    priority: Priority  # Constrained to enum values
    status: Status

client = instructor.from_openai(OpenAI())

task = client.chat.completions.create(
    model="gpt-4o",
    response_model=Task,
    messages=[{
        "role": "user",
        "content": "Create a task: Fix login bug, urgent, currently working on it"
    }]
)

# task.priority is guaranteed to be a Priority enum value
print(task.priority)  # Priority.HIGH or Priority.CRITICAL
```

## 40.10 Summary

| Library | Approach | Models |
|---------|----------|--------|
| OpenAI Structured | Native API | GPT-4o |
| Outlines | Grammar/regex | Local models |
| Guidance | Template-based | Local models |
| LMQL | Query language | Various |
| Instructor | Pydantic + retry | API models |

**Best practices:**
- Use native structured outputs when available
- Define clear schemas with Pydantic
- Add validation constraints (min, max, pattern)
- Use enums for categorical outputs
- Implement retry logic for complex schemas
- Test edge cases thoroughly
