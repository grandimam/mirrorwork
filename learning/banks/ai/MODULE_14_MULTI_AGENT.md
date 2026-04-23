# Module 14: Multi-Agent Systems

## 14.1 When to Use Multiple Agents

```
Single Agent: Simple tasks, linear workflows
Multi-Agent: Complex tasks requiring specialization, parallelization, or collaboration
```

## 14.2 Multi-Agent Patterns

```
1. Supervisor: One agent orchestrates others
2. Hierarchical: Layers of agents (manager → workers)
3. Collaborative: Agents work together as peers
4. Pipeline: Agents in sequence, each transforms output
5. Debate: Agents argue to find best answer
```

## 14.3 Supervisor Pattern

```python
class SupervisorAgent:
    def __init__(self, workers: dict[str, Agent]):
        self.workers = workers
        self.client = anthropic.Anthropic()

    async def run(self, task: str) -> str:
        # Supervisor decides which worker to use
        prompt = f"""
You are a supervisor managing these workers:
{self._describe_workers()}

Task: {task}

Which worker should handle this? Respond with worker name only."""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )

        worker_name = response.content[0].text.strip().lower()

        if worker_name in self.workers:
            return await self.workers[worker_name].run(task)
        else:
            return f"Unknown worker: {worker_name}"

    def _describe_workers(self) -> str:
        return "\n".join([
            f"- {name}: {worker.description}"
            for name, worker in self.workers.items()
        ])
```

## 14.4 Worker Agents

```python
class ResearchAgent:
    description = "Searches and gathers information"

    def __init__(self, client, search_tool):
        self.client = client
        self.search = search_tool

    async def run(self, task: str) -> str:
        # Search for information
        results = await self.search(task)

        # Synthesize findings
        prompt = f"""
Research task: {task}

Search results:
{results}

Provide a comprehensive summary."""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

class WritingAgent:
    description = "Writes and edits content"

    async def run(self, task: str) -> str:
        # Writing-focused prompt
        pass

class CodeAgent:
    description = "Writes and reviews code"

    async def run(self, task: str) -> str:
        # Code-focused prompt with tools
        pass
```

## 14.5 Agent Handoff

```python
class AgentOrchestrator:
    def __init__(self, agents: dict[str, Agent]):
        self.agents = agents
        self.current_agent = None
        self.context = []

    async def handoff(self, to_agent: str, message: str):
        """Transfer control to another agent"""
        self.context.append({
            "from": self.current_agent,
            "to": to_agent,
            "message": message
        })
        self.current_agent = to_agent

    async def run(self, task: str, start_agent: str) -> str:
        self.current_agent = start_agent
        self.context = [{"task": task}]

        for _ in range(10):  # Max handoffs
            agent = self.agents[self.current_agent]

            result = await agent.run(
                task=task,
                context=self.context,
                can_handoff=True,
                available_agents=list(self.agents.keys())
            )

            if result.get("handoff"):
                await self.handoff(result["handoff"], result["message"])
            else:
                return result["answer"]

        return "Max handoffs reached"
```

## 14.6 Parallel Agents

```python
async def parallel_agents(task: str, agents: list[Agent]) -> list:
    """Run multiple agents in parallel"""
    tasks = [agent.run(task) for agent in agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return [
        {"agent": agents[i].name, "result": r}
        for i, r in enumerate(results)
    ]

async def parallel_subtasks(subtasks: list[str], agent: Agent) -> list:
    """One agent handling multiple subtasks in parallel"""
    tasks = [agent.run(subtask) for subtask in subtasks]
    return await asyncio.gather(*tasks)
```

## 14.7 Debate Pattern

```python
class DebateSystem:
    def __init__(self, client, num_rounds: int = 3):
        self.client = client
        self.num_rounds = num_rounds

    async def debate(self, question: str) -> str:
        positions = []

        # Initial positions
        for side in ["pro", "con"]:
            pos = await self._generate_position(question, side)
            positions.append({"side": side, "argument": pos})

        # Debate rounds
        for round in range(self.num_rounds):
            for i, pos in enumerate(positions):
                other = positions[1 - i]
                rebuttal = await self._generate_rebuttal(
                    question, pos["argument"], other["argument"]
                )
                positions[i]["argument"] = rebuttal

        # Judge decides
        return await self._judge(question, positions)

    async def _generate_position(self, question: str, side: str) -> str:
        prompt = f"Argue {side} for: {question}"
        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    async def _judge(self, question: str, positions: list) -> str:
        prompt = f"""
Question: {question}

Arguments:
{positions}

Which side has the stronger argument? Explain your reasoning."""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
```

## 14.8 Shared State

```python
class SharedState:
    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()

    async def get(self, key: str):
        async with self.lock:
            return self.data.get(key)

    async def set(self, key: str, value: any):
        async with self.lock:
            self.data[key] = value

    async def update(self, key: str, func: callable):
        async with self.lock:
            self.data[key] = func(self.data.get(key))

class MultiAgentSystem:
    def __init__(self, agents: list[Agent]):
        self.agents = agents
        self.shared = SharedState()

    async def run(self, task: str):
        # All agents can read/write shared state
        for agent in self.agents:
            agent.shared_state = self.shared
```

## 14.9 Summary

| Pattern | Use Case |
|---------|----------|
| Supervisor | Route tasks to specialists |
| Hierarchical | Complex org structures |
| Parallel | Independent subtasks |
| Pipeline | Sequential processing |
| Debate | Finding best answer |

**Best practices:**
- Clear agent responsibilities
- Explicit handoff protocols
- Shared state management
- Limit agent interactions
- Track conversation flow
