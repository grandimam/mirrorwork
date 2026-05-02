# Chapter 56: Custom Exceptions

## 56.1 Creating Custom Exceptions

```python
class MyError(Exception):
    """Base exception for my application."""
    pass

class ValidationError(MyError):
    """Raised when validation fails."""
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")

class ConfigError(MyError):
    """Raised for configuration issues."""
    def __init__(self, key, reason):
        self.key = key
        self.reason = reason
        super().__init__(f"Config error for '{key}': {reason}")
```

## 56.2 Exception Best Practices

```python
# 1. Create hierarchy for your application
class AppError(Exception):
    """Base for all application errors."""
    pass

class DatabaseError(AppError):
    pass

class ConnectionError(DatabaseError):
    pass

class QueryError(DatabaseError):
    pass

# 2. Include useful context
class APIError(Exception):
    def __init__(self, status_code, message, response=None):
        self.status_code = status_code
        self.response = response
        super().__init__(f"API Error {status_code}: {message}")

# 3. Support exception chaining
try:
    external_call()
except ExternalError as e:
    raise AppError("External service failed") from e
```

## 56.3 Exception Groups (Python 3.11+)

```python
# Raise multiple exceptions together
exceptions = [ValueError("error 1"), TypeError("error 2")]
raise ExceptionGroup("multiple errors", exceptions)

# Catch specific types from group
try:
    risky_operation()
except* ValueError as eg:
    handle_value_errors(eg.exceptions)
except* TypeError as eg:
    handle_type_errors(eg.exceptions)
```

## Summary

- Create exception hierarchies for organization
- Include contextual information in exceptions
- Use exception chaining for debugging
- ExceptionGroup handles multiple simultaneous errors

---

[Next: Debugging Tools →](../part-13-debugging/chapter-57-debugging-tools.md)
