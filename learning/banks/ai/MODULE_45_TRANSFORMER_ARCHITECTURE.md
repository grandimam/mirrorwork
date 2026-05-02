# Module 45: Transformer Architecture Deep Dive

## 45.1 The Transformer Revolution

```
Before Transformers (RNNs/LSTMs):
- Sequential processing: O(n) time complexity
- Vanishing gradients over long sequences
- Limited parallelization

Transformers (2017 - "Attention Is All You Need"):
- Parallel processing: O(1) time with attention
- Direct connections between all positions
- Massive parallelization on GPUs
```

## 45.2 High-Level Architecture

```
Input Sequence
      ↓
[Token Embeddings] + [Positional Embeddings]
      ↓
┌─────────────────────────────────────────┐
│           Transformer Block (×N)         │
│  ┌─────────────────────────────────────┐ │
│  │    Multi-Head Self-Attention        │ │
│  │    + Residual Connection + LayerNorm│ │
│  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │    Feed-Forward Network (FFN)       │ │
│  │    + Residual Connection + LayerNorm│ │
│  └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
      ↓
[Output Projection]
      ↓
Next Token Probabilities
```

## 45.3 Token Embeddings

```python
import numpy as np

class TokenEmbedding:
    def __init__(self, vocab_size: int, d_model: int):
        self.vocab_size = vocab_size
        self.d_model = d_model
        # Learned embedding matrix: vocab_size × d_model
        self.embedding = np.random.randn(vocab_size, d_model) * 0.02

    def forward(self, token_ids: np.ndarray) -> np.ndarray:
        """
        token_ids: shape (batch_size, seq_len)
        returns: shape (batch_size, seq_len, d_model)
        """
        return self.embedding[token_ids]

# Example
vocab_size = 50000  # Typical vocabulary size
d_model = 768       # Embedding dimension (e.g., GPT-2 small)

embedder = TokenEmbedding(vocab_size, d_model)
tokens = np.array([[101, 2054, 2003, 102]])  # "What is"
embeddings = embedder.forward(tokens)  # Shape: (1, 4, 768)
```

## 45.4 Positional Encoding

```python
class SinusoidalPositionalEncoding:
    """Original transformer positional encoding"""

    def __init__(self, d_model: int, max_seq_len: int = 8192):
        self.d_model = d_model
        self.encoding = self._create_encoding(max_seq_len, d_model)

    def _create_encoding(self, max_len: int, d_model: int) -> np.ndarray:
        position = np.arange(max_len)[:, np.newaxis]  # (max_len, 1)
        div_term = np.exp(np.arange(0, d_model, 2) * (-np.log(10000.0) / d_model))

        encoding = np.zeros((max_len, d_model))
        encoding[:, 0::2] = np.sin(position * div_term)  # Even indices
        encoding[:, 1::2] = np.cos(position * div_term)  # Odd indices

        return encoding

    def forward(self, seq_len: int) -> np.ndarray:
        return self.encoding[:seq_len]


class LearnedPositionalEmbedding:
    """Learned positional embeddings (used in GPT models)"""

    def __init__(self, max_seq_len: int, d_model: int):
        self.position_embedding = np.random.randn(max_seq_len, d_model) * 0.02

    def forward(self, seq_len: int) -> np.ndarray:
        return self.position_embedding[:seq_len]


class RotaryPositionalEmbedding:
    """RoPE - Rotary Position Embedding (used in LLaMA, etc.)

    Key insight: encode position in the rotation of the embedding space
    Allows for extrapolation to longer sequences
    """

    def __init__(self, d_model: int, base: int = 10000):
        self.d_model = d_model
        self.base = base

    def _compute_freqs(self, seq_len: int) -> np.ndarray:
        freqs = 1.0 / (self.base ** (np.arange(0, self.d_model, 2) / self.d_model))
        positions = np.arange(seq_len)
        freqs = np.outer(positions, freqs)  # (seq_len, d_model/2)
        return freqs

    def apply_rotary(self, x: np.ndarray, freqs: np.ndarray) -> np.ndarray:
        # Split into pairs and rotate
        x_reshape = x.reshape(*x.shape[:-1], -1, 2)
        cos_freqs = np.cos(freqs)
        sin_freqs = np.sin(freqs)

        x_rot = np.stack([
            x_reshape[..., 0] * cos_freqs - x_reshape[..., 1] * sin_freqs,
            x_reshape[..., 0] * sin_freqs + x_reshape[..., 1] * cos_freqs
        ], axis=-1)

        return x_rot.reshape(x.shape)
```

## 45.5 Self-Attention Mechanism

```python
def scaled_dot_product_attention(
    query: np.ndarray,    # (batch, heads, seq_len, d_k)
    key: np.ndarray,      # (batch, heads, seq_len, d_k)
    value: np.ndarray,    # (batch, heads, seq_len, d_v)
    mask: np.ndarray = None
) -> tuple[np.ndarray, np.ndarray]:
    """
    Core attention computation:
    Attention(Q, K, V) = softmax(QK^T / √d_k) V
    """
    d_k = query.shape[-1]

    # Compute attention scores: QK^T
    scores = np.matmul(query, key.transpose(0, 1, 3, 2))  # (batch, heads, seq, seq)

    # Scale by √d_k to prevent softmax saturation
    scores = scores / np.sqrt(d_k)

    # Apply mask (for causal/padding)
    if mask is not None:
        scores = np.where(mask == 0, -1e9, scores)

    # Softmax to get attention weights
    attention_weights = softmax(scores, axis=-1)

    # Apply attention to values
    output = np.matmul(attention_weights, value)  # (batch, heads, seq, d_v)

    return output, attention_weights


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    exp_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


class MultiHeadAttention:
    def __init__(self, d_model: int, num_heads: int):
        assert d_model % num_heads == 0

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        # Projection matrices
        self.W_q = np.random.randn(d_model, d_model) * 0.02
        self.W_k = np.random.randn(d_model, d_model) * 0.02
        self.W_v = np.random.randn(d_model, d_model) * 0.02
        self.W_o = np.random.randn(d_model, d_model) * 0.02

    def forward(
        self,
        x: np.ndarray,           # (batch, seq_len, d_model)
        mask: np.ndarray = None
    ) -> np.ndarray:
        batch_size, seq_len, _ = x.shape

        # Linear projections
        Q = x @ self.W_q  # (batch, seq, d_model)
        K = x @ self.W_k
        V = x @ self.W_v

        # Reshape for multi-head: (batch, seq, d_model) -> (batch, heads, seq, d_k)
        Q = Q.reshape(batch_size, seq_len, self.num_heads, self.d_k).transpose(0, 2, 1, 3)
        K = K.reshape(batch_size, seq_len, self.num_heads, self.d_k).transpose(0, 2, 1, 3)
        V = V.reshape(batch_size, seq_len, self.num_heads, self.d_k).transpose(0, 2, 1, 3)

        # Apply attention
        attn_output, _ = scaled_dot_product_attention(Q, K, V, mask)

        # Reshape back: (batch, heads, seq, d_k) -> (batch, seq, d_model)
        attn_output = attn_output.transpose(0, 2, 1, 3).reshape(batch_size, seq_len, self.d_model)

        # Final projection
        output = attn_output @ self.W_o

        return output
```

## 45.6 Causal Masking (Decoder-Only)

```python
def create_causal_mask(seq_len: int) -> np.ndarray:
    """
    Creates lower-triangular mask for autoregressive generation.
    Prevents attending to future tokens.

    Example for seq_len=4:
    [[1, 0, 0, 0],
     [1, 1, 0, 0],
     [1, 1, 1, 0],
     [1, 1, 1, 1]]
    """
    mask = np.tril(np.ones((seq_len, seq_len)))
    return mask


class CausalSelfAttention(MultiHeadAttention):
    def forward(self, x: np.ndarray) -> np.ndarray:
        seq_len = x.shape[1]
        causal_mask = create_causal_mask(seq_len)
        return super().forward(x, mask=causal_mask)


# Visualization of attention pattern
def visualize_attention(attention_weights: np.ndarray, tokens: list[str]):
    """
    attention_weights: (seq_len, seq_len)
    tokens: list of token strings
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 10))
    im = ax.imshow(attention_weights, cmap='Blues')

    ax.set_xticks(range(len(tokens)))
    ax.set_yticks(range(len(tokens)))
    ax.set_xticklabels(tokens, rotation=45)
    ax.set_yticklabels(tokens)

    plt.colorbar(im)
    plt.title("Attention Weights")
    plt.show()
```

## 45.7 Feed-Forward Network

```python
class FeedForwardNetwork:
    """
    Position-wise Feed-Forward Network
    FFN(x) = max(0, xW1 + b1)W2 + b2

    Typically: d_ff = 4 * d_model
    """

    def __init__(self, d_model: int, d_ff: int):
        self.W1 = np.random.randn(d_model, d_ff) * 0.02
        self.b1 = np.zeros(d_ff)
        self.W2 = np.random.randn(d_ff, d_model) * 0.02
        self.b2 = np.zeros(d_model)

    def forward(self, x: np.ndarray) -> np.ndarray:
        # First linear + ReLU
        hidden = np.maximum(0, x @ self.W1 + self.b1)
        # Second linear
        output = hidden @ self.W2 + self.b2
        return output


class GatedFeedForward:
    """
    Gated FFN (used in LLaMA, PaLM)
    Uses SwiGLU activation: Swish(xW_gate) ⊙ (xW_up)
    """

    def __init__(self, d_model: int, d_ff: int):
        self.W_gate = np.random.randn(d_model, d_ff) * 0.02
        self.W_up = np.random.randn(d_model, d_ff) * 0.02
        self.W_down = np.random.randn(d_ff, d_model) * 0.02

    def swish(self, x: np.ndarray) -> np.ndarray:
        return x * (1 / (1 + np.exp(-x)))  # x * sigmoid(x)

    def forward(self, x: np.ndarray) -> np.ndarray:
        gate = self.swish(x @ self.W_gate)
        up = x @ self.W_up
        return (gate * up) @ self.W_down
```

## 45.8 Layer Normalization

```python
class LayerNorm:
    """
    Normalizes across the feature dimension
    LayerNorm(x) = γ * (x - μ) / √(σ² + ε) + β
    """

    def __init__(self, d_model: int, eps: float = 1e-6):
        self.gamma = np.ones(d_model)   # Learned scale
        self.beta = np.zeros(d_model)   # Learned shift
        self.eps = eps

    def forward(self, x: np.ndarray) -> np.ndarray:
        mean = np.mean(x, axis=-1, keepdims=True)
        var = np.var(x, axis=-1, keepdims=True)

        normalized = (x - mean) / np.sqrt(var + self.eps)
        return self.gamma * normalized + self.beta


class RMSNorm:
    """
    Root Mean Square Layer Normalization (used in LLaMA)
    Simpler than LayerNorm - no mean centering
    RMSNorm(x) = x / √(mean(x²) + ε) * γ
    """

    def __init__(self, d_model: int, eps: float = 1e-6):
        self.gamma = np.ones(d_model)
        self.eps = eps

    def forward(self, x: np.ndarray) -> np.ndarray:
        rms = np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True) + self.eps)
        return (x / rms) * self.gamma
```

## 45.9 Complete Transformer Block

```python
class TransformerBlock:
    """
    Pre-LayerNorm Transformer Block (modern default):

    x = x + Attention(LayerNorm(x))
    x = x + FFN(LayerNorm(x))
    """

    def __init__(self, d_model: int, num_heads: int, d_ff: int):
        self.attention = CausalSelfAttention(d_model, num_heads)
        self.ffn = GatedFeedForward(d_model, d_ff)
        self.norm1 = RMSNorm(d_model)
        self.norm2 = RMSNorm(d_model)

    def forward(self, x: np.ndarray) -> np.ndarray:
        # Self-attention with residual
        x = x + self.attention.forward(self.norm1.forward(x))

        # FFN with residual
        x = x + self.ffn.forward(self.norm2.forward(x))

        return x


class Transformer:
    """Complete decoder-only transformer (GPT-style)"""

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        max_seq_len: int
    ):
        self.token_embedding = TokenEmbedding(vocab_size, d_model)
        self.position_embedding = LearnedPositionalEmbedding(max_seq_len, d_model)

        self.layers = [
            TransformerBlock(d_model, num_heads, d_ff)
            for _ in range(num_layers)
        ]

        self.final_norm = RMSNorm(d_model)
        self.output_projection = np.random.randn(d_model, vocab_size) * 0.02

    def forward(self, token_ids: np.ndarray) -> np.ndarray:
        """
        token_ids: (batch, seq_len)
        returns: logits (batch, seq_len, vocab_size)
        """
        seq_len = token_ids.shape[1]

        # Embeddings
        x = self.token_embedding.forward(token_ids)
        x = x + self.position_embedding.forward(seq_len)

        # Transformer layers
        for layer in self.layers:
            x = layer.forward(x)

        # Final norm and projection
        x = self.final_norm.forward(x)
        logits = x @ self.output_projection

        return logits
```

## 45.10 KV Cache for Efficient Generation

```python
class KVCache:
    """
    Cache key/value projections for efficient autoregressive generation.

    Without cache: O(n²) per token (recompute all attention)
    With cache: O(n) per token (only compute new token's attention)
    """

    def __init__(self, num_layers: int, batch_size: int, num_heads: int, d_k: int):
        self.num_layers = num_layers
        # Initialize empty caches for each layer
        self.k_cache = [None] * num_layers
        self.v_cache = [None] * num_layers

    def update(self, layer_idx: int, new_k: np.ndarray, new_v: np.ndarray):
        """Append new key/value to cache"""
        if self.k_cache[layer_idx] is None:
            self.k_cache[layer_idx] = new_k
            self.v_cache[layer_idx] = new_v
        else:
            self.k_cache[layer_idx] = np.concatenate([self.k_cache[layer_idx], new_k], axis=2)
            self.v_cache[layer_idx] = np.concatenate([self.v_cache[layer_idx], new_v], axis=2)

    def get(self, layer_idx: int) -> tuple[np.ndarray, np.ndarray]:
        return self.k_cache[layer_idx], self.v_cache[layer_idx]


class CachedAttention(MultiHeadAttention):
    def forward_with_cache(
        self,
        x: np.ndarray,
        cache: KVCache,
        layer_idx: int
    ) -> np.ndarray:
        batch_size = x.shape[0]

        # Project current token
        Q = x @ self.W_q
        K = x @ self.W_k
        V = x @ self.W_v

        # Reshape for multi-head
        Q = Q.reshape(batch_size, 1, self.num_heads, self.d_k).transpose(0, 2, 1, 3)
        K = K.reshape(batch_size, 1, self.num_heads, self.d_k).transpose(0, 2, 1, 3)
        V = V.reshape(batch_size, 1, self.num_heads, self.d_k).transpose(0, 2, 1, 3)

        # Update cache
        cache.update(layer_idx, K, V)

        # Get full K, V from cache
        K_full, V_full = cache.get(layer_idx)

        # Attention with full context
        attn_output, _ = scaled_dot_product_attention(Q, K_full, V_full)

        # Reshape and project
        attn_output = attn_output.transpose(0, 2, 1, 3).reshape(batch_size, 1, self.d_model)
        return attn_output @ self.W_o
```

## 45.11 Generation and Sampling

```python
class TextGenerator:
    def __init__(self, model: Transformer, tokenizer):
        self.model = model
        self.tokenizer = tokenizer

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_k: int = 50,
        top_p: float = 0.9
    ) -> str:
        # Tokenize prompt
        token_ids = self.tokenizer.encode(prompt)
        token_ids = np.array([token_ids])

        # Initialize KV cache
        cache = KVCache(...)

        # Generate tokens
        for _ in range(max_new_tokens):
            # Forward pass (only last token if using cache)
            logits = self.model.forward(token_ids)
            next_token_logits = logits[0, -1, :]  # Last position

            # Apply temperature
            next_token_logits = next_token_logits / temperature

            # Apply top-k filtering
            if top_k > 0:
                indices_to_remove = np.argsort(next_token_logits)[:-top_k]
                next_token_logits[indices_to_remove] = -np.inf

            # Apply top-p (nucleus) filtering
            if top_p < 1.0:
                sorted_indices = np.argsort(next_token_logits)[::-1]
                sorted_logits = next_token_logits[sorted_indices]
                cumulative_probs = np.cumsum(softmax(sorted_logits))

                # Remove tokens with cumulative prob > top_p
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[1:] = sorted_indices_to_remove[:-1].copy()
                sorted_indices_to_remove[0] = False

                indices_to_remove = sorted_indices[sorted_indices_to_remove]
                next_token_logits[indices_to_remove] = -np.inf

            # Sample from distribution
            probs = softmax(next_token_logits)
            next_token = np.random.choice(len(probs), p=probs)

            # Append to sequence
            token_ids = np.concatenate([token_ids, [[next_token]]], axis=1)

            # Check for end of sequence
            if next_token == self.tokenizer.eos_token_id:
                break

        return self.tokenizer.decode(token_ids[0])
```

## 45.12 Model Configurations

```python
# Common model configurations

GPT2_SMALL = {
    "vocab_size": 50257,
    "d_model": 768,
    "num_heads": 12,
    "num_layers": 12,
    "d_ff": 3072,
    "max_seq_len": 1024,
    "parameters": "124M"
}

GPT2_LARGE = {
    "vocab_size": 50257,
    "d_model": 1280,
    "num_heads": 20,
    "num_layers": 36,
    "d_ff": 5120,
    "max_seq_len": 1024,
    "parameters": "774M"
}

LLAMA_7B = {
    "vocab_size": 32000,
    "d_model": 4096,
    "num_heads": 32,
    "num_layers": 32,
    "d_ff": 11008,  # 2.7x multiplier with SwiGLU
    "max_seq_len": 4096,
    "parameters": "7B"
}

LLAMA_70B = {
    "vocab_size": 32000,
    "d_model": 8192,
    "num_heads": 64,
    "num_kv_heads": 8,  # Grouped-Query Attention
    "num_layers": 80,
    "d_ff": 28672,
    "max_seq_len": 8192,
    "parameters": "70B"
}

# Parameter count estimation
def estimate_parameters(config: dict) -> int:
    d = config["d_model"]
    L = config["num_layers"]
    V = config["vocab_size"]
    d_ff = config["d_ff"]

    # Embeddings: V × d
    embeddings = V * d

    # Per layer:
    # - Attention: 4 × d² (Q, K, V, O projections)
    # - FFN: 2 × d × d_ff (or 3× for gated)
    # - LayerNorm: 2 × d
    per_layer = 4 * d * d + 2 * d * d_ff + 2 * d

    total = embeddings + L * per_layer + V * d  # + output projection
    return total
```

## 45.13 Attention Variants

```python
class GroupedQueryAttention:
    """
    GQA: Groups of query heads share same K/V heads
    Reduces KV cache size while maintaining quality
    Used in LLaMA 2 70B, Mistral
    """

    def __init__(self, d_model: int, num_q_heads: int, num_kv_heads: int):
        self.num_q_heads = num_q_heads
        self.num_kv_heads = num_kv_heads
        self.heads_per_group = num_q_heads // num_kv_heads
        self.d_k = d_model // num_q_heads

        # Q has full heads, K/V have fewer
        self.W_q = np.random.randn(d_model, num_q_heads * self.d_k) * 0.02
        self.W_k = np.random.randn(d_model, num_kv_heads * self.d_k) * 0.02
        self.W_v = np.random.randn(d_model, num_kv_heads * self.d_k) * 0.02
        self.W_o = np.random.randn(num_q_heads * self.d_k, d_model) * 0.02

    def forward(self, x: np.ndarray) -> np.ndarray:
        batch, seq_len, _ = x.shape

        Q = (x @ self.W_q).reshape(batch, seq_len, self.num_q_heads, self.d_k)
        K = (x @ self.W_k).reshape(batch, seq_len, self.num_kv_heads, self.d_k)
        V = (x @ self.W_v).reshape(batch, seq_len, self.num_kv_heads, self.d_k)

        # Repeat K/V for each query group
        K = np.repeat(K, self.heads_per_group, axis=2)
        V = np.repeat(V, self.heads_per_group, axis=2)

        # Standard attention from here
        # ...


class SlidingWindowAttention:
    """
    Attention limited to local window
    Reduces complexity from O(n²) to O(n × window_size)
    Used in Mistral, Longformer
    """

    def __init__(self, d_model: int, num_heads: int, window_size: int):
        self.window_size = window_size
        self.base_attention = MultiHeadAttention(d_model, num_heads)

    def create_sliding_mask(self, seq_len: int) -> np.ndarray:
        mask = np.zeros((seq_len, seq_len))
        for i in range(seq_len):
            start = max(0, i - self.window_size)
            mask[i, start:i+1] = 1
        return mask


class FlashAttention:
    """
    Memory-efficient attention using tiling

    Key insight: Compute attention in blocks to:
    1. Reduce memory from O(n²) to O(n)
    2. Maximize GPU memory bandwidth utilization

    This is a conceptual implementation - real FlashAttention
    requires custom CUDA kernels
    """

    def __init__(self, block_size: int = 256):
        self.block_size = block_size

    def forward(self, Q: np.ndarray, K: np.ndarray, V: np.ndarray) -> np.ndarray:
        seq_len = Q.shape[1]
        d_k = Q.shape[-1]
        output = np.zeros_like(Q)

        # Process in blocks
        for i in range(0, seq_len, self.block_size):
            i_end = min(i + self.block_size, seq_len)
            Q_block = Q[:, i:i_end]

            # Accumulate attention over K/V blocks
            block_output = np.zeros_like(Q_block)
            normalizer = np.zeros((Q_block.shape[0], Q_block.shape[1], 1))
            max_score = np.full((Q_block.shape[0], Q_block.shape[1], 1), -np.inf)

            for j in range(0, seq_len, self.block_size):
                j_end = min(j + self.block_size, seq_len)
                K_block = K[:, j:j_end]
                V_block = V[:, j:j_end]

                # Compute block attention scores
                scores = Q_block @ K_block.transpose(0, 2, 1) / np.sqrt(d_k)

                # Online softmax update
                new_max = np.maximum(max_score, scores.max(axis=-1, keepdims=True))
                exp_scores = np.exp(scores - new_max)

                # Update running sums
                scale = np.exp(max_score - new_max)
                block_output = scale * block_output + exp_scores @ V_block
                normalizer = scale * normalizer + exp_scores.sum(axis=-1, keepdims=True)
                max_score = new_max

            output[:, i:i_end] = block_output / normalizer

        return output
```

## 45.14 Summary

| Component | Purpose | Complexity |
|-----------|---------|------------|
| Token Embedding | Convert tokens to vectors | O(1) lookup |
| Positional Encoding | Encode sequence order | O(n) |
| Self-Attention | Compute token relationships | O(n²) |
| FFN | Transform representations | O(n) |
| LayerNorm | Stabilize training | O(n) |
| KV Cache | Efficient generation | Reduces O(n²) → O(n) |

**Key architectural choices:**
- Pre-norm vs post-norm (pre-norm is now standard)
- RoPE vs learned positions (RoPE better for extrapolation)
- GQA vs MHA (GQA reduces memory at scale)
- SwiGLU vs ReLU (SwiGLU slightly better quality)

**Scaling insights:**
- More layers → better reasoning
- Wider layers → more knowledge capacity
- Longer context → more KV cache memory
- Attention is the bottleneck for long sequences
