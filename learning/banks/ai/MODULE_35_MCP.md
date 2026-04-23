# Module 35: Model Context Protocol (MCP)

## 35.1 What is MCP?

```
MCP = Standard protocol for LLM ↔ External Systems

Before MCP:
- Every app builds custom integrations
- No standard for tools, resources, prompts
- Hard to share and reuse

With MCP:
- Standard protocol for connections
- Reusable servers and clients
- Ecosystem of integrations
```

## 35.2 MCP Architecture

```
┌─────────────┐     MCP Protocol     ┌─────────────┐
│   Client    │◄───────────────────►│   Server    │
│  (Claude,   │                      │ (Database,  │
│   App)      │                      │  Files,     │
└─────────────┘                      │  APIs)      │
                                     └─────────────┘

MCP provides:
- Tools: Functions the LLM can call
- Resources: Data the LLM can read
- Prompts: Reusable prompt templates
```

## 35.3 MCP Server Example

```python
from mcp.server import Server
from mcp.types import Tool, TextContent

# Create server
server = Server("my-server")

# Define a tool
@server.tool()
async def get_weather(location: str) -> str:
    """Get current weather for a location"""
    # Fetch weather data
    weather = await fetch_weather(location)
    return f"Weather in {location}: {weather['temp']}°C, {weather['condition']}"

# Define a resource
@server.resource("config://settings")
async def get_settings() -> str:
    """Application settings"""
    return json.dumps({"theme": "dark", "language": "en"})

# Run server
if __name__ == "__main__":
    server.run()
```

## 35.4 MCP Client Usage

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def use_mcp_server():
    # Connect to MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["my_server.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")

            # Call a tool
            result = await session.call_tool(
                "get_weather",
                arguments={"location": "Tokyo"}
            )
            print(result.content[0].text)
```

## 35.5 Database MCP Server

```python
from mcp.server import Server
import sqlite3

server = Server("sqlite-server")

@server.tool()
async def query_database(sql: str) -> str:
    """Execute a read-only SQL query"""
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries allowed"

    conn = sqlite3.connect("database.db")
    cursor = conn.execute(sql)
    results = cursor.fetchall()
    columns = [d[0] for d in cursor.description]
    conn.close()

    return json.dumps({"columns": columns, "rows": results})

@server.resource("schema://tables")
async def get_schema() -> str:
    """Database schema"""
    conn = sqlite3.connect("database.db")
    cursor = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table'"
    )
    tables = cursor.fetchall()
    conn.close()

    return json.dumps([{"name": t[0], "sql": t[1]} for t in tables])
```

## 35.6 File System MCP Server

```python
from mcp.server import Server
from pathlib import Path

server = Server("filesystem-server")

ALLOWED_PATHS = [Path("/data"), Path("/documents")]

def is_allowed(path: Path) -> bool:
    return any(path.is_relative_to(allowed) for allowed in ALLOWED_PATHS)

@server.tool()
async def read_file(path: str) -> str:
    """Read a file's contents"""
    p = Path(path).resolve()
    if not is_allowed(p):
        return f"Error: Access denied to {path}"
    return p.read_text()

@server.tool()
async def list_directory(path: str) -> str:
    """List files in a directory"""
    p = Path(path).resolve()
    if not is_allowed(p):
        return f"Error: Access denied to {path}"

    files = [
        {"name": f.name, "is_dir": f.is_dir(), "size": f.stat().st_size}
        for f in p.iterdir()
    ]
    return json.dumps(files)

@server.tool()
async def search_files(pattern: str, path: str = "/data") -> str:
    """Search for files matching pattern"""
    p = Path(path).resolve()
    if not is_allowed(p):
        return f"Error: Access denied"

    matches = list(p.glob(f"**/{pattern}"))[:100]
    return json.dumps([str(m) for m in matches])
```

## 35.7 Using MCP with Claude

```python
import anthropic
from mcp import ClientSession

async def claude_with_mcp(task: str, mcp_session: ClientSession):
    # Get tools from MCP server
    mcp_tools = await mcp_session.list_tools()

    # Convert to Anthropic tool format
    tools = [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        }
        for tool in mcp_tools.tools
    ]

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": task}]

    while True:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return extract_text(response)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # Call MCP server tool
                    result = await mcp_session.call_tool(
                        block.name,
                        arguments=block.input
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.content[0].text
                    })

            messages.append({"role": "user", "content": tool_results})
```

## 35.8 Popular MCP Servers

```python
# Available MCP servers:

MCP_SERVERS = {
    "filesystem": "File read/write operations",
    "postgres": "PostgreSQL database access",
    "sqlite": "SQLite database access",
    "github": "GitHub API integration",
    "slack": "Slack messaging",
    "playwright": "Browser automation",
    "puppeteer": "Browser automation",
    "memory": "Persistent memory/notes",
    "fetch": "HTTP requests",
    "google-drive": "Google Drive access",
    "google-maps": "Google Maps API",
}

# Configure in Claude Desktop settings.json
{
    "mcpServers": {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]
        },
        "postgres": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres"],
            "env": {"DATABASE_URL": "postgresql://..."}
        }
    }
}
```

## 35.9 Building Custom MCP Server

```python
from mcp.server import Server
from mcp.types import Resource, Prompt

server = Server("custom-server")

# Tool with complex schema
@server.tool()
async def create_task(
    title: str,
    description: str = "",
    priority: str = "medium",
    due_date: str = None
) -> str:
    """Create a new task in the task management system"""
    task = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
        "created_at": datetime.now().isoformat()
    }
    # Save task
    return json.dumps({"success": True, "task": task})

# Resource with URI template
@server.resource("task://{task_id}")
async def get_task(task_id: str) -> str:
    """Get a specific task by ID"""
    task = await load_task(task_id)
    return json.dumps(task)

# Reusable prompt template
@server.prompt("summarize-tasks")
async def summarize_prompt() -> str:
    """Prompt for summarizing pending tasks"""
    return """Please summarize all pending tasks, grouped by priority.
Include due dates and highlight any overdue items."""
```

## 35.10 Summary

| Concept | Description |
|---------|-------------|
| Server | Exposes tools, resources, prompts |
| Client | Connects to servers, calls tools |
| Tool | Function the LLM can invoke |
| Resource | Data the LLM can read |
| Prompt | Reusable prompt template |

**Best practices:**
- Use existing MCP servers when available
- Validate inputs in tool handlers
- Implement proper access controls
- Return structured JSON responses
- Document tools clearly
- Handle errors gracefully
