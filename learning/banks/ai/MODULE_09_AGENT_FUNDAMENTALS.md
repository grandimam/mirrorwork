# Module 9: Agent Fundamentals

## 9.1 What is an Agent?

An agent is an LLM that can take actions to accomplish goals autonomously.

```
Assistant: Responds to questions
Agent: Takes actions to accomplish tasks

User: "What's the weather?"
Assistant: "I don't have access to weather data."
Agent: [calls weather API] → "It's 72°F and sunny in NYC."
```

## 9.2 Agent vs Assistant

| Aspect | Assistant | Agent |
|--------|-----------|-------|
| Scope | Single response | Multi-step task |
| Actions | None | Tools, APIs, code |
| Memory | Conversation only | Task state + memory |
| Autonomy | Reactive | Proactive |
| Control | User-driven | Goal-driven |

## 9.3 The Agent Loop

```
┌─────────────────────────────────────────┐
│              Agent Loop                  │
├─────────────────────────────────────────┤
│  1. Perceive (get input/state)          │
│          ↓                              │
│  2. Think (reason about what to do)     │
│          ↓                              │
│  3. Act (execute action/tool)           │
│          ↓                              │
│  4. Observe (get result)                │
│          ↓                              │
│  5. Update state                        │
│          ↓                              │
│  6. Check if done → if not, loop        │
└─────────────────────────────────────────┘
```

```python
async def agent_loop(
    task: str,
    tools: list,
    max_iterations: int = 10
) -> str:
    messages = [{"role": "user", "content": task}]

    for i in range(max_iterations):
        # Think
        response = await llm.create(
            messages=messages,
            tools=tools
        )

        # Check if done
        if response.stop_reason == "end_turn":
            return extract_final_answer(response)

        # Act
        if response.stop_reason == "tool_use":
            tool_results = await execute_tools(response)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    return "Max iterations reached"
```

## 9.4 ReAct Pattern

ReAct = Reasoning + Acting. The model explicitly states its reasoning before acting.

```
Thought: I need to find the current weather in Tokyo.
Action: get_weather(location="Tokyo")
Observation: {"temp": 22, "condition": "cloudy"}
Thought: Now I have the weather data. I can answer the user.
Action: respond("It's 22°C and cloudy in Tokyo.")
```

```python
REACT_PROMPT = """
You are an agent that solves tasks by reasoning and taking actions.

Available tools:
{tools_description}

Use this format:
Thought: [your reasoning about what to do next]
Action: [tool_name(param="value")]
Observation: [tool result - will be filled in]
... (repeat as needed)
Thought: [final reasoning]
Answer: [final response to user]

Task: {task}
"""
```

## 9.5 Agent State

```python
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

class AgentStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"  # For human input

@dataclass
class AgentState:
    task: str
    status: AgentStatus = AgentStatus.RUNNING
    messages: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    iterations: int = 0
    result: Any = None
    error: str = None
    metadata: dict = field(default_factory=dict)

    def add_thought(self, thought: str):
        self.messages.append({"type": "thought", "content": thought})

    def add_action(self, tool: str, inputs: dict, result: Any):
        self.tool_calls.append({
            "tool": tool,
            "inputs": inputs,
            "result": result,
            "iteration": self.iterations
        })
```

## 9.6 Stop Conditions

When should an agent stop?

```python
class StopCondition:
    def __init__(
        self,
        max_iterations: int = 10,
        max_tokens: int = 50000,
        max_time_seconds: float = 300,
        max_tool_calls: int = 50
    ):
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.max_time = max_time_seconds
        self.max_tool_calls = max_tool_calls
        self.start_time = None

    def start(self):
        self.start_time = time.time()

    def should_stop(self, state: AgentState) -> tuple[bool, str]:
        if state.iterations >= self.max_iterations:
            return True, "max_iterations"

        if len(state.tool_calls) >= self.max_tool_calls:
            return True, "max_tool_calls"

        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed >= self.max_time:
                return True, "timeout"

        return False, ""
```

## 9.7 Simple Agent Implementation

```python
class SimpleAgent:
    def __init__(self, client, tools: list, system_prompt: str = None):
        self.client = client
        self.tools = tools
        self.system_prompt = system_prompt or "You are a helpful agent."
        self.tool_executor = ToolExecutor(tools)

    async def run(self, task: str, max_iterations: int = 10) -> AgentState:
        state = AgentState(task=task)
        state.messages = [{"role": "user", "content": task}]

        for _ in range(max_iterations):
            state.iterations += 1

            # Get LLM response
            response = await self.client.messages.create(
                model="claude-3-5-sonnet",
                system=self.system_prompt,
                max_tokens=4096,
                tools=self.tools,
                messages=state.messages
            )

            # Check if task complete
            if response.stop_reason == "end_turn":
                state.status = AgentStatus.COMPLETED
                state.result = self._extract_text(response)
                return state

            # Handle tool use
            if response.stop_reason == "tool_use":
                state.messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self.tool_executor.execute(
                            block.name,
                            block.input
                        )
                        state.add_action(block.name, block.input, result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })

                state.messages.append({
                    "role": "user",
                    "content": tool_results
                })

        state.status = AgentStatus.FAILED
        state.error = "Max iterations reached"
        return state

    def _extract_text(self, response) -> str:
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
```

## 9.8 Agent Evaluation

```python
@dataclass
class AgentEvalResult:
    task: str
    success: bool
    iterations: int
    tool_calls: int
    total_tokens: int
    time_seconds: float
    error: str = None

async def evaluate_agent(
    agent: SimpleAgent,
    test_cases: list[dict]
) -> list[AgentEvalResult]:
    results = []

    for case in test_cases:
        start = time.time()

        try:
            state = await agent.run(case["task"])
            success = case["validator"](state.result)
        except Exception as e:
            state = AgentState(task=case["task"], status=AgentStatus.FAILED)
            success = False

        results.append(AgentEvalResult(
            task=case["task"],
            success=success,
            iterations=state.iterations,
            tool_calls=len(state.tool_calls),
            total_tokens=0,  # Track from responses
            time_seconds=time.time() - start,
            error=state.error
        ))

    return results
```

## 9.9 Common Agent Patterns

```python
# 1. Single-turn agent (simple tool use)
# Task → [Tool] → Answer

# 2. Multi-turn agent (sequential tools)
# Task → [Tool1] → [Tool2] → [Tool3] → Answer

# 3. ReAct agent (reasoning + acting)
# Task → Think → Act → Observe → Think → Act → ... → Answer

# 4. Plan-then-execute agent
# Task → [Make Plan] → [Execute Step 1] → [Execute Step 2] → ... → Answer

# 5. Self-correcting agent
# Task → [Try] → [Check] → [Fix if wrong] → ... → Answer
```

## 9.10 Summary

| Component | Purpose |
|-----------|---------|
| Loop | Core execution cycle |
| State | Track progress and history |
| Tools | Actions the agent can take |
| Stop conditions | When to terminate |
| ReAct | Explicit reasoning pattern |

**Key principles:**
- Agents are LLMs + tools + loop
- Always have stop conditions
- Track state for debugging
- ReAct improves transparency
- Start simple, add complexity as needed
