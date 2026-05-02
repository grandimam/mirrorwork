# Chapter 6: Prompt Templates and Variables

## 6.1 Why Templates?

Templates separate prompt structure from data:

```python
# Without template (hard to maintain)
prompt = f"Summarize this article about {topic}: {article}"

# With template (reusable, testable)
SUMMARY_TEMPLATE = """
Task: Summarize the following article
Topic: {topic}
Style: {style}

Article:
{article}

Provide a {length} summary.
"""

prompt = SUMMARY_TEMPLATE.format(
    topic="technology",
    style="professional",
    article=article_text,
    length="2-3 sentence"
)
```

## 6.2 Basic String Templates

```python
from string import Template

# Python's Template class (safe substitution)
template = Template("""
You are a $role assistant.
Help the user with $task.
""")

prompt = template.safe_substitute(
    role="coding",
    task="debugging Python"
)
```

## 6.3 Jinja2 Templates

```python
from jinja2 import Template

template = Template("""
{% if system_context %}
Context: {{ system_context }}
{% endif %}

Task: {{ task }}

{% if examples %}
Examples:
{% for ex in examples %}
Input: {{ ex.input }}
Output: {{ ex.output }}
{% endfor %}
{% endif %}

Input: {{ user_input }}
Output:
""")

prompt = template.render(
    task="Translate to French",
    examples=[
        {"input": "Hello", "output": "Bonjour"},
        {"input": "Goodbye", "output": "Au revoir"},
    ],
    user_input="Thank you"
)
```

## 6.4 Template Class

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class PromptTemplate:
    template: str
    required_vars: list[str]
    default_vars: dict[str, Any] = None

    def __post_init__(self):
        self.default_vars = self.default_vars or {}

    def format(self, **kwargs) -> str:
        # Check required variables
        missing = set(self.required_vars) - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing required variables: {missing}")

        # Merge with defaults
        vars = {**self.default_vars, **kwargs}
        return self.template.format(**vars)

# Usage
summary_template = PromptTemplate(
    template="""
Summarize in {style} style:
{text}

Length: {length}
""",
    required_vars=["text"],
    default_vars={"style": "professional", "length": "2-3 sentences"}
)

prompt = summary_template.format(text="Article content here...")
```

## 6.5 Template Registry

```python
class PromptRegistry:
    def __init__(self):
        self.templates: dict[str, PromptTemplate] = {}

    def register(self, name: str, template: PromptTemplate):
        self.templates[name] = template

    def get(self, name: str) -> PromptTemplate:
        if name not in self.templates:
            raise KeyError(f"Template '{name}' not found")
        return self.templates[name]

    def render(self, name: str, **kwargs) -> str:
        return self.get(name).format(**kwargs)

# Global registry
prompts = PromptRegistry()

prompts.register("summarize", PromptTemplate(
    template="Summarize: {text}",
    required_vars=["text"]
))

prompts.register("translate", PromptTemplate(
    template="Translate to {language}: {text}",
    required_vars=["text", "language"]
))

# Usage
prompt = prompts.render("translate", text="Hello", language="Spanish")
```

## 6.6 Composable Templates

```python
class ComposableTemplate:
    def __init__(self):
        self.sections = []

    def add_section(self, name: str, content: str, condition: bool = True):
        if condition:
            self.sections.append((name, content))
        return self

    def build(self) -> str:
        parts = []
        for name, content in self.sections:
            parts.append(f"## {name}\n{content}")
        return "\n\n".join(parts)

# Usage
template = (
    ComposableTemplate()
    .add_section("Role", "You are a helpful assistant")
    .add_section("Context", context, condition=bool(context))
    .add_section("Task", "Answer the user's question")
    .add_section("Rules", rules, condition=bool(rules))
)

prompt = template.build()
```

## 6.7 Template Validation

```python
import re

def validate_template(template: str, required_vars: list[str]) -> list[str]:
    """Validate template has all required variables"""
    # Find all {variable} patterns
    found_vars = set(re.findall(r'\{(\w+)\}', template))
    required_set = set(required_vars)

    errors = []

    # Check for missing required variables
    missing = required_set - found_vars
    if missing:
        errors.append(f"Missing variables in template: {missing}")

    # Check for undefined variables
    undefined = found_vars - required_set
    if undefined:
        errors.append(f"Undefined variables used: {undefined}")

    return errors

# Usage
errors = validate_template(
    "Hello {name}, your order {order_id} is ready",
    ["name", "order_id"]
)
```

## 6.8 Environment-Specific Templates

```python
TEMPLATES = {
    "development": {
        "system": "You are a test assistant. Be verbose for debugging.",
        "max_tokens": 2000,
    },
    "production": {
        "system": "You are a helpful assistant. Be concise.",
        "max_tokens": 500,
    }
}

def get_template(name: str, env: str = "production") -> dict:
    return TEMPLATES.get(env, TEMPLATES["production"])
```

## 6.9 Template Inheritance

```python
class BaseTemplate:
    system = "You are a helpful assistant."
    format_instructions = "Respond clearly and concisely."

class CodeTemplate(BaseTemplate):
    system = "You are an expert programmer."
    format_instructions = "Provide code with brief explanations."

class SQLTemplate(CodeTemplate):
    system = "You are a SQL expert."
    format_instructions = "Return only valid SQL queries."

def build_prompt(template_class, task: str) -> str:
    return f"""
{template_class.system}
{template_class.format_instructions}

Task: {task}
"""
```

## 6.10 Template Testing

```python
import pytest

def test_template_renders():
    template = PromptTemplate(
        template="Translate {text} to {language}",
        required_vars=["text", "language"]
    )
    result = template.format(text="Hello", language="French")
    assert "Hello" in result
    assert "French" in result

def test_template_missing_var():
    template = PromptTemplate(
        template="Hello {name}",
        required_vars=["name"]
    )
    with pytest.raises(ValueError):
        template.format()  # Missing 'name'

def test_template_output():
    """Test that template produces expected model output"""
    prompt = prompts.render("classify", text="Great product!")
    response = client.messages.create(...)
    assert response.content[0].text in ["positive", "negative", "neutral"]
```

## 6.11 Summary

| Approach | Use Case |
|----------|----------|
| f-strings | Simple, one-off prompts |
| string.Template | Safe substitution |
| Jinja2 | Complex logic, loops |
| Custom class | Validation, defaults |
| Registry | Managing many templates |

**Best practices:**
- Separate templates from code
- Validate variables at creation time
- Use defaults for optional parameters
- Version control templates
- Test templates produce expected outputs
