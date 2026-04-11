# mirrorwork

> Your career, reflected.

Career OS built on Claude Code. Track achievements, prep for interviews, search for jobs.

## Quick Start

```
/mirrorwork init    # Set up profile (paste resume)
/mirrorwork         # See status
/mirrorwork sync    # Regenerate storybank
/github sync        # Sync GitHub contributions
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  SOURCES (raw inputs)                                       │
│  ├── resume/latest.md      # Your resume text               │
│  ├── documents/*.pdf       # Work samples                   │
│  ├── research/*.md         # Company notes                  │
│  └── github/**/*.json      # GitHub API data                │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mirrorwork init
                      │ /mirrorwork ingest
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PROFILE (structured YAML)                                  │
│  ├── identity.yml          # Name, contact, links           │
│  ├── experience.yml        # Work history                   │
│  ├── education.yml         # Education                      │
│  ├── skills.yml            # Skills inventory               │
│  ├── positioning.yml       # Headline, target roles         │
│  ├── stories.yml           # STAR stories                   │
│  └── proof-points.yml      # Achievements with metrics      │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mirrorwork sync (auto via hooks)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STORYBANK (consolidated snapshot)                          │
│  └── storybank.yml         # Single file for agents         │
└─────────────────────────────────────────────────────────────┘
```

## Structure

```
cv.md                       # Master resume (markdown)
storybank.yml               # Consolidated profile (auto-generated)

profile/                    # WHO YOU ARE (structured)
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
├── storybank.md            # Regenerate storybank.yml
└── fit-agent.md            # Compare profile vs job

scripts/                    # Python tools
└── github_tracker/         # GitHub contribution CLI

.claude/                    # Claude Code config
├── skills/
│   ├── mirrorwork/SKILL.md # /mirrorwork command router
│   ├── mw/SKILL.md         # /mw shorthand alias
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
| `/mirrorwork` | Career OS main router |
| `/mw` | Shorthand for `/mirrorwork` |
| `/github` | GitHub contribution analysis |

## Agents

| Agent | Purpose | Trigger |
|-------|---------|---------|
| `ingest.md` | Route to specialized ingest | `/mirrorwork ingest` |
| `ingest-resume.md` | Parse resume → profile/ | `/mirrorwork init`, `ingest resume` |
| `ingest-job.md` | Parse JD → activity/jobs/ | `/mirrorwork ingest job` |
| `ingest-brag.md` | Capture achievement | `/mirrorwork ingest brag` |
| `storybank.md` | Consolidate profile | `/mirrorwork sync`, hooks |
| `fit-agent.md` | Build case for candidate | After job ingest |

## Storybank

`storybank.yml` is a consolidated snapshot of your entire profile.

**Auto-regenerated when:**
- Profile files change (`profile/*.yml`)
- GitHub data syncs (`sources/github/**/*.json`)

**Used by:**
- fit-agent (compare against jobs)
- interview agents (prep and practice)
- Any agent needing full context

## Hooks

Automated workflows triggered by file changes.

| Trigger | Action |
|---------|--------|
| Write to `profile/*.yml` | Regenerate storybank |
| Write to `sources/github/**` | Regenerate storybank |
| Write to `activity/jobs/*.yml` | Run fit analysis |

## Commands

| Command | Agent | Description |
|---------|-------|-------------|
| `/mirrorwork` | (inline) | Show status |
| `/mirrorwork init` | ingest-resume | First-time setup |
| `/mirrorwork sync` | storybank | Regenerate storybank |
| `/mirrorwork ingest` | ingest | Route to ingest type |
| `/mirrorwork ingest resume` | ingest-resume | Parse resume |
| `/mirrorwork ingest job` | ingest-job | Parse job description |
| `/mirrorwork ingest brag` | ingest-brag | Capture achievement |
| `/github sync` | (skill) | Sync GitHub data |
| `/github fetch` | (skill) | Fetch contributions |
| `/github story` | (skill) | Build org narrative |

## Conventions

- **YAML** for profile data (structured, editable)
- **JSON** for external/API data (GitHub)
- **Markdown** for narratives (cv.md, research notes)
- File names: `kebab-case.yml`
- IDs: `{company}-{slug}` (e.g., `dubizzle-latency-fix`)
- Dates: `YYYY-MM-DD` or `YYYY-MM`

## Principles

1. **Privacy first** — All data stays local
2. **Single source of truth** — storybank.yml for agents
3. **Progressive disclosure** — Simple by default, powerful when needed
4. **Separation of concerns** — Sources (raw) → Profile (structured) → Storybank (consolidated)
