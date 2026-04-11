# mirrorwork

> Your career, reflected.

Career OS built on Claude Code. Track achievements, prep for interviews, search for jobs.

## Quick Start

```
/mw init           # Set up profile (paste resume)
/mw                # See status
/mw ingest resume  # Add another resume (merges into profile)
/github sync       # Sync GitHub contributions
```

## Core Concept

```
Resume₁ ──┐
Resume₂ ──┼──► Master Profile ──► Job Analysis ──► Derived Positioning
Resume₃ ──┘        (facts)          (fit)            (per job)
```

- **Profile** = who you are (facts, grows over time)
- **Positioning** = how you present yourself (derived per job)
- Each resume ADDS to your profile, never overwrites

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  SOURCES (raw inputs)                                       │
│  ├── resume/               # All ingested resumes           │
│  │   ├── manifest.json     # Tracks what's been ingested    │
│  │   ├── 2024-01-paste.md  # Resume v1                      │
│  │   └── 2026-04-file.md   # Resume v2                      │
│  ├── documents/*.pdf       # Work samples                   │
│  ├── research/*.md         # Company notes                  │
│  └── github/**/*.json      # GitHub API data                │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mw init, /mw ingest resume (MERGE)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PROFILE (master record - merged from all sources)          │
│  ├── identity.json         # Name, contact, links           │
│  ├── experience.json       # All roles (merged, deduped)    │
│  ├── skills.json           # All skills (union)             │
│  └── proof-points.json     # All achievements (merged)      │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mw ingest job
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  JOBS (per-job analysis + derived positioning)              │
│  └── activity/jobs/*.json                                   │
│      ├── requirements      # What they want                 │
│      ├── positioning       # DERIVED: how to present        │
│      └── fit               # Brutal honest assessment       │
└─────────────────────────────────────────────────────────────┘
```

## Structure

```
profile/                    # MASTER PROFILE (merged from all resumes)
├── identity.json           # Name, email, location, links
├── experience.json         # Work history (merged, deduped)
├── education.json          # Degrees, certifications
├── skills.json             # Expert/proficient/familiar (union)
└── proof-points.json       # Quantified achievements (merged)

activity/                   # JOBS + DERIVED POSITIONING
└── jobs/*.json             # Each job includes:
                            #   - requirements
                            #   - positioning (derived for THIS job)
                            #   - fit analysis

sources/                    # RAW INPUTS
├── resume/                 # All ingested resumes
│   ├── manifest.json       # Tracks ingested resumes
│   ├── 2024-01-paste.md    # Resume v1
│   └── 2026-04-file.md     # Resume v2 (adds to profile)
├── documents/              # Work samples, tech specs
├── research/               # Company research, strategy notes
└── github/                 # GitHub API data
    ├── reports/            # Yearly contribution summaries
    └── stories/            # Per-organization narratives

agents/                     # Agent instructions (markdown)
├── ingest.md               # Ingest router
├── ingest-resume.md        # Resume → MERGE into profile
├── ingest-job.md           # JD → job file + derived positioning + fit
├── ingest-brag.md          # Achievement → proof-points.json
├── fit-analysis.md         # Brutal, honest fit check
└── case-agent.md           # Advocacy mode, build your case

scripts/                    # Python tools
└── github_tracker/         # GitHub contribution CLI

.claude/                    # Claude Code config
├── skills/
│   ├── mw/SKILL.md         # /mw command router
│   └── github/SKILL.md     # /github command router
├── hooks.json              # Workflow automation
└── settings.json           # Permissions
```

## Multi-Resume Flow

Each `/mw ingest resume` MERGES into the master profile:

```
Resume 1 (2024)          Resume 2 (2026)
├── 3 roles              ├── 4 roles (1 new, 3 overlap)
├── 10 skills            ├── 12 skills (5 new, 7 overlap)
└── 2 proof points       └── 4 proof points (2 new)
        │                        │
        └────────┬───────────────┘
                 ▼
         Master Profile
         ├── 4 roles (merged)
         ├── 15 skills (union, tiers upgraded)
         └── 4 proof points (merged)
```

**Merge rules:**
- **Experience:** Dedup by (company, role, start_date). Merge highlights.
- **Skills:** Union. Upgrade tiers (familiar → proficient → expert).
- **Proof Points:** Dedup by id. Merge metrics.

## Profile Files

| File               | Purpose            | Key Fields                                |
| ------------------ | ------------------ | ----------------------------------------- |
| `identity.json`    | Contact info       | name, email, location, linkedin, github   |
| `experience.json`  | Work history       | company, role, dates, highlights, skills  |
| `education.json`   | Education          | institution, degree, field, year          |
| `skills.json`      | Skills inventory   | expert, proficient, familiar, learning    |
| `proof-points.json`| Achievements       | id, summary, metrics, skills, story_ready |

**Note:** No `positioning.json` — positioning is derived per job.

## Job Files

Each job in `activity/jobs/*.json` contains:

```json
{
  "id": "stripe-staff-backend",
  "company": "Stripe",
  "title": "Staff Backend Engineer",
  "requirements": { "must_have": [...], "nice_to_have": [...] },

  "positioning": {
    "headline": "10-year backend engineer scaling transaction systems",
    "angle": "Ad-tech scale → financial reliability",
    "lead_with": ["1B+ events/day", "P95 ≤5ms"],
    "relevant_experience": ["Snapdeal", "Cisco"],
    "relevant_proof_points": ["snapdeal-ad-pipeline"]
  },

  "fit": {
    "score": 85,
    "matches": [...],
    "gaps": [...],
    "verdict": "Strong technical fit"
  }
}
```

## Agents

| Agent              | Purpose                     | Trigger                     |
| ------------------ | --------------------------- | --------------------------- |
| `ingest.md`        | Route to specialized ingest | `/mw ingest`                |
| `ingest-resume.md` | Parse resume → MERGE        | `/mw init`, `ingest resume` |
| `ingest-job.md`    | JD + derive positioning     | `/mw ingest job`            |
| `ingest-brag.md`   | Capture achievement         | `/mw ingest brag`           |
| `fit-analysis.md`  | Brutal, honest fit check    | Auto after job ingest       |
| `case-agent.md`    | Build advocacy case         | `/mw case <job-id>`         |

## Two-Step Job Analysis

```
/mw ingest job              /mw case <job-id>
      │                            │
      ▼                            ▼
┌─────────────┐             ┌─────────────┐
│ FIT ANALYSIS│             │ MAKE A CASE │
│             │             │             │
│ • Brutal    │     ──►     │ • Advocate  │
│ • Honest    │  (if you    │ • Reframe   │
│ • Binary    │   decide    │ • Story     │
│             │  to apply)  │             │
│ "Do I meet  │             │ "How do I   │
│  the reqs?" │             │  position?" │
└─────────────┘             └─────────────┘

Positioning is DERIVED during /mw ingest job
based on master profile + job requirements
```

## Commands

| Command             | Agent         | Description                    |
| ------------------- | ------------- | ------------------------------ |
| `/mw`               | (inline)      | Show status                    |
| `/mw init`          | ingest-resume | First-time setup               |
| `/mw ingest resume` | ingest-resume | Add resume (merges)            |
| `/mw ingest job`    | ingest-job    | Add job + derive positioning   |
| `/mw ingest brag`   | ingest-brag   | Capture achievement            |
| `/mw case <job-id>` | case-agent    | Build advocacy case            |
| `/github sync`      | (skill)       | Sync GitHub data               |

## Hooks

| Trigger                         | Action           |
| ------------------------------- | ---------------- |
| Write to `activity/jobs/*.json` | Run fit analysis |

## Conventions

- **JSON** for all structured data (profile, jobs, GitHub)
- **Markdown** for narratives (career.md, research notes)
- File names: `kebab-case.json`
- IDs: `{company}-{slug}` (e.g., `dubizzle-latency-fix`)
- Dates: `YYYY-MM-DD` or `YYYY-MM`
- Resume files: `{YYYY-MM-DD}-{source}.md`

## Principles

1. **Privacy first** — All data stays local
2. **Accumulate, don't overwrite** — Each resume adds to master profile
3. **Positioning is contextual** — Derived per job, not global
4. **Brutal honesty first** — Fit analysis before advocacy
