# Chapter 1: How LLMs Work (High-Level)

## 1.1 What is a Large Language Model?

A Large Language Model (LLM) is a neural network trained to predict the next token in a sequence. That's it. Everything else - conversation, reasoning, code generation - emerges from this simple objective.

```
Input:  "The capital of France is"
Output: "Paris" (with high probability)
```

The model learns patterns from massive amounts of text (books, websites, code) and uses those patterns to generate plausible continuations.

## 1.2 The Core Mechanism: Next Token Prediction

LLMs work by:

1. **Taking input text** (your prompt)
2. **Converting to tokens** (numerical representations)
3. **Processing through neural network layers**
4. **Outputting probability distribution** over all possible next tokens
5. **Selecting one token** (based on sampling strategy)
6. **Repeating** until done

```
Prompt: "Write a function to add two numbers"

Step 1: Model sees prompt
Step 2: Predicts "def" as likely next token
Step 3: Predicts "add" as next token
Step 4: Predicts "(" as next token
... continues until complete
```

Each token generation is independent - the model has no memory between calls. It only sees what's in the current context.

## 1.3 Transformer Architecture (Developer Mental Model)

You don't need to understand the math, but knowing the structure helps:

```
┌─────────────────────────────────────┐
│           Input Tokens              │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│         Embedding Layer             │
│   (tokens → vector representations) │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│      Transformer Blocks (×N)        │
│  ┌───────────────────────────────┐  │
│  │    Self-Attention Layer       │  │
│  │ (tokens attend to each other) │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │    Feed-Forward Layer         │  │
│  │   (process each position)     │  │
│  └───────────────────────────────┘  │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│         Output Probabilities        │
│   (probability for each token)      │
└─────────────────────────────────────┘
```

**Key insight**: Self-attention allows every token to "look at" every other token. This is how the model understands context - "it" in a sentence can refer back to the subject mentioned earlier.

## 1.4 What the Model Actually Learns

During training, the model learns:

1. **Syntax and grammar** - how languages are structured
2. **Facts and knowledge** - information from training data
3. **Patterns** - code conventions, writing styles, formats
4. **Reasoning patterns** - step-by-step problem solving (from examples in training data)

```python
# The model learned that this pattern:
# "Q: What is 2+2? A: 4"
# means questions should be followed by answers

# So when you write:
prompt = "Q: What is the capital of Japan? A:"
# It continues with: "Tokyo"
```

## 1.5 What the Model Does NOT Have

Understanding these limitations is crucial:

| Does NOT Have | Implication |
|---------------|-------------|
| Memory | Each API call is independent; no recall of previous conversations unless you include them |
| Real-time knowledge | Training data has a cutoff date |
| Internet access | Cannot browse unless you provide tools |
| Computation | Cannot actually calculate; predicts what answer "looks right" |
| Truth verification | Can confidently state incorrect information |

```python
# Common mistake: assuming memory
response1 = client.chat("My name is Alice")  # "Nice to meet you, Alice!"
response2 = client.chat("What's my name?")   # "I don't know your name"

# Correct: include context
response = client.chat([
    {"role": "user", "content": "My name is Alice"},
    {"role": "assistant", "content": "Nice to meet you, Alice!"},
    {"role": "user", "content": "What's my name?"}
])  # "Your name is Alice"
```

## 1.6 Why This Matters for Developers

Understanding next-token prediction explains:

**Why prompts matter**: The model continues patterns. A well-structured prompt sets up the pattern you want.

```python
# Poor: vague pattern
prompt = "Help me with code"

# Better: clear pattern to continue
prompt = """Task: Write a Python function
Input: Two integers
Output: Their sum
Function:"""
```

**Why examples work**: Few-shot examples establish the pattern.

```python
prompt = """
Convert to JSON:
Name: John, Age: 30 → {"name": "John", "age": 30}
Name: Jane, Age: 25 → {"name": "Jane", "age": 25}
Name: Bob, Age: 40 →"""
# Model continues the pattern: {"name": "Bob", "age": 40}
```

**Why hallucinations happen**: The model predicts plausible text, not verified facts.

```python
# Model will confidently generate plausible-looking but potentially wrong:
# - Citations that don't exist
# - API methods that aren't real
# - Historical events that didn't happen
```

## 1.7 The Generation Process

When you call an LLM API:

```python
import anthropic

client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=100,
    messages=[{"role": "user", "content": "Hello"}]
)
```

What happens:

1. Your prompt is tokenized
2. Tokens pass through the model
3. Model outputs probability distribution
4. A token is sampled (influenced by temperature)
5. That token is appended to context
6. Steps 2-5 repeat until stop condition
7. Response returned to you

**Stop conditions**:
- Max tokens reached
- End-of-sequence token generated
- Stop sequence encountered

## 1.8 Model Sizes and Capabilities

Larger models generally = better capabilities:

| Size | Parameters | Typical Use |
|------|------------|-------------|
| Small | 7-13B | Simple tasks, fast, cheap |
| Medium | 30-70B | Good balance of cost/capability |
| Large | 100B+ | Complex reasoning, best quality |

```python
# Choose based on task complexity
simple_task = "Extract the email from this text"  # Small model fine
complex_task = "Analyze this codebase and suggest architecture improvements"  # Large model needed
```

## 1.9 Summary

- LLMs predict the next token based on patterns learned from training
- No memory between calls - you must provide context
- They learn patterns, not truth - verify important outputs
- Prompt engineering works because you're setting up patterns to continue
- Larger models capture more complex patterns

Understanding this foundation helps you:
- Write better prompts (set up clear patterns)
- Debug failures (model didn't have the right pattern/context)
- Choose appropriate models (match capability to task)
- Set realistic expectations (know the limitations)
