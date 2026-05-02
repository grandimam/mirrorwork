# Module 23: Fine-tuning Basics

## 23.1 When to Fine-tune

```
Fine-tuning is NOT needed for:
- Following instructions (use prompts)
- Using specific knowledge (use RAG)
- Output formatting (use structured outputs)

Fine-tuning IS useful for:
- Consistent style/tone
- Domain-specific language
- Reducing prompt length
- Improving latency (smaller prompts)
```

## 23.2 Preparing Training Data

```python
# JSONL format for fine-tuning
# Each line: {"messages": [{"role": "...", "content": "..."}]}

def prepare_dataset(examples: list[dict]) -> str:
    """Convert examples to fine-tuning format"""
    lines = []
    for ex in examples:
        entry = {
            "messages": [
                {"role": "system", "content": ex.get("system", "")},
                {"role": "user", "content": ex["input"]},
                {"role": "assistant", "content": ex["output"]}
            ]
        }
        lines.append(json.dumps(entry))
    return "\n".join(lines)

# Example dataset
examples = [
    {
        "system": "You are a customer support agent for Acme Corp.",
        "input": "How do I reset my password?",
        "output": "To reset your password: 1) Go to acme.com/reset 2) Enter your email 3) Click the link in your email"
    },
    {
        "system": "You are a customer support agent for Acme Corp.",
        "input": "What's your refund policy?",
        "output": "Acme offers full refunds within 30 days of purchase. Contact support@acme.com with your order number."
    }
]

# Save as training file
with open("training.jsonl", "w") as f:
    f.write(prepare_dataset(examples))
```

## 23.3 Data Quality Guidelines

```python
class DataValidator:
    def validate_example(self, example: dict) -> list[str]:
        issues = []

        # Check required fields
        if "input" not in example:
            issues.append("Missing input")
        if "output" not in example:
            issues.append("Missing output")

        # Check lengths
        if len(example.get("input", "")) < 10:
            issues.append("Input too short")
        if len(example.get("output", "")) < 10:
            issues.append("Output too short")

        # Check for quality
        if example.get("output", "").startswith("I don't"):
            issues.append("Output is a refusal - remove or fix")

        return issues

    def validate_dataset(self, examples: list[dict]) -> dict:
        all_issues = []
        valid = []

        for i, ex in enumerate(examples):
            issues = self.validate_example(ex)
            if issues:
                all_issues.append({"index": i, "issues": issues})
            else:
                valid.append(ex)

        return {
            "valid_count": len(valid),
            "invalid_count": len(all_issues),
            "issues": all_issues,
            "valid_examples": valid
        }
```

## 23.4 Fine-tuning with OpenAI

```python
from openai import OpenAI

client = OpenAI()

# Upload training file
with open("training.jsonl", "rb") as f:
    file = client.files.create(file=f, purpose="fine-tune")

# Create fine-tuning job
job = client.fine_tuning.jobs.create(
    training_file=file.id,
    model="gpt-4o-mini-2024-07-18",
    hyperparameters={
        "n_epochs": 3
    }
)

# Check status
status = client.fine_tuning.jobs.retrieve(job.id)
print(f"Status: {status.status}")

# Use fine-tuned model
if status.status == "succeeded":
    response = client.chat.completions.create(
        model=status.fine_tuned_model,
        messages=[{"role": "user", "content": "How do I reset my password?"}]
    )
```

## 23.5 Evaluation Before/After

```python
class FineTuneEvaluator:
    def __init__(self, base_model: str, fine_tuned_model: str):
        self.base = base_model
        self.tuned = fine_tuned_model

    async def compare(self, test_cases: list[dict]) -> dict:
        results = {"base": [], "tuned": []}

        for case in test_cases:
            # Run both models
            base_response = await self._run(self.base, case["input"])
            tuned_response = await self._run(self.tuned, case["input"])

            # Score against expected
            base_score = self._score(base_response, case["expected"])
            tuned_score = self._score(tuned_response, case["expected"])

            results["base"].append(base_score)
            results["tuned"].append(tuned_score)

        return {
            "base_avg": sum(results["base"]) / len(results["base"]),
            "tuned_avg": sum(results["tuned"]) / len(results["tuned"]),
            "improvement": (sum(results["tuned"]) - sum(results["base"])) / len(results["base"])
        }
```

## 23.6 Cost Considerations

```python
# Fine-tuning costs
FINE_TUNE_COSTS = {
    "gpt-4o-mini": {
        "training": 3.00,     # per 1M tokens
        "inference_input": 0.30,
        "inference_output": 1.20
    }
}

def estimate_fine_tune_cost(
    training_tokens: int,
    epochs: int,
    expected_requests: int,
    avg_input_tokens: int,
    avg_output_tokens: int
) -> dict:
    pricing = FINE_TUNE_COSTS["gpt-4o-mini"]

    training_cost = (training_tokens * epochs * pricing["training"]) / 1_000_000

    inference_cost_per_request = (
        avg_input_tokens * pricing["inference_input"] +
        avg_output_tokens * pricing["inference_output"]
    ) / 1_000_000

    monthly_inference = inference_cost_per_request * expected_requests

    return {
        "training_cost": training_cost,
        "monthly_inference": monthly_inference,
        "break_even_months": training_cost / (monthly_inference * 0.5)  # Assuming 50% savings
    }
```

## 23.7 Alternatives to Fine-tuning

```python
# Often better alternatives exist

# 1. Few-shot prompting
PROMPT_WITH_EXAMPLES = """You are a support agent for Acme Corp.

Example 1:
User: How do I reset my password?
Agent: To reset your password: 1) Go to acme.com/reset 2) Enter your email 3) Click the link

Example 2:
User: What's the refund policy?
Agent: Acme offers full refunds within 30 days. Contact support@acme.com

Now respond to:
User: {query}
Agent:"""

# 2. RAG for domain knowledge
# 3. System prompts for style
# 4. Structured outputs for format
```

## 23.8 Summary

| Approach | Best For |
|----------|----------|
| Prompting | Most cases |
| RAG | Domain knowledge |
| Fine-tuning | Style, tone, format consistency |
| Full training | Specialized capabilities |

**Best practices:**
- Start with prompting, fine-tune only if needed
- Need 50-100+ high-quality examples
- Validate data quality thoroughly
- Evaluate before and after
- Consider cost vs benefit
- Keep evaluation set separate
