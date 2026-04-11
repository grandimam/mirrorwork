import re
from collections import defaultdict
from datetime import datetime

from .types import (
    CategorySummary,
    OrgStory,
    PRCategory,
    PullRequest,
    ServiceStory,
    ServiceSummary,
    StorySummary,
    YearlyReport,
)

CATEGORY_PATTERNS: dict[str, list[str]] = {
    "feature": [
        r"\badd(ed|ing|s)?\b",
        r"\bimplement(ed|ing|s)?\b",
        r"\bcreate(d|s)?\b",
        r"\bbuild(ing)?\b",
        r"\bintroduc(e|ed|ing)\b",
        r"\bnew\b",
        r"\bsupport\b",
        r"\benable\b",
        r"\bintegrat(e|ed|ing|ion)\b",
    ],
    "fix": [
        r"\bfix(ed|es|ing)?\b",
        r"\bbug\b",
        r"\bpatch\b",
        r"\bresolv(e|ed|ing)\b",
        r"\bhotfix\b",
        r"\bissue\b",
        r"\bcorrect(ed|ing|s)?\b",
    ],
    "refactor": [
        r"\brefactor(ed|ing|s)?\b",
        r"\brestructur(e|ed|ing)\b",
        r"\bclean(ed|ing|up)?\b",
        r"\bsimplif(y|ied|ying)\b",
        r"\breorganiz(e|ed|ing)\b",
        r"\bmodulariz(e|ed|ing)\b",
    ],
    "infra": [
        r"\bdeploy(ment|ed|ing|s)?\b",
        r"\bci(/cd)?\b",
        r"\bpipeline\b",
        r"\bdocker\b",
        r"\bkubernetes\b",
        r"\bk8s\b",
        r"\bhelm\b",
        r"\bterraform\b",
        r"\bconfig(uration)?\b",
        r"\benv(ironment)?\b",
        r"\binfra(structure)?\b",
    ],
    "perf": [
        r"\bperformance\b",
        r"\boptimiz(e|ed|ing|ation)\b",
        r"\bspeed\b",
        r"\bfast(er)?\b",
        r"\bcache\b",
        r"\bcaching\b",
        r"\blatency\b",
        r"\bscal(e|ing|ability)\b",
    ],
    "docs": [
        r"\bdoc(s|umentation)?\b",
        r"\breadme\b",
        r"\bcomment(s|ed|ing)?\b",
        r"\bchangelog\b",
    ],
    "test": [
        r"\btest(s|ed|ing)?\b",
        r"\bspec(s)?\b",
        r"\bcoverage\b",
        r"\bmock(s|ed|ing)?\b",
        r"\bunit\b",
        r"\bintegration\b",
        r"\be2e\b",
    ],
    "chore": [
        r"\bchore\b",
        r"\bbump\b",
        r"\bupgrad(e|ed|ing)\b",
        r"\bupdat(e|ed|ing)\b",
        r"\bdependenc(y|ies)\b",
        r"\bversion\b",
        r"\bmerge\b",
        r"\bsync\b",
    ],
}

TECH_PATTERNS: dict[str, list[str]] = {
    "Python": [r"\bpython\b", r"\.py\b"],
    "FastAPI": [r"\bfastapi\b", r"\bendpoint\b", r"\broute\b", r"\bapi\b"],
    "PostgreSQL": [r"\bpostgres(ql)?\b", r"\bpsql\b", r"\bdatabase\b", r"\bdb\b", r"\bsql\b"],
    "Redis": [r"\bredis\b", r"\bcache\b", r"\bcaching\b"],
    "Kafka": [r"\bkafka\b", r"\bproducer\b", r"\bconsumer\b", r"\btopic\b", r"\bmessage\b"],
    "Algolia": [r"\balgolia\b", r"\bsearch\b", r"\bindex(ing|es)?\b"],
    "Elasticsearch": [r"\belastic(search)?\b", r"\bes\b"],
    "Docker": [r"\bdocker\b", r"\bcontainer\b", r"\bimage\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b", r"\bhelm\b", r"\bpod\b"],
    "AWS": [r"\baws\b", r"\bs3\b", r"\blambda\b", r"\bsqs\b", r"\bsns\b", r"\bec2\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle cloud\b", r"\bbigquery\b", r"\bpubsub\b"],
    "CI/CD": [r"\bci(/cd)?\b", r"\bpipeline\b", r"\bgithub actions\b", r"\bjenkins\b"],
    "GraphQL": [r"\bgraphql\b", r"\bquery\b", r"\bmutation\b"],
    "REST": [r"\brest\b", r"\bendpoint\b", r"\bapi\b"],
    "Celery": [r"\bcelery\b", r"\btask\b", r"\bworker\b", r"\basync\b"],
    "Authentication": [r"\bauth\b", r"\bjwt\b", r"\boauth\b", r"\btoken\b", r"\blogin\b"],
    "Testing": [r"\bpytest\b", r"\bunittest\b", r"\btest\b", r"\bmock\b"],
}

HIGHLIGHT_PATTERNS: list[tuple[str, str]] = [
    (r"\bmigrat(e|ed|ing|ion)\b", "Migration"),
    (r"\bintegrat(e|ed|ing|ion)\b", "Integration"),
    (r"\boptimiz(e|ed|ing|ation)\b", "Optimization"),
    (r"\bscal(e|ed|ing|ability)\b", "Scaling"),
    (r"\bperformance\b", "Performance"),
    (r"\bsecurity\b", "Security"),
    (r"\bauth(entication|orization)?\b", "Authentication"),
    (r"\bapi\b", "API"),
    (r"\bsearch\b", "Search"),
    (r"\balgolia\b", "Algolia"),
    (r"\bkafka\b", "Kafka"),
    (r"\bwebhook\b", "Webhook"),
    (r"\bnotification\b", "Notification"),
    (r"\bemail\b", "Email"),
    (r"\bsms\b", "SMS"),
    (r"\bpayment\b", "Payment"),
    (r"\banalytics\b", "Analytics"),
    (r"\bdashboard\b", "Dashboard"),
    (r"\breport(ing)?\b", "Reporting"),
    (r"\bexport\b", "Export"),
    (r"\bimport\b", "Import"),
    (r"\bsync\b", "Sync"),
    (r"\bcron\b", "Scheduled Jobs"),
    (r"\bcelery\b", "Background Jobs"),
    (r"\bqueue\b", "Queue"),
    (r"\bcache\b", "Caching"),
    (r"\bvalidat(e|ion)\b", "Validation"),
    (r"\berror\s*handl(e|ing)\b", "Error Handling"),
    (r"\blogg(ing|er)\b", "Logging"),
    (r"\bmonitor(ing)?\b", "Monitoring"),
    (r"\balert\b", "Alerting"),
]


def categorize_pr(title: str) -> str:
    title_lower = title.lower()
    scores: dict[str, int] = defaultdict(int)

    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, title_lower):
                scores[category] += 1

    if not scores:
        return "other"

    return max(scores, key=lambda k: scores[k])


def extract_technologies(prs: list[PullRequest]) -> list[str]:
    tech_scores: dict[str, int] = defaultdict(int)

    for pr in prs:
        title_lower = pr.title.lower()
        for tech, patterns in TECH_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, title_lower):
                    tech_scores[tech] += 1
                    break

    sorted_techs = sorted(tech_scores.items(), key=lambda x: -x[1])
    return [tech for tech, _ in sorted_techs[:8]]


def extract_highlights(prs: list[PullRequest]) -> list[str]:
    highlights: dict[str, list[str]] = defaultdict(list)

    for pr in prs:
        title_lower = pr.title.lower()
        for pattern, label in HIGHLIGHT_PATTERNS:
            if re.search(pattern, title_lower):
                highlights[label].append(pr.title)
                break

    result: list[str] = []
    for label, pr_titles in sorted(highlights.items(), key=lambda x: -len(x[1])):
        if len(pr_titles) >= 2:
            result.append(f"{label} ({len(pr_titles)} PRs)")
        elif len(pr_titles) == 1:
            result.append(f"{label}: {pr_titles[0][:60]}")

    return result[:10]


def determine_role(pr_count: int, total_prs_in_repo: int) -> str:
    if total_prs_in_repo == 0:
        return "Contributor"
    ratio = pr_count / total_prs_in_repo
    if ratio > 0.3:
        return "Primary Contributor"
    elif ratio > 0.15:
        return "Major Contributor"
    elif ratio > 0.05:
        return "Regular Contributor"
    else:
        return "Contributor"


def get_key_prs(prs: list[PullRequest], limit: int = 5) -> list[PullRequest]:
    keywords = [
        "implement", "add", "create", "build", "integrate", "migrate",
        "launch", "release", "major", "new", "feature", "system"
    ]

    scored: list[tuple[PullRequest, int]] = []
    for pr in prs:
        title_lower = pr.title.lower()
        score = sum(1 for kw in keywords if kw in title_lower)
        score += len(pr.title.split()) // 3
        if pr.merged_at:
            score += 2
        scored.append((pr, score))

    scored.sort(key=lambda x: -x[1])
    return [pr for pr, _ in scored[:limit]]


def build_service_story(
    service: str,
    prs: list[PullRequest],
    commits_count: int,
) -> ServiceStory:
    if not prs:
        return ServiceStory(
            service=service,
            role="Contributor",
            tenure_start=datetime.now(),
            tenure_end=datetime.now(),
            total_commits=commits_count,
        )

    categories = PRCategory()
    for pr in prs:
        category = categorize_pr(pr.title)
        current = getattr(categories, category)
        setattr(categories, category, current + 1)

    dates = [pr.created_at for pr in prs]
    tenure_start = min(dates)
    tenure_end = max(dates)

    return ServiceStory(
        service=service,
        role=determine_role(len(prs), len(prs)),
        tenure_start=tenure_start,
        tenure_end=tenure_end,
        total_prs=len(prs),
        total_commits=commits_count,
        categories=categories,
        highlights=extract_highlights(prs),
        technologies=extract_technologies(prs),
        key_prs=get_key_prs(prs),
    )


def build_org_story(reports: list[YearlyReport], org: str) -> OrgStory:
    all_prs: dict[str, list[PullRequest]] = defaultdict(list)
    all_commits: dict[str, int] = defaultdict(int)
    all_dates: list[datetime] = []

    user = reports[0].user if reports else "unknown"

    for report in reports:
        if org not in report.organizations:
            continue
        org_data = report.organizations[org]
        for repo_name, repo_data in org_data.repos.items():
            all_prs[repo_name].extend(repo_data.prs)
            all_commits[repo_name] += len(repo_data.commits)
            all_dates.extend([pr.created_at for pr in repo_data.prs])

    if not all_dates:
        return OrgStory(
            organization=org,
            user=user,
            tenure_start=datetime.now(),
            tenure_end=datetime.now(),
        )

    services: dict[str, ServiceStory] = {}
    for repo_name, prs in all_prs.items():
        services[repo_name] = build_service_story(
            repo_name, prs, all_commits.get(repo_name, 0)
        )

    sorted_services = dict(
        sorted(services.items(), key=lambda x: -(x[1].total_prs + x[1].total_commits))
    )

    total_prs = sum(s.total_prs for s in services.values())
    total_commits = sum(s.total_commits for s in services.values())

    tenure_start = min(all_dates)
    tenure_end = max(all_dates)
    tenure_months = (tenure_end.year - tenure_start.year) * 12 + (tenure_end.month - tenure_start.month)

    summary = build_summary(sorted_services, tenure_months, total_prs, total_commits)

    return OrgStory(
        organization=org,
        user=user,
        tenure_start=tenure_start,
        tenure_end=tenure_end,
        total_prs=total_prs,
        total_commits=total_commits,
        services=sorted_services,
        summary=summary,
    )


def build_summary(
    services: dict[str, ServiceStory],
    tenure_months: int,
    total_prs: int,
    total_commits: int,
) -> StorySummary:
    top_services: list[ServiceSummary] = []
    for name, svc in list(services.items())[:10]:
        if svc.total_prs == 0 and svc.total_commits == 0:
            continue
        key_themes = [h.split(" (")[0].split(":")[0] for h in svc.highlights[:4]]
        top_services.append(
            ServiceSummary(
                service=name,
                prs=svc.total_prs,
                commits=svc.total_commits,
                role=svc.role,
                key_themes=key_themes,
            )
        )

    cat_totals = CategorySummary()
    all_techs: dict[str, int] = defaultdict(int)
    for svc in services.values():
        cat_totals.feature += svc.categories.feature
        cat_totals.fix += svc.categories.fix
        cat_totals.refactor += svc.categories.refactor
        cat_totals.infra += svc.categories.infra
        cat_totals.perf += svc.categories.perf
        cat_totals.docs += svc.categories.docs
        cat_totals.test += svc.categories.test
        cat_totals.chore += svc.categories.chore
        cat_totals.other += svc.categories.other
        for tech in svc.technologies:
            all_techs[tech] += 1

    sorted_techs = sorted(all_techs.items(), key=lambda x: -x[1])
    technologies = [t for t, _ in sorted_techs[:10]]

    return StorySummary(
        tenure_months=tenure_months,
        total_prs=total_prs,
        total_commits=total_commits,
        total_services=len([s for s in services.values() if s.total_prs > 0 or s.total_commits > 0]),
        top_services=top_services,
        categories=cat_totals,
        technologies=technologies,
    )
