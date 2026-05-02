# Module 36: Extended Thinking and Reasoning Models

## 36.1 What is Extended Thinking?

```
Standard LLM:
- Generates response directly
- Fast but may miss complex reasoning

Extended Thinking:
- Model "thinks" before responding
- Uses internal reasoning tokens
- Better for complex problems

Examples:
- OpenAI o1, o3
- Claude with extended thinking
- DeepSeek-R1
```

## 36.2 Claude Extended Thinking

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=16000,
    thinking={
        "type": "enabled",
        "budget_tokens": 10000  # Max thinking tokens
    },
    messages=[{
        "role": "user",
        "content": "Solve this step by step: What is 247 * 893?"
    }]
)

# Response contains thinking blocks
for block in response.content:
    if block.type == "thinking":
        print(f"Thinking: {block.thinking}")
    elif block.type == "text":
        print(f"Answer: {block.text}")
```

## 36.3 OpenAI o1 Models

```python
from openai import OpenAI

client = OpenAI()

# o1 models automatically use reasoning
response = client.chat.completions.create(
    model="o1-preview",
    messages=[{
        "role": "user",
        "content": "Write a proof that there are infinitely many primes."
    }]
)

# Reasoning tokens are used internally
# You see final response, not reasoning process
print(response.choices[0].message.content)
print(f"Reasoning tokens: {response.usage.completion_tokens_details.reasoning_tokens}")
```

## 36.4 When to Use Extended Thinking

```python
# Good use cases for extended thinking:
COMPLEX_TASKS = [
    "Multi-step math problems",
    "Logic puzzles",
    "Code debugging",
    "Scientific reasoning",
    "Strategic planning",
    "Complex analysis",
]

# Not needed for:
SIMPLE_TASKS = [
    "Factual questions",
    "Simple translations",
    "Text formatting",
    "Basic summarization",
]

def should_use_thinking(task: str) -> bool:
    complexity_indicators = [
        "step by step",
        "prove",
        "analyze",
        "debug",
        "solve",
        "why does",
        "compare and contrast",
    ]
    return any(ind in task.lower() for ind in complexity_indicators)
```

## 36.5 Structured Reasoning Prompts

```python
# Even without extended thinking, prompt for reasoning

REASONING_PROMPT = """
Before answering, think through this step by step:

1. What is being asked?
2. What information do I have?
3. What approach should I take?
4. Work through the solution
5. Verify the answer

Question: {question}

Let me think through this...
"""

# Chain of thought prompting
COT_PROMPT = """
{question}

Let's approach this step by step:
"""

# Self-consistency: generate multiple reasoning paths
async def self_consistent_answer(question: str, n: int = 3) -> str:
    responses = []
    for _ in range(n):
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            temperature=0.7,  # Some variation
            messages=[{
                "role": "user",
                "content": COT_PROMPT.format(question=question)
            }]
        )
        responses.append(response.content[0].text)

    # Find consensus
    return find_majority_answer(responses)
```

## 36.6 Thinking Budget Management

```python
class ThinkingManager:
    def __init__(self, default_budget: int = 5000):
        self.default_budget = default_budget

    def estimate_budget(self, task: str) -> int:
        """Estimate thinking tokens needed"""
        # More complex tasks need more thinking
        if any(w in task.lower() for w in ["prove", "analyze deeply"]):
            return 15000
        if any(w in task.lower() for w in ["solve", "debug", "explain why"]):
            return 10000
        if any(w in task.lower() for w in ["summarize", "list"]):
            return 2000
        return self.default_budget

    async def run_with_thinking(self, task: str) -> dict:
        budget = self.estimate_budget(task)

        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=budget + 4000,  # Budget + response
            thinking={"type": "enabled", "budget_tokens": budget},
            messages=[{"role": "user", "content": task}]
        )

        return {
            "thinking": self._extract_thinking(response),
            "answer": self._extract_text(response),
            "tokens_used": response.usage.output_tokens
        }
```

## 36.7 Reasoning Verification

```python
class ReasoningVerifier:
    """Verify the reasoning is sound"""

    async def verify(self, question: str, reasoning: str, answer: str) -> dict:
        prompt = f"""
Review this reasoning for errors:

Question: {question}

Reasoning:
{reasoning}

Final Answer: {answer}

Check for:
1. Logical errors
2. Mathematical mistakes
3. Missing steps
4. Incorrect conclusions

Is the reasoning valid? Respond with:
VALID: [yes/no]
ISSUES: [list any problems found]
"""
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_verification(response.content[0].text)
```

## 36.8 Reasoning with Tools

```python
async def reason_and_act(task: str, tools: list) -> str:
    """Combine extended thinking with tool use"""

    # First, reason about the approach
    planning_response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=10000,
        thinking={"type": "enabled", "budget_tokens": 5000},
        messages=[{
            "role": "user",
            "content": f"""
Plan how to solve this task. Think about what tools you'll need and in what order.

Available tools: {[t['name'] for t in tools]}

Task: {task}
"""
        }]
    )

    plan = extract_text(planning_response)

    # Then execute with tools
    execution_response = await client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=4096,
        tools=tools,
        messages=[
            {"role": "user", "content": task},
            {"role": "assistant", "content": f"Plan: {plan}\n\nNow executing..."}
        ]
    )

    # Continue tool loop...
    return await complete_tool_loop(execution_response, tools)
```

## 36.9 Cost Considerations

```python
# Extended thinking uses more tokens

THINKING_COSTS = {
    "claude-3-5-sonnet": {
        "thinking_input": 3.00,   # per 1M tokens
        "thinking_output": 15.00,
        "regular_input": 3.00,
        "regular_output": 15.00,
    },
    "o1-preview": {
        "input": 15.00,
        "output": 60.00,  # Includes reasoning
    }
}

def estimate_thinking_cost(
    input_tokens: int,
    thinking_tokens: int,
    output_tokens: int,
    model: str = "claude-3-5-sonnet"
) -> float:
    pricing = THINKING_COSTS[model]
    return (
        input_tokens * pricing["thinking_input"] / 1_000_000 +
        (thinking_tokens + output_tokens) * pricing["thinking_output"] / 1_000_000
    )
```

## 36.10 Summary

| Model | Thinking Style |
|-------|----------------|
| Claude (extended) | Explicit thinking blocks |
| OpenAI o1 | Internal reasoning tokens |
| DeepSeek-R1 | Open-source reasoning |
| Standard + CoT | Prompted reasoning |

**Best practices:**
- Use extended thinking for complex tasks
- Set appropriate token budgets
- Verify reasoning on critical tasks
- Consider cost vs. quality tradeoff
- Combine with tools for best results
- Don't use for simple tasks
