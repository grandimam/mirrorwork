# Module 19: Evaluation and Testing

## 19.1 Why Evaluation Matters

```
Traditional software: deterministic, unit testable
LLM applications: probabilistic, need statistical evaluation

Key questions:
- Is the output correct?
- Is it consistent?
- Is it safe?
- Does it meet quality standards?
```

## 19.2 Evaluation Metrics

```python
# Exact match
def exact_match(predicted: str, expected: str) -> bool:
    return predicted.strip().lower() == expected.strip().lower()

# Contains expected content
def contains_answer(response: str, expected: str) -> bool:
    return expected.lower() in response.lower()

# Semantic similarity
async def semantic_similarity(text1: str, text2: str, embedder) -> float:
    emb1 = await embedder.embed(text1)
    emb2 = await embedder.embed(text2)
    return cosine_similarity(emb1, emb2)

# LLM-as-judge
async def llm_judge(response: str, criteria: str, client) -> dict:
    prompt = f"""
Rate this response on a scale of 1-5 for: {criteria}

Response: {response}

Provide score and brief explanation.
Format: SCORE: X
REASON: ..."""

    result = await client.messages.create(
        model="claude-3-haiku",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_score(result.content[0].text)
```

## 19.3 Evaluation Dataset

```python
@dataclass
class EvalCase:
    input: str
    expected_output: str = None
    expected_contains: list[str] = None
    metadata: dict = None

class EvalDataset:
    def __init__(self, cases: list[EvalCase]):
        self.cases = cases

    @classmethod
    def from_jsonl(cls, path: str) -> "EvalDataset":
        cases = []
        with open(path) as f:
            for line in f:
                data = json.loads(line)
                cases.append(EvalCase(**data))
        return cls(cases)

    def sample(self, n: int) -> list[EvalCase]:
        return random.sample(self.cases, min(n, len(self.cases)))

# Example dataset
dataset = EvalDataset([
    EvalCase(
        input="What is 2+2?",
        expected_output="4",
        expected_contains=["4"]
    ),
    EvalCase(
        input="Summarize: The cat sat on the mat.",
        expected_contains=["cat", "mat"]
    ),
])
```

## 19.4 Running Evaluations

```python
class Evaluator:
    def __init__(self, agent, metrics: list[callable]):
        self.agent = agent
        self.metrics = metrics

    async def evaluate(self, dataset: EvalDataset) -> dict:
        results = []

        for case in dataset.cases:
            output = await self.agent.run(case.input)

            scores = {}
            for metric in self.metrics:
                scores[metric.__name__] = metric(output, case)

            results.append({
                "input": case.input,
                "output": output,
                "expected": case.expected_output,
                "scores": scores
            })

        return self._aggregate(results)

    def _aggregate(self, results: list) -> dict:
        metrics_avg = {}
        for metric in self.metrics:
            name = metric.__name__
            scores = [r["scores"][name] for r in results]
            metrics_avg[name] = sum(scores) / len(scores)

        return {
            "total_cases": len(results),
            "metrics": metrics_avg,
            "results": results
        }
```

## 19.5 A/B Testing Prompts

```python
class PromptABTest:
    def __init__(self, client):
        self.client = client
        self.results = {"A": [], "B": []}

    async def run_test(self, prompt_a: str, prompt_b: str, test_cases: list[str], n_runs: int = 3):
        for case in test_cases:
            for _ in range(n_runs):
                # Run both prompts
                result_a = await self._run_prompt(prompt_a, case)
                result_b = await self._run_prompt(prompt_b, case)

                self.results["A"].append(result_a)
                self.results["B"].append(result_b)

        return self._analyze()

    def _analyze(self) -> dict:
        return {
            "A": {
                "avg_score": sum(r["score"] for r in self.results["A"]) / len(self.results["A"]),
                "avg_latency": sum(r["latency"] for r in self.results["A"]) / len(self.results["A"]),
            },
            "B": {
                "avg_score": sum(r["score"] for r in self.results["B"]) / len(self.results["B"]),
                "avg_latency": sum(r["latency"] for r in self.results["B"]) / len(self.results["B"]),
            }
        }
```

## 19.6 Regression Testing

```python
class RegressionTester:
    def __init__(self, baseline_path: str):
        self.baseline = self._load_baseline(baseline_path)

    def _load_baseline(self, path: str) -> dict:
        with open(path) as f:
            return json.load(f)

    async def check_regression(self, agent, dataset: EvalDataset) -> dict:
        evaluator = Evaluator(agent, [exact_match, contains_answer])
        current = await evaluator.evaluate(dataset)

        regressions = []
        for metric, score in current["metrics"].items():
            baseline_score = self.baseline["metrics"].get(metric, 0)
            if score < baseline_score * 0.95:  # 5% threshold
                regressions.append({
                    "metric": metric,
                    "baseline": baseline_score,
                    "current": score,
                    "delta": score - baseline_score
                })

        return {
            "passed": len(regressions) == 0,
            "regressions": regressions,
            "current_metrics": current["metrics"]
        }
```

## 19.7 Testing Tool Use

```python
class ToolUseTester:
    async def test_tool_selection(self, agent, cases: list[dict]) -> dict:
        """Test if agent selects correct tools"""
        results = []

        for case in cases:
            # Run agent and capture tool calls
            tool_calls = []
            original_execute = agent.execute_tool

            async def capture_execute(name, inputs):
                tool_calls.append({"name": name, "inputs": inputs})
                return await original_execute(name, inputs)

            agent.execute_tool = capture_execute
            await agent.run(case["input"])
            agent.execute_tool = original_execute

            # Check expected tools were called
            called_tools = [t["name"] for t in tool_calls]
            expected_tools = case.get("expected_tools", [])

            results.append({
                "input": case["input"],
                "called": called_tools,
                "expected": expected_tools,
                "correct": set(expected_tools).issubset(set(called_tools))
            })

        return {
            "accuracy": sum(r["correct"] for r in results) / len(results),
            "results": results
        }
```

## 19.8 Summary

| Test Type | What It Measures |
|-----------|------------------|
| Accuracy | Correct outputs |
| Consistency | Same input → similar output |
| Latency | Response time |
| Cost | Token usage |
| Tool use | Correct tool selection |
| Safety | No harmful outputs |

**Best practices:**
- Build evaluation datasets early
- Run evals on every prompt change
- Use LLM-as-judge for subjective quality
- Track metrics over time
- Set regression thresholds
