# Module 10: Building Your First Agent

## 10.1 Agent Components

A complete agent needs:
1. LLM client
2. Tools
3. System prompt
4. Execution loop
5. State management

## 10.2 Define Tools

```python
# Tools are functions the agent can call
def search_web(query: str) -> dict:
    """Search the web for information"""
    # Actual implementation would call search API
    return {"results": [f"Result for: {query}"]}

def read_file(path: str) -> dict:
    """Read contents of a file"""
    try:
        with open(path) as f:
            return {"content": f.read()}
    except Exception as e:
        return {"error": str(e)}

def write_file(path: str, content: str) -> dict:
    """Write content to a file"""
    try:
        with open(path, 'w') as f:
            f.write(content)
        return {"success": True}
    except Exception as e:
        return {"error": str(e)}

# Tool definitions for LLM
TOOLS = [
    {
        "name": "search_web",
        "description": "Search the web for current information. Use for facts, news, or data you don't know.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file. Use to examine existing files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Use to create or update files.",
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
```

## 10.3 Tool Executor

```python
class ToolExecutor:
    def __init__(self):
        self.tools = {
            "search_web": search_web,
            "read_file": read_file,
            "write_file": write_file,
        }

    def execute(self, tool_name: str, inputs: dict) -> dict:
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return self.tools[tool_name](**inputs)
        except Exception as e:
            return {"error": f"Tool execution failed: {e}"}
```

## 10.4 Agent System Prompt

```python
AGENT_SYSTEM_PROMPT = """
You are a helpful agent that can use tools to accomplish tasks.

When given a task:
1. Think about what information or actions you need
2. Use available tools to gather information or take action
3. Continue until the task is complete
4. Provide a clear final answer

Be thorough but efficient. Don't use tools unnecessarily.
If you make an error, acknowledge it and try a different approach.
"""
```

## 10.5 The Complete Agent

```python
import anthropic
import json

class Agent:
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.executor = ToolExecutor()

    async def run(self, task: str) -> str:
        messages = [{"role": "user", "content": task}]

        for iteration in range(10):  # Max 10 iterations
            print(f"\n--- Iteration {iteration + 1} ---")

            # Call LLM
            response = self.client.messages.create(
                model="claude-3-5-sonnet",
                max_tokens=4096,
                system=AGENT_SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            print(f"Stop reason: {response.stop_reason}")

            # Task complete
            if response.stop_reason == "end_turn":
                return self._get_text_response(response)

            # Handle tool calls
            if response.stop_reason == "tool_use":
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                tool_results = self._execute_tools(response)
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

        return "Agent reached maximum iterations"

    def _execute_tools(self, response) -> list:
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"Calling tool: {block.name}({block.input})")

                result = self.executor.execute(block.name, block.input)
                print(f"Result: {result}")

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result)
                })
        return results

    def _get_text_response(self, response) -> str:
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

# Run the agent
async def main():
    agent = Agent()
    result = await agent.run(
        "Create a file called hello.txt with the content 'Hello World'"
    )
    print(f"\nFinal result: {result}")
```

## 10.6 Testing the Agent

```python
import pytest

@pytest.mark.asyncio
async def test_agent_file_creation():
    agent = Agent()
    result = await agent.run("Create a file test.txt with 'test content'")

    # Verify file was created
    assert os.path.exists("test.txt")
    with open("test.txt") as f:
        assert f.read() == "test content"

    # Cleanup
    os.remove("test.txt")

@pytest.mark.asyncio
async def test_agent_search():
    agent = Agent()
    result = await agent.run("What is the capital of France?")

    assert "Paris" in result
```

## 10.7 Adding Logging

```python
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent")

class LoggingAgent(Agent):
    async def run(self, task: str) -> str:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        logger.info(f"[{run_id}] Starting task: {task}")

        try:
            result = await super().run(task)
            logger.info(f"[{run_id}] Completed successfully")
            return result
        except Exception as e:
            logger.error(f"[{run_id}] Failed: {e}")
            raise

    def _execute_tools(self, response) -> list:
        for block in response.content:
            if block.type == "tool_use":
                logger.info(f"Tool call: {block.name}")
                logger.debug(f"Inputs: {block.input}")

        results = super()._execute_tools(response)

        for r in results:
            logger.debug(f"Tool result: {r['content'][:100]}...")

        return results
```

## 10.8 Error Recovery

```python
class RobustAgent(Agent):
    def _execute_tools(self, response) -> list:
        results = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    result = self.executor.execute(block.name, block.input)
                except Exception as e:
                    result = {
                        "error": str(e),
                        "suggestion": "Try a different approach"
                    }

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                    "is_error": "error" in result
                })
        return results
```

## 10.9 Streaming Output

```python
class StreamingAgent(Agent):
    async def run_streaming(self, task: str):
        messages = [{"role": "user", "content": task}]

        for iteration in range(10):
            async with self.client.messages.stream(
                model="claude-3-5-sonnet",
                max_tokens=4096,
                system=AGENT_SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            ) as stream:
                collected_content = []

                async for event in stream:
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            print(event.delta.text, end="", flush=True)

                response = await stream.get_final_message()

            if response.stop_reason == "end_turn":
                return self._get_text_response(response)

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = self._execute_tools(response)
                messages.append({"role": "user", "content": tool_results})
```

## 10.10 Summary

Building an agent requires:
1. **Tools**: Define what actions the agent can take
2. **Executor**: Run tools safely
3. **System prompt**: Guide agent behavior
4. **Loop**: Iterate until task complete
5. **Error handling**: Recover from failures

```python
# Minimal agent structure
async def minimal_agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]

    while True:
        response = await llm.create(messages=messages, tools=TOOLS)

        if response.stop_reason == "end_turn":
            return get_text(response)

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": execute_tools(response)})
```

**Next steps:**
- Add more tools
- Improve error handling
- Add memory
- Implement planning
