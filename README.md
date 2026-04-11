# Mirrorwork

> Your career, reflected.

A Career OS built on [Claude Code](https://claude.ai/claude-code). Build a master profile from your resumes, discover jobs, get honest fit analysis, and generate tailored resumes — all from your terminal.

```
Resume₁ ──┐
Resume₂ ──┼──► Master Profile ──► Job Analysis ──► Derived Positioning
Resume₃ ──┘        (facts)          (fit)            (per job)
```

## Installation

### 1. Install Claude Code

```bash
# macOS / Linux
brew install claude-code

# or via npm
npm install -g @anthropic/claude-code
```

### 2. Clone this repo

```bash
git clone https://github.com/grandimam/mirrorwork.git
cd mirrorwork
```

### 3. Start Claude Code

```bash
claude
```

That's it. The `/mw` commands are now available.

## Getting Started

### Step 1: Initialize your profile

```bash
/mw init
```

You'll be asked to paste your resume. Mirrorwork extracts:
- Your identity (name, contact, location)
- Work experience (companies, roles, highlights)
- Skills (categorized by proficiency)
- Proof points (quantified achievements)

### Step 2: Configure job portals

Edit `activity/manifest.json` to add companies you want to track:

```json
{
  "portals": [
    {
      "name": "Stripe",
      "url": "https://stripe.com/jobs/search",
      "location": "Remote",
      "target_roles": ["backend", "senior", "staff", "platform"],
      "enabled": true
    },
    {
      "name": "Airbnb",
      "url": "https://careers.airbnb.com/positions/",
      "location": "Remote",
      "target_roles": ["backend", "senior", "engineer"],
      "enabled": true
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `name` | Company name (for display) |
| `url` | Careers page URL |
| `location` | Your target location |
| `target_roles` | Keywords to filter job titles (e.g., "backend", "senior") |
| `enabled` | Set to `false` to skip this portal |

### Step 3: Discover jobs

```bash
/mw scan
```

This scans all enabled portals and finds jobs matching your `target_roles`. New jobs go to your inbox.

### Step 4: Review your inbox

```bash
/mw inbox
```

You'll see discovered jobs and can:
- **Add** — Analyze the job (fit + positioning)
- **Skip** — Not interested
- **Preview** — See job details first

### Step 5: Track your applications

```bash
/mw tracker
```

See all jobs in one view:

```
| Company | Role | Fit | Status | Applied | Next Step |
|---------|------|-----|--------|---------|-----------|
| Stripe | Staff Backend | 85% | applied | 2026-04-10 | Interview 4/15 |
| Airbnb | Senior Engineer | 72% | saved | - | Need to apply |
```

Update status when you apply:
```bash
/mw tracker update stripe-staff-backend --status applied
```

Add notes:
```bash
/mw tracker note stripe-staff-backend "Interview Monday 2pm"
```

## Daily Workflow

```
Morning:
  /mw scan              # Check for new jobs

When you find interesting jobs:
  /mw inbox             # Review and add jobs you like

Before applying:
  /mw resume <job-id>   # Generate tailored resume

After applying:
  /mw tracker update <job-id> --status applied

Track progress:
  /mw tracker           # See all applications
```

## Commands Reference

| Command | What it does |
|---------|--------------|
| `/mw` | Show status dashboard |
| `/mw init` | First-time setup (paste your resume) |
| `/mw scan` | Discover jobs from configured portals |
| `/mw inbox` | Review discovered jobs |
| `/mw tracker` | View/update applications tracker |
| `/mw add job [url]` | Analyze a specific job posting |
| `/mw add resume` | Add another resume (merges into profile) |
| `/mw add brag` | Capture a new achievement |
| `/mw case <job-id>` | Build advocacy talking points |
| `/mw resume <job-id>` | Generate a tailored resume |

## How It Works

### Master Profile

Your profile lives in `profile/` and is built from all your resumes:

```
profile/
├── identity.json       # Name, email, location, links
├── experience.json     # All roles (merged from resumes)
├── skills.json         # Expert / proficient / familiar
└── proof-points.json   # Quantified achievements
```

Each `/mw add resume` **merges** into your profile — it never overwrites. Add multiple resumes to build a complete picture.

### Contextual Positioning

When you analyze a job, mirrorwork doesn't just check fit — it derives **positioning for that specific role**:

```json
{
  "positioning": {
    "headline": "10-year backend engineer scaling transaction systems",
    "angle": "Ad-tech scale → financial reliability",
    "lead_with": ["1B+ events/day", "P95 ≤5ms"],
    "relevant_experience": ["Snapdeal", "Cisco"],
    "bridge_gaps_with": "Ad-tech revenue systems = same audit requirements"
  }
}
```

This tells you exactly how to position yourself for THIS job.

### Honest Fit Analysis

No sugar-coating. For each job you get:

```
| Requirement         | Met? | Evidence                    |
|---------------------|------|-----------------------------|
| 8+ years backend    | ✓    | 10 years at Cisco, Snapdeal |
| Distributed systems | ✓    | Kafka pipelines             |
| Fintech experience  | ✗    | No direct fintech           |

Fit Score: 85%
Verdict: Strong technical fit. Apply with confidence.
```

### Applications Tracker

All jobs in one place with status tracking:

```
saved → applied → interviewing → offered → accepted
                              ↘ rejected
                              ↘ withdrawn
```

## Project Structure

```
profile/              # Your master profile
├── identity.json
├── experience.json
├── skills.json
└── proof-points.json

activity/             # Job pipeline
├── manifest.json     # Portal configuration
├── tracker.md        # Applications tracker
├── inbox/            # Discovered jobs (by date)
└── jobs/             # Analyzed jobs

sources/              # Your raw inputs
├── resume/           # All your resumes
└── work-samples/     # Tech specs, design docs

generated/            # Output artifacts
└── {job-id}/         # Tailored resumes per job
```

## Adding a Job Manually

Don't want to scan? Add a job directly:

```bash
# From URL
/mw add job https://stripe.com/jobs/staff-backend-engineer

# Or paste the job description
/mw add job
# Then paste the JD when prompted
```

## Multiple Resumes

Have different resume versions? Add them all:

```bash
/mw add resume
# Paste your backend-focused resume

/mw add resume
# Paste your platform-focused resume
```

Mirrorwork merges them intelligently:
- Experiences are deduplicated by (company, role, dates)
- Skills are unioned (highest proficiency wins)
- Proof points are merged by ID

## Privacy

All data stays on your machine. Nothing is sent anywhere except:
- Claude API calls (for analysis)
- Job portal fetches (to read postings)

Your profile, resumes, and job data never leave your machine.

## Status

This is an early preview. The core flow works:

- ✅ Profile building from resumes
- ✅ Job scanning with filtering
- ✅ Inbox review workflow
- ✅ Positioning derivation
- ✅ Fit analysis
- ✅ Applications tracker

### Roadmap

- [ ] API scanning for Greenhouse/Ashby/Lever (faster)
- [ ] Legitimacy check (is the posting still active?)
- [ ] Interview story bank (STAR stories)
- [ ] Cover letter generation

## Contributing

PRs welcome! Areas that need help:

1. **Portal patterns** — Add extraction logic for more job boards
2. **Fit analysis** — Make scoring more nuanced
3. **Zero-token scripts** — Move scanning to Node.js for speed

## License

MIT

---

Built with [Claude Code](https://claude.ai/claude-code)
