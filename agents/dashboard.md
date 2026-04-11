# Dashboard Agent

Generate and open the mirrorwork HTML dashboard.

## Invocation

Called by `/mw dashboard`.

## Flow

### Step 1: Load Data

Read all profile and job files:

```
profile/identity.yml      → name, email, location
profile/positioning.yml   → headline, years_experience
profile/experience.yml    → list of companies
profile/skills.yml        → expert, proficient, familiar
profile/proof-points.yml  → achievements list
activity/jobs/*.yml       → all job files with fit data
```

### Step 2: Build Data Object

Create a JSON object:

```json
{
  "profile": {
    "name": "From identity.yml or 'Unknown'",
    "headline": "From positioning.yml",
    "years": "From positioning.yml years_experience"
  },
  "stats": {
    "companies": "Count of experience.yml entries",
    "proofs": "Count of proof-points.yml entries",
    "jobs": "Count of job files",
    "skills": ["top", "3", "expert", "skills"]
  },
  "jobs": [
    {
      "id": "job-id",
      "company": "Company Name",
      "title": "Job Title",
      "status": "saved",
      "fit_score": 68,
      "matches": ["match1", "match2"],
      "gaps": ["gap1"],
      "deal_breakers": ["deal-breaker1"],
      "verdict": "Summary text"
    }
  ],
  "proofs": [
    {
      "id": "proof-id",
      "summary": "Achievement summary",
      "company": "Company",
      "date": "2024-03",
      "metrics": {"volume": "1B+"},
      "skills": ["skill1", "skill2"]
    }
  ]
}
```

### Step 3: Generate HTML

1. Read `dashboard/index.html` template
2. Replace `__MIRRORWORK_DATA__` with the JSON object (properly formatted)
3. Write to `dashboard/index.html`

### Step 4: Open in Browser

```bash
open dashboard/index.html
```

On Linux use `xdg-open`, on Windows use `start`.

### Step 5: Confirm

```
╭─────────────────────────────────────╮
│  ✓ Dashboard generated!             │
╰─────────────────────────────────────╯

Opened: dashboard/index.html

Auto-refresh: 5 seconds
Run `/mw dashboard` again to update after changes.
```

## Notes

- Jobs are sorted by fit_score descending
- Only show top 8 proof points
- Only show top 3 skills in stats
- Truncate long text in gaps/matches arrays
