# Chapter 1: API Authentication and Setup

## 1.1 API Keys

API keys are secret tokens that authenticate your requests:

```python
# Never hardcode API keys
# BAD
client = anthropic.Anthropic(api_key="sk-ant-xxxxx")

# GOOD - environment variable
import os
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# GOOD - auto-loads from ANTHROPIC_API_KEY env var
client = anthropic.Anthropic()
```

## 1.2 Environment Variables

```bash
# .env file (never commit this)
ANTHROPIC_API_KEY=sk-ant-xxxxx
OPENAI_API_KEY=sk-xxxxx

# Load in Python
from dotenv import load_dotenv
load_dotenv()

# Or export in shell
export ANTHROPIC_API_KEY=sk-ant-xxxxx
```

```python
# Verify key is set
import os

def get_api_key(provider: str) -> str:
    key_names = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    key_name = key_names.get(provider)
    key = os.environ.get(key_name)

    if not key:
        raise ValueError(f"Missing {key_name} environment variable")
    return key
```

## 1.3 Client Initialization

### Anthropic

```python
import anthropic

# Basic
client = anthropic.Anthropic()

# With explicit key
client = anthropic.Anthropic(api_key="sk-ant-xxxxx")

# Async client
client = anthropic.AsyncAnthropic()
```

### OpenAI

```python
from openai import OpenAI, AsyncOpenAI

# Basic
client = OpenAI()

# Async
client = AsyncOpenAI()
```

### Multiple Providers

```python
class LLMClients:
    def __init__(self):
        self.anthropic = anthropic.Anthropic()
        self.openai = OpenAI()

    def get(self, provider: str):
        return getattr(self, provider)

clients = LLMClients()
```

## 1.4 API Base URLs

For proxies, custom endpoints, or local models:

```python
# Custom base URL
client = anthropic.Anthropic(
    base_url="https://my-proxy.example.com/v1"
)

# OpenAI-compatible endpoints (e.g., local models)
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="not-needed"  # Local models may not need auth
)
```

## 1.5 Timeouts and Retries

```python
import httpx

# Anthropic with custom timeout
client = anthropic.Anthropic(
    timeout=httpx.Timeout(60.0, connect=5.0)
)

# OpenAI with custom timeout
client = OpenAI(
    timeout=60.0,
    max_retries=3,
)
```

## 1.6 Security Best Practices

```python
# 1. Never commit keys
# Add to .gitignore:
# .env
# .env.local
# *.key

# 2. Use different keys for dev/prod
DEV_KEY = os.environ.get("ANTHROPIC_API_KEY_DEV")
PROD_KEY = os.environ.get("ANTHROPIC_API_KEY_PROD")

# 3. Rotate keys periodically
# 4. Use minimum required permissions
# 5. Monitor key usage for anomalies
```

## 1.7 Testing Without Real API Calls

```python
# Mock client for testing
class MockAnthropicClient:
    def __init__(self):
        self.messages = MockMessages()

class MockMessages:
    def create(self, **kwargs):
        return MockResponse(
            content=[MockContentBlock(text="Mock response")],
            stop_reason="end_turn",
            usage=MockUsage(input_tokens=10, output_tokens=5)
        )

# Use in tests
def test_my_function():
    client = MockAnthropicClient()
    result = my_function(client)
    assert result == expected
```

## 1.8 Verifying Setup

```python
def verify_api_setup(provider: str = "anthropic") -> bool:
    """Quick test that API is configured correctly"""
    try:
        if provider == "anthropic":
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
        elif provider == "openai":
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}]
            )
        print(f"✓ {provider} API configured correctly")
        return True
    except Exception as e:
        print(f"✗ {provider} API error: {e}")
        return False

if __name__ == "__main__":
    verify_api_setup("anthropic")
```

## 1.9 Summary

- Store API keys in environment variables, never in code
- Use `.env` files for local development (add to `.gitignore`)
- Initialize clients once and reuse
- Configure appropriate timeouts
- Use different keys for dev/staging/prod
- Test your setup before building features
