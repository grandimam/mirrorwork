# Mirrorwork — Career OS

Your career, reflected.

## Commands

On EVERY invocation, first check if `profile/identity.yml` exists.

If file does not exist:

```
> "Welcome to mirrorwork! I don't have your profile yet.
>
> Run `/mw init` to get started."
```

### Available Commands

#### `/mw` (no args)

Show current status:
1. Check if `profile/identity.yml` exists
2. If NO → prompt to run `/mw init`
3. If YES → read `profile/career.md` and `profile/identity.yml`, show summary:
   - Name, current role, target roles
   - Proof points count
   - Jobs in pipeline count
   - GitHub stats (if synced)

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
profile/                    # WHO YOU ARE
├── career.md               # Living career narrative (grows over time)
├── identity.yml
├── experience.yml
├── education.yml
├── skills.yml
├── positioning.yml         # Headline, target roles, superpowers
├── stories.yml             # STAR stories
└── proof-points.yml        # Achievements with metrics

activity/
└── jobs/*.yml              # Job descriptions + fit analysis

output/
└── {year}/                 # Tailored resumes, cover letters

sources/                    # RAW INPUTS
├── resume/                 # Uploaded resume files (PDF, DOCX)
├── documents/              # Work samples, tech specs
├── research/               # Company notes, strategy
└── github/                 # GitHub API data
    ├── reports/            # Yearly: 2025.json
    └── stories/            # Per-org: dubizzle.json
```

## Agent Routing

| Command | Agent |
|---------|-------|
| `init` | `agents/ingest-resume.md` |
| `ingest` | `agents/ingest.md` |
| `ingest resume` | `agents/ingest-resume.md` |
| `ingest job` | `agents/ingest-job.md` |
| `ingest brag` | `agents/ingest-brag.md` |
