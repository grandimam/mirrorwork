# Dashboard Agent

Open the mirrorwork HTML dashboard.

## Invocation

Called by `/mw dashboard`.

## How It Works

The dashboard is a static HTML file that fetches JSON data directly using JavaScript. No build step needed.

**Data sources (fetched via browser):**
- `profile/identity.json`
- `profile/positioning.json`
- `profile/experience.json`
- `profile/skills.json`
- `profile/proof-points.json`
- `activity/jobs/*.json`

## Flow

### Step 1: Start Server

Start a local HTTP server in the project root:

```bash
cd /path/to/mirrorwork && python -m http.server 3333 &
```

Check if already running first to avoid port conflicts.

### Step 2: Open Dashboard

```bash
open http://localhost:3333/dashboard/
```

On Linux use `xdg-open`, on Windows use `start`.

### Step 3: Confirm

```
╭─────────────────────────────────────╮
│  ✓ Dashboard ready!                 │
╰─────────────────────────────────────╯

→ Open: http://localhost:3333/dashboard/

The dashboard auto-refreshes every 5 seconds.
Edit your profile or job files and watch it update.

To stop the server: kill %1 (or close terminal)
```

## Updating Job List

The dashboard currently needs a list of job files. To add new jobs to the dashboard, update the `files` array in `dashboard/index.html`:

```javascript
const files = ['unison-group-senior-java-backend.json', 'new-job.json'];
```

Or implement a manifest file (`activity/jobs/manifest.json`) for dynamic loading.
