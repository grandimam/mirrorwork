# Mirrorwork

> Your career, reflected.

Career OS built on Claude Code. Track achievements, prep for interviews, search for jobs.

```
Resume₁ ──┐
Resume₂ ──┼──► Master Profile ──► Job Analysis ──► Derived Positioning
Resume₃ ──┘        (facts)          (fit)            (per job)
```

- **Profile** = who you are (facts, grows over time)
- **Positioning** = how you present yourself (derived per job)
- Each resume ADDS to your profile, never overwrites

## Structure

```
profile/                    # MASTER PROFILE (merged from all resumes)
├── identity.json           # Name, email, location, links
├── experience.json         # Work history (merged, deduped)
├── education.json          # Degrees, certifications
├── skills.json             # Expert/proficient/familiar (union)
└── proof-points.json       # Quantified achievements (merged)

activity/                   # JOBS + PIPELINE
├── manifest.json           # Portals config for scanning
├── tracker.md              # Applications tracker (unified view)
├── inbox/                  # All discovered jobs (by date)
│   └── {date}.json         # matched + filtered jobs for dedup
└── jobs/*.json             # Analyzed jobs

sources/                    # RAW INPUTS
├── manifest.json           # Central registry (tracks all files)
├── resume/                 # All resumes
│   └── {date}-{source}.md  # e.g., 2026-04-11-backend.md
└── work-samples/           # Tech specs, design docs, RFCs
    └── *.pdf, *.md

agents/                     # Agent instructions (markdown)
├── scan.md                 # Discover jobs from portals
├── inbox.md                # Review discovered jobs
├── tracker.md              # View/update applications tracker
├── add-resume.md           # Resume → MERGE into profile
├── add-job.md              # JD → job file + positioning + fit
├── add-brag.md             # Achievement → proof-points.json
├── add-doc.md              # Tech spec → proof points + skills
├── fit-analysis.md         # Brutal, honest fit check
├── case-agent.md           # Advocacy mode, build your case
└── generate-resume.md      # Generate tailored resumes

generated/                  # GENERATED ARTIFACTS
└── {job-id}/               # Per-job output folder
    └── {date}-resume.md    # Tailored resume

scripts/                    # Python tools
└── github_tracker/         # GitHub contribution CLI

.claude/                    # Claude Code config
├── skills/
│   ├── mw/SKILL.md         # /mw command router
│   └── github/SKILL.md     # /github command router
├── hooks.json              # Workflow automation
└── settings.json           # Permissions
```

### Profile

| File                | Purpose          | Key Fields                                |
| ------------------- | ---------------- | ----------------------------------------- |
| `identity.json`     | Contact info     | name, email, location, linkedin, github   |
| `experience.json`   | Work history     | company, role, dates, highlights, skills  |
| `education.json`    | Education        | institution, degree, field, year          |
| `skills.json`       | Skills inventory | expert, proficient, familiar, learning    |
| `proof-points.json` | Achievements     | id, summary, metrics, skills, story_ready |

**Note:** No `positioning.json` — positioning is derived per job.

### Job

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

### Sources Manifest

All source files are tracked in `sources/manifest.json`:

```json
{
  "files": [
    {
      "path": "resume/2026-04-11-backend.md",
      "type": "resume",
      "label": "Backend-focused resume",
      "added_at": "2026-04-11",
      "status": "processed",
      "extracted": {
        "experience": 4,
        "skills": 15,
        "proof_points": 3
      }
    },
    {
      "path": "work-samples/payment-rfc.pdf",
      "type": "tech-spec",
      "label": "Payment gateway design doc",
      "added_at": "2026-04-11",
      "status": "pending",
      "extracted": null
    }
  ]
}
```

| Field       | Purpose                                                         |
| ----------- | --------------------------------------------------------------- |
| `path`      | Relative to `sources/`                                          |
| `type`      | `resume`, `tech-spec`, `case-study`, `code-sample`              |
| `label`     | User-provided description                                       |
| `added_at`  | When file was added                                             |
| `status`    | `processed` / `failed` (processed immediately on add)           |
| `extracted` | What was pulled out (type-specific, populated after processing) |

## Agents

| Agent                | Purpose                    | Trigger                  |
| -------------------- | -------------------------- | ------------------------ |
| `scan.md`            | Discover jobs from portals | `/mw scan`               |
| `inbox.md`           | Review discovered jobs     | `/mw inbox`              |
| `tracker.md`         | View/update tracker        | `/mw tracker`            |
| `add-resume.md`      | Parse resume → MERGE       | `/mw init`, `add resume` |
| `add-job.md`         | JD + derive positioning    | `/mw add job [url]`      |
| `add-brag.md`        | Capture achievement        | `/mw add brag`           |
| `add-doc.md`         | Tech spec → proof points   | `/mw add doc`            |
| `fit-analysis.md`    | Brutal, honest fit check   | Auto after add job       |
| `case-agent.md`      | Build advocacy case        | `/mw case <job-id>`      |
| `generate-resume.md` | Generate tailored resume   | `/mw resume <job-id>`    |

## Features

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  SOURCES (raw inputs)                                       │
│  ├── manifest.json         # Central registry of all files  │
│  ├── resume/               # All resumes                    │
│  │   ├── 2024-01-paste.md  # Resume v1                      │
│  │   └── 2026-04-file.md   # Resume v2                      │
│  └── work-samples/         # Tech specs, design docs        │
│      └── *.pdf, *.md                                        │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mw add <type> (MERGE)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PROFILE (master record - merged from all sources)          │
│  ├── identity.json         # Name, contact, links           │
│  ├── experience.json       # All roles (merged, deduped)    │
│  ├── skills.json           # All skills (union)             │
│  └── proof-points.json     # All achievements (merged)      │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mw add job
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  JOBS (per-job analysis + derived positioning)              │
│  └── activity/jobs/*.json                                   │
│      ├── requirements      # What they want                 │
│      ├── positioning       # DERIVED: how to present        │
│      └── fit               # Brutal honest assessment       │
└─────────────────────────────────────────────────────────────┘
```

### Multi-Resume Flow

Each `/mw add resume` MERGES into the master profile:

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

**Workflow:**

1. User runs `/mw add <type>` (resume, job, brag, doc)
2. Agent prompts for file/content
3. File saved to `sources/`, registered in manifest
4. Parsed immediately → merged into profile
5. Manifest updated with `extracted` details

### Pipeline Flow

```
/mw scan                    /mw inbox                   /mw add job
    │                           │                           │
    ▼                           ▼                           ▼
┌─────────────┐           ┌─────────────┐           ┌─────────────┐
│ DISCOVER    │           │ REVIEW      │           │ ANALYZE     │
│             │           │             │           │             │
│ • Fetch     │──────────►│ • Pending   │──────────►│ • Parse JD  │
│   portals   │           │   jobs      │           │ • Fit check │
│ • Dedup     │           │ • Add/Skip  │           │ • Position  │
│ • Filter    │           │             │           │             │
└─────────────┘           └─────────────┘           └─────────────┘
       │                                                   │
       ▼                                                   ▼
activity/inbox/                                      activity/jobs/
(all jobs: matched + filtered)
```

**Portals config** (`activity/manifest.json`):

```json
{
  "portals": [
    {
      "name": "Careem",
      "url": "https://jobs.careem.com/",
      "location": "United Arab Emirates, Remote",
      "target_roles": ["backend", "platform", "senior"],
      "last_scan": "2026-04-12",
      "enabled": true
    }
  ]
}
```

| Field          | Purpose                       |
| -------------- | ----------------------------- |
| `name`         | Display name                  |
| `url`          | Careers page URL              |
| `location`     | Target location               |
| `target_roles` | Keywords to filter job titles |
| `last_scan`    | When last scanned             |
| `enabled`      | Include in scans              |

**Inbox file** (`activity/inbox/{date}.json`):

```json
{
  "date": "2026-04-12",
  "jobs": [
    {
      "url": "https://...",
      "portal": "Talabat",
      "title": "Senior Backend Engineer",
      "matched": true,
      "status": "pending"
    },
    {
      "url": "https://...",
      "portal": "Talabat",
      "title": "Office Manager",
      "matched": false,
      "status": "filtered"
    }
  ]
}
```

| Field     | Values                                                |
| --------- | ----------------------------------------------------- |
| `matched` | `true` = matches target_roles, `false` = filtered out |
| `status`  | `pending`, `added`, `skipped`, `filtered`             |

### Job → Resume Flow

```
/mw add job
      │
      ▼
┌─────────────┐
│ PARSE JD    │
│ + POSITION  │
│ + FIT CHECK │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│ "Generate resume now?"                       │
│                                              │
│  [Yes] ──────► Generate tailored resume      │
│  [Not now] ──► Run /mw resume later          │
│  [Case first] ► Build talking points first   │
└─────────────────────────────────────────────┘
       │
       ▼
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

**Streamlined workflow:** Paste JD → Fit Analysis → Generate Resume (all in one flow)

### Commands

| Command               | Agent           | Description                      |
| --------------------- | --------------- | -------------------------------- |
| `/mw`                 | (inline)        | Show status                      |
| `/mw init`            | add-resume      | First-time setup                 |
| `/mw scan`            | scan            | Discover jobs from portals       |
| `/mw inbox`           | inbox           | Review discovered jobs           |
| `/mw add resume`      | add-resume      | Add resume (merges into profile) |
| `/mw add job [url]`   | add-job         | Add job + derive positioning     |
| `/mw add brag`        | add-brag        | Capture achievement              |
| `/mw add doc`         | add-doc         | Add tech spec, work sample       |
| `/mw case <job-id>`   | case-agent      | Build advocacy case              |
| `/mw resume <job-id>` | generate-resume | Generate tailored resume         |
| `/github sync`        | (skill)         | Sync GitHub data                 |

### Hooks

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
