# Module 11: Agent Planning

## 11.1 Why Planning?

Without planning, agents act reactively. With planning, they think ahead.

```
Without Planning:
User: "Build a website"
Agent: [starts coding immediately] → [realizes missing requirements] → [restarts]

With Planning:
User: "Build a website"
Agent: [creates plan] → [validates plan] → [executes step by step] → [completes]
```

## 11.2 Task Decomposition

Break complex tasks into subtasks:

```python
DECOMPOSITION_PROMPT = """
Break down this task into clear, sequential steps.

Task: {task}

Provide steps in this format:
1. [Step description] - [Expected outcome]
2. [Step description] - [Expected outcome]
...

Keep steps atomic and actionable.
"""

async def decompose_task(task: str) -> list[str]:
    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": DECOMPOSITION_PROMPT.format(task=task)
        }]
    )

    # Parse steps from response
    text = response.content[0].text
    steps = []
    for line in text.split('\n'):
        if line.strip() and line[0].isdigit():
            steps.append(line.split('.', 1)[1].strip())
    return steps
```

## 11.3 Plan-and-Execute Pattern

```python
class PlanAndExecuteAgent:
    def __init__(self, client, tools):
        self.client = client
        self.tools = tools

    async def run(self, task: str) -> str:
        # Phase 1: Create plan
        plan = await self.create_plan(task)
        print(f"Plan: {plan}")

        # Phase 2: Execute plan
        results = []
        for step in plan:
            result = await self.execute_step(step, results)
            results.append({"step": step, "result": result})

            # Check if we need to replan
            if result.get("needs_replan"):
                plan = await self.replan(task, results)

        # Phase 3: Synthesize final answer
        return await self.synthesize(task, results)

    async def create_plan(self, task: str) -> list[str]:
        prompt = f"""
Create a step-by-step plan to accomplish this task.
Each step should be specific and actionable.
Available tools: {[t['name'] for t in self.tools]}

Task: {task}

Plan:"""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_plan(response.content[0].text)

    async def execute_step(self, step: str, previous_results: list) -> dict:
        context = "\n".join([
            f"- {r['step']}: {r['result']}"
            for r in previous_results[-3:]  # Last 3 results for context
        ])

        prompt = f"""
Execute this step of the plan.

Previous results:
{context}

Current step: {step}

Use tools as needed to complete this step."""

        # Use regular agent loop for execution
        return await self._execute_with_tools(prompt)

    async def replan(self, task: str, results: list) -> list[str]:
        prompt = f"""
The original plan needs adjustment based on these results.

Original task: {task}
Progress so far: {results}

Create an updated plan to complete the task."""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_plan(response.content[0].text)
```

## 11.4 Dynamic Replanning

```python
class AdaptiveAgent(PlanAndExecuteAgent):
    async def execute_step(self, step: str, previous_results: list) -> dict:
        result = await super().execute_step(step, previous_results)

        # Check if step failed or discovered new info
        if result.get("error") or result.get("unexpected"):
            result["needs_replan"] = True

        return result

    async def should_replan(self, step_result: dict, plan: list, current_index: int) -> bool:
        prompt = f"""
Given this step result, should we adjust the remaining plan?

Step result: {step_result}
Remaining steps: {plan[current_index + 1:]}

Answer YES or NO with brief explanation."""

        response = await self.client.messages.create(
            model="claude-3-haiku",  # Fast model for decision
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        return "YES" in response.content[0].text.upper()
```

## 11.5 Hierarchical Planning

```python
class HierarchicalPlanner:
    """Break tasks into high-level goals, then detailed steps"""

    async def plan(self, task: str) -> dict:
        # Level 1: High-level goals
        goals = await self.identify_goals(task)

        # Level 2: Steps for each goal
        plan = {"goals": []}
        for goal in goals:
            steps = await self.plan_goal(goal)
            plan["goals"].append({
                "goal": goal,
                "steps": steps
            })

        return plan

    async def identify_goals(self, task: str) -> list[str]:
        prompt = f"""
Identify the main goals needed to complete this task.
List 2-5 high-level goals.

Task: {task}

Goals:"""
        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_list(response.content[0].text)

    async def plan_goal(self, goal: str) -> list[str]:
        prompt = f"""
Break this goal into specific actionable steps.

Goal: {goal}

Steps:"""
        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_list(response.content[0].text)
```

## 11.6 Plan Validation

```python
async def validate_plan(plan: list[str], tools: list, task: str) -> dict:
    """Validate that a plan is feasible"""

    tool_names = [t["name"] for t in tools]

    prompt = f"""
Validate this plan for the given task.

Task: {task}
Available tools: {tool_names}

Plan:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(plan))}

Check for:
1. Are all steps achievable with available tools?
2. Are steps in logical order?
3. Are there missing steps?
4. Are there unnecessary steps?

Return JSON:
{{
    "valid": true/false,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1"]
}}"""

    response = await client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(response.content[0].text)
```

## 11.7 Plan Representation

```python
from dataclasses import dataclass
from enum import Enum

class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class PlanStep:
    id: str
    description: str
    status: StepStatus = StepStatus.PENDING
    result: dict = None
    dependencies: list[str] = None  # IDs of steps this depends on

@dataclass
class Plan:
    task: str
    steps: list[PlanStep]
    created_at: datetime = None
    status: str = "active"

    def get_next_step(self) -> PlanStep | None:
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                # Check dependencies
                if step.dependencies:
                    deps_complete = all(
                        self.get_step(dep_id).status == StepStatus.COMPLETED
                        for dep_id in step.dependencies
                    )
                    if not deps_complete:
                        continue
                return step
        return None

    def get_step(self, step_id: str) -> PlanStep:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
```

## 11.8 Plan Execution Tracking

```python
class PlanExecutor:
    def __init__(self, agent):
        self.agent = agent

    async def execute_plan(self, plan: Plan) -> Plan:
        while True:
            step = plan.get_next_step()
            if not step:
                break

            step.status = StepStatus.IN_PROGRESS
            print(f"Executing: {step.description}")

            try:
                result = await self.agent.execute_step(step.description)
                step.result = result
                step.status = StepStatus.COMPLETED
            except Exception as e:
                step.result = {"error": str(e)}
                step.status = StepStatus.FAILED

                # Decide whether to continue or abort
                if not await self.should_continue(plan, step):
                    plan.status = "failed"
                    break

        if all(s.status == StepStatus.COMPLETED for s in plan.steps):
            plan.status = "completed"

        return plan
```

## 11.9 Summary

| Pattern | Use Case |
|---------|----------|
| Task decomposition | Breaking complex tasks |
| Plan-and-execute | Structured execution |
| Dynamic replanning | Handling failures |
| Hierarchical | Very complex tasks |
| Plan validation | Ensuring feasibility |

**Best practices:**
- Always validate plans before execution
- Keep plans flexible for replanning
- Track step dependencies
- Log execution for debugging
- Set maximum replanning iterations
