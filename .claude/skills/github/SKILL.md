# GitHub Tracker

Analyze GitHub contributions to enrich your career profile.

## Commands

### `/github` (no args)

Show available commands.

### `/github fetch`

Fetch contributions for a GitHub user.

```bash
python -m scripts.github_tracker.cli fetch --user <username> --year <year> --output sources/github/reports/<year>.json
```

### `/github story`

Build contribution story for an organization.

```bash
python -m scripts.github_tracker.cli story --user <username> --org <org> --output sources/github/stories/<org>.json
```

### `/github orgs`

List organizations for a user.

```bash
python -m scripts.github_tracker.cli orgs --user <username>
```

### `/github compare`

Compare contributions across users.

```bash
python -m scripts.github_tracker.cli compare --users <user1,user2> [--year <year>]
```

### `/github sync`

Sync all GitHub data and update storybank.

1. Read GitHub username from `profile/identity.yml` or ask
2. Fetch current year contributions
3. Save to `sources/github/reports/{year}.json`
4. Generate stories for each org
5. Save to `sources/github/stories/{org}.json`
6. Trigger storybank regeneration

### `/github enrich`

Auto-generate proof points from GitHub activity.

1. Read stories from `sources/github/stories/`
2. Extract key PRs and highlights
3. Convert to proof-point format
4. Append to `profile/proof-points.yml`
5. Trigger storybank regeneration

## Data Storage

```
sources/github/
├── reports/                # Yearly contributions
│   ├── 2024.json
│   └── 2025.json
└── stories/                # Organization stories
    ├── dubizzle.json
    └── stripe.json
```

## CLI Location

```
scripts/github_tracker/
├── cli.py
├── client.py
├── tracker.py
├── story.py
├── export.py
└── types.py
```

## Requirements

- `gh` CLI installed and authenticated
- Python: `typer`, `rich`, `httpx`, `pydantic`
