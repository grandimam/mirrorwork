from datetime import date, datetime
from typing import Any

from rich.progress import Progress, SpinnerColumn, TextColumn

from .client import GitHubClient
from .types import Commit, OrgStats, PullRequest, RepoStats, YearlyReport


def parse_repo_info(url: str) -> tuple[str, str]:
    parts = url.replace("https://github.com/", "").replace("https://api.github.com/repos/", "").split("/")
    return parts[0], parts[1]


def parse_pr(item: dict[str, Any]) -> PullRequest:
    org, repo = parse_repo_info(item["repository_url"])
    return PullRequest(
        id=item["id"],
        number=item["number"],
        title=item["title"],
        url=item["html_url"],
        state=item["state"],
        created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
        merged_at=datetime.fromisoformat(item["pull_request"]["merged_at"].replace("Z", "+00:00"))
        if item.get("pull_request", {}).get("merged_at")
        else None,
        repository=repo,
        organization=org,
    )


def parse_commit(item: dict[str, Any]) -> Commit:
    org, repo = parse_repo_info(item["repository"]["html_url"])
    commit_date = item["commit"]["committer"]["date"]
    return Commit(
        sha=item["sha"],
        message=item["commit"]["message"].split("\n")[0],
        url=item["html_url"],
        created_at=datetime.fromisoformat(commit_date.replace("Z", "+00:00")),
        repository=repo,
        organization=org,
    )


def fetch_contributions(
    user: str,
    start_date: date,
    end_date: date,
    org: str | None = None,
    show_progress: bool = True,
) -> YearlyReport:
    with GitHubClient() as client:
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
            ) as progress:
                progress.add_task("Fetching pull requests...", total=None)
                raw_prs = client.search_prs(user, start_date, end_date, org)

                progress.add_task("Fetching commits...", total=None)
                raw_commits = client.search_commits(user, start_date, end_date, org)
        else:
            raw_prs = client.search_prs(user, start_date, end_date, org)
            raw_commits = client.search_commits(user, start_date, end_date, org)

    prs = [parse_pr(item) for item in raw_prs]
    commits = [parse_commit(item) for item in raw_commits]

    return build_report(user, start_date.year, prs, commits)


def build_report(
    user: str,
    year: int,
    prs: list[PullRequest],
    commits: list[Commit],
) -> YearlyReport:
    organizations: dict[str, OrgStats] = {}

    for pr in prs:
        if pr.organization not in organizations:
            organizations[pr.organization] = OrgStats(organization=pr.organization)

        org_stats = organizations[pr.organization]
        if pr.repository not in org_stats.repos:
            org_stats.repos[pr.repository] = RepoStats(repository=pr.repository)

        org_stats.repos[pr.repository].prs.append(pr)

    for commit in commits:
        if commit.organization not in organizations:
            organizations[commit.organization] = OrgStats(organization=commit.organization)

        org_stats = organizations[commit.organization]
        if commit.repository not in org_stats.repos:
            org_stats.repos[commit.repository] = RepoStats(repository=commit.repository)

        org_stats.repos[commit.repository].commits.append(commit)

    return YearlyReport(
        user=user,
        year=year,
        organizations=organizations,
    )


def list_user_orgs(user: str) -> list[str]:
    with GitHubClient() as client:
        orgs = client.get_user_orgs(user)
    return [org["login"] for org in orgs]
