# Mirrorwork

> Your career, reflected.

Career OS built on Claude Code. Build your profile, analyze jobs, prepare for interviews, and master your skills.

```
Resume₁ ──┐
Resume₂ ──┼──► Master Profile ──► Job Analysis ──► Interview Prep
Resume₃ ──┘        (facts)          (fit)         (company-modeled)
                     │
                     └──► Skills Learning (evaluate, remember, improve)
```

- **Profile** = who you are (facts, grows over time)
- **Positioning** = how you present yourself (derived per job)
- **Interview Prep** = practice with a simulated interviewer from the company
- **Learning** = evaluate and improve your skills with spaced repetition

## Structure

```
profile/                      # MASTER PROFILE (merged from all resumes)
├── identity.json             # Name, email, location, links
├── experience.json           # Work history (merged, deduped)
├── education.json            # Degrees, certifications
├── skills.json               # Expert/proficient/familiar (union)
└── proof-points.json         # Quantified achievements (merged)

activity/                     # JOBS + TRACKING
├── tracker.md                # Applications tracker (status + outcomes)
└── jobs/
    └── {job-id}.json         # Analyzed jobs (JD + positioning + fit)

interview/                    # INTERVIEW PREP (company-based)
├── banks/                    # Generic question banks (fallback)
│   ├── behavioral.json
│   ├── coding/
│   └── system-design/
└── {company-slug}/           # Per-company
    ├── intel.json            # Company research
    ├── questions.json        # Company-specific questions
    └── sessions/

learning/                     # SKILLS LEARNING (evaluate + improve)
├── progress.json             # Overall progress summary
├── banks/                    # Question banks by skill
│   ├── python/
│   │   ├── basics.json
│   │   ├── data-structures.json
│   │   ├── concurrency.json
│   │   └── advanced.json
│   ├── system-design/
│   │   ├── fundamentals.json
│   │   ├── components.json
│   │   └── patterns.json
│   └── databases/
│       ├── sql.json
│       └── nosql.json
└── {skill-slug}/             # Per-skill progress
    ├── progress.json         # Scores by topic, gaps, schedule
    └── sessions/             # Practice history
        └── {date}.json

sources/                      # RAW INPUTS
├── manifest.json
├── resume/
└── work-samples/

agents/                       # AGENTS
├── add-resume.md
├── add-job.md
├── add-brag.md
├── add-doc.md
├── fit-analysis.md
├── case-agent.md
├── generate-resume.md
├── tracker.md
├── company-research.md
├── prep.md
├── behavioral.md
├── coding.md
├── system-design.md
└── learn.md                  # Skills learning agent

generated/
└── {job-id}/
    └── {date}-resume.md

scripts/
└── github_tracker/

.claude/
├── skills/
│   ├── mirrorwork/SKILL.md
│   └── github/SKILL.md
├── hooks.json
└── settings.json
```

## Profile

| File                | Purpose          | Key Fields                                |
| ------------------- | ---------------- | ----------------------------------------- |
| `identity.json`     | Contact info     | name, email, location, linkedin, github   |
| `experience.json`   | Work history     | company, role, dates, highlights, skills  |
| `education.json`    | Education        | institution, degree, field, year          |
| `skills.json`       | Skills inventory | expert, proficient, familiar, learning    |
| `proof-points.json` | Achievements     | id, summary, metrics, skills, story_ready |

## Job

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

## Company Intel

Each company in `interview/{company-slug}/intel.json` contains:

```json
{
  "company": "Stripe",
  "slug": "stripe",
  "researched_at": "2026-04-12",

  "values": [
    {
      "name": "Users first",
      "description": "Build for the user, not for yourself",
      "interview_signals": ["How did you handle conflicting user needs?"]
    }
  ],

  "interview_process": {
    "rounds": ["phone screen", "coding", "system design", "hiring manager"],
    "style": "collaborative, focus on tradeoffs",
    "what_they_look_for": ["clarity of thought", "API design sense"]
  },

  "tech_context": {
    "stack": ["Ruby", "Go", "AWS"],
    "scale": "millions of API calls/day",
    "challenges": ["reliability at scale", "developer experience"]
  },

  "recent_news": ["launched X", "expanding to Y"]
}
```

## Skill Progress

Each skill in `learning/{skill-slug}/progress.json` contains:

```json
{
  "skill": "python",
  "current_level": "proficient",
  "target_level": "expert",
  "started_at": "2026-04-01",
  "last_practice": "2026-04-20",
  "total_sessions": 12,
  "total_questions": 85,

  "topics": {
    "data-structures": {
      "score": 85,
      "questions_seen": 20,
      "correct": 17,
      "last_practiced": "2026-04-20",
      "confidence": "high",
      "next_review": "2026-04-27"
    },
    "concurrency": {
      "score": 45,
      "questions_seen": 10,
      "correct": 4,
      "last_practiced": "2026-04-18",
      "confidence": "low",
      "next_review": "2026-04-21"
    }
  },

  "weak_areas": ["concurrency", "metaclasses"],
  "strong_areas": ["data-structures", "comprehensions"]
}
```

## Agents

| Agent                | Purpose                        | Trigger                           |
| -------------------- | ------------------------------ | --------------------------------- |
| `add-resume.md`      | Parse resume → MERGE           | `/mirrorwork init`, `add resume`  |
| `add-job.md`         | JD + company research + fit    | `/mirrorwork add job`             |
| `add-brag.md`        | Capture achievement            | `/mirrorwork add brag`            |
| `add-doc.md`         | Tech spec → proof points       | `/mirrorwork add doc`             |
| `fit-analysis.md`    | Brutal, honest fit check       | Auto after add job                |
| `case-agent.md`      | Build advocacy case            | `/mirrorwork case <job-id>`       |
| `generate-resume.md` | Generate tailored resume       | `/mirrorwork resume <job-id>`     |
| `tracker.md`         | View/update tracker            | `/mirrorwork tracker`             |
| `company-research.md`| Research company intel         | Auto when new company added       |
| `prep.md`            | Interview prep orchestrator    | `/mirrorwork prep <company>`      |
| `behavioral.md`      | Behavioral interview coach     | `/mirrorwork prep <company> behavioral` |
| `coding.md`          | Coding practice                | `/mirrorwork prep <company> coding` |
| `system-design.md`   | System design practice         | `/mirrorwork prep <company> system-design` |
| `learn.md`           | Skills learning + evaluation   | `/mirrorwork learn <skill>`       |

## Commands

| Command | Description |
|---------|-------------|
| `/mirrorwork` | Status overview |
| `/mirrorwork init` | First-time setup |
| `/mirrorwork add resume` | Add resume (merges into profile) |
| `/mirrorwork add job` | Paste JD → analyze + research company |
| `/mirrorwork add brag` | Capture achievement |
| `/mirrorwork add doc` | Add work sample |
| `/mirrorwork prep <company>` | Interview prep (pick type) |
| `/mirrorwork prep <company> behavioral` | Behavioral practice |
| `/mirrorwork prep <company> coding` | Coding practice |
| `/mirrorwork prep <company> system-design` | System design practice |
| `/mirrorwork learn` | Skills dashboard |
| `/mirrorwork learn <skill>` | Practice a skill |
| `/mirrorwork learn <skill> --topic <topic>` | Focus on specific topic |
| `/mirrorwork learn <skill> --review` | Review weak areas (spaced repetition) |
| `/mirrorwork learn <skill> --assess` | Full assessment |
| `/mirrorwork progress` | Overall learning progress |
| `/mirrorwork case <job-id>` | Build advocacy case |
| `/mirrorwork resume <job-id>` | Generate tailored resume |
| `/mirrorwork tracker` | View/update tracker |
| `/github sync` | Sync GitHub data |

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  SOURCES (raw inputs)                                       │
│  ├── manifest.json         # Central registry of all files  │
│  ├── resume/               # All resumes                    │
│  └── work-samples/         # Tech specs, design docs        │
└─────────────────────┬───────────────────────────────────────┘
                      │ /mirrorwork add <type> (MERGE)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PROFILE (master record - merged from all sources)          │
│  ├── identity.json         # Name, contact, links           │
│  ├── experience.json       # All roles (merged, deduped)    │
│  ├── skills.json           # All skills (union)             │
│  └── proof-points.json     # All achievements (merged)      │
└───────────┬─────────────────────────────┬───────────────────┘
            │                             │
            │ /mirrorwork add job         │ /mirrorwork learn
            ▼                             ▼
┌───────────────────────────┐   ┌─────────────────────────────┐
│  JOB ANALYSIS             │   │  SKILLS LEARNING            │
│  ├── activity/jobs/*.json │   │  ├── Evaluate by topic      │
│  └── interview/{company}/ │   │  ├── Track progress         │
└───────────┬───────────────┘   │  ├── Spaced repetition      │
            │                   │  └── Identify gaps           │
            │ /mirrorwork prep  └─────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────┐
│  INTERVIEW PREP                                             │
│  ├── Behavioral   # Questions from company values           │
│  ├── Coding       # Prioritized by YOUR weak areas          │
│  └── System Design # Company-relevant problems              │
└─────────────────────────────────────────────────────────────┘
```

## Learning Flow

```
/mirrorwork learn python

╭─────────────────────────────────────╮
│  mirrorwork · Learn: Python         │
╰─────────────────────────────────────╯

Level: proficient → expert

───────────────────────────────────────
📊 **Progress by Topic**

| Topic | Score | Confidence | Review |
|-------|-------|------------|--------|
| basics | 95% | ✓ high | — |
| data-structures | 85% | ✓ high | Apr 27 |
| oop | 75% | ~ medium | Apr 25 |
| concurrency | 45% | ✗ low | TODAY |
| advanced | 40% | ✗ low | Apr 22 |

**Recommendation:** Review concurrency (due today)

───────────────────────────────────────
```

## Spaced Repetition

Uses SM-2 algorithm for review scheduling:

```
Correct → Interval grows: 1d → 3d → 7d → 14d → 30d
Wrong   → Reset to 1 day

Topics with low confidence are reviewed more frequently.
```

## Tracker

The tracker (`activity/tracker.md`) tracks application status and interview outcomes:

```markdown
| Company | Role | Fit | Status | Stage | Outcome | Notes |
|---------|------|-----|--------|-------|---------|-------|
| Stripe | Staff Backend | 85% | interviewing | system-design | pending | Round 3 on Monday |
| Careem | Platform Lead | 90% | rejected | coding | failed | Struggled with DP |
| Talabat | Backend Lead | 78% | offer | final | passed | Negotiating |
```

**Statuses:** `saved`, `applied`, `interviewing`, `offered`, `accepted`, `rejected`, `withdrawn`

**Stages:** `phone`, `coding`, `system-design`, `behavioral`, `hiring-manager`, `final`

**Outcomes:** `pending`, `passed`, `failed`

## Hooks

| Trigger                         | Action           |
| ------------------------------- | ---------------- |
| Write to `activity/jobs/*.json` | Run fit analysis |

## Conventions

- **JSON** for all structured data (profile, jobs, company intel, progress)
- **Markdown** for narratives and session transcripts
- File names: `kebab-case.json`
- IDs: `{company}-{slug}` (e.g., `stripe-staff-backend`)
- Company slugs: `kebab-case` (e.g., `stripe`, `dt-one`)
- Skill slugs: `kebab-case` (e.g., `python`, `system-design`)
- Dates: `YYYY-MM-DD` or `YYYY-MM`

## Principles

1. **Privacy first** — All data stays local
2. **Accumulate, don't overwrite** — Each resume adds to master profile
3. **Positioning is contextual** — Derived per job, not global
4. **Brutal honesty first** — Fit analysis before advocacy
5. **Answers from facts** — Behavioral answers come from your proof points
6. **Company-modeled prep** — Interview practice shaped by company values
7. **Learn through repetition** — Spaced review for lasting retention
8. **Track to improve** — Know your weak areas, focus practice there
