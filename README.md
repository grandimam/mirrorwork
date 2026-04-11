# mirrorwork

> Your career, reflected.

A career OS built on Claude Code. Track achievements, prep for interviews, search for jobs — all from one place.

## Quick Start

```bash
claude
> /mirrorwork init    # Set up your profile (paste resume)
> /mirrorwork         # See status (or /mw for short)
> /github sync        # Sync GitHub contributions
```

## Features

- **Resume Parsing** — Paste or upload resume, extract structured profile
- **Job Tracking** — Save job descriptions, get fit analysis
- **Achievement Capture** — Log proof points with metrics
- **GitHub Integration** — Pull contribution data to enrich profile
- **Fit Analysis** — AI builds your strongest case for each role
- **Storybank** — Consolidated profile for interview prep

## Structure

```
cv.md                       # Master resume
storybank.yml               # Consolidated profile (auto-generated)

profile/                    # WHO YOU ARE (structured YAML)
├── identity.yml            # Name, contact, links
├── experience.yml          # Work history with highlights
├── education.yml           # Degrees, certifications
├── skills.yml              # Expert/proficient/familiar
├── positioning.yml         # Headline, target roles
├── stories.yml             # STAR interview stories
└── proof-points.yml        # Quantified achievements

activity/                   # WHAT'S HAPPENING
└── jobs/*.yml              # Job descriptions + fit analysis

sources/                    # RAW INPUTS
├── resume/                 # Resume versions
│   └── latest.md
├── documents/              # Work samples, tech specs
├── research/               # Company notes, strategy
└── github/                 # GitHub API data
    ├── reports/            # Yearly contributions
    └── stories/            # Per-org narratives

agents/                     # Agent instructions
scripts/github_tracker/     # GitHub CLI tool
.claude/                    # Skills, hooks, config
```

## Commands

### Core

| Command            | Description                     |
| ------------------ | ------------------------------- |
| `/mirrorwork`      | Show profile status             |
| `/mirrorwork init` | First-time setup (parse resume) |
| `/mirrorwork sync` | Regenerate storybank            |

### Ingest

| Command                     | Description                        |
| --------------------------- | ---------------------------------- |
| `/mirrorwork ingest`        | Choose what to ingest              |
| `/mirrorwork ingest resume` | Parse resume into profile          |
| `/mirrorwork ingest job`    | Add job description + fit analysis |
| `/mirrorwork ingest brag`   | Capture achievement                |

### GitHub

| Command         | Description                      |
| --------------- | -------------------------------- |
| `/github sync`  | Sync all GitHub data             |
| `/github fetch` | Fetch yearly contributions       |
| `/github story` | Build org contribution narrative |
| `/github orgs`  | List organizations               |

## Data Flow

```
Sources (raw)  →  Profile (structured)  →  Storybank (consolidated)
     ↑                    ↑                        ↓
  /ingest            auto-generated           agents read
```

**Hooks auto-trigger:**

- Profile changes → regenerate storybank
- GitHub sync → regenerate storybank
- Job added → run fit analysis

## Fit Agent

The fit agent is your advocate. It doesn't judge — it builds your strongest case.

**Outputs:**

- Career narrative connecting you to the role
- Strongest matches with proof points
- Gap reframes as transferable skills
- Cover letter hooks & interview talking points
- Resume rewrites using company's language
- Red flag responses prepared

## Philosophy

1. **Privacy first** — All data local, no external services
2. **Advocate, not judge** — Agents build your case, not evaluate you
3. **Sources of truth** — Raw inputs → structured profile → consolidated storybank
4. **Progressive disclosure** — Simple by default, powerful when needed

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3.10+ (for GitHub tracker)
- `gh` CLI authenticated (for GitHub features)

## License

MIT
