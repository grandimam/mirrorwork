# Chapter 4: Temperature, Top-p, and Sampling

## 4.1 How Token Selection Works

After processing your prompt, the model outputs a probability distribution over all possible next tokens:

```
Token        Probability
"Paris"      0.85
"Lyon"       0.05
"France"     0.03
"the"        0.02
...          ...
```

**Sampling** is how we pick one token from this distribution.

## 4.2 Temperature

Temperature controls the "randomness" of token selection by adjusting the probability distribution.

```
Temperature = 0 (deterministic)
├── Always picks highest probability token
├── Same input → same output
└── Best for: factual tasks, code, structured output

Temperature = 1 (neutral)
├── Uses probabilities as-is
├── Balanced creativity/coherence
└── Best for: general conversation

Temperature = 2 (creative)
├── Flattens distribution (more randomness)
├── Lower probability tokens more likely
└── Best for: creative writing, brainstorming
```

Mathematically:

```python
# Temperature adjusts logits before softmax
adjusted_probs = softmax(logits / temperature)

# temperature < 1: sharpen distribution (more deterministic)
# temperature = 1: unchanged
# temperature > 1: flatten distribution (more random)
```

## 4.3 Temperature in Practice

```python
# Deterministic - same output every time
response = client.messages.create(
    model="claude-3-5-sonnet",
    temperature=0,
    messages=[{"role": "user", "content": "What is 2+2?"}]
)
# Always: "4"

# Creative - varied outputs
response = client.messages.create(
    model="claude-3-5-sonnet",
    temperature=1.5,
    messages=[{"role": "user", "content": "Write a haiku about coding"}]
)
# Different each time
```

**Recommended temperature by task**:

| Task                   | Temperature |
| ---------------------- | ----------- |
| Code generation        | 0 - 0.2     |
| JSON/structured output | 0           |
| Factual Q&A            | 0 - 0.3     |
| General chat           | 0.7 - 1.0   |
| Creative writing       | 1.0 - 1.5   |
| Brainstorming          | 1.2 - 1.8   |

## 4.4 Top-p (Nucleus Sampling)

Top-p limits selection to tokens whose cumulative probability reaches p.

```
Probabilities (sorted):
"Paris"   0.70  ─┐
"Lyon"    0.15  ─┼─ top_p=0.9 includes these (cumulative: 0.85, then 0.92)
"Nice"    0.07  ─┘
"Marseille" 0.04  ← excluded
"London"    0.02  ← excluded
...

With top_p=0.9, only "Paris", "Lyon", "Nice" are candidates
```

```python
response = client.messages.create(
    model="claude-3-5-sonnet",
    top_p=0.9,  # Consider tokens comprising top 90% probability mass
    messages=[...]
)
```

## 4.5 Top-k Sampling

Top-k limits selection to the k most likely tokens.

```python
# Only consider top 40 tokens
response = client.messages.create(
    model="claude-3-5-sonnet",
    top_k=40,
    messages=[...]
)
```

```
With top_k=3:
"Paris"   0.70  ─┐
"Lyon"    0.15  ─┼─ candidates
"Nice"    0.07  ─┘
"Marseille" 0.04  ← excluded (4th)
...           ← excluded
```

## 4.6 Combining Parameters

These parameters work together:

```python
response = client.messages.create(
    model="claude-3-5-sonnet",
    temperature=0.8,  # Applied first: adjusts distribution
    top_p=0.95,       # Applied second: limits candidates
    top_k=50,         # Can further limit (if supported)
    messages=[...]
)
```

Order of operations:

1. **Temperature**: Adjust probabilities
2. **Top-k**: Keep only top k tokens
3. **Top-p**: Keep tokens until cumulative prob reaches p
4. **Sample**: Pick one token from remaining candidates

## 4.7 Common Configurations

```python
# Configuration presets
SAMPLING_PRESETS = {
    "deterministic": {
        "temperature": 0,
        # top_p and top_k don't matter when temp=0
    },
    "balanced": {
        "temperature": 0.7,
        "top_p": 0.9,
    },
    "creative": {
        "temperature": 1.2,
        "top_p": 0.95,
    },
    "code": {
        "temperature": 0,
    },
    "json": {
        "temperature": 0,
    },
}

def get_sampling_config(task_type: str) -> dict:
    return SAMPLING_PRESETS.get(task_type, SAMPLING_PRESETS["balanced"])
```

## 4.8 When Temperature 0 Still Varies

Even with temperature=0, outputs can vary due to:

1. **Floating point precision**: Tiny differences in computation
2. **Batching effects**: Different batch sizes can affect results
3. **Hardware differences**: GPU vs CPU, different GPUs
4. **Model updates**: Provider may update model weights

```python
# For true determinism, some APIs offer a seed parameter
response = client.chat.completions.create(
    model="gpt-4",
    temperature=0,
    seed=42,  # OpenAI-specific
    messages=[...]
)
```

## 4.9 Debugging Sampling Issues

**Problem: Output too repetitive**

```python
# Increase temperature or top_p
temperature=0.9
top_p=0.95
```

**Problem: Output too random/incoherent**

```python
# Decrease temperature, tighten top_p
temperature=0.5
top_p=0.8
```

**Problem: Code has subtle bugs**

```python
# Use temperature=0 for code
temperature=0
```

**Problem: Same response every time (unwanted)**

```python
# Increase temperature
temperature=0.8
```

## 4.10 Practical Examples

```python
async def generate_with_config(client, prompt: str, task_type: str):
    configs = {
        "extract_data": {"temperature": 0},
        "write_code": {"temperature": 0},
        "summarize": {"temperature": 0.3},
        "chat": {"temperature": 0.7},
        "write_story": {"temperature": 1.0},
        "brainstorm": {"temperature": 1.3},
    }

    config = configs.get(task_type, {"temperature": 0.7})

    return await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        **config,
        messages=[{"role": "user", "content": prompt}]
    )

# Usage
response = await generate_with_config(client, "Extract emails from: ...", "extract_data")
response = await generate_with_config(client, "Write a poem about...", "write_story")
```

## 4.11 Summary

| Parameter   | What It Does                   | Low Value              | High Value       |
| ----------- | ------------------------------ | ---------------------- | ---------------- |
| Temperature | Adjusts probability sharpness  | Deterministic, focused | Random, creative |
| Top-p       | Limits to top probability mass | Fewer choices          | More choices     |
| Top-k       | Limits to top k tokens         | Fewer choices          | More choices     |

**Rules of thumb**:

- Use `temperature=0` for code, JSON, factual extraction
- Use `temperature=0.7-1.0` for conversation
- Use `temperature=1.0-1.5` for creative tasks
- `top_p=0.9-0.95` is a sensible default
- Don't over-tune - defaults work well for most cases
