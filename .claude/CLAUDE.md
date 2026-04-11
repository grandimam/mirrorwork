# mirrorwork

> Your career, reflected.

Career OS built on Claude Code. Track achievements, prep for interviews, search for jobs.

## Quick Start

```
/mw init           # Set up profile (paste resume)
/mw                # See status
/github sync       # Sync GitHub contributions
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  SOURCES (raw inputs)                                       │
│  ├── resume/*.pdf          # Uploaded resume files          │
│  ├── documents/*.pdf       # Work samples                   │
│  ├── research/*.md         # Company notes                  │
│  └── github/**/*.json      # GitHub API data                │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mw init
                      │ /mw ingest
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PROFILE (who you are)                                      │
│  ├── career.md             # Living narrative (grows)       │
│  ├── identity.yml          # Name, contact, links           │
│  ├── experience.yml        # Work history                   │
│  ├── skills.yml            # Skills inventory               │
│  └── proof-points.yml      # Achievements with metrics      │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mw prep, fit-agent
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  OUTPUT (generated artifacts)                               │
│  └── {year}/               # Tailored resumes, cover letters│
└─────────────────────────────────────────────────────────────┘
```

## Structure

```
profile/                    # WHO YOU ARE
├── career.md               # Living career narrative (grows over time)
├── identity.yml            # Name, email, location, links
├── experience.yml          # Work history with highlights
├── education.yml           # Degrees, certifications
├── skills.yml              # Expert/proficient/familiar
├── positioning.yml         # Headline, target roles, superpowers
├── stories.yml             # STAR format interview stories
└── proof-points.yml        # Quantified achievements

activity/                   # WHAT'S HAPPENING
└── jobs/*.yml              # Job descriptions + fit analysis

sources/                    # RAW INPUTS
├── resume/                 # Resume versions
│   └── latest.md           # Current resume (auto-saved on ingest)
├── documents/              # Work samples, tech specs, presentations
├── research/               # Company research, strategy notes
└── github/                 # GitHub API data
    ├── reports/            # Yearly contribution summaries
    │   └── {year}.json     # e.g., 2025.json
    └── stories/            # Per-organization narratives
        └── {org}.json      # e.g., dubizzle.json

agents/                     # Agent instructions (markdown)
├── ingest.md               # Ingest router
├── ingest-resume.md        # Resume → profile/
├── ingest-job.md           # JD → activity/jobs/ + fit
├── ingest-brag.md          # Achievement → proof-points.yml
└── fit-agent.md            # Compare profile vs job

scripts/                    # Python tools
└── github_tracker/         # GitHub contribution CLI

.claude/                    # Claude Code config
├── skills/
│   ├── mw/SKILL.md         # /mw command router
│   └── github/SKILL.md     # /github command router
├── hooks.json              # Workflow automation
└── settings.json           # Permissions
```

## Sources

Raw inputs that feed into your structured profile.

| Directory | Purpose | Examples |
|-----------|---------|----------|
| `sources/resume/` | Resume versions | `latest.md` (auto-saved on ingest) |
| `sources/documents/` | Work samples | Tech specs, presentations, designs |
| `sources/research/` | Research & notes | Company research, job search strategy |
| `sources/github/reports/` | GitHub yearly data | `2025.json`, `2026.json` |
| `sources/github/stories/` | GitHub org narratives | `dubizzle.json`, `stripe.json` |

## Profile

Structured YAML files generated from sources.

| File | Purpose | Key Fields |
|------|---------|------------|
| `identity.yml` | Contact info | name, email, location, linkedin, github |
| `experience.yml` | Work history | company, role, dates, highlights, skills |
| `education.yml` | Education | institution, degree, field, year |
| `skills.yml` | Skills inventory | expert, proficient, familiar, learning |
| `positioning.yml` | Career positioning | headline, target_roles, superpower |
| `stories.yml` | Interview stories | STAR format (situation, task, action, result) |
| `proof-points.yml` | Achievements | id, summary, metrics, skills, story_ready |

## Skills

| Skill | Purpose |
|-------|---------|
| `/mw` | Career OS main router |
| `/github` | GitHub contribution analysis |

## Agents

| Agent | Purpose | Trigger |
|-------|---------|---------|
| `ingest.md` | Route to specialized ingest | `/mw ingest` |
| `ingest-resume.md` | Parse resume → profile/ | `/mw init`, `ingest resume` |
| `ingest-job.md` | Parse JD → activity/jobs/ | `/mw ingest job` |
| `ingest-brag.md` | Capture achievement | `/mw ingest brag` |
| `fit-agent.md` | Build case for candidate | After job ingest |

## Hooks

Automated workflows triggered by file changes.

| Trigger | Action |
|---------|--------|
| Write to `activity/jobs/*.yml` | Run fit analysis |

## Commands

| Command | Agent | Description |
|---------|-------|-------------|
| `/mw` | (inline) | Show status |
| `/mw init` | ingest-resume | First-time setup |
| `/mw ingest` | ingest | Route to ingest type |
| `/mw ingest resume` | ingest-resume | Parse resume |
| `/mw ingest job` | ingest-job | Parse job description |
| `/mw ingest brag` | ingest-brag | Capture achievement |
| `/github sync` | (skill) | Sync GitHub data |
| `/github fetch` | (skill) | Fetch contributions |
| `/github story` | (skill) | Build org narrative |

## Conventions

- **YAML** for profile data (structured, editable)
- **JSON** for external/API data (GitHub)
- **Markdown** for narratives (career.md, research notes)
- File names: `kebab-case.yml`
- IDs: `{company}-{slug}` (e.g., `dubizzle-latency-fix`)
- Dates: `YYYY-MM-DD` or `YYYY-MM`

## Principles

1. **Privacy first** — All data stays local
2. **Single source of truth** — profile/career.md as living narrative
3. **Progressive disclosure** — Simple by default, powerful when needed
4. **Separation of concerns** — Sources (raw) → Profile (structured) → Output (tailored)
