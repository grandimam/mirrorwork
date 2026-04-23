# Mirrorwork

> Your career, reflected.

You've applied to 50 jobs. Heard back from 3. Bombed an interview because you blanked on a behavioral question you should've nailed. Sound familiar?

**Mirrorwork fixes this.**

It's a career OS that knows your experience better than you do. It tells you which jobs you'll actually get. It practices interviews with you — not generic questions, but questions _the way that company asks them_. And when you blank, it reminds you: "Remember that time you reduced latency by 40x at Snapdeal? Use that."

All local. All private. All yours.

---

## The Problem

**Job hunting is broken:**

- You apply to jobs you're not qualified for (wasting everyone's time)
- You skip jobs you'd be perfect for (because the JD sounds intimidating)
- You prep with generic interview questions (that don't match how the company actually interviews)
- You forget your own accomplishments (and undersell yourself)
- You study skills you'll never use (and ignore the ones you're weak on)

**Mirrorwork solves each of these.**

---

## What Makes It Different

### 1. Brutal Honesty

Most tools tell you what you want to hear. Mirrorwork tells you the truth.

```
Fit Score: 65%

| Requirement | Met? | Evidence |
|-------------|------|----------|
| 8+ years backend | ✓ | 10 years at Cisco, Snapdeal |
| Banking domain | ✗ | No banking experience |

Verdict: You meet the technical bar, but banking is mandatory.
Don't apply unless you can bridge this gap.
```

Stop wasting time on jobs you won't get. Focus on the ones you will.

### 2. Answers From YOUR Experience

Generic interview prep gives you generic answers. Mirrorwork gives you _your_ answers.

When Stripe asks about reliability, it doesn't suggest a hypothetical. It pulls from your profile:

```
📌 snapdeal-ad-pipeline
   "Reduced P95 latency from 200ms to 5ms while handling 1B+ events/day"

STAR format:
• Situation: Ad platform hitting latency issues at scale
• Task: Maintain SLAs while traffic grew 10x
• Action: Redesigned pipeline with batching + caching
• Result: P95 ≤5ms, zero incidents in 6 months

Stripe angle: Emphasize reliability metrics and user impact.
```

Your stories. Your numbers. Your voice.

### 3. Company-Modeled Practice

Not "tell me about a time you showed leadership." That's lazy.

Mirrorwork researches each company — their values, their interview style, what they actually look for — and asks you questions _the way they would ask them_:

```
┌─────────────────────────────────────────────────────────────┐
│ INTERVIEWER (as Stripe engineering manager)                 │
│                                                             │
│ "At Stripe, we obsess over reliability. Our users trust us │
│  with their revenue. Tell me about a time you improved     │
│  system reliability when the stakes were high."            │
└─────────────────────────────────────────────────────────────┘
```

Practice like it's the real thing. Because it basically is.

### 4. Skills That Actually Stick

You cram before interviews. Forget everything after. Repeat.

Mirrorwork uses spaced repetition. Topics you're weak on come back. Topics you've mastered fade away. Over time, you actually _know_ the material.

```
| Topic | Score | Next Review |
|-------|-------|-------------|
| basics | 95% | — |
| concurrency | 45% | TODAY |
| metaclasses | 30% | TODAY |
```

No more cramming. Just steady improvement.

---

## How It Works

### Step 1: Build Your Profile

```bash
/mirrorwork init
```

Paste your resume. Mirrorwork extracts everything: experience, skills, quantified achievements. Add multiple resumes — they merge together, building a complete picture of your career.

### Step 2: Analyze Jobs

```bash
/mirrorwork add job
```

Paste any job description. Get:

- **Fit analysis** — Do you actually qualify?
- **Positioning** — How to present yourself for this role
- **Company intel** — Their values, interview process, what they look for

### Step 3: Practice Interviews

```bash
/mirrorwork prep stripe behavioral
/mirrorwork prep stripe coding
/mirrorwork prep stripe system-design
```

Practice with an interviewer who sounds like they work there. Get feedback. Get better.

### Step 4: Master Your Skills

```bash
/mirrorwork learn python
/mirrorwork learn system-design --review
```

Evaluate your knowledge. Drill weak areas. Track progress over time.

### Step 5: Track Everything

```bash
/mirrorwork tracker
```

See all your applications in one place:

```
| Company | Role | Fit | Status | Stage | Outcome |
|---------|------|-----|--------|-------|---------|
| Stripe | Staff Backend | 85% | interviewing | coding | passed |
| Careem | Platform Lead | 90% | rejected | system-design | failed |
```

See patterns. "I keep failing system design rounds" → focus your practice there.

---

## Commands

| Command                                    | What it does             |
| ------------------------------------------ | ------------------------ |
| `/mirrorwork`                              | Status dashboard         |
| `/mirrorwork init`                         | First-time setup         |
| `/mirrorwork add job`                      | Analyze a job posting    |
| `/mirrorwork add resume`                   | Add another resume       |
| `/mirrorwork add brag`                     | Capture an achievement   |
| `/mirrorwork prep <company>`               | Interview prep menu      |
| `/mirrorwork prep <company> behavioral`    | Behavioral practice      |
| `/mirrorwork prep <company> coding`        | Coding practice          |
| `/mirrorwork prep <company> system-design` | System design            |
| `/mirrorwork learn <skill>`                | Practice a skill         |
| `/mirrorwork learn <skill> --review`       | Spaced repetition        |
| `/mirrorwork case <job-id>`                | Build talking points     |
| `/mirrorwork resume <job-id>`              | Generate tailored resume |
| `/mirrorwork tracker`                      | View applications        |
| `/mirrorwork progress`                     | Learning dashboard       |

---

## Installation

```bash
# Install Claude Code
npm install -g @anthropic/claude-code

# Clone mirrorwork
git clone https://github.com/grandimam/mirrorwork.git
cd mirrorwork

# Start
claude
```

That's it. `/mirrorwork` is now available.

---

## Privacy

Everything stays on your machine. Your resumes, your profile, your interview practice — none of it leaves your computer.

The only external calls:

- Claude API (for analysis)
- Web fetches (to read job postings)

Your career data is yours alone.

---

## Philosophy

1. **Facts first** — Build a profile of what you've actually done
2. **Honesty over hype** — Know the truth about your fit
3. **Your voice, not AI's** — Answers come from your experience
4. **Practice like it's real** — Company-modeled, not generic
5. **Learn for keeps** — Spaced repetition over cramming
