# Chapter 5: Chain-of-Thought Prompting

## 5.1 What is Chain-of-Thought?

Chain-of-thought (CoT) prompting encourages the model to show its reasoning step-by-step before giving a final answer.

```python
# Without CoT
prompt = "What is 23 * 17?"
# Model might guess: "391" (correct) or "401" (wrong)

# With CoT
prompt = """
What is 23 * 17?
Think step by step.
"""
# Model: "Let me break this down:
# 23 * 17 = 23 * (10 + 7) = 230 + 161 = 391"
```

## 5.2 Why CoT Works

- Forces model to decompose problems
- Each step can be verified
- Reduces reasoning errors
- Works especially well for math, logic, multi-step problems

## 5.3 Basic CoT Patterns

```python
# Pattern 1: "Think step by step"
prompt = f"{question}\n\nThink step by step."

# Pattern 2: "Let's work through this"
prompt = f"{question}\n\nLet's work through this systematically:"

# Pattern 3: "Show your reasoning"
prompt = f"{question}\n\nShow your reasoning, then give the answer."

# Pattern 4: Structured steps
prompt = f"""
{question}

Work through this:
1. Identify what we know
2. Identify what we need to find
3. Solve step by step
4. State the final answer
"""
```

## 5.4 Zero-Shot CoT

Just add "Think step by step":

```python
def zero_shot_cot(question: str) -> str:
    prompt = f"{question}\n\nThink step by step."
    response = client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

## 5.5 Few-Shot CoT

Provide examples with reasoning:

```python
prompt = """
Q: Roger has 5 tennis balls. He buys 2 cans of 3 balls each. How many balls does he have?
A: Roger starts with 5 balls. He buys 2 cans × 3 balls = 6 balls. Total: 5 + 6 = 11 balls.

Q: The cafeteria had 23 apples. They used 20 for lunch and bought 6 more. How many do they have?
A: Started with 23. Used 20, so 23 - 20 = 3. Bought 6 more, so 3 + 6 = 9 apples.

Q: {user_question}
A:"""
```

## 5.6 CoT for Code Problems

```python
prompt = """
Problem: Find the bug in this code:
```python
def find_max(numbers):
    max_val = 0
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val
```

Think through:
1. What is this function supposed to do?
2. Trace through with example inputs
3. Identify the bug
4. Explain the fix
"""
```

## 5.7 CoT for Analysis

```python
prompt = """
Analyze whether we should migrate to microservices:

Current state:
- Monolithic Django app
- 50k LOC
- 5 developers
- Moderate traffic

Think through:
1. What problems would microservices solve?
2. What new problems would it create?
3. What's the migration cost?
4. What are the alternatives?
5. Recommendation
"""
```

## 5.8 Extracting the Final Answer

```python
def extract_answer_from_cot(response: str) -> str:
    """Extract final answer from chain-of-thought response"""
    # Look for common answer patterns
    patterns = [
        r"(?:final answer|answer|therefore|thus|so)[:\s]+(.+?)(?:\.|$)",
        r"(?:the result is|this gives us)[:\s]+(.+?)(?:\.|$)",
        r"= (\d+(?:\.\d+)?)\s*$",
    ]

    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()

    # If no pattern, return last line
    lines = [l.strip() for l in response.strip().split('\n') if l.strip()]
    return lines[-1] if lines else response

# Better: Ask for structured output
prompt = """
{question}

Think step by step, then provide your answer in this format:
REASONING: [your step-by-step reasoning]
ANSWER: [final answer only]
"""
```

## 5.9 Self-Consistency

Run CoT multiple times and take majority vote:

```python
async def self_consistent_cot(question: str, n_samples: int = 5) -> str:
    """Run CoT multiple times and return most common answer"""
    prompt = f"{question}\n\nThink step by step."

    responses = await asyncio.gather(*[
        client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            temperature=0.7,  # Some variation
            messages=[{"role": "user", "content": prompt}]
        )
        for _ in range(n_samples)
    ])

    answers = [
        extract_answer_from_cot(r.content[0].text)
        for r in responses
    ]

    # Return most common answer
    from collections import Counter
    return Counter(answers).most_common(1)[0][0]
```

## 5.10 When to Use CoT

**Good for:**
- Math and arithmetic
- Logical reasoning
- Multi-step problems
- Code debugging
- Analysis and decision-making

**Not needed for:**
- Simple factual questions
- Creative writing
- Translation
- Simple extraction

```python
def should_use_cot(task_type: str) -> bool:
    cot_tasks = {"math", "logic", "reasoning", "debugging", "analysis"}
    return task_type in cot_tasks
```

## 5.11 CoT Variants

```python
# Plan-and-solve
prompt = """
{question}

First, devise a plan to solve this.
Then, execute the plan step by step.
"""

# Least-to-most
prompt = """
{question}

First, identify the simplest sub-problem.
Solve it, then build up to the full solution.
"""

# Self-ask
prompt = """
{question}

Ask yourself what information you need.
Answer each sub-question, then combine for final answer.
"""
```

## 5.12 Summary

| Technique | When to Use |
|-----------|-------------|
| Zero-shot CoT | Quick reasoning tasks |
| Few-shot CoT | Complex reasoning with examples |
| Self-consistency | High-stakes decisions |
| Structured CoT | When you need parseable output |

**Best practices:**
- Use CoT for multi-step reasoning
- Provide examples for complex tasks
- Extract final answer explicitly
- Use self-consistency for important decisions
- Don't use CoT for simple tasks (wastes tokens)
