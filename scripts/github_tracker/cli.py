from datetime import date
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from .export import export_json, export_json_string
from .story import build_org_story
from .tracker import fetch_contributions, list_user_orgs
from .types import OrgStory, YearlyReport

app = typer.Typer(
    name="github-tracker",
    help="GitHub Contributions Tracker - Track PRs and commits grouped by organization, year, and repository.",
)
console = Console()


@app.command()
def fetch(
    user: Annotated[str, typer.Option("--user", "-u", help="GitHub username")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Year to fetch contributions for")] = None,
    org: Annotated[Optional[str], typer.Option("--org", "-o", help="Filter by organization")] = None,
    from_date: Annotated[
        Optional[str], typer.Option("--from", "-f", help="Start date (YYYY-MM-DD)")
    ] = None,
    to_date: Annotated[Optional[str], typer.Option("--to", "-t", help="End date (YYYY-MM-DD)")] = None,
    output: Annotated[
        Optional[Path], typer.Option("--output", "-O", help="Output file path for JSON export")
    ] = None,
) -> None:
    if year and (from_date or to_date):
        rprint("[red]Error: Cannot specify both --year and --from/--to[/red]")
        raise typer.Exit(1)

    if year:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
    elif from_date and to_date:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)
    elif from_date or to_date:
        rprint("[red]Error: Both --from and --to are required when using date range[/red]")
        raise typer.Exit(1)
    else:
        current_year = date.today().year
        start = date(current_year, 1, 1)
        end = date(current_year, 12, 31)

    rprint(f"[bold]Fetching contributions for [cyan]{user}[/cyan]...[/bold]")
    rprint(f"Date range: {start} to {end}")
    if org:
        rprint(f"Organization: {org}")

    report = fetch_contributions(user, start, end, org)

    if output:
        export_json(report, output)
        rprint(f"\n[green]Report exported to {output}[/green]")
    else:
        rprint(export_json_string(report))

    rprint(f"\n[bold]Summary:[/bold]")
    rprint(f"  Total PRs: {report.total_prs}")
    rprint(f"  Total Commits: {report.total_commits}")
    rprint(f"  Organizations: {len(report.organizations)}")


@app.command()
def orgs(
    user: Annotated[str, typer.Option("--user", "-u", help="GitHub username")],
) -> None:
    rprint(f"[bold]Fetching organizations for [cyan]{user}[/cyan]...[/bold]")

    org_list = list_user_orgs(user)

    if not org_list:
        rprint("[yellow]No public organizations found[/yellow]")
        return

    table = Table(title=f"Organizations for {user}")
    table.add_column("Organization", style="cyan")

    for org_name in org_list:
        table.add_row(org_name)

    console.print(table)


@app.command()
def compare(
    users: Annotated[str, typer.Option("--users", "-u", help="Comma-separated list of GitHub usernames")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Year to compare")] = None,
    org: Annotated[Optional[str], typer.Option("--org", "-o", help="Filter by organization")] = None,
    from_date: Annotated[Optional[str], typer.Option("--from", "-f", help="Start date (YYYY-MM-DD)")] = None,
    to_date: Annotated[Optional[str], typer.Option("--to", "-t", help="End date (YYYY-MM-DD)")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-O", help="Output JSON file")] = None,
) -> None:
    if year and (from_date or to_date):
        rprint("[red]Error: Cannot specify both --year and --from/--to[/red]")
        raise typer.Exit(1)

    if year:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
    elif from_date and to_date:
        start = date.fromisoformat(from_date)
        end = date.fromisoformat(to_date)
    elif from_date or to_date:
        rprint("[red]Error: Both --from and --to are required when using date range[/red]")
        raise typer.Exit(1)
    else:
        current_year = date.today().year
        start = date(current_year, 1, 1)
        end = date(current_year, 12, 31)

    user_list = [u.strip() for u in users.split(",")]
    rprint(f"[bold]Comparing {len(user_list)} users for {start.year}...[/bold]")
    if org:
        rprint(f"Organization: {org}")

    reports: list[YearlyReport] = []
    for user in user_list:
        rprint(f"  Fetching [cyan]{user}[/cyan]...")
        report = fetch_contributions(user, start, end, org, show_progress=False)
        reports.append(report)

    table = Table(title=f"GitHub Contributions Comparison ({start.year})")
    table.add_column("User", style="cyan", no_wrap=True)
    table.add_column("PRs", justify="right", style="green")
    table.add_column("Commits", justify="right", style="yellow")
    table.add_column("Orgs", justify="right")
    table.add_column("Repos", justify="right")
    table.add_column("PRs/month", justify="right", style="dim")
    table.add_column("Commits/month", justify="right", style="dim")

    sorted_reports = sorted(reports, key=lambda r: (r.total_prs + r.total_commits), reverse=True)

    for report in sorted_reports:
        total_repos = sum(len(org_stats.repos) for org_stats in report.organizations.values())
        months = 12 if end.year == start.year else ((end - start).days / 30)
        prs_per_month = round(report.total_prs / months, 1)
        commits_per_month = round(report.total_commits / months, 1)

        table.add_row(
            report.user,
            str(report.total_prs),
            str(report.total_commits),
            str(len(report.organizations)),
            str(total_repos),
            str(prs_per_month),
            str(commits_per_month),
        )

    console.print()
    console.print(table)

    if output:
        import json
        comparison_data = {
            "year": start.year,
            "users": [
                {
                    "user": r.user,
                    "total_prs": r.total_prs,
                    "total_commits": r.total_commits,
                    "organizations": len(r.organizations),
                }
                for r in sorted_reports
            ],
        }
        output.write_text(json.dumps(comparison_data, indent=2))
        rprint(f"\n[green]Comparison exported to {output}[/green]")


@app.command()
def story(
    user: Annotated[str, typer.Option("--user", "-u", help="GitHub username")],
    org: Annotated[str, typer.Option("--org", "-o", help="Organization to generate story for")],
    years: Annotated[str, typer.Option("--years", "-y", help="Comma-separated years (e.g., 2023,2024,2025)")] = None,
    output: Annotated[Optional[Path], typer.Option("--output", "-O", help="Output JSON file")] = None,
) -> None:
    if years:
        year_list = [int(y.strip()) for y in years.split(",")]
    else:
        current_year = date.today().year
        year_list = [current_year - 1, current_year]

    rprint(f"[bold]Building story for [cyan]{user}[/cyan] at [magenta]{org}[/magenta]...[/bold]")
    rprint(f"Years: {', '.join(map(str, year_list))}")

    reports: list[YearlyReport] = []
    for year in year_list:
        rprint(f"  Fetching {year}...")
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        report = fetch_contributions(user, start, end, org, show_progress=False)
        reports.append(report)

    org_story = build_org_story(reports, org)

    _print_story(org_story)

    if output:
        import json
        output.write_text(json.dumps(org_story.model_dump(mode="json"), indent=2, default=str))
        rprint(f"\n[green]Story exported to {output}[/green]")


def _print_story(story: OrgStory) -> None:
    console.print()
    console.print(f"[bold blue]{'='*60}[/bold blue]")
    console.print(f"[bold blue]  {story.organization.upper()} - CONTRIBUTION STORY[/bold blue]")
    console.print(f"[bold blue]{'='*60}[/bold blue]")
    console.print()

    summary = story.summary
    console.print(f"[bold]User:[/bold] {story.user}")
    console.print(f"[bold]Tenure:[/bold] {story.tenure_start.strftime('%b %Y')} - {story.tenure_end.strftime('%b %Y')} ({summary.tenure_months} months)")
    console.print(f"[bold]Total PRs:[/bold] {story.total_prs}")
    console.print(f"[bold]Total Commits:[/bold] {story.total_commits}")
    console.print(f"[bold]Services:[/bold] {summary.total_services}")
    console.print()

    console.print(f"[bold yellow]{'─'*60}[/bold yellow]")
    console.print(f"[bold yellow]  SUMMARY[/bold yellow]")
    console.print(f"[bold yellow]{'─'*60}[/bold yellow]")
    console.print()

    svc_table = Table(title="Top Services by Contribution", show_header=True)
    svc_table.add_column("Service", style="cyan", no_wrap=True)
    svc_table.add_column("PRs", justify="right", style="green")
    svc_table.add_column("Commits", justify="right", style="yellow")
    svc_table.add_column("Role", style="dim")
    svc_table.add_column("Key Themes", style="magenta")

    for svc in summary.top_services:
        svc_table.add_row(
            svc.service,
            str(svc.prs),
            str(svc.commits),
            svc.role,
            ", ".join(svc.key_themes) if svc.key_themes else "-",
        )
    console.print(svc_table)
    console.print()

    cat = summary.categories
    cat_table = Table(title="PR Categories", show_header=True)
    cat_table.add_column("Category", style="bold")
    cat_table.add_column("Count", justify="right")

    if cat.feature: cat_table.add_row("[green]Feature[/green]", str(cat.feature))
    if cat.fix: cat_table.add_row("[red]Fix[/red]", str(cat.fix))
    if cat.chore: cat_table.add_row("[dim]Chore[/dim]", str(cat.chore))
    if cat.refactor: cat_table.add_row("[yellow]Refactor[/yellow]", str(cat.refactor))
    if cat.infra: cat_table.add_row("[blue]Infra[/blue]", str(cat.infra))
    if cat.perf: cat_table.add_row("[magenta]Performance[/magenta]", str(cat.perf))
    if cat.test: cat_table.add_row("[cyan]Test[/cyan]", str(cat.test))
    if cat.docs: cat_table.add_row("[white]Docs[/white]", str(cat.docs))
    if cat.other: cat_table.add_row("[dim]Other[/dim]", str(cat.other))

    console.print(cat_table)
    console.print()

    if summary.technologies:
        console.print(f"[bold]Technologies:[/bold] {', '.join(summary.technologies)}")
        console.print()

    console.print(f"[bold yellow]{'─'*60}[/bold yellow]")
    console.print(f"[bold yellow]  SERVICE DETAILS[/bold yellow]")
    console.print(f"[bold yellow]{'─'*60}[/bold yellow]")

    for service_name, service in story.services.items():
        if service.total_prs == 0 and service.total_commits == 0:
            continue

        console.print(f"[bold cyan]{'─'*60}[/bold cyan]")
        console.print(f"[bold cyan]  {service_name}[/bold cyan]")
        console.print(f"[bold cyan]{'─'*60}[/bold cyan]")
        console.print(f"  [bold]Role:[/bold] {service.role}")
        console.print(f"  [bold]Period:[/bold] {service.tenure_start.strftime('%b %Y')} - {service.tenure_end.strftime('%b %Y')}")
        console.print(f"  [bold]PRs:[/bold] {service.total_prs} | [bold]Commits:[/bold] {service.total_commits}")
        console.print()

        cat = service.categories
        categories_str = []
        if cat.feature: categories_str.append(f"[green]feature:{cat.feature}[/green]")
        if cat.fix: categories_str.append(f"[red]fix:{cat.fix}[/red]")
        if cat.refactor: categories_str.append(f"[yellow]refactor:{cat.refactor}[/yellow]")
        if cat.infra: categories_str.append(f"[blue]infra:{cat.infra}[/blue]")
        if cat.perf: categories_str.append(f"[magenta]perf:{cat.perf}[/magenta]")
        if cat.chore: categories_str.append(f"[dim]chore:{cat.chore}[/dim]")
        if cat.test: categories_str.append(f"[cyan]test:{cat.test}[/cyan]")
        if cat.docs: categories_str.append(f"[white]docs:{cat.docs}[/white]")
        if cat.other: categories_str.append(f"[dim]other:{cat.other}[/dim]")

        if categories_str:
            console.print(f"  [bold]Categories:[/bold] {' | '.join(categories_str)}")

        if service.technologies:
            console.print(f"  [bold]Technologies:[/bold] {', '.join(service.technologies)}")

        if service.highlights:
            console.print(f"  [bold]Highlights:[/bold]")
            for highlight in service.highlights[:5]:
                console.print(f"    - {highlight}")

        if service.key_prs:
            console.print(f"  [bold]Key PRs:[/bold]")
            for pr in service.key_prs[:3]:
                console.print(f"    - {pr.title[:70]}")
                console.print(f"      [dim]{pr.url}[/dim]")

        console.print()


if __name__ == "__main__":
    app()
