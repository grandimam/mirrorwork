# Chapter 2: Tokens and Tokenization

## 2.1 What is a Token?

A token is the basic unit of text that LLMs process. Tokens are not characters, not words - they're chunks determined by the tokenizer.

```
Text:    "Hello, world!"
Tokens:  ["Hello", ",", " world", "!"]  # 4 tokens

Text:    "tokenization"
Tokens:  ["token", "ization"]  # 2 tokens

Text:    "Hello"  (in some languages)
Tokens:  ["Hel", "lo"]  # depends on tokenizer
```

**Rule of thumb**: 1 token ≈ 4 characters in English, or about 0.75 words.

## 2.2 Why Tokenization Matters

Tokens directly impact:

| Aspect | Impact |
|--------|--------|
| Cost | You pay per token (input + output) |
| Context limits | Models have max token limits |
| Performance | More tokens = slower response |
| Behavior | How text is split affects model understanding |

```python
# Cost calculation
input_tokens = 1000
output_tokens = 500
cost_per_1k_input = 0.003   # example pricing
cost_per_1k_output = 0.015

total_cost = (input_tokens * cost_per_1k_input / 1000) + \
             (output_tokens * cost_per_1k_output / 1000)
```

## 2.3 How Tokenizers Work

Most modern LLMs use **Byte Pair Encoding (BPE)** or variants:

1. Start with character-level vocabulary
2. Find most frequent character pairs
3. Merge them into new tokens
4. Repeat until vocabulary size reached

```
Training corpus: "low lower lowest"

Step 1: Characters: ['l', 'o', 'w', 'e', 'r', 's', 't', ' ']
Step 2: Most frequent pair: 'l' + 'o' → merge to 'lo'
Step 3: Most frequent pair: 'lo' + 'w' → merge to 'low'
Step 4: Continue...

Result: Common words become single tokens
```

## 2.4 Counting Tokens

```python
# Using tiktoken (OpenAI's tokenizer)
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4")
text = "Hello, how are you?"
tokens = enc.encode(text)
print(f"Token count: {len(tokens)}")  # 6 tokens
print(f"Tokens: {tokens}")  # [9906, 11, 1268, 527, 499, 30]
print(f"Decoded: {[enc.decode([t]) for t in tokens]}")
# ['Hello', ',', ' how', ' are', ' you', '?']

# For Anthropic models (approximate)
# Use their API or estimate: len(text) / 4
```

```python
# Quick estimation function
def estimate_tokens(text: str) -> int:
    """Rough estimate: 1 token ≈ 4 chars"""
    return len(text) // 4 + 1
```

## 2.5 Token Boundaries Affect Behavior

The same text tokenized differently can produce different results:

```python
# "GPT-4" might tokenize as:
# ["G", "PT", "-", "4"] or ["GPT", "-4"] or ["GPT-4"]

# This matters for:
# 1. Exact string matching
# 2. Code generation (variable names)
# 3. Unusual words or formats
```

**Common issues**:

```python
# Numbers are often split
"123456789" → ["123", "456", "789"]  # Model sees as separate

# Leading spaces matter
"hello" vs " hello"  # Different tokens!

# Case sensitivity
"Hello" vs "hello"  # Different tokens
```

## 2.6 Special Tokens

Models use special tokens for structure:

```
<|endoftext|>     - End of sequence
<|im_start|>      - Start of message (some models)
<|im_end|>        - End of message
[INST]            - Instruction marker (Llama)
<|system|>        - System message marker
```

These are typically handled by the API - you don't insert them manually.

## 2.7 Token Limits in Practice

```python
# Managing context within limits
def truncate_to_token_limit(messages, max_tokens, reserved_for_response):
    """Keep messages within token budget"""
    available = max_tokens - reserved_for_response

    total_tokens = 0
    kept_messages = []

    # Keep system message always
    system_msg = messages[0] if messages[0]["role"] == "system" else None
    if system_msg:
        total_tokens += estimate_tokens(system_msg["content"])
        kept_messages.append(system_msg)
        messages = messages[1:]

    # Add messages from most recent, working backwards
    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg["content"])
        if total_tokens + msg_tokens <= available:
            kept_messages.insert(1 if system_msg else 0, msg)
            total_tokens += msg_tokens
        else:
            break

    return kept_messages
```

## 2.8 Tokenization and Code

Code has unique tokenization patterns:

```python
# Python code tokenization
code = "def hello_world():"
# Might become: ["def", " hello", "_", "world", "():", ]

# This is why models sometimes struggle with:
# - Unusual variable names
# - Very long identifiers
# - Non-English code/comments
```

```python
# Indentation matters and costs tokens
code_compact = "def f(x):return x*2"      # ~8 tokens
code_formatted = """
def f(x):
    return x * 2
"""                                         # ~12 tokens
```

## 2.9 Optimizing Token Usage

**Reduce input tokens**:

```python
# Verbose (more tokens, more cost)
prompt = """
I would like you to please help me write a Python function
that takes two numbers as input and returns their sum.
Please make sure the function is well documented.
"""

# Concise (fewer tokens, same result)
prompt = """
Write a Python function:
- Input: two numbers
- Output: their sum
- Include docstring
"""
```

**Reduce output tokens**:

```python
# Request concise output
prompt = "List 3 benefits of exercise. Be brief, one sentence each."

# Use structured output
prompt = "Return only JSON: {benefits: [str, str, str]}"
```

## 2.10 Summary

- Tokens are the atomic units LLMs process (not characters or words)
- ~4 characters = 1 token in English
- You pay for input tokens + output tokens
- Token limits constrain your context window
- Different tokenizers produce different results
- Optimize prompts to reduce token usage

**Key developer actions**:
- Count tokens before sending large prompts
- Truncate conversation history to fit limits
- Keep prompts concise to reduce costs
- Be aware of tokenization quirks with code/numbers
