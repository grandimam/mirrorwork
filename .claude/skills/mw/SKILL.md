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
• Sources: {count} files

───────────────────────────────────────
🎯 **Job Pipeline**

• {count} jobs tracked
• {count} with fit analysis

───────────────────────────────────────
**Quick actions**

→ `/mw add resume` — Add another resume
→ `/mw add job` — Track a job
→ `/mw add brag` — Capture achievement
→ `/mw add doc` — Add work sample
```

#### `/mw init`

First-time setup. Read `agents/add-resume.md` and follow its instructions.

#### `/mw status`

Same as `/mw` with no args.

---

### Add Commands

All `/mw add` commands process immediately — no separate "ingest" step.

#### `/mw add resume`

Add a resume and merge into profile.

Read `agents/add-resume.md` and follow its instructions.

#### `/mw add job`

Add a job description, analyze fit, derive positioning.

Read `agents/add-job.md` and follow its instructions.

#### `/mw add brag`

Capture a professional achievement.

Read `agents/add-brag.md` and follow its instructions.

#### `/mw add doc`

Add a tech spec, RFC, design doc, or work sample.

Read `agents/add-doc.md` and follow its instructions.

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

### Resume Commands

#### `/mw resume <job-id>`

Generate a tailored resume for a specific job.

**Prerequisites:** Job must exist in `activity/jobs/` with fit analysis completed.

Read `agents/generate-resume.md` and follow its instructions.

Features:
- Select which experiences to include
- Choose highlights per experience
- Pick relevant skills
- Select proof points to feature
- Generate tailored headline
- Reword bullets to match job language

Output saved to `generated/{job-id}/{date}-resume.md`

If no job-id provided, list available jobs (same as case command).

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
profile/                    # MASTER PROFILE (merged from all sources)
├── identity.json           # Name, contact, links
├── experience.json         # Work history (merged, deduped)
├── education.json          # Degrees, certifications
├── skills.json             # Skills (union of all sources)
└── proof-points.json       # Achievements (merged)

activity/
└── jobs/*.json             # Job + DERIVED positioning + fit analysis

sources/                    # RAW INPUTS
├── manifest.json           # Central registry (tracks ALL files)
├── resume/                 # All resumes
│   └── {date}-{source}.md
└── work-samples/           # Tech specs, design docs, RFCs
    └── *.pdf, *.md

generated/
└── {job-id}/               # Per-job output
    └── {date}-resume.md    # Tailored resume
```

### Manifest Schema

All source files tracked in `sources/manifest.json`:

| Field       | Purpose                                            |
| ----------- | -------------------------------------------------- |
| `path`      | Relative to `sources/`                             |
| `type`      | `resume`, `tech-spec`, `case-study`, `code-sample` |
| `label`     | User-provided description                          |
| `added_at`  | When file was added                                |
| `status`    | `pending` → `processed` / `failed`                 |
| `extracted` | What was pulled out (populated after processing)   |

**Note:** No `positioning.json` — positioning is derived per job during `/mw add job`.

## Agent Routing

| Command | Agent | Purpose |
|---------|-------|---------|
| `init` | `agents/add-resume.md` | Setup profile |
| `add resume` | `agents/add-resume.md` | Parse resume → merge |
| `add job` | `agents/add-job.md` | Parse JD + brutal fit |
| `add brag` | `agents/add-brag.md` | Capture achievement |
| `add doc` | `agents/add-doc.md` | Extract proof points |
| `case` | `agents/case-agent.md` | Build advocacy case |
| `resume` | `agents/generate-resume.md` | Generate tailored resume |

## Two-Step Job Analysis

```
/mw add job             /mw case <job-id>
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
