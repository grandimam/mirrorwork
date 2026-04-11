from datetime import datetime
from pydantic import BaseModel, Field


class PullRequest(BaseModel):
    id: int
    number: int
    title: str
    url: str
    state: str
    created_at: datetime
    merged_at: datetime | None = None
    repository: str
    organization: str


class Commit(BaseModel):
    sha: str
    message: str
    url: str
    created_at: datetime
    repository: str
    organization: str


class RepoStats(BaseModel):
    repository: str
    prs: list[PullRequest] = Field(default_factory=list)
    commits: list[Commit] = Field(default_factory=list)

    @property
    def pr_count(self) -> int:
        return len(self.prs)

    @property
    def commit_count(self) -> int:
        return len(self.commits)

    def model_dump(self, **kwargs) -> dict:
        data = super().model_dump(**kwargs)
        data["pr_count"] = self.pr_count
        data["commit_count"] = self.commit_count
        return data


class OrgStats(BaseModel):
    organization: str
    repos: dict[str, RepoStats] = Field(default_factory=dict)

    @property
    def total_prs(self) -> int:
        return sum(repo.pr_count for repo in self.repos.values())

    @property
    def total_commits(self) -> int:
        return sum(repo.commit_count for repo in self.repos.values())

    def model_dump(self, **kwargs) -> dict:
        data = super().model_dump(**kwargs)
        data["total_prs"] = self.total_prs
        data["total_commits"] = self.total_commits
        return data


class YearlyReport(BaseModel):
    user: str
    year: int
    organizations: dict[str, OrgStats] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.now)

    @property
    def total_prs(self) -> int:
        return sum(org.total_prs for org in self.organizations.values())

    @property
    def total_commits(self) -> int:
        return sum(org.total_commits for org in self.organizations.values())

    def model_dump(self, **kwargs) -> dict:
        data = super().model_dump(**kwargs)
        data["total_prs"] = self.total_prs
        data["total_commits"] = self.total_commits
        return data


class PRCategory(BaseModel):
    feature: int = 0
    fix: int = 0
    refactor: int = 0
    infra: int = 0
    perf: int = 0
    docs: int = 0
    test: int = 0
    chore: int = 0
    other: int = 0


class ServiceStory(BaseModel):
    service: str
    role: str
    tenure_start: datetime
    tenure_end: datetime
    total_prs: int = 0
    total_commits: int = 0
    categories: PRCategory = Field(default_factory=PRCategory)
    highlights: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    key_prs: list[PullRequest] = Field(default_factory=list)


class ServiceSummary(BaseModel):
    service: str
    prs: int
    commits: int
    role: str
    key_themes: list[str] = Field(default_factory=list)


class CategorySummary(BaseModel):
    feature: int = 0
    fix: int = 0
    refactor: int = 0
    infra: int = 0
    perf: int = 0
    docs: int = 0
    test: int = 0
    chore: int = 0
    other: int = 0


class StorySummary(BaseModel):
    tenure_months: int = 0
    total_prs: int = 0
    total_commits: int = 0
    total_services: int = 0
    top_services: list[ServiceSummary] = Field(default_factory=list)
    categories: CategorySummary = Field(default_factory=CategorySummary)
    technologies: list[str] = Field(default_factory=list)


class OrgStory(BaseModel):
    organization: str
    user: str
    tenure_start: datetime
    tenure_end: datetime
    total_prs: int = 0
    total_commits: int = 0
    services: dict[str, ServiceStory] = Field(default_factory=dict)
    summary: StorySummary = Field(default_factory=StorySummary)
    generated_at: datetime = Field(default_factory=datetime.now)
