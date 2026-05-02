# Module 29: Content Moderation

## 29.1 Why Moderation Matters

```
Risks without moderation:
- Harmful content generation
- Legal/compliance issues
- Brand reputation damage
- User safety concerns
- Platform abuse

Moderation points:
- Input: Block harmful requests
- Output: Filter harmful responses
- Storage: Scan stored content
```

## 29.2 OpenAI Moderation API

```python
from openai import OpenAI

client = OpenAI()

def check_content(text: str) -> dict:
    response = client.moderations.create(input=text)

    result = response.results[0]
    return {
        "flagged": result.flagged,
        "categories": {
            k: v for k, v in result.categories.model_dump().items() if v
        },
        "scores": {
            k: v for k, v in result.category_scores.model_dump().items() if v > 0.1
        }
    }

# Usage
result = check_content("Some text to check")
if result["flagged"]:
    print(f"Content flagged for: {result['categories']}")
```

## 29.3 LLM-Based Moderation

```python
class LLMModeration:
    CATEGORIES = [
        "hate_speech",
        "violence",
        "sexual_content",
        "self_harm",
        "illegal_activity",
        "personal_info"
    ]

    async def moderate(self, text: str) -> dict:
        prompt = f"""Analyze this text for policy violations.

Categories to check: {', '.join(self.CATEGORIES)}

Text: {text}

Return JSON:
{{"flagged": true/false, "categories": ["..."], "reason": "brief explanation"}}"""

        response = await client.messages.create(
            model="claude-3-haiku",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text)

    async def moderate_batch(self, texts: list[str]) -> list[dict]:
        tasks = [self.moderate(t) for t in texts]
        return await asyncio.gather(*tasks)
```

## 29.4 Input Filtering

```python
class InputFilter:
    def __init__(self):
        self.blocked_patterns = [
            r"how to (make|build|create) (a )?(bomb|weapon|explosive)",
            r"(hack|steal|attack) .*(account|system|password)",
            r"generate .*(malware|virus|ransomware)",
        ]

    def check(self, text: str) -> dict:
        text_lower = text.lower()

        for pattern in self.blocked_patterns:
            if re.search(pattern, text_lower):
                return {"allowed": False, "reason": "blocked_pattern"}

        return {"allowed": True}

class ModerationPipeline:
    def __init__(self):
        self.input_filter = InputFilter()
        self.llm_moderator = LLMModeration()

    async def check_input(self, text: str) -> dict:
        # Fast pattern check first
        pattern_result = self.input_filter.check(text)
        if not pattern_result["allowed"]:
            return pattern_result

        # Then LLM moderation
        llm_result = await self.llm_moderator.moderate(text)
        if llm_result["flagged"]:
            return {"allowed": False, "reason": llm_result["reason"]}

        return {"allowed": True}
```

## 29.5 Output Filtering

```python
class OutputFilter:
    def __init__(self):
        self.pii_patterns = {
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b\d{3}[-.)\s]?\d{3}[-.)\s]?\d{4}\b",
        }

    def filter_pii(self, text: str) -> str:
        """Redact PII from output"""
        for pii_type, pattern in self.pii_patterns.items():
            text = re.sub(pattern, f"[{pii_type.upper()}_REDACTED]", text)
        return text

    def check_output(self, text: str) -> dict:
        issues = []

        for pii_type, pattern in self.pii_patterns.items():
            if re.search(pattern, text):
                issues.append(f"contains_{pii_type}")

        return {
            "clean": len(issues) == 0,
            "issues": issues
        }
```

## 29.6 Rate Limiting for Abuse

```python
class AbuseDetector:
    def __init__(self):
        self.user_requests = {}  # user_id -> list of timestamps
        self.flagged_users = {}  # user_id -> flag count

    def check_user(self, user_id: str) -> dict:
        now = time.time()

        # Check if user is blocked
        if self.flagged_users.get(user_id, 0) >= 3:
            return {"allowed": False, "reason": "user_blocked"}

        # Check rate limit
        requests = self.user_requests.get(user_id, [])
        requests = [r for r in requests if now - r < 60]  # Last minute

        if len(requests) >= 20:  # 20 requests per minute
            return {"allowed": False, "reason": "rate_limit"}

        self.user_requests[user_id] = requests + [now]
        return {"allowed": True}

    def flag_user(self, user_id: str):
        self.flagged_users[user_id] = self.flagged_users.get(user_id, 0) + 1
```

## 29.7 Moderation Logging

```python
class ModerationLogger:
    def __init__(self, log_path: str = "moderation.log"):
        self.log_path = log_path

    def log_decision(self, user_id: str, content: str, decision: dict):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "content_hash": hashlib.md5(content.encode()).hexdigest(),
            "content_preview": content[:100] if decision.get("flagged") else None,
            "decision": decision
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_flagged_content(self, hours: int = 24) -> list:
        cutoff = datetime.now() - timedelta(hours=hours)
        flagged = []

        with open(self.log_path) as f:
            for line in f:
                entry = json.loads(line)
                if datetime.fromisoformat(entry["timestamp"]) > cutoff:
                    if entry["decision"].get("flagged"):
                        flagged.append(entry)

        return flagged
```

## 29.8 Summary

| Layer | Protection |
|-------|------------|
| Input patterns | Fast blocking of known bad |
| Input LLM | Nuanced understanding |
| Output PII | Protect user data |
| Output content | Prevent harmful generation |
| Rate limiting | Prevent abuse |
| Logging | Audit and improve |

**Best practices:**
- Layer multiple moderation methods
- Fast checks first, LLM checks second
- Log all moderation decisions
- Review flagged content regularly
- Update patterns based on new threats
- Balance safety with user experience
