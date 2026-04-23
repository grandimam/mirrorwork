# Chapter 60: Logging Internals

## 60.1 Logging Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              Logging Flow                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Logger.info("message")                                          │
│      │                                                          │
│      ▼                                                          │
│  LogRecord created                                               │
│      │                                                          │
│      ▼                                                          │
│  Filters applied                                                 │
│      │                                                          │
│      ▼                                                          │
│  Handlers (StreamHandler, FileHandler, etc.)                    │
│      │                                                          │
│      ▼                                                          │
│  Formatters                                                      │
│      │                                                          │
│      ▼                                                          │
│  Output (console, file, network)                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 60.2 Logger Configuration

```python
import logging

# Basic configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# Get logger
logger = logging.getLogger(__name__)
logger.info("Application started")
```

## 60.3 Custom Handlers

```python
import logging

class DatabaseHandler(logging.Handler):
    def __init__(self, connection):
        super().__init__()
        self.conn = connection

    def emit(self, record):
        msg = self.format(record)
        self.conn.execute(
            "INSERT INTO logs (level, message) VALUES (?, ?)",
            (record.levelname, msg)
        )
```

## Summary

- Loggers create LogRecords
- Handlers route to outputs
- Formatters control message format
- Filters control what gets logged

---

[Next: C API Overview →](../part-14-capi/chapter-61-capi-overview.md)
