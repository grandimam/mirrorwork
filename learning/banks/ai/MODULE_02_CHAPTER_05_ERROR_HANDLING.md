# Chapter 5: Error Handling Patterns

## 5.1 Common Error Types

```python
import anthropic

# Anthropic exceptions
errors = {
    anthropic.APIConnectionError: "Network issue",
    anthropic.RateLimitError: "Too many requests",
    anthropic.AuthenticationError: "Invalid API key",
    anthropic.BadRequestError: "Invalid request parameters",
    anthropic.NotFoundError: "Model not found",
    anthropic.APIStatusError: "Server error (5xx)",
}
```

## 5.2 Basic Error Handling

```python
import anthropic

def safe_call(prompt: str) -> tuple[str | None, str | None]:
    """Returns (response, error)"""
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text, None

    except anthropic.AuthenticationError:
        return None, "Invalid API key"
    except anthropic.RateLimitError:
        return None, "Rate limited - try again later"
    except anthropic.BadRequestError as e:
        return None, f"Bad request: {e.message}"
    except anthropic.APIConnectionError:
        return None, "Connection failed - check network"
    except anthropic.APIStatusError as e:
        return None, f"API error: {e.status_code}"
    except Exception as e:
        return None, f"Unexpected error: {e}"
```

## 5.3 Async Error Handling

```python
async def safe_call_async(prompt: str):
    try:
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"success": True, "data": response.content[0].text}

    except anthropic.RateLimitError as e:
        return {"success": False, "error": "rate_limited", "retry_after": 60}
    except anthropic.APIConnectionError:
        return {"success": False, "error": "connection_failed", "retry": True}
    except Exception as e:
        return {"success": False, "error": "unknown", "message": str(e)}
```

## 5.4 Error Categories

```python
from enum import Enum

class ErrorCategory(Enum):
    RETRYABLE = "retryable"       # Retry with backoff
    CLIENT_ERROR = "client"       # Fix request and retry
    AUTH_ERROR = "auth"           # Fix credentials
    FATAL = "fatal"               # Don't retry

def categorize_error(error: Exception) -> ErrorCategory:
    if isinstance(error, anthropic.RateLimitError):
        return ErrorCategory.RETRYABLE
    if isinstance(error, anthropic.APIConnectionError):
        return ErrorCategory.RETRYABLE
    if isinstance(error, anthropic.AuthenticationError):
        return ErrorCategory.AUTH_ERROR
    if isinstance(error, anthropic.BadRequestError):
        return ErrorCategory.CLIENT_ERROR
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code >= 500:
            return ErrorCategory.RETRYABLE
        return ErrorCategory.CLIENT_ERROR
    return ErrorCategory.FATAL
```

## 5.5 Context-Aware Error Handling

```python
class LLMError(Exception):
    def __init__(self, message: str, category: ErrorCategory, original: Exception = None):
        super().__init__(message)
        self.category = category
        self.original = original
        self.retryable = category == ErrorCategory.RETRYABLE

class LLMClient:
    async def call(self, prompt: str) -> str:
        try:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text

        except anthropic.RateLimitError as e:
            raise LLMError(
                "Service busy, please retry",
                ErrorCategory.RETRYABLE,
                e
            )
        except anthropic.BadRequestError as e:
            raise LLMError(
                f"Invalid request: {e.message}",
                ErrorCategory.CLIENT_ERROR,
                e
            )
```

## 5.6 Validation Errors

```python
class ValidationError(Exception):
    pass

def validate_request(prompt: str, max_tokens: int):
    if not prompt or not prompt.strip():
        raise ValidationError("Prompt cannot be empty")

    if len(prompt) > 1_000_000:
        raise ValidationError("Prompt too long")

    if max_tokens < 1:
        raise ValidationError("max_tokens must be positive")

    if max_tokens > 100_000:
        raise ValidationError("max_tokens too high")

async def safe_generate(prompt: str, max_tokens: int = 1024):
    try:
        validate_request(prompt, max_tokens)
        return await client.messages.create(...)
    except ValidationError as e:
        return {"error": "validation", "message": str(e)}
    except anthropic.BadRequestError as e:
        return {"error": "api_validation", "message": str(e)}
```

## 5.7 Logging Errors

```python
import logging

logger = logging.getLogger(__name__)

async def call_with_logging(prompt: str):
    request_id = generate_request_id()

    try:
        logger.info(f"[{request_id}] Starting request, prompt_length={len(prompt)}")

        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        logger.info(f"[{request_id}] Success, tokens={response.usage}")
        return response

    except anthropic.RateLimitError as e:
        logger.warning(f"[{request_id}] Rate limited")
        raise
    except anthropic.APIConnectionError as e:
        logger.error(f"[{request_id}] Connection failed: {e}")
        raise
    except Exception as e:
        logger.exception(f"[{request_id}] Unexpected error")
        raise
```

## 5.8 User-Friendly Error Messages

```python
ERROR_MESSAGES = {
    "rate_limited": "Our AI service is busy. Please try again in a moment.",
    "connection_failed": "Unable to connect to AI service. Check your internet.",
    "invalid_key": "Configuration error. Please contact support.",
    "content_filtered": "Your request couldn't be processed. Try rephrasing.",
    "context_too_long": "Your conversation is too long. Start a new chat.",
    "unknown": "Something went wrong. Please try again.",
}

def get_user_message(error: Exception) -> str:
    if isinstance(error, anthropic.RateLimitError):
        return ERROR_MESSAGES["rate_limited"]
    if isinstance(error, anthropic.APIConnectionError):
        return ERROR_MESSAGES["connection_failed"]
    if isinstance(error, anthropic.AuthenticationError):
        return ERROR_MESSAGES["invalid_key"]
    if isinstance(error, anthropic.BadRequestError):
        if "context" in str(error).lower():
            return ERROR_MESSAGES["context_too_long"]
    return ERROR_MESSAGES["unknown"]
```

## 5.9 Error Recovery Strategies

```python
async def call_with_recovery(prompt: str, fallback_model: str = None):
    try:
        return await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.BadRequestError as e:
        if "context length" in str(e).lower():
            # Truncate and retry
            truncated = prompt[:10000]
            return await client.messages.create(
                model="claude-3-5-sonnet",
                max_tokens=1024,
                messages=[{"role": "user", "content": truncated}]
            )
        raise
    except anthropic.RateLimitError:
        if fallback_model:
            return await client.messages.create(
                model=fallback_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
        raise
```

## 5.10 Summary

| Error Type | Action |
|------------|--------|
| Rate limit | Retry with backoff |
| Connection | Retry with backoff |
| Auth | Fix credentials, don't retry |
| Bad request | Fix request, then retry |
| Server (5xx) | Retry with backoff |

**Best practices**:
- Categorize errors by recoverability
- Log all errors with context
- Show user-friendly messages
- Have fallback strategies
- Never expose internal error details to users
