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
│  ├── identity.json         # Name, contact, links           │
│  ├── experience.json       # Work history                   │
│  ├── skills.json           # Skills inventory               │
│  └── proof-points.json     # Achievements with metrics      │
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
├── identity.json           # Name, email, location, links
├── experience.json         # Work history with highlights
├── education.json          # Degrees, certifications
├── skills.json             # Expert/proficient/familiar
├── positioning.json        # Headline, target roles, superpowers
├── stories.json            # STAR format interview stories
└── proof-points.json       # Quantified achievements

activity/                   # WHAT'S HAPPENING
└── jobs/*.json             # Job descriptions + fit analysis

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
├── ingest-job.md           # JD → activity/jobs/ + brutal fit
├── ingest-brag.md          # Achievement → proof-points.yml
├── fit-analysis.md         # Brutal, honest fit check
├── case-agent.md           # Advocacy mode, build your case
└── dashboard.md            # Generate HTML dashboard

dashboard/                  # HTML dashboard
└── index.html              # Fetches JSON directly via JS

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

| Directory                 | Purpose               | Examples                              |
| ------------------------- | --------------------- | ------------------------------------- |
| `sources/resume/`         | Resume versions       | `latest.md` (auto-saved on ingest)    |
| `sources/documents/`      | Work samples          | Tech specs, presentations, designs    |
| `sources/research/`       | Research & notes      | Company research, job search strategy |
| `sources/github/reports/` | GitHub yearly data    | `2025.json`, `2026.json`              |
| `sources/github/stories/` | GitHub org narratives | `dubizzle.json`, `stripe.json`        |

## Profile

Structured JSON files generated from sources.

| File               | Purpose            | Key Fields                                    |
| ------------------ | ------------------ | --------------------------------------------- |
| `identity.json`    | Contact info       | name, email, location, linkedin, github       |
| `experience.json`  | Work history       | company, role, dates, highlights, skills      |
| `education.json`   | Education          | institution, degree, field, year              |
| `skills.json`      | Skills inventory   | expert, proficient, familiar, learning        |
| `positioning.json` | Career positioning | headline, target_roles, superpower            |
| `stories.json`     | Interview stories  | STAR format (situation, task, action, result) |
| `proof-points.json`| Achievements       | id, summary, metrics, skills, story_ready     |

## Skills

| Skill     | Purpose                      |
| --------- | ---------------------------- |
| `/mw`     | Career OS main router        |
| `/github` | GitHub contribution analysis |

## Agents

| Agent              | Purpose                     | Trigger                     |
| ------------------ | --------------------------- | --------------------------- |
| `ingest.md`        | Route to specialized ingest | `/mw ingest`                |
| `ingest-resume.md` | Parse resume → profile/     | `/mw init`, `ingest resume` |
| `ingest-job.md`    | Parse JD + brutal fit       | `/mw ingest job`            |
| `ingest-brag.md`   | Capture achievement         | `/mw ingest brag`           |
| `fit-analysis.md`  | Brutal, honest fit check    | Auto after job ingest       |
| `case-agent.md`    | Build advocacy case         | `/mw case <job-id>`         |
| `dashboard.md`     | Generate HTML dashboard     | `/mw dashboard`             |

### Two-Step Job Analysis

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
```

## Hooks

Automated workflows triggered by file changes.

| Trigger                         | Action           |
| ------------------------------- | ---------------- |
| Write to `activity/jobs/*.json` | Run fit analysis |

## Commands

| Command             | Agent         | Description             |
| ------------------- | ------------- | ----------------------- |
| `/mw`               | (inline)      | Show status             |
| `/mw init`          | ingest-resume | First-time setup        |
| `/mw ingest`        | ingest        | Route to ingest type    |
| `/mw ingest resume` | ingest-resume | Parse resume            |
| `/mw ingest job`    | ingest-job    | Parse JD + brutal fit   |
| `/mw ingest brag`   | ingest-brag   | Capture achievement     |
| `/mw case <job-id>` | case-agent    | Build advocacy case     |
| `/mw dashboard`     | (inline)      | Generate & open HTML    |
| `/github sync`      | (skill)       | Sync GitHub data        |
| `/github fetch`     | (skill)       | Fetch contributions     |
| `/github story`     | (skill)       | Build org narrative     |

## Conventions

- **JSON** for all structured data (profile, jobs, GitHub)
- **Markdown** for narratives (career.md, research notes)
- File names: `kebab-case.json`
- IDs: `{company}-{slug}` (e.g., `dubizzle-latency-fix`)
- Dates: `YYYY-MM-DD` or `YYYY-MM`

## Dashboard Design System

All apps use the **Terminal-Inspired Design System**. No exceptions.

### Core Principles

- Terminal/CLI aesthetic
- Light theme (Stone + Teal)
- Monospace everywhere
- Information density
- Dark inversion on hover

### Branding

- **Logo**: Reflected M (teal `#14b8a6` background, white stroke)
- **Tagline**: "Know where you stand."

### Colors

| Usage          | Class                              |
| -------------- | ---------------------------------- |
| Page           | `bg-stone-50`                      |
| Cards          | `bg-white border border-stone-200` |
| Primary text   | `text-stone-900`                   |
| Secondary text | `text-stone-500`                   |
| Muted          | `text-stone-400`                   |
| Success        | `text-teal-600`                    |
| Warning        | `text-yellow-600`                  |
| Error          | `text-rose-600`                    |

### Typography

- Font: `font-mono` (JetBrains Mono)
- Numbers: `tabular-nums`, zero-padded (`04`, `12`)
- Labels: `text-2xs uppercase tracking-wider text-stone-400`
- Section headers: `text-xs font-bold uppercase tracking-wider`
- Base size: `text-sm` (14px)

### Components

| Component        | Classes                                                      |
| ---------------- | ------------------------------------------------------------ |
| Primary button   | `bg-stone-900 text-white hover:bg-stone-800 rounded`         |
| Secondary button | `bg-white border border-stone-200 hover:bg-stone-50 rounded` |
| Card             | `bg-white border border-stone-200 rounded`                   |
| Input            | `bg-stone-50 border border-stone-200 rounded font-mono`      |

### Layout

```tsx
<div className="min-h-screen bg-stone-50 flex flex-col font-mono">
  <header className="bg-white border-b border-stone-200 h-10" />
  <main className="flex-1 py-8 px-4">
    <div className="max-w-4xl mx-auto">{/* content */}</div>
  </main>
  <footer className="bg-white border-t border-stone-200 h-10" />
</div>
```

### Terminal Elements

- Prompt: `<span className="text-stone-300">&gt;</span>`
- Separator: `<span className="text-stone-400">|</span>`
- Back: `← BACK`

### Dark Inversion Hover

```tsx
<button className="group hover:bg-stone-900 transition-colors">
  <span className="text-stone-900 group-hover:text-white">Text</span>
  <span className="text-teal-600 group-hover:text-teal-400">Accent</span>
</button>
```

## Principles

1. **Privacy first** — All data stays local
2. **Single source of truth** — profile/career.md as living narrative
3. **Progressive disclosure** — Simple by default, powerful when needed
4. **Separation of concerns** — Sources (raw) → Profile (structured) → Output (tailored)
