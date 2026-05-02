# Module 13: Agent Tools

## 13.1 Tool Design Principles

```python
# Good tool: Single purpose, clear inputs/outputs
{
    "name": "get_current_time",
    "description": "Get the current time in a specific timezone",
    "input_schema": {
        "type": "object",
        "properties": {
            "timezone": {"type": "string", "default": "UTC"}
        }
    }
}

# Bad tool: Too broad, unclear
{
    "name": "do_stuff",
    "description": "Does various things"
}
```

## 13.2 Common Tool Categories

```python
# File System Tools
FILE_TOOLS = [
    {
        "name": "read_file",
        "description": "Read contents of a file at the given path",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_directory",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."}
            }
        }
    }
]

# HTTP Tools
HTTP_TOOLS = [
    {
        "name": "http_request",
        "description": "Make an HTTP request",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "url": {"type": "string"},
                "headers": {"type": "object"},
                "body": {"type": "string"}
            },
            "required": ["method", "url"]
        }
    }
]

# Database Tools
DB_TOOLS = [
    {
        "name": "query_database",
        "description": "Execute a read-only SQL query",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    }
]
```

## 13.3 Tool Implementation

```python
class ToolRegistry:
    def __init__(self):
        self.tools = {}
        self.schemas = []

    def register(self, name: str, func: callable, schema: dict):
        self.tools[name] = func
        self.schemas.append({
            "name": name,
            "description": schema.get("description", ""),
            "input_schema": schema
        })

    def execute(self, name: str, inputs: dict) -> dict:
        if name not in self.tools:
            return {"error": f"Unknown tool: {name}"}
        try:
            result = self.tools[name](**inputs)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def get_schemas(self) -> list:
        return self.schemas

# Register tools
registry = ToolRegistry()

registry.register(
    "calculator",
    func=lambda expression: eval(expression),  # Safe math only!
    schema={
        "description": "Evaluate a mathematical expression",
        "type": "object",
        "properties": {
            "expression": {"type": "string"}
        },
        "required": ["expression"]
    }
)
```

## 13.4 Async Tool Execution

```python
class AsyncToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute(self, name: str, inputs: dict) -> dict:
        func = self.registry.tools.get(name)
        if not func:
            return {"error": f"Unknown tool: {name}"}

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(**inputs)
            else:
                result = await asyncio.to_thread(func, **inputs)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    async def execute_parallel(self, tool_calls: list) -> list:
        tasks = [
            self.execute(call["name"], call["inputs"])
            for call in tool_calls
        ]
        return await asyncio.gather(*tasks)
```

## 13.5 Tool from Function Decorator

```python
def tool(description: str):
    """Decorator to convert function to tool"""
    def decorator(func):
        hints = get_type_hints(func)
        sig = inspect.signature(func)

        properties = {}
        required = []

        for name, param in sig.parameters.items():
            prop = {"type": "string"}

            if name in hints:
                if hints[name] == int:
                    prop["type"] = "integer"
                elif hints[name] == float:
                    prop["type"] = "number"
                elif hints[name] == bool:
                    prop["type"] = "boolean"

            if param.default == inspect.Parameter.empty:
                required.append(name)

            properties[name] = prop

        func._tool_schema = {
            "name": func.__name__,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
        return func
    return decorator

# Usage
@tool("Search the web for information")
def search_web(query: str) -> dict:
    return {"results": [...]}

@tool("Calculate mathematical expression")
def calculate(expression: str) -> float:
    return eval(expression)
```

## 13.6 Tool Composition

```python
class ComposedTool:
    """Combine multiple tools into a workflow"""

    def __init__(self, name: str, description: str, steps: list):
        self.name = name
        self.description = description
        self.steps = steps

    async def execute(self, inputs: dict, executor: AsyncToolExecutor) -> dict:
        context = inputs.copy()

        for step in self.steps:
            tool_name = step["tool"]
            # Map inputs from context
            tool_inputs = {
                k: context.get(v, v)
                for k, v in step.get("inputs", {}).items()
            }

            result = await executor.execute(tool_name, tool_inputs)

            if "error" in result:
                return result

            # Store result in context
            if "output_key" in step:
                context[step["output_key"]] = result["result"]

        return {"result": context}

# Example: Search and summarize
search_and_summarize = ComposedTool(
    name="search_and_summarize",
    description="Search for info and summarize results",
    steps=[
        {"tool": "search_web", "inputs": {"query": "query"}, "output_key": "search_results"},
        {"tool": "summarize", "inputs": {"text": "search_results"}, "output_key": "summary"}
    ]
)
```

## 13.7 Tool Safety

```python
class SafeToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.blocked_patterns = [
            r"rm\s+-rf",
            r"sudo",
            r"DROP\s+TABLE",
        ]

    def is_safe(self, name: str, inputs: dict) -> tuple[bool, str]:
        # Check input patterns
        input_str = json.dumps(inputs)
        for pattern in self.blocked_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                return False, f"Blocked pattern detected: {pattern}"

        # Tool-specific checks
        if name == "write_file":
            path = inputs.get("path", "")
            if path.startswith("/etc") or path.startswith("/sys"):
                return False, "Writing to system directories not allowed"

        return True, ""

    async def execute(self, name: str, inputs: dict) -> dict:
        safe, reason = self.is_safe(name, inputs)
        if not safe:
            return {"error": f"Safety check failed: {reason}"}

        return await self.registry.execute(name, inputs)
```

## 13.8 Summary

| Aspect | Guidance |
|--------|----------|
| Naming | Clear, verb-based (get_, create_, search_) |
| Description | What it does, when to use it |
| Schema | Required vs optional params clear |
| Errors | Return structured error info |
| Safety | Validate inputs, block dangerous ops |

**Best practices:**
- One tool = one purpose
- Clear, detailed descriptions
- Validate all inputs
- Return structured results
- Log all tool executions
