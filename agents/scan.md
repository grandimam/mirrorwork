# Scan Agent

You are the **scan agent** for mirrorwork. Your job is to discover new job postings from configured portals.

## Invocation

Called by `/mw scan`.

## UX Guidelines

```
╭─────────────────────────────────────╮
│  mirrorwork · Scan                  │
╰─────────────────────────────────────╯
```

## Workflow

### Step 1: Load Configuration

Read `activity/manifest.json` to get portals list.

If no portals configured:
```
No portals configured.

Add portals to activity/manifest.json:
{
  "portals": [
    {
      "name": "Company Name",
      "url": "https://careers.company.com",
      "location": "City, Remote",
      "target_roles": ["backend", "senior", "platform"],
      "last_scan": null,
      "enabled": true
    }
  ]
}
```

Portal fields:
- `name`: Display name
- `url`: Careers page URL
- `location`: Target location (for reference)
- `target_roles`: Keywords to filter job titles
- `last_scan`: When last scanned (auto-updated)
- `enabled`: Include in scans

### Step 2: Load Seen URLs

Read all files in `activity/inbox/*.json` and collect all URLs into a Set for dedup.

### Step 3: Scan Each Portal

For each portal with `enabled: true`:

1. **Fetch the careers page** using Playwright:
   - `browser_navigate` to portal URL
   - `browser_snapshot` to read content
   - `browser_screenshot` if content is hard to parse (JS-heavy pages, complex layouts)

   **When to use screenshot:**
   - Page content loads dynamically via JavaScript
   - Job cards are rendered as complex visual components
   - Snapshot returns incomplete or garbled content
   - Need to visually verify pagination controls

2. **Handle pagination** (collect jobs from ALL pages):

   **Detection:** Look for pagination indicators:
   - "Next" / "→" / ">" links
   - Page numbers (1, 2, 3...)
   - "Load more" buttons
   - URL contains `page=`, `offset=`, `start=`

   **Pagination patterns:**
   | Pattern | Example | How to paginate |
   |---------|---------|-----------------|
   | Query param | `?page=1` | Increment `page` param |
   | Offset | `?offset=0` | Add page size to offset |
   | Infinite scroll | (no URL change) | Scroll down, wait for load |
   | Load more | Button on page | Click button, wait for load |

   **Process:**
   - Extract jobs from current page
   - Check for next page indicator
   - If found: navigate to next page, repeat
   - **Max 10 pages** per portal (safety limit)
   - Stop if page returns 0 new jobs (end of list)

3. **Extract job listings** from each page:

   **Method A: From snapshot (preferred)**
   - Look for job titles + URLs in HTML content
   - Common patterns:
     - Lever: `<a>` tags with `/jobs/` in href
     - Greenhouse: job cards with links
     - Ashby: job listing components
     - Delivery Hero: job cards with links to `/jobs/`
     - Generic: links containing "job", "position", "career"

   **Method B: From screenshot (fallback)**
   - Take screenshot with `browser_screenshot`
   - Visually identify job titles from the image
   - Extract URLs by clicking on visible job cards
   - Use when: snapshot is incomplete, page is JS-heavy, or layout is visual-first

4. **Filter by target_roles**:
   - If `target_roles` is set, check if job title contains any keyword (case-insensitive)
   - If no match, skip this job
   - If `target_roles` is empty/null, include all jobs

5. **For each matching job**:
   - Check if URL is in seen Set
   - If new: add to today's inbox
   - If seen: skip

6. **Update portal.last_scan** to today's date

### Step 4: Save Results

Get today's date as `YYYY-MM-DD`.

**Save all jobs to `activity/inbox/{date}.json`:**
```json
{
  "date": "2026-04-12",
  "jobs": [
    {
      "url": "https://jobs.lever.co/anthropic/abc123",
      "portal": "Anthropic",
      "title": "Senior Backend Engineer",
      "matched": true,
      "status": "pending"
    },
    {
      "url": "https://jobs.lever.co/anthropic/def456",
      "portal": "Anthropic",
      "title": "Office Manager",
      "matched": false,
      "status": "filtered"
    }
  ]
}
```

**Job fields:**
- `matched: true` → Job title contains a target_role keyword, status starts as `"pending"`
- `matched: false` → Filtered out by target_roles, status is `"filtered"`

If file exists, append to jobs array. If not, create new file.

**Update `activity/manifest.json`** with new `last_scan` dates.

### Step 5: Show Summary

```
───────────────────────────────────────
📡 **Scan Complete**

| Portal | Jobs Found | New |
|--------|------------|-----|
| Anthropic | 12 | 3 |
| OpenAI | 8 | 1 |
| Stripe | 15 | 0 |

**4 new jobs added to inbox**

• Anthropic — Senior Backend Engineer
• Anthropic — Staff ML Engineer
• Anthropic — Platform Engineer
• OpenAI — Research Engineer

───────────────────────────────────────
→ Run `/mw inbox` to review
```

## Error Handling

If a portal fails to load:
- Log the error
- Continue with other portals
- Show in summary: `Anthropic — ⚠️ Failed to load`

## Supported Portal Patterns

| Platform | URL Pattern | Extraction | Pagination |
|----------|-------------|------------|------------|
| Lever | jobs.lever.co/{company} | `<a>` with `/jobs/` href | Usually single page |
| Greenhouse | boards.greenhouse.io/{company} | Job cards | `?page=N` param |
| Ashby | jobs.ashbyhq.com/{company} | Job listings | Infinite scroll |
| Workday | {company}.wd5.myworkdayjobs.com | Job table | `?offset=N` param |
| Delivery Hero | careers.deliveryhero.com | Job cards | `?page=N` param |
| Generic | Any careers page | Links with job/position keywords | Detect from page |

## Notes

- Run scans during off-peak hours if possible
- Respect rate limits — don't scan too frequently
- Some portals may require scrolling to load all jobs
- Always check for pagination before finishing a portal
- Stop pagination after 10 pages or when no new jobs found
