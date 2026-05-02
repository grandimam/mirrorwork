# Module 24: Local LLMs

## 24.1 Why Run Locally?

```
Benefits:
- Privacy: data never leaves your machine
- Cost: no API fees after hardware
- Latency: no network round-trip
- Offline: works without internet
- Customization: full control

Tradeoffs:
- Hardware requirements
- Smaller models = less capable
- Setup complexity
- No continuous improvements
```

## 24.2 Ollama Basics

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2
ollama pull mistral
ollama pull codellama

# Run interactively
ollama run llama3.2

# List models
ollama list
```

```python
# Python client
import ollama

response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response["message"]["content"])

# Streaming
for chunk in ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True
):
    print(chunk["message"]["content"], end="")
```

## 24.3 OpenAI-Compatible API

```python
# Ollama serves OpenAI-compatible API
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"  # Required but unused
)

response = client.chat.completions.create(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)

# Works with existing OpenAI code!
```

## 24.4 Model Selection

```python
# Model recommendations by use case
MODELS = {
    "general": {
        "small": "llama3.2:1b",     # ~1GB, basic tasks
        "medium": "llama3.2:3b",    # ~2GB, good balance
        "large": "llama3.1:8b",     # ~5GB, high quality
    },
    "code": {
        "small": "codellama:7b",
        "large": "codellama:34b",
    },
    "embedding": {
        "default": "nomic-embed-text",
    }
}

def select_model(task: str, memory_gb: int) -> str:
    """Select best model for available memory"""
    if memory_gb < 4:
        return MODELS["general"]["small"]
    elif memory_gb < 8:
        return MODELS["general"]["medium"]
    else:
        return MODELS["general"]["large"]
```

## 24.5 Local Embeddings

```python
# Generate embeddings locally
embeddings = ollama.embeddings(
    model="nomic-embed-text",
    prompt="Hello world"
)
vector = embeddings["embedding"]  # List of floats

# Batch embeddings
def embed_batch(texts: list[str]) -> list[list[float]]:
    return [
        ollama.embeddings(model="nomic-embed-text", prompt=t)["embedding"]
        for t in texts
    ]
```

## 24.6 LlamaCpp for Control

```python
from llama_cpp import Llama

# Load model with specific parameters
llm = Llama(
    model_path="./models/llama-3.2-3b.gguf",
    n_ctx=4096,        # Context window
    n_gpu_layers=35,   # GPU acceleration
    n_threads=8        # CPU threads
)

# Generate
output = llm(
    "Q: What is Python? A:",
    max_tokens=100,
    temperature=0.7,
    stop=["Q:"]
)
print(output["choices"][0]["text"])

# Chat format
output = llm.create_chat_completion(
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## 24.7 Hybrid Architecture

```python
class HybridLLM:
    """Use local for simple, cloud for complex"""

    def __init__(self):
        self.local = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        self.cloud = anthropic.Anthropic()

    async def run(self, prompt: str, complexity: str = "auto") -> str:
        if complexity == "auto":
            complexity = self._assess_complexity(prompt)

        if complexity == "simple":
            return await self._local(prompt)
        else:
            return await self._cloud(prompt)

    def _assess_complexity(self, prompt: str) -> str:
        # Simple heuristics
        if len(prompt) < 100:
            return "simple"
        if any(w in prompt.lower() for w in ["analyze", "complex", "detailed"]):
            return "complex"
        return "simple"

    async def _local(self, prompt: str) -> str:
        response = self.local.chat.completions.create(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    async def _cloud(self, prompt: str) -> str:
        response = await self.cloud.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

## 24.8 Summary

| Tool | Best For |
|------|----------|
| Ollama | Easy setup, good defaults |
| LlamaCpp | Fine control, optimization |
| vLLM | Production serving |
| Text Generation Inference | Docker deployment |

**Hardware recommendations:**
- 8GB RAM: 3B models
- 16GB RAM: 7-8B models
- 32GB RAM: 13B models
- GPU: Much faster inference

**Best practices:**
- Start with Ollama for simplicity
- Use quantized models (Q4, Q5) for efficiency
- Match model size to hardware
- Consider hybrid local + cloud
- Test thoroughly before production
