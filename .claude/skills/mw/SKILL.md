# Mirrorwork — Career OS

Your career, reflected.

## UX Guidelines

Always use rich formatting for a polished terminal experience:

- **Box borders** for headers: `╭───╮ │ │ ╰───╯`
- **Separators** between sections: `───────────────────────────────────────`
- **Icons** for status: `✓` success, `⏳` loading, `→` actions
- **Bullets** for lists: `•`

## Commands

On EVERY invocation, first check if `profile/identity.json` exists.

If file does not exist, show welcome:

```
╭─────────────────────────────────────╮
│  mirrorwork                         │
│  Your career, reflected.            │
╰─────────────────────────────────────╯

Welcome! I don't have your profile yet.

→ Run `/mw init` to get started
```

### Available Commands

#### `/mw` (no args)

Show current status:
1. Check if `profile/identity.json` exists
2. If NO → show welcome message above
3. If YES → read profile files and show rich status dashboard:

```
╭─────────────────────────────────────╮
│  mirrorwork · {Name}                │
╰─────────────────────────────────────╯

**{Current Role}** at {Company}
{Location}

───────────────────────────────────────
📊 **Profile**

• Experience: {X} years across {Y} companies
• Skills: {top 3 expert skills}
• Proof points: {count}
• Resumes ingested: {count from manifest}

───────────────────────────────────────
🎯 **Job Pipeline**

• {count} jobs tracked
• {count} with fit analysis

───────────────────────────────────────
**Quick actions**

→ `/mw ingest resume` — Add another resume
→ `/mw ingest brag` — Add achievement
→ `/mw ingest job` — Track a job
→ `/github sync` — Sync GitHub
```

#### `/mw init`

First-time setup. Read `agents/ingest-resume.md` and follow its instructions.

#### `/mw status`

Same as `/mw` with no args.

---

### Ingest Commands

#### `/mw ingest`

Router for ingesting career data.

Read `agents/ingest.md` and follow its instructions.

#### `/mw ingest resume`

Parse a resume and create/update profile.

Read `agents/ingest-resume.md` and follow its instructions.

#### `/mw ingest job`

Parse a job description and add to pipeline.

Read `agents/ingest-job.md` and follow its instructions.

#### `/mw ingest brag`

Capture a professional achievement.

Read `agents/ingest-brag.md` and follow its instructions.

---

### Case Commands

#### `/mw case <job-id>`

Build the strongest case for a job you want to apply to.

**Prerequisites:** Job must exist in `activity/jobs/` with fit analysis completed.

Read `agents/case-agent.md` and follow its instructions.

If no job-id provided, list available jobs:
```
───────────────────────────────────────
📋 **Jobs in pipeline**

| ID | Company | Title | Fit |
|----|---------|-------|-----|
| unison-group-senior-java | Unison Group | Senior Java Backend | 65% |

Which job? Enter the ID:
```

---

### Planned Commands

| Command | Purpose | Status |
|---------|---------|--------|
| `/mw reflect` | Weekly reflection | Planned |
| `/mw feedback` | Digest feedback | Planned |
| `/mw prep` | Interview prep | Planned |
| `/mw interview` | Interview practice | Planned |

---

## Data Model

```
profile/                    # MASTER PROFILE (merged from all resumes)
├── identity.json           # Name, contact, links
├── experience.json         # Work history (merged, deduped)
├── education.json          # Degrees, certifications
├── skills.json             # Skills (union of all resumes)
└── proof-points.json       # Achievements (merged)

activity/
└── jobs/*.json             # Job + DERIVED positioning + fit analysis

sources/                    # RAW INPUTS
├── resume/                 # All ingested resumes
│   ├── manifest.json       # Tracks what's been ingested
│   └── {date}-{source}.md  # Individual resume files
├── documents/              # Work samples, tech specs
├── research/               # Company notes, strategy
└── github/                 # GitHub API data
    ├── reports/            # Yearly: 2025.json
    └── stories/            # Per-org: dubizzle.json

output/
└── {year}/                 # Tailored resumes, cover letters
```

**Note:** No `positioning.json` — positioning is derived per job during `/mw ingest job`.

## Agent Routing

| Command | Agent | Purpose |
|---------|-------|---------|
| `init` | `agents/ingest-resume.md` | Setup profile |
| `ingest` | `agents/ingest.md` | Route to ingest type |
| `ingest resume` | `agents/ingest-resume.md` | Parse resume |
| `ingest job` | `agents/ingest-job.md` | Parse JD + brutal fit |
| `ingest brag` | `agents/ingest-brag.md` | Capture achievement |
| `case` | `agents/case-agent.md` | Build advocacy case |

## Two-Step Job Analysis

```
/mw ingest job          /mw case <job-id>
      │                        │
      ▼                        ▼
┌─────────────┐         ┌─────────────┐
│ FIT ANALYSIS│         │ MAKE A CASE │
│             │         │             │
│ • Brutal    │         │ • Advocate  │
│ • Honest    │         │ • Reframe   │
│ • Binary    │         │ • Story     │
│             │         │             │
│ "Do I meet  │         │ "How do I   │
│  the reqs?" │         │  position?" │
└─────────────┘         └─────────────┘
```
