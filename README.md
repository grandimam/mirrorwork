# Mirrorwork

> Your career, reflected.

A Career OS built on [Claude Code](https://claude.ai/claude-code). Build a master profile from your resumes, discover jobs, get honest fit analysis, and generate tailored resumes — all from your terminal.

```
Resume₁ ──┐
Resume₂ ──┼──► Master Profile ──► Job Analysis ──► Derived Positioning
Resume₃ ──┘        (facts)          (fit)            (per job)
```

## Why Mirrorwork?

Most job tools make you re-enter your info for every application. Mirrorwork flips this:

1. **Build once** — Create a master profile from all your resumes
2. **Position contextually** — Derive positioning per job, not generic
3. **Stay honest** — Get brutal fit analysis before you apply
4. **Own your data** — Everything stays local, in JSON files you control

## Quick Start

### Prerequisites

- [Claude Code CLI](https://claude.ai/claude-code) installed
- Playwright MCP (for job scanning): `npx @anthropic/mcp-server-playwright`

### Setup

```bash
git clone https://github.com/grandimam/mirrorwork.git
cd mirrorwork

# Initialize with your resume
/mw init
```

## Commands

| Command | What it does |
|---------|--------------|
| `/mw` | Show status |
| `/mw init` | First-time setup with your resume |
| `/mw scan` | Discover jobs from configured portals |
| `/mw inbox` | Review discovered jobs |
| `/mw tracker` | View/update applications tracker |
| `/mw add job [url]` | Analyze a job posting |
| `/mw add resume` | Add another resume (merges into profile) |
| `/mw add brag` | Capture an achievement |
| `/mw case <job-id>` | Build advocacy talking points |
| `/mw resume <job-id>` | Generate a tailored resume |

## How It Works

### 1. Master Profile

Your profile is built from all your resumes, merged and deduplicated:

```
profile/
├── identity.json       # Name, contact, links
├── experience.json     # All roles (merged)
├── skills.json         # Expert / proficient / familiar
└── proof-points.json   # Quantified achievements
```

Each `/mw add resume` **adds** to your profile — never overwrites.

### 2. Job Discovery

Configure portals to scan in `activity/manifest.json`:

```json
{
  "portals": [
    {
      "name": "Stripe",
      "url": "https://stripe.com/jobs/search",
      "location": "Remote",
      "target_roles": ["backend", "senior", "staff"],
      "enabled": true
    }
  ]
}
```

Run `/mw scan` to discover jobs matching your `target_roles`.

### 3. Contextual Positioning

When you add a job, mirrorwork derives positioning **for that specific role**:

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

This isn't generic — it's derived from YOUR profile matched against THIS job.

### 4. Honest Fit Analysis

No sugar-coating. You get:

- **Matches** — Requirements you meet with evidence
- **Gaps** — What's missing and how severe
- **Verdict** — Should you actually apply?

```
| Requirement         | Met? | Evidence                    |
|---------------------|------|-----------------------------|
| 8+ years backend    | ✓    | 10 years at Cisco, Snapdeal |
| Distributed systems | ✓    | Kafka pipelines             |
| Fintech experience  | ✗    | No direct fintech           |

Fit Score: 85%
Verdict: Strong technical fit. Apply with confidence.
```

## Project Structure

```
profile/            # Your master profile (merged from resumes)
activity/           # Job pipeline
├── manifest.json   # Portal config
├── inbox/          # Discovered jobs
└── jobs/           # Analyzed jobs with positioning + fit
sources/            # Raw inputs (resumes, work samples)
agents/             # Agent instructions (the brains)
generated/          # Output artifacts (tailored resumes)
```

## Status: Early Preview

This is a work in progress. The core flow works:

- ✅ Profile building from resumes
- ✅ Job scanning with filtering
- ✅ Inbox review workflow
- ✅ Positioning derivation
- ✅ Fit analysis

### Roadmap

- [x] Applications tracker (unified view)
- [ ] API scanning for Greenhouse/Ashby/Lever (faster, zero-token)
- [ ] Legitimacy check (is the posting still active?)
- [ ] Interview story bank (STAR stories across jobs)
- [ ] Cover letter generation

## Contributing

PRs welcome! Areas that need help:

1. **Portal patterns** — Add extraction logic for more job boards
2. **Fit analysis** — Make scoring more nuanced
3. **Zero-token scripts** — Move scanning to Node.js scripts

## Privacy

All data stays local. Nothing is sent anywhere except:
- Claude API calls (for analysis)
- Job portal fetches (to read postings)

Your profile, resumes, and job data never leave your machine.

## License

MIT

---

Built with [Claude Code](https://claude.ai/claude-code)
