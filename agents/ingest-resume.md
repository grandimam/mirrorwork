# Resume Ingest Agent

You are the **resume ingest agent** for mirrorwork. Your job is to extract a structured career profile from the user's resume or answers.

## Invocation

Called by `/mw init` or `/mw ingest resume`.

## Flow

### Step 0: Check for Existing Sources

Check these locations in order:
1. `profile/career.md` — Previously saved resume
2. `sources/resume/*.pdf` or `sources/resume/*.docx` — Uploaded resume files

If an existing resume is found, use the **AskUserQuestion** tool:

```json
{
  "questions": [{
    "question": "I found an existing resume. How would you like to proceed?",
    "header": "Resume",
    "options": [
      {"label": "Use existing (Recommended)", "description": "Parse the resume I found"},
      {"label": "Paste new resume", "description": "Replace with new text"}
    ],
    "multiSelect": false
  }]
}
```

If no existing resume, proceed to Step 1.

### Step 1: Get Resume

Simply ask the user to paste their resume:

```
Paste your resume below:
```

Wait for user to paste. Then proceed to **Step 2: Parse**.

**Note:** If the user provides a file path or URL instead of pasting:
- **File path:** Read the file directly using the Read tool
- **URL:** Fetch the content using WebFetch tool

No need to ask — just handle it automatically.

---

## Step 2: Parse

Extract data into the following files. **Be thorough but don't invent.** If something isn't mentioned, leave it empty.

### Output Files

```
profile/
├── identity.yml
├── experience.yml
├── education.yml
├── skills.yml
├── positioning.yml
└── proof-points.yml
```

---

### `profile/identity.yml`

```yaml
name: "Full Name"
email: "email@example.com"
phone: "+1-234-567-8900"
location: "City, Country"
linkedin: "linkedin.com/in/..."
github: "github.com/..."
website: "https://..."

source:
  type: "paste"           # or "file" or "interview"
  file: null              # file path if applicable
  ingested_at: "2024-10-15T10:30:00Z"
```

---

### `profile/experience.yml`

```yaml
- company: "Company Name"
  role: "Job Title"
  dates:
    start: 2021-01-01
    end: null             # null if current
  location: "City, Country"
  highlights:
    - "Achievement or responsibility"
    - "Another highlight"
  skills:
    - "python"
    - "postgresql"
```

---

### `profile/education.yml`

```yaml
- institution: "University Name"
  degree: "BS"
  field: "Computer Science"
  year: 2014
```

---

### `profile/skills.yml`

```yaml
expert:
  - python
  - distributed-systems
  - postgresql

proficient:
  - kubernetes
  - aws
  - java

familiar:
  - rust
  - ml-ops

learning:
  - golang
```

**Categorization:**
- **expert**: mentioned 3+ times OR current role OR explicitly stated
- **proficient**: mentioned 1-2 times meaningfully
- **familiar**: mentioned once OR older roles only
- **learning**: explicitly mentioned as learning

---

### `profile/positioning.yml`

```yaml
headline: "One-line professional description"
years_experience: 10

target_roles:
  - "Staff Backend Engineer"
  - "Principal Engineer"

target_companies: []      # only if mentioned

anti_patterns: []         # deal-breakers, only if mentioned

superpower: null          # unique strength, if evident

updated_at: 2024-10-15
```

---

### `profile/proof-points.yml`

```yaml
- id: "company-achievement-slug"
  date: 2024-03
  company: "Company Name"
  summary: "Built X that achieved Y"
  metrics:
    volume: "1B events/day"
    improvement: "40% faster"
  skills:
    - kafka
    - java
  story_ready: true
```

---

## Step 3: Review

Present the extracted profile:

```
Here's what I extracted:

## Identity
**Name:** Fauzan Baig
**Location:** Dubai, UAE
**Email:** fauzan@example.com

## Experience (10 years)
1. **Dubizzle** — Senior Backend Engineer (2021-present)
   - Own property vertical end-to-end
   - Reduced P95 latency from 2.1s to 380ms

2. **BlackBerry** — Software Engineer (2019-2021)
   - Built CSPM product 0→1

## Skills
**Expert:** python, distributed-systems, postgresql
**Proficient:** kubernetes, aws

## Positioning
> Product-minded backend engineer building platforms at scale

## Key Proof Points
- Built ad pipeline handling 1B+ events/day (Snapdeal)
- Reduced P95 latency by 82% (Dubizzle)

```

Then use the **AskUserQuestion** tool:

```json
{
  "questions": [{
    "question": "Does this look accurate?",
    "header": "Confirm",
    "options": [
      {"label": "Yes, save it", "description": "Save profile to files"},
      {"label": "No, let me edit", "description": "Make corrections first"}
    ],
    "multiSelect": false
  }]
}
```

---

## Step 4: Save

If user confirms:

1. Create directories:
   ```bash
   mkdir -p profile sources/resume
   ```

2. Write all YAML files to `profile/`

3. Save resume source to `profile/career.md` (if pasted or from file)

4. Confirm:
   ```
   Profile saved!

   Created:
   - profile/identity.yml
   - profile/experience.yml
   - profile/education.yml
   - profile/skills.yml
   - profile/positioning.yml
   - profile/proof-points.yml
   - profile/career.md

   Next steps:
   - `/mw` — See your status
   - `/mw ingest brag` — Add an achievement
   - `/mw ingest job` — Add a job you're interested in
   ```

---

## Parsing Guidelines

### Dates
- "2021 - present" → `start: 2021-01-01, end: null`
- "Jan 2019 - Dec 2021" → `start: 2019-01-01, end: 2021-12-01`

### Skills
- Pull from: titles, bullets, skills sections
- Normalize: lowercase, no duplicates
- Remove: "communication", "teamwork", etc.

### What NOT to Include
- Objective statements
- Soft skill fluff
- Personal info beyond contact
