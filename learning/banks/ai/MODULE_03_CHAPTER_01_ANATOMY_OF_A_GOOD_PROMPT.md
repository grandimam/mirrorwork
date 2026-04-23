# Chapter 1: Anatomy of a Good Prompt

## 1.1 The Fundamental Principle

LLMs continue patterns. A good prompt establishes a clear pattern for the model to continue.

```python
# Vague - many possible continuations
prompt = "Help with code"

# Clear - specific pattern to continue
prompt = """
Task: Write a Python function
Input: A list of integers
Output: The sum of all even numbers
Requirements: Use list comprehension

Function:
```python
def sum_even(numbers: list[int]) -> int:
"""
```

## 1.2 Prompt Components

```
┌─────────────────────────────────────────┐
│  1. CONTEXT                             │
│     Background information              │
├─────────────────────────────────────────┤
│  2. TASK                                │
│     What you want done                  │
├─────────────────────────────────────────┤
│  3. INPUT                               │
│     Data to work with                   │
├─────────────────────────────────────────┤
│  4. FORMAT                              │
│     How to structure output             │
├─────────────────────────────────────────┤
│  5. CONSTRAINTS                         │
│     Rules and limitations               │
└─────────────────────────────────────────┘
```

## 1.3 Context

Provide relevant background:

```python
# Without context
prompt = "Review this code"

# With context
prompt = """
You are reviewing code for a financial application where precision is critical.
The codebase uses Python 3.11 and follows PEP 8.
Team preference: explicit error handling over silent failures.

Review this code:
{code}
"""
```

## 1.4 Task

Be specific about what you want:

```python
# Vague task
prompt = "Improve this code"

# Specific task
prompt = """
Refactor this function to:
1. Handle edge cases (empty input, None values)
2. Add type hints
3. Reduce cyclomatic complexity
"""
```

## 1.5 Input Formatting

Structure input data clearly:

```python
# Unstructured
prompt = f"Here's some data: {data} and user said {user_input}"

# Structured
prompt = f"""
## Data
```json
{json.dumps(data, indent=2)}
```

## User Query
{user_input}

## Task
Answer the user's query using only the provided data.
"""
```

## 1.6 Output Format

Specify exactly what you want back:

```python
# Ambiguous output
prompt = "Analyze this text and tell me about it"

# Explicit format
prompt = """
Analyze the following text and return JSON:
{
    "sentiment": "positive" | "negative" | "neutral",
    "confidence": 0.0-1.0,
    "key_topics": ["topic1", "topic2"],
    "summary": "one sentence summary"
}

Text: {text}
"""
```

## 1.7 Constraints

Define boundaries:

```python
prompt = """
Summarize this article.

Constraints:
- Maximum 3 sentences
- Use simple language (8th grade reading level)
- Do not include opinions, only facts
- If information is unclear, say "unclear" rather than guessing
"""
```

## 1.8 Good vs Bad Prompts

```python
# Bad: Vague, no structure
bad_prompt = "Write some code to process data"

# Good: Specific, structured
good_prompt = """
Task: Write a Python function to process CSV data

Input:
- CSV file path (string)
- Column names to extract (list of strings)

Output:
- List of dictionaries with extracted columns

Requirements:
- Handle missing files gracefully
- Skip rows with missing values
- Return empty list for empty files

Example:
Input: "data.csv", ["name", "age"]
Output: [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
"""
```

## 1.9 Prompt Template

```python
def create_prompt(
    task: str,
    context: str = "",
    input_data: str = "",
    output_format: str = "",
    constraints: list[str] = None,
    examples: list[dict] = None
) -> str:
    parts = []

    if context:
        parts.append(f"## Context\n{context}")

    parts.append(f"## Task\n{task}")

    if input_data:
        parts.append(f"## Input\n{input_data}")

    if output_format:
        parts.append(f"## Output Format\n{output_format}")

    if constraints:
        parts.append("## Constraints\n" + "\n".join(f"- {c}" for c in constraints))

    if examples:
        examples_text = "\n\n".join(
            f"Input: {ex['input']}\nOutput: {ex['output']}"
            for ex in examples
        )
        parts.append(f"## Examples\n{examples_text}")

    return "\n\n".join(parts)
```

## 1.10 Iterative Refinement

Start simple, add detail based on results:

```python
# Version 1: Simple
v1 = "Summarize this article"
# Result: Too long, includes opinions

# Version 2: Add constraint
v2 = "Summarize this article in 2 sentences. Only facts."
# Result: Better, but misses key points

# Version 3: Add structure
v3 = """
Summarize this article:
1. Main topic (1 sentence)
2. Key finding (1 sentence)

Rules: Only facts, no opinions
"""
# Result: Good
```

## 1.11 Summary

**Good prompts have:**
- Clear task specification
- Structured input
- Explicit output format
- Defined constraints
- Examples when helpful

**Process:**
1. Start with clear task
2. Add necessary context
3. Specify output format
4. Add constraints
5. Include examples if needed
6. Iterate based on results
