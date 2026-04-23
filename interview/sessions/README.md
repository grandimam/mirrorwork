# Interview Practice Sessions

Sessions are logged automatically when you use `/mirrorwork prep <company>`.

## File Format

```
{company}-{date}-{type}.json
```

Example: `revolut-2026-04-24-coding.json`

## Session Schema

```json
{
  "company": "revolut",
  "type": "coding|system-design|behavioral",
  "date": "2026-04-24",
  "duration_minutes": 45,

  "questions": [
    {
      "question": "Implement a thread-safe Load Balancer",
      "your_approach": "Strategy pattern with ReentrantLock",
      "outcome": "completed",
      "feedback": "Good structure, could improve error handling",
      "areas_to_improve": ["Custom exceptions", "Edge case tests"]
    }
  ],

  "overall_score": 7,
  "strengths": ["Clean code", "Good communication"],
  "weaknesses": ["Thread safety gaps"],
  "next_focus": ["Practice concurrent data structures"]
}
```

## Session Types

| Type | Focus |
|------|-------|
| `coding` | Live coding problems (Load Balancer, URL Shortener, etc.) |
| `system-design` | Architecture, API design, database schemas |
| `behavioral` | STAR format answers, values alignment |
| `mock` | Full mock interview simulation |
