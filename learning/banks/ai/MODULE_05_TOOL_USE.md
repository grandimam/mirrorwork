# Module 5: Function Calling / Tool Use

## 5.1 What is Tool Use?

Tool use allows LLMs to invoke external functions to get information or take actions.

```
User: "What's the weather in Tokyo?"

Without tools:
  Model: "I don't have real-time weather data."

With tools:
  Model: [calls get_weather("Tokyo")]
  Tool returns: {"temp": 22, "condition": "sunny"}
  Model: "It's currently 22°C and sunny in Tokyo."
```

## 5.2 Tool Definition

```python
# Anthropic tool definition
tools = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name or coordinates"
                },
                "units": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature units"
                }
            },
            "required": ["location"]
        }
    }
]
```

## 5.3 Basic Tool Call Flow

```python
import anthropic

client = anthropic.Anthropic()

# Step 1: Send message with tools
response = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "What's the weather in Tokyo?"}]
)

# Step 2: Check if model wants to use a tool
if response.stop_reason == "tool_use":
    # Find tool use block
    tool_use = next(
        block for block in response.content
        if block.type == "tool_use"
    )

    print(f"Tool: {tool_use.name}")
    print(f"Input: {tool_use.input}")

    # Step 3: Execute the tool
    result = execute_tool(tool_use.name, tool_use.input)

    # Step 4: Send result back
    final_response = client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        tools=tools,
        messages=[
            {"role": "user", "content": "What's the weather in Tokyo?"},
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result)
                }]
            }
        ]
    )
```

## 5.4 Tool Executor

```python
class ToolExecutor:
    def __init__(self):
        self.tools: dict[str, callable] = {}

    def register(self, name: str, func: callable, schema: dict):
        self.tools[name] = {"func": func, "schema": schema}

    def get_tool_definitions(self) -> list:
        return [
            {
                "name": name,
                "description": tool["schema"].get("description", ""),
                "input_schema": tool["schema"]
            }
            for name, tool in self.tools.items()
        ]

    def execute(self, name: str, inputs: dict) -> dict:
        if name not in self.tools:
            return {"error": f"Unknown tool: {name}"}
        try:
            result = self.tools[name]["func"](**inputs)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

# Usage
executor = ToolExecutor()

executor.register(
    "get_weather",
    func=lambda location, units="celsius": {"temp": 22, "condition": "sunny"},
    schema={
        "description": "Get weather for a location",
        "type": "object",
        "properties": {
            "location": {"type": "string"},
            "units": {"type": "string", "enum": ["celsius", "fahrenheit"]}
        },
        "required": ["location"]
    }
)
```

## 5.5 Tool Call Loop

```python
async def run_with_tools(
    client,
    messages: list,
    tools: list,
    executor: ToolExecutor,
    max_iterations: int = 10
) -> str:
    """Run conversation with tool use until completion"""

    for _ in range(max_iterations):
        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1024,
            tools=tools,
            messages=messages
        )

        # Check if done
        if response.stop_reason == "end_turn":
            # Extract text response
            text_blocks = [b for b in response.content if b.type == "text"]
            return text_blocks[0].text if text_blocks else ""

        # Handle tool use
        if response.stop_reason == "tool_use":
            # Add assistant's response
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = executor.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # Add tool results
            messages.append({"role": "user", "content": tool_results})

    raise Exception("Max iterations reached")
```

## 5.6 Parallel Tool Calls

Model can request multiple tools at once:

```python
# Model response might contain multiple tool_use blocks
for block in response.content:
    if block.type == "tool_use":
        # Execute in parallel
        tasks.append(execute_tool_async(block.name, block.input))

results = await asyncio.gather(*tasks)

# Send all results back together
tool_results = [
    {
        "type": "tool_result",
        "tool_use_id": blocks[i].id,
        "content": json.dumps(results[i])
    }
    for i in range(len(results))
]
```

## 5.7 Tool Descriptions Matter

Good descriptions help the model use tools correctly:

```python
# Bad description
{
    "name": "search",
    "description": "Search things",
}

# Good description
{
    "name": "search_documents",
    "description": """
Search internal documents by keyword or semantic query.
Use this when the user asks about company policies, procedures, or documentation.
Returns top 5 most relevant documents with snippets.
NOT for web search - use web_search for external information.
""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query - can be keywords or natural language question"
            },
            "department": {
                "type": "string",
                "enum": ["engineering", "hr", "finance", "all"],
                "description": "Filter by department, use 'all' for company-wide search"
            }
        },
        "required": ["query"]
    }
}
```

## 5.8 Error Handling

```python
def execute_tool_safely(name: str, inputs: dict) -> dict:
    """Execute tool with proper error handling"""
    try:
        # Validate inputs
        if name not in available_tools:
            return {
                "error": f"Tool '{name}' not found",
                "available_tools": list(available_tools.keys())
            }

        # Execute
        result = available_tools[name](**inputs)
        return {"success": True, "result": result}

    except TypeError as e:
        return {
            "error": f"Invalid arguments: {e}",
            "hint": "Check required parameters"
        }
    except Exception as e:
        return {
            "error": f"Tool execution failed: {e}",
            "type": type(e).__name__
        }

# Model will see error and can retry or explain
```

## 5.9 Common Tools

```python
# File operations
file_tools = [
    {
        "name": "read_file",
        "description": "Read contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
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
    }
]

# HTTP requests
http_tools = [
    {
        "name": "http_get",
        "description": "Make HTTP GET request",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "headers": {"type": "object"}
            },
            "required": ["url"]
        }
    }
]

# Database
db_tools = [
    {
        "name": "query_database",
        "description": "Execute read-only SQL query",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL SELECT query"}
            },
            "required": ["query"]
        }
    }
]
```

## 5.10 Tool Choice Control

```python
# Let model decide
response = client.messages.create(
    tool_choice={"type": "auto"},  # Default
    ...
)

# Force tool use
response = client.messages.create(
    tool_choice={"type": "any"},  # Must use a tool
    ...
)

# Force specific tool
response = client.messages.create(
    tool_choice={"type": "tool", "name": "get_weather"},
    ...
)
```

## 5.11 Building a Tool from Function

```python
import inspect
from typing import get_type_hints

def function_to_tool(func: callable) -> dict:
    """Convert Python function to tool definition"""
    hints = get_type_hints(func)
    sig = inspect.signature(func)
    doc = func.__doc__ or ""

    properties = {}
    required = []

    for name, param in sig.parameters.items():
        prop = {"type": "string"}  # Default

        # Infer type from hints
        if name in hints:
            hint = hints[name]
            if hint == int:
                prop["type"] = "integer"
            elif hint == float:
                prop["type"] = "number"
            elif hint == bool:
                prop["type"] = "boolean"

        # Check if required
        if param.default == inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default

        properties[name] = prop

    return {
        "name": func.__name__,
        "description": doc.strip(),
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }

# Usage
def calculate_tip(bill_amount: float, tip_percentage: float = 18.0) -> float:
    """Calculate tip amount for a bill"""
    return bill_amount * (tip_percentage / 100)

tool_def = function_to_tool(calculate_tip)
```

## 5.12 Summary

| Concept | Purpose |
|---------|---------|
| Tool definition | Describe what tool does |
| Input schema | Define expected parameters |
| Tool loop | Handle multi-turn tool use |
| Error handling | Graceful failure recovery |
| Parallel calls | Efficiency |

**Best practices:**
- Write clear, detailed tool descriptions
- Include examples in descriptions
- Handle errors gracefully
- Validate inputs before execution
- Use parallel execution when possible
- Limit tool iterations to prevent infinite loops
