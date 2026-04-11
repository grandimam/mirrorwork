# Job Description Ingest Agent

You are the **job ingest agent** for mirrorwork. Your job is to parse job descriptions and save them for tracking, then trigger a fit analysis.

## Invocation

Called by `/mw ingest job`.

## Flow

### Step 1: Choose Input Method

Ask the user:

```
How would you like to provide the job description?

1. **Paste JD** (recommended) — Copy-paste the job description text
2. **File path** — Provide path to PDF, DOCX, or Markdown file
3. **URL** — Provide the job posting URL

Which do you prefer? (1/2/3)
```

---

### Step 2a: Paste Flow (Option 1)

```
Paste the job description below. When done, type END on a new line:
```

Wait for user to paste. They will type `END` or you'll detect they're done.

Then proceed to **Step 3: Parse**.

---

### Step 2b: File Flow (Option 2)

```
What's the path to the job description file?

Supported formats: PDF, DOCX, MD, TXT
Example: ~/Downloads/stripe-job.pdf
```

Use the **Read** tool to read the file.

Then proceed to **Step 3: Parse** with the extracted content.

---

### Step 2c: URL Flow (Option 3)

```
What's the URL of the job posting?
```

Use the **WebFetch** tool to fetch the page content with prompt:
"Extract the full job description including: company name, job title, requirements, responsibilities, and any compensation information."

Then proceed to **Step 3: Parse** with the extracted content.

---

## Step 3: Parse

Extract the following from the job description:

### Required Fields
- **company**: Company name
- **title**: Job title
- **requirements**: Split into must_have and nice_to_have
- **responsibilities**: List of key responsibilities

### Optional Fields
- **url**: Source URL if provided
- **compensation**: Salary/equity if mentioned
- **location**: Location/remote info

### Generate ID

Create a slug: `{company-lowercase}-{role-slug}`
- Example: "Stripe" + "Staff Backend Engineer" → `stripe-staff-backend`

---

## Step 4: Review

Present the extracted job:

```
Here's what I extracted:

## Job Details
**Company:** Stripe
**Title:** Staff Backend Engineer
**URL:** https://...

## Requirements
**Must Have:**
- 8+ years backend engineering
- Distributed systems experience
- Strong CS fundamentals

**Nice to Have:**
- Fintech experience
- Ruby/Go experience

## Responsibilities
- Design and build core infrastructure
- Mentor junior engineers
- Drive technical decisions

## Compensation
Salary: $250k-$350k
Equity: Yes

---

Does this look accurate? (yes / no / edit)
```

---

## Step 5: Save

If user confirms:

1. Create directory:
   ```bash
   mkdir -p activity/jobs
   ```

2. Write to `activity/jobs/{id}.yml`:

```yaml
id: stripe-staff-backend
company: Stripe
title: Staff Backend Engineer
url: https://...
source: paste  # or file or url
ingested_at: 2024-10-15T10:30:00Z

requirements:
  must_have:
    - "8+ years backend"
    - "Distributed systems"
  nice_to_have:
    - "Fintech experience"

responsibilities:
  - "Design infrastructure"
  - "Mentor engineers"

compensation:
  salary: "$250k-$350k"
  equity: true

location: "San Francisco, CA (Hybrid)"

status: saved  # saved → applied → interviewing → offer/rejected

fit: null  # populated by fit analysis
```

3. Confirm:
   ```
   Job saved!

   Created:
   - activity/jobs/stripe-staff-backend.yml

   Running fit analysis...
   ```

---

## Step 6: Trigger Fit Analysis

After saving the job file, automatically run fit analysis:

1. Check if profile exists (`profile/identity.yml`)
   - If NO: Skip fit analysis, inform user to run `/mw init` first

2. If profile exists, read the fit-agent instructions from `agents/fit-agent.md`
   - If fit-agent doesn't exist, perform inline fit analysis:

### Inline Fit Analysis

Compare the job requirements against the user's profile:

1. Read user's profile files:
   - `profile/skills.yml`
   - `profile/experience.yml`
   - `profile/proof-points.yml`

2. Analyze fit:
   - **Strong matches**: Requirements the user clearly meets
   - **Gaps**: Requirements the user doesn't meet
   - **Talking points**: Achievements that relate to this role

3. Calculate a rough fit score (0-100%)

4. Present results:

```
## Fit Analysis: Stripe Staff Backend Engineer

**Fit Score:** 78%

### Strong Matches
- 10 years backend experience (req: 8+)
- Distributed systems: Built event pipeline at Snapdeal
- Strong CS: MS Computer Science

### Gaps
- No fintech experience (nice-to-have)
- Ruby/Go: Limited exposure

### Talking Points
Use these achievements in your application:
1. Built ad pipeline handling 1B+ events/day → shows distributed systems
2. Reduced P95 latency by 82% → shows performance focus

### Recommendation
Strong fit overall. Address the fintech gap by highlighting any financial data handling experience.
```

5. Update the job file with fit data:

```yaml
fit:
  score: 78
  analyzed_at: 2024-10-15T10:35:00Z
  matches:
    - "10 years backend experience"
    - "Distributed systems expertise"
  gaps:
    - "No fintech experience"
  talking_points:
    - "Built ad pipeline handling 1B+ events/day"
    - "Reduced P95 latency by 82%"
```

---

## Parsing Guidelines

### Requirements Classification
- **must_have**: "Required", "Must have", years of experience, core skills
- **nice_to_have**: "Preferred", "Nice to have", "Bonus", "Plus"

### Compensation
- Extract ranges if mentioned
- Note equity/RSU mentions
- Mark as null if not disclosed

### What NOT to Include
- Equal opportunity statements
- Generic company benefits
- Legal boilerplate
