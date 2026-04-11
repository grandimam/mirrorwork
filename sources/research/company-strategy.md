# Job Search Strategy

## The Problem

Your profile requires a human to see the pattern. Cold applications get filtered by ATS and recruiters who scan for domain keywords. You need warm paths.

| Channel                   | Conversion Rate |
| ------------------------- | --------------- |
| Cold application          | 1-3%            |
| Recruiter inbound         | 5-10%           |
| Warm referral             | 20-40%          |
| Strong referral ("vouch") | 40-60%          |

**Goal:** Build referral channels and create inbound interest organically.

## Strategy 1: Leverage Barq

You have an asset most candidates don't: an open source project that outperforms FastAPI.

### Actions

**Write a technical deep-dive:**

- Title: "How I made Barq 2-5x faster than FastAPI"
- Include: Architecture decisions, benchmarks, free-threaded Python 3.13 details
- Publish on: Personal blog, Dev.to, Hashnode
- Cross-post to: Reddit r/Python, Hacker News

**Submit to newsletters:**

- Python Weekly (pythonweekly.com)
- PyCoder's Weekly (pycoders.com)
- Real Python newsletter

**Social amplification:**

- Post on X/Twitter with technical insights
- Tag Python influencers, FastAPI creator (Sebastián Ramírez)
- Engage in Python community discussions

**Speaking opportunities:**

- Submit CFP to PyCon, PyData, local Python meetups
- Pitch podcast appearances (Talk Python to Me, Python Bytes)
- Title angle: "I built a faster alternative to FastAPI without async/await"

### Goal

Become "the Barq guy" in Python circles. When you apply to Python-heavy companies, someone on the team has heard of you.

---

## Strategy 2: Targeted Cold Outreach

Don't apply cold to jobs. Reach out cold to humans, then apply warm.

### Finding the Right People

**Where to look:**

- LinkedIn: Engineers at target companies
- X/Twitter: Active technical voices
- GitHub: Contributors to projects your target companies use

**Who to target:**

- Python backend engineers at target companies
- Staff+ engineers (they influence hiring)
- Hiring managers
- People who've posted about hiring, open source, or technical topics

### Outreach Template

```
Hey [Name],

I built Barq, a Python framework that's 2-5x faster than FastAPI
using free-threaded Python 3.13. Saw you're working on [specific
thing at their company] — curious if [specific technical question
related to their work]?

Not asking for anything, just wanted to connect with engineers
working on similar problems.
```

**Why this works:**

- Leads with credibility (Barq)
- Shows you researched them
- Asks a question (engineers love talking about their work)
- Doesn't ask for referral upfront

### Follow-up (After Building Rapport)

```
By the way, I'm exploring roles — is [Company] hiring for backend?
Would love to learn more about the team.
```

### Volume

- Send 5-10 outreach messages per week
- Expect 20-30% response rate
- Track in spreadsheet: Name, Company, Date, Status, Notes

---

## Strategy 3: GitHub as a Resume

When recruiters or engineers Google you, GitHub should impress in 10 seconds.

### Checklist

- [ ] Barq README is polished with benchmarks and clear value prop
- [ ] Pinned repos show your best work (Barq, Protego, Barebone)
- [ ] Contribution graph is active (green squares matter)
- [ ] Profile README exists with one-liner and links
- [ ] Clean commit history on public repos

### Barq README Structure

```
# Barq

A pure-Python HTTP framework for free-threaded Python 3.13+.
2-5x faster than FastAPI on real workloads.

## Why Barq?
[One paragraph on the problem it solves]

## Benchmarks
[Table or chart showing performance vs FastAPI]

## Quick Start
[5-line code example]

## Installation
[pip install command]
```

---

## Strategy 4: Recruiter Relationships

### Who to Target

- In-house recruiters at target companies (not agencies)
- Agency recruiters who specialize in your target domains (fintech, dev tools)

### How to Find Them

- LinkedIn search: "[Company] Technical Recruiter"
- Look for recruiters who post about roles you'd want
- Check who posted the job listings you're interested in

### Approach

```
Hi [Name],

I'm a backend engineer with 10+ years building high-throughput
systems (1B+ events/day). I also created Barq, a Python framework
faster than FastAPI.

Would love to be on your radar for backend/platform roles at
[Company]. Happy to share more context if helpful.
```

### Nurturing

- Share your Barq blog post when published
- Engage with their LinkedIn posts
- Follow up every 4-6 weeks with updates

---

## Strategy 5: Second-Degree Network Mining

You know more people than you think.

### LinkedIn Audit

1. Search: Your connections + "[Target Company]"
2. Look for: College classmates, ex-colleagues now at target companies
3. Reach out:

```
Hey [Name], long time! Saw you're at [Company] now — how's it going?

I'm exploring backend roles and [Company] is on my list. Would you
be open to a quick chat about the team/culture? Or if easier, could
you intro me to someone on the backend team?
```

### Ex-Colleague Network

People from Snapdeal, Cisco, BlackBerry, Dubizzle have dispersed.

1. List former colleagues you had good relationships with
2. Check where they are now on LinkedIn
3. Reach out casually, then steer toward your search

### Alumni Networks

- Anna University alumni at target companies
- Indian engineering alumni networks (strong in tech)
- University LinkedIn groups

---

## Strategy 6: Content for Inbound

Long game, but compounds over time.

### Content Calendar

| Type                | Frequency | Platform              |
| ------------------- | --------- | --------------------- |
| Technical blog post | 1-2/month | Personal blog, Dev.to |
| X/Twitter threads   | 2-3/week  | Twitter               |
| LinkedIn posts      | 1-2/week  | LinkedIn              |
| Open source updates | Ongoing   | GitHub, Twitter       |

### Blog Post Ideas

1. "How I made Barq 2-5x faster than FastAPI"
2. "Free-threaded Python: What it means for web frameworks"
3. "Building a 1B events/day pipeline: Lessons from Snapdeal"
4. "Multi-tenant architecture patterns I learned at BlackBerry"
5. "Why I stopped using async/await in Python"

### X/Twitter Strategy

- Share technical insights (not just links)
- Engage with Python community, target company engineers
- Build in public: Share Barq progress, learnings
- Controversial takes get engagement: "async/await is overrated"

### Compounding Effect

Post about Barq → Gets shared → Recruiter sees it → Inbound message
Talk at PyCon → Video on YouTube → Someone watches later → Inbound

---

## Immediate Action Plan

### Week 1

| Day | Action                                             |
| --- | -------------------------------------------------- |
| 1-2 | Write "How I made Barq faster than FastAPI" post   |
| 3   | Publish on Dev.to, cross-post to Reddit r/Python   |
| 4   | Submit to Python Weekly, PyCoder's Weekly          |
| 5   | LinkedIn audit — find 10 second-degree connections |
| 6-7 | Send 5 cold outreach messages to engineers         |

### Week 2

| Day | Action                                        |
| --- | --------------------------------------------- |
| 1-2 | Follow up on Week 1 outreach                  |
| 3   | Post Barq thread on X/Twitter                 |
| 4-5 | Send 5 more outreach messages                 |
| 6   | Connect with 3 recruiters at target companies |
| 7   | Review what's working, adjust                 |

### Ongoing Weekly Cadence

- 5-10 cold outreach messages
- 1-2 LinkedIn posts
- 2-3 X/Twitter posts
- 1 blog post per month
- Follow up on all conversations

---

## Tracking

### Outreach Tracker

| Name | Company | Role | Date | Channel | Status | Notes |
| ---- | ------- | ---- | ---- | ------- | ------ | ----- |
|      |         |      |      |         |        |       |

### Status Options

- Sent
- Responded
- Conversation
- Referral given
- Applied
- Interviewing
- No response

### Metrics to Watch

- Outreach response rate (target: 20-30%)
- Referrals generated per month
- Inbound messages per month
- Content engagement (views, shares)

---

## Mindset

**Stop thinking:** "I need to apply to jobs"

**Start thinking:** "I need to become visible to people who hire for jobs I want"

Your profile is high-variance. Cold applications will mostly fail. But one viral Barq post, one good conversation with a Staff engineer at Stripe, one podcast appearance — and suddenly you have warm paths.

The goal isn't to spray applications. The goal is to make the right people know you exist before you apply.
