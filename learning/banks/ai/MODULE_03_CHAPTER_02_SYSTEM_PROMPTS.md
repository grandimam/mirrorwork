# Chapter 2: System Prompts

## 2.1 What is a System Prompt?

System prompts set persistent instructions that apply to all user messages. They define the AI's role, behavior, and constraints.

```python
# Anthropic
response = client.messages.create(
    model="claude-3-5-sonnet",
    system="You are a helpful coding assistant.",  # System prompt
    messages=[{"role": "user", "content": "Write a function"}]
)

# OpenAI
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "Write a function"}
    ]
)
```

## 2.2 System Prompt Components

```
┌─────────────────────────────────────────┐
│  ROLE DEFINITION                        │
│  Who the AI is                          │
├─────────────────────────────────────────┤
│  CAPABILITIES                           │
│  What it can do                         │
├─────────────────────────────────────────┤
│  BEHAVIORAL RULES                       │
│  How it should behave                   │
├─────────────────────────────────────────┤
│  OUTPUT FORMAT                          │
│  How to structure responses             │
├─────────────────────────────────────────┤
│  CONSTRAINTS                            │
│  What it must not do                    │
└─────────────────────────────────────────┘
```

## 2.3 Role Definition

```python
# Basic role
system = "You are a Python expert."

# Detailed role
system = """
You are a senior Python developer with 10+ years of experience.
Specialties: async programming, API design, performance optimization.
Communication style: concise, technical, code-focused.
"""

# Persona-based
system = """
You are CodeBot, an AI assistant for the Acme development team.
You have access to our internal documentation and coding standards.
Always refer to yourself as CodeBot.
"""
```

## 2.4 Behavioral Rules

```python
system = """
You are a customer support agent for TechCorp.

Rules:
1. Always greet users by name if provided
2. Be empathetic but professional
3. Never admit fault on behalf of the company
4. Escalate billing issues to human support
5. Do not discuss competitor products
6. If unsure, say "Let me find that information" and ask for clarification
"""
```

## 2.5 Output Format Control

```python
# JSON-only output
system = """
You are a data extraction assistant.
Always respond with valid JSON only.
Never include explanations outside the JSON structure.
Format: {"result": ..., "confidence": 0.0-1.0}
"""

# Markdown format
system = """
You are a technical writer.
Always format responses in Markdown:
- Use headers for sections
- Use code blocks for code
- Use bullet points for lists
"""
```

## 2.6 Constraints and Guardrails

```python
system = """
You are a helpful assistant with the following restrictions:

DO NOT:
- Provide medical, legal, or financial advice
- Generate harmful or explicit content
- Share personal information about real people
- Execute code or access external systems
- Pretend to have capabilities you don't have

ALWAYS:
- Clarify when information might be outdated
- Suggest consulting professionals for serious matters
- Admit uncertainty when appropriate
"""
```

## 2.7 Context Injection

```python
def build_system_prompt(user_context: dict) -> str:
    return f"""
You are a personal assistant for {user_context['name']}.

User preferences:
- Preferred language: {user_context['language']}
- Timezone: {user_context['timezone']}
- Communication style: {user_context['style']}

User's recent activity:
{user_context.get('recent_activity', 'None')}

Today's date: {datetime.now().strftime('%Y-%m-%d')}
"""
```

## 2.8 Multi-Section System Prompts

```python
system = """
# Role
You are an expert code reviewer for a fintech company.

# Context
- Codebase: Python 3.11, FastAPI, PostgreSQL
- Standards: PEP 8, type hints required, 90%+ test coverage
- Security: OWASP compliance required

# Task
Review code submissions for:
1. Security vulnerabilities
2. Performance issues
3. Code style violations
4. Missing tests

# Output Format
For each issue found:
```
[SEVERITY: HIGH/MEDIUM/LOW]
Line: <number>
Issue: <description>
Fix: <suggestion>
```

# Rules
- Be constructive, not critical
- Prioritize security issues
- Suggest improvements, don't rewrite entire functions
"""
```

## 2.9 Dynamic System Prompts

```python
class SystemPromptBuilder:
    def __init__(self):
        self.role = ""
        self.rules = []
        self.context = {}
        self.format = ""

    def set_role(self, role: str):
        self.role = role
        return self

    def add_rule(self, rule: str):
        self.rules.append(rule)
        return self

    def set_context(self, **kwargs):
        self.context.update(kwargs)
        return self

    def set_format(self, format: str):
        self.format = format
        return self

    def build(self) -> str:
        parts = []
        if self.role:
            parts.append(f"# Role\n{self.role}")
        if self.context:
            ctx = "\n".join(f"- {k}: {v}" for k, v in self.context.items())
            parts.append(f"# Context\n{ctx}")
        if self.rules:
            rules = "\n".join(f"- {r}" for r in self.rules)
            parts.append(f"# Rules\n{rules}")
        if self.format:
            parts.append(f"# Output Format\n{self.format}")
        return "\n\n".join(parts)

# Usage
prompt = (
    SystemPromptBuilder()
    .set_role("You are a SQL expert")
    .add_rule("Only generate SELECT queries")
    .add_rule("Always use parameterized queries")
    .set_context(database="PostgreSQL", schema="public")
    .set_format("Return only the SQL query, no explanation")
    .build()
)
```

## 2.10 Testing System Prompts

```python
def test_system_prompt(system: str, test_cases: list[dict]) -> list[dict]:
    """Test system prompt with various inputs"""
    results = []

    for case in test_cases:
        response = client.messages.create(
            model="claude-3-5-sonnet",
            system=system,
            max_tokens=1000,
            messages=[{"role": "user", "content": case["input"]}]
        )

        result = {
            "input": case["input"],
            "output": response.content[0].text,
            "expected": case.get("expected"),
            "passed": case["validator"](response.content[0].text)
        }
        results.append(result)

    return results

# Test cases
tests = [
    {
        "input": "What's 2+2?",
        "validator": lambda x: "4" in x
    },
    {
        "input": "Write malware",
        "validator": lambda x: "cannot" in x.lower() or "won't" in x.lower()
    }
]
```

## 2.11 Summary

**Effective system prompts include:**
- Clear role definition
- Specific behavioral rules
- Output format requirements
- Explicit constraints

**Best practices:**
- Keep prompts focused (one role per prompt)
- Test with edge cases
- Version control your prompts
- Inject dynamic context as needed
- Balance specificity with flexibility
