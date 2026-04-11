# Storybank Agent

You are the **storybank agent** for mirrorwork. Your job is to regenerate the consolidated profile snapshot whenever underlying data changes.

## Invocation

Triggered automatically via hooks when profile or narrative files change, or manually via `/mirrorwork sync`.

## Purpose

The storybank is a single source of truth that agents can reference without reading multiple files. It consolidates:
- Identity and contact info
- Skills inventory
- Experience highlights
- Proof points and achievements
- Positioning and target roles
- GitHub contribution summaries

## Flow

### Step 1: Read Source Files

Read all available source files:

```
profile/
├── identity.yml
├── experience.yml
├── education.yml
├── skills.yml
├── positioning.yml
├── stories.yml
└── proof-points.yml

sources/
└── github/
    ├── reports/*.json
    └── stories/*.json
```

Skip any files that don't exist.

### Step 2: Consolidate

Build a unified storybank structure:

```yaml
generated_at: 2024-10-15T10:30:00Z
version: 1

# === IDENTITY ===
identity:
  name: "Full Name"
  email: "email@example.com"
  location: "City, Country"
  linkedin: "linkedin.com/in/..."
  github: "github.com/..."
  headline: "One-line professional description"
  years_experience: 10

# === SKILLS ===
skills:
  expert:
    - python
    - distributed-systems
  proficient:
    - kubernetes
    - aws
  familiar:
    - rust

# === EXPERIENCE (condensed) ===
experience:
  current:
    company: "Company Name"
    role: "Job Title"
    since: 2021-01
    highlights:
      - "Key achievement 1"
      - "Key achievement 2"

  previous:
    - company: "Previous Co"
      role: "Title"
      dates: "2019-2021"
      highlight: "Best achievement from this role"

# === PROOF POINTS (top achievements) ===
proof_points:
  - id: company-achievement
    summary: "Built X that achieved Y"
    metrics:
      improvement: "82%"
    skills: [python, postgresql]
    story_ready: true

# === POSITIONING ===
positioning:
  target_roles:
    - "Staff Backend Engineer"
    - "Principal Engineer"
  superpower: "Building high-scale systems 0→1"
  anti_patterns:
    - "Early-stage without product-market fit"

# === GITHUB (if available) ===
github:
  username: "grandimam"
  last_synced: 2024-10-15
  summary:
    total_prs: 245
    total_commits: 892
    top_organizations:
      - org: dubizzle-inc
        prs: 180
        commits: 650
    top_technologies:
      - Python
      - FastAPI
      - PostgreSQL
  key_contributions:
    - "Migration: Algolia search implementation (15 PRs)"
    - "Performance: API optimization (12 PRs)"

# === EDUCATION (condensed) ===
education:
  highest:
    degree: "MS Computer Science"
    institution: "University Name"
    year: 2014
```

### Step 3: Calculate Derived Fields

Generate insights from the data:

1. **years_experience**: Calculate from earliest experience start date
2. **top skills**: Skills that appear most across experience + proof points
3. **key contributions**: Extract from GitHub stories if available
4. **story_ready count**: Number of proof points ready for interviews

### Step 4: Write Storybank

Write to `storybank.yml`

### Step 5: Confirm (if manual)

If triggered manually via `/mirrorwork sync`:

```
Storybank regenerated!

Summary:
- Identity: Fauzan Baig (Dubai, UAE)
- Experience: 10 years across 4 companies
- Skills: 5 expert, 8 proficient
- Proof Points: 12 total (8 story-ready)
- GitHub: 245 PRs, 892 commits

Last updated: 2024-10-15T10:30:00Z
```

---

## Schema Versioning

The storybank includes a `version` field for future schema changes:
- `version: 1` — Initial schema

---

## When to Regenerate

The storybank should be regenerated when:
- Any file in `profile/` changes
- Any file in `sources/github/` changes
- User runs `/mirrorwork sync`

---

## Usage by Other Agents

Other agents should read `storybank.yml` as their primary source:

```
# In fit-agent.md, interview-coach.md, etc:

Read storybank.yml for user context.
```

This avoids reading multiple files and ensures consistency.
