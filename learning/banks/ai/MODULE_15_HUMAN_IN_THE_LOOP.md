# Module 15: Human-in-the-Loop

## 15.1 Why Human-in-the-Loop?

- Approval for sensitive actions
- Clarification when uncertain
- Quality control
- Compliance requirements
- Building trust

## 15.2 Approval Workflows

```python
class ApprovalRequired(Exception):
    def __init__(self, action: str, details: dict):
        self.action = action
        self.details = details

class ApprovalAgent:
    def __init__(self, client, tools, approval_callback):
        self.client = client
        self.tools = tools
        self.approval_callback = approval_callback
        self.sensitive_tools = {"delete_file", "send_email", "execute_sql"}

    async def run(self, task: str) -> str:
        messages = [{"role": "user", "content": task}]

        while True:
            response = await self.client.messages.create(
                model="claude-3-5-sonnet",
                max_tokens=4096,
                tools=self.tools,
                messages=messages
            )

            if response.stop_reason == "end_turn":
                return self._get_text(response)

            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        # Check if approval needed
                        if block.name in self.sensitive_tools:
                            approved = await self.approval_callback(
                                action=block.name,
                                details=block.input
                            )
                            if not approved:
                                tool_results.append({
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": "Action denied by user",
                                    "is_error": True
                                })
                                continue

                        # Execute tool
                        result = await self.execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
```

## 15.3 Confirmation Patterns

```python
async def confirm_action(action: str, details: dict) -> bool:
    """Simple confirmation prompt"""
    print(f"\n⚠️  Action requires approval:")
    print(f"   Action: {action}")
    print(f"   Details: {json.dumps(details, indent=2)}")

    response = input("Approve? (yes/no): ").strip().lower()
    return response in ["yes", "y"]

async def confirm_with_options(action: str, details: dict) -> str:
    """Confirmation with multiple options"""
    print(f"\n⚠️  Action: {action}")
    print(f"   Details: {details}")
    print("\nOptions:")
    print("  1. Approve")
    print("  2. Deny")
    print("  3. Modify and approve")
    print("  4. Ask agent to explain")

    choice = input("Choice (1-4): ").strip()
    return choice
```

## 15.4 Feedback Collection

```python
class FeedbackCollector:
    def __init__(self):
        self.feedback = []

    async def collect_rating(self, response: str) -> dict:
        print(f"\nResponse: {response[:200]}...")
        rating = input("Rate (1-5): ").strip()
        comment = input("Comment (optional): ").strip()

        feedback = {
            "rating": int(rating),
            "comment": comment,
            "timestamp": datetime.now().isoformat()
        }
        self.feedback.append(feedback)
        return feedback

    async def collect_preference(self, options: list[str]) -> int:
        print("\nWhich response is better?")
        for i, opt in enumerate(options):
            print(f"  {i + 1}. {opt[:100]}...")

        choice = input("Choice: ").strip()
        return int(choice) - 1
```

## 15.5 Clarification Requests

```python
class ClarifyingAgent:
    async def run(self, task: str) -> str:
        # Check if clarification needed
        needs_clarification = await self._check_clarity(task)

        if needs_clarification:
            questions = await self._generate_questions(task)
            answers = await self._ask_user(questions)
            task = f"{task}\n\nClarifications:\n{answers}"

        return await self._execute(task)

    async def _check_clarity(self, task: str) -> bool:
        prompt = f"""
Is this task clear enough to execute, or does it need clarification?
Task: {task}

Answer CLEAR or NEEDS_CLARIFICATION."""

        response = await self.client.messages.create(
            model="claude-3-haiku",
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}]
        )
        return "NEEDS_CLARIFICATION" in response.content[0].text

    async def _generate_questions(self, task: str) -> list[str]:
        prompt = f"""
Generate 1-3 clarifying questions for this task:
{task}

Questions:"""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_questions(response.content[0].text)

    async def _ask_user(self, questions: list[str]) -> str:
        answers = []
        for q in questions:
            print(f"\n❓ {q}")
            answer = input("Answer: ").strip()
            answers.append(f"Q: {q}\nA: {answer}")
        return "\n".join(answers)
```

## 15.6 Escalation Logic

```python
class EscalatingAgent:
    def __init__(self, client, escalation_handler):
        self.client = client
        self.escalation_handler = escalation_handler
        self.confidence_threshold = 0.7

    async def run(self, task: str) -> str:
        response, confidence = await self._execute_with_confidence(task)

        if confidence < self.confidence_threshold:
            return await self.escalation_handler(
                task=task,
                response=response,
                confidence=confidence,
                reason="Low confidence"
            )

        return response

    async def _execute_with_confidence(self, task: str) -> tuple[str, float]:
        prompt = f"""
{task}

After your response, rate your confidence (0.0-1.0) in this format:
CONFIDENCE: 0.X"""

        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text
        confidence = self._extract_confidence(text)
        return text, confidence
```

## 15.7 Intervention Points

```python
class InterventionAgent:
    def __init__(self, client, tools):
        self.client = client
        self.tools = tools
        self.paused = False
        self.step_mode = False

    async def run(self, task: str) -> str:
        messages = [{"role": "user", "content": task}]
        iteration = 0

        while True:
            # Check for pause/intervention
            if self.paused:
                await self._wait_for_resume()

            if self.step_mode:
                print(f"\n[Step {iteration}] Press Enter to continue...")
                input()

            response = await self.client.messages.create(
                model="claude-3-5-sonnet",
                max_tokens=4096,
                tools=self.tools,
                messages=messages
            )

            # Show progress
            self._show_progress(response, iteration)
            iteration += 1

            if response.stop_reason == "end_turn":
                return self._get_text(response)

            # Handle tool use
            messages = await self._process_tools(messages, response)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def toggle_step_mode(self):
        self.step_mode = not self.step_mode
```

## 15.8 Summary

| Pattern | Use Case |
|---------|----------|
| Approval | Sensitive actions |
| Confirmation | Destructive operations |
| Clarification | Ambiguous tasks |
| Feedback | Quality improvement |
| Escalation | Uncertainty handling |
| Intervention | Real-time control |

**Best practices:**
- Clear approval UI
- Meaningful confirmation messages
- Non-blocking where possible
- Log all human decisions
- Allow intervention at any point
