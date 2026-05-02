# Chapter 3: Few-Shot Examples

## 3.1 What is Few-Shot Learning?

Few-shot learning provides examples in the prompt to teach the model the desired behavior without fine-tuning.

```
Zero-shot:  No examples, just instructions
One-shot:   One example
Few-shot:   2-5 examples
```

```python
# Zero-shot
prompt = "Convert to JSON: Name is John, age is 30"

# Few-shot
prompt = """
Convert to JSON:

Name is Alice, age is 25 → {"name": "Alice", "age": 25}
Name is Bob, age is 40 → {"name": "Bob", "age": 40}
Name is John, age is 30 →"""
```

## 3.2 Why Few-Shot Works

Examples establish patterns more reliably than instructions:

```python
# Instruction (might not follow exactly)
prompt = "Always respond with exactly 3 bullet points"

# Examples (model mimics the pattern)
prompt = """
Summarize this topic in 3 bullet points:

Topic: Climate change
• Global temperatures are rising
• Ice caps are melting
• Sea levels are increasing

Topic: Renewable energy
• Solar power is becoming cheaper
• Wind farms are expanding
• Battery storage is improving

Topic: Machine learning
•"""
```

## 3.3 Example Format

```python
def format_examples(examples: list[dict], final_input: str) -> str:
    """Format few-shot examples"""
    formatted = []

    for ex in examples:
        formatted.append(f"Input: {ex['input']}\nOutput: {ex['output']}")

    formatted.append(f"Input: {final_input}\nOutput:")

    return "\n\n".join(formatted)

examples = [
    {"input": "Hello", "output": "Bonjour"},
    {"input": "Goodbye", "output": "Au revoir"},
    {"input": "Thank you", "output": "Merci"},
]

prompt = format_examples(examples, "Good morning")
# Model continues pattern: "Bonjour" or "Bon matin"
```

## 3.4 Choosing Examples

**Diversity**: Cover different cases

```python
# Bad: All similar examples
examples = [
    {"input": "happy", "output": "positive"},
    {"input": "joyful", "output": "positive"},
    {"input": "excited", "output": "positive"},
]

# Good: Diverse examples
examples = [
    {"input": "happy", "output": "positive"},
    {"input": "angry", "output": "negative"},
    {"input": "okay", "output": "neutral"},
]
```

**Edge cases**: Include tricky scenarios

```python
examples = [
    {"input": "Great product!", "output": "positive"},
    {"input": "Terrible service", "output": "negative"},
    {"input": "It's fine I guess", "output": "neutral"},
    {"input": "Not bad, not great", "output": "neutral"},  # Edge case
    {"input": "", "output": "unknown"},  # Empty input
]
```

## 3.5 Example Ordering

Order matters - put most representative examples first and last:

```python
def order_examples(examples: list, query: str) -> list:
    """Order examples by relevance to query"""
    # Most similar first (or use embedding similarity)
    # Most representative last (recency bias)
    return sorted(examples, key=lambda x: similarity(x["input"], query))
```

## 3.6 Few-Shot for Classification

```python
classification_prompt = """
Classify the support ticket:

Ticket: "I can't log in to my account"
Category: access_issue

Ticket: "When will my order arrive?"
Category: shipping

Ticket: "I want a refund"
Category: billing

Ticket: "The app crashes on startup"
Category: technical

Ticket: "How do I change my password?"
Category: access_issue

Ticket: "{user_ticket}"
Category:"""
```

## 3.7 Few-Shot for Extraction

```python
extraction_prompt = """
Extract contact information:

Text: "Call me at 555-1234 or email john@example.com"
Result: {"phone": "555-1234", "email": "john@example.com"}

Text: "Reach out via alice@company.org"
Result: {"phone": null, "email": "alice@company.org"}

Text: "My number is (555) 987-6543"
Result: {"phone": "(555) 987-6543", "email": null}

Text: "{input_text}"
Result:"""
```

## 3.8 Few-Shot for Transformation

```python
transformation_prompt = """
Convert natural language to SQL:

Question: "How many users signed up last month?"
SQL: SELECT COUNT(*) FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH)

Question: "What are the top 5 products by revenue?"
SQL: SELECT product_name, SUM(revenue) as total FROM sales GROUP BY product_name ORDER BY total DESC LIMIT 5

Question: "Show me all orders from customer 123"
SQL: SELECT * FROM orders WHERE customer_id = 123

Question: "{user_question}"
SQL:"""
```

## 3.9 Dynamic Example Selection

```python
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class ExampleSelector:
    def __init__(self, examples: list[dict], embeddings: np.ndarray):
        self.examples = examples
        self.embeddings = embeddings

    def select(self, query: str, k: int = 3) -> list[dict]:
        query_embedding = get_embedding(query)
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        top_indices = np.argsort(similarities)[-k:][::-1]
        return [self.examples[i] for i in top_indices]

# Usage
selector = ExampleSelector(all_examples, example_embeddings)
relevant_examples = selector.select(user_query, k=3)
prompt = format_examples(relevant_examples, user_query)
```

## 3.10 How Many Examples?

```python
# Rule of thumb
EXAMPLE_COUNTS = {
    "simple_classification": 2-3,
    "complex_classification": 5-7,
    "format_transformation": 2-3,
    "complex_reasoning": 3-5,
    "style_transfer": 3-4,
}

# Balance: More examples = better pattern, but more tokens
def optimal_example_count(task_type: str, context_budget: int) -> int:
    base = EXAMPLE_COUNTS.get(task_type, 3)
    # Reduce if context is tight
    if context_budget < 4000:
        return min(2, base)
    return base
```

## 3.11 Anti-Patterns

```python
# Bad: Inconsistent format
examples = [
    {"input": "hello", "output": "HELLO"},
    {"input": "world", "output": "World"},  # Different casing!
]

# Bad: Examples that contradict
examples = [
    {"input": "good", "output": "positive"},
    {"input": "good", "output": "neutral"},  # Contradiction!
]

# Bad: Too complex examples
examples = [
    {"input": "...(500 words)...", "output": "...(500 words)..."},
]
# Use simpler, shorter examples
```

## 3.12 Summary

**Few-shot is effective for:**
- Classification tasks
- Format transformation
- Style consistency
- Complex instructions

**Best practices:**
- 3-5 diverse examples usually sufficient
- Include edge cases
- Keep examples consistent
- Order by relevance
- Select dynamically when possible
- Balance tokens vs accuracy
