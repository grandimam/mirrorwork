# Chapter 7: Prompt Versioning and Testing

## 7.1 Why Version Prompts?

Prompts are code. They need:
- Version control
- Testing
- Rollback capability
- A/B testing

```python
# Bad: Prompts inline in code
response = client.messages.create(
    system="You are helpful...",  # Can't track changes
    ...
)

# Good: Prompts in versioned files
prompts/
├── summarize/
│   ├── v1.yaml
│   ├── v2.yaml
│   └── current.yaml -> v2.yaml
```

## 7.2 Prompt Storage

```yaml
# prompts/summarize/v2.yaml
name: summarize
version: "2.0"
description: "Summarization prompt with length control"
created: "2024-01-15"
author: "team"

system: |
  You are a professional summarizer.
  Create concise, accurate summaries.

template: |
  Summarize the following text in {length} sentences.
  Focus on: {focus_areas}

  Text:
  {text}

defaults:
  length: 3
  focus_areas: "key points and conclusions"

test_cases:
  - input:
      text: "Long article about AI..."
      length: 2
    expected_contains: ["AI", "technology"]
```

## 7.3 Prompt Loader

```python
import yaml
from pathlib import Path

class PromptLoader:
    def __init__(self, prompts_dir: str = "prompts"):
        self.dir = Path(prompts_dir)
        self.cache = {}

    def load(self, name: str, version: str = "current") -> dict:
        cache_key = f"{name}:{version}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        path = self.dir / name / f"{version}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {path}")

        with open(path) as f:
            prompt = yaml.safe_load(f)

        self.cache[cache_key] = prompt
        return prompt

    def render(self, name: str, version: str = "current", **kwargs) -> str:
        prompt = self.load(name, version)
        vars = {**prompt.get("defaults", {}), **kwargs}
        return prompt["template"].format(**vars)

# Usage
loader = PromptLoader()
prompt = loader.render("summarize", text="Article content...")
```

## 7.4 Version Comparison

```python
class PromptVersionManager:
    def __init__(self, loader: PromptLoader):
        self.loader = loader

    def list_versions(self, name: str) -> list[str]:
        prompt_dir = self.loader.dir / name
        versions = []
        for f in prompt_dir.glob("v*.yaml"):
            versions.append(f.stem)
        return sorted(versions)

    def diff(self, name: str, v1: str, v2: str) -> dict:
        p1 = self.loader.load(name, v1)
        p2 = self.loader.load(name, v2)

        return {
            "system_changed": p1.get("system") != p2.get("system"),
            "template_changed": p1.get("template") != p2.get("template"),
            "v1_template": p1.get("template"),
            "v2_template": p2.get("template"),
        }
```

## 7.5 Prompt Testing

```python
import pytest

class PromptTester:
    def __init__(self, client, loader: PromptLoader):
        self.client = client
        self.loader = loader

    async def run_tests(self, name: str, version: str = "current") -> list[dict]:
        prompt_config = self.loader.load(name, version)
        test_cases = prompt_config.get("test_cases", [])
        results = []

        for case in test_cases:
            rendered = self.loader.render(name, version, **case["input"])

            response = await self.client.messages.create(
                model="claude-3-5-sonnet",
                system=prompt_config.get("system", ""),
                max_tokens=1000,
                messages=[{"role": "user", "content": rendered}]
            )

            output = response.content[0].text
            passed = self._check_expectations(output, case)

            results.append({
                "input": case["input"],
                "output": output,
                "passed": passed,
            })

        return results

    def _check_expectations(self, output: str, case: dict) -> bool:
        if "expected_contains" in case:
            return all(s in output for s in case["expected_contains"])
        if "expected_not_contains" in case:
            return not any(s in output for s in case["expected_not_contains"])
        if "validator" in case:
            return case["validator"](output)
        return True

# Run tests
tester = PromptTester(client, loader)
results = await tester.run_tests("summarize", "v2")
```

## 7.6 A/B Testing Prompts

```python
import random
from dataclasses import dataclass

@dataclass
class ABTest:
    name: str
    control: str      # version A
    treatment: str    # version B
    split: float = 0.5

class ABTestManager:
    def __init__(self, loader: PromptLoader):
        self.loader = loader
        self.tests: dict[str, ABTest] = {}
        self.results: dict[str, list] = {}

    def create_test(self, test: ABTest):
        self.tests[test.name] = test
        self.results[test.name] = []

    def get_version(self, prompt_name: str, user_id: str = None) -> tuple[str, str]:
        """Returns (version, group) for tracking"""
        test = self.tests.get(prompt_name)
        if not test:
            return "current", "none"

        # Consistent assignment based on user_id
        if user_id:
            in_treatment = hash(user_id) % 100 < (test.split * 100)
        else:
            in_treatment = random.random() < test.split

        version = test.treatment if in_treatment else test.control
        group = "treatment" if in_treatment else "control"
        return version, group

    def record_result(self, test_name: str, group: str, metrics: dict):
        self.results[test_name].append({"group": group, **metrics})

# Usage
ab_manager = ABTestManager(loader)
ab_manager.create_test(ABTest(
    name="summarize",
    control="v1",
    treatment="v2",
    split=0.5
))

version, group = ab_manager.get_version("summarize", user_id="user123")
prompt = loader.render("summarize", version=version, text=text)

# After getting feedback
ab_manager.record_result("summarize", group, {"rating": 5, "length": len(response)})
```

## 7.7 Prompt CI/CD

```python
# tests/test_prompts.py
import pytest
from prompt_loader import PromptLoader
from prompt_tester import PromptTester

loader = PromptLoader()
tester = PromptTester(client, loader)

@pytest.mark.asyncio
async def test_summarize_prompt():
    results = await tester.run_tests("summarize")
    failures = [r for r in results if not r["passed"]]
    assert len(failures) == 0, f"Failed tests: {failures}"

@pytest.mark.asyncio
async def test_all_prompts_valid():
    """Ensure all prompts load without errors"""
    for prompt_dir in loader.dir.iterdir():
        if prompt_dir.is_dir():
            prompt = loader.load(prompt_dir.name)
            assert "template" in prompt
```

```yaml
# .github/workflows/prompts.yml
name: Prompt Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run prompt tests
        run: pytest tests/test_prompts.py
```

## 7.8 Prompt Metrics

```python
class PromptMetrics:
    def __init__(self):
        self.metrics = []

    def record(self, prompt_name: str, version: str, metrics: dict):
        self.metrics.append({
            "timestamp": datetime.now(),
            "prompt": prompt_name,
            "version": version,
            **metrics
        })

    def analyze(self, prompt_name: str) -> dict:
        prompt_metrics = [m for m in self.metrics if m["prompt"] == prompt_name]
        by_version = {}

        for m in prompt_metrics:
            v = m["version"]
            if v not in by_version:
                by_version[v] = []
            by_version[v].append(m)

        return {
            version: {
                "count": len(records),
                "avg_latency": sum(r.get("latency", 0) for r in records) / len(records),
                "avg_tokens": sum(r.get("tokens", 0) for r in records) / len(records),
            }
            for version, records in by_version.items()
        }
```

## 7.9 Summary

| Practice | Why |
|----------|-----|
| Version prompts | Track changes, rollback |
| Store in files | Code review, git history |
| Test prompts | Catch regressions |
| A/B test | Compare versions |
| Track metrics | Monitor performance |

**Best practices:**
- Treat prompts as code artifacts
- Version with semantic versioning
- Write tests for expected behaviors
- A/B test before full rollout
- Monitor quality metrics
