import subprocess
import time
from datetime import date, timedelta
from typing import Any, Callable, Generator

import httpx

GITHUB_API_URL = "https://api.github.com"
MAX_SEARCH_RESULTS = 1000
MAX_RETRIES = 5


def get_gh_token() -> str:
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Failed to get GitHub token. Make sure 'gh' CLI is installed and authenticated.")
    return result.stdout.strip()


class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or get_gh_token()
        self.client = httpx.Client(
            base_url=GITHUB_API_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    def _request_with_retry(self, url: str, params: dict[str, Any]) -> httpx.Response:
        for attempt in range(MAX_RETRIES):
            response = self.client.get(url, params=params)
            if response.status_code == 403:
                retry_after = int(response.headers.get("Retry-After", 60))
                reset_time = response.headers.get("X-RateLimit-Reset")
                if reset_time:
                    wait_time = max(1, int(reset_time) - int(time.time()) + 1)
                else:
                    wait_time = retry_after * (2 ** attempt)
                time.sleep(min(wait_time, 120))
                continue
            response.raise_for_status()
            return response
        response.raise_for_status()
        return response

    def _paginate(self, url: str, params: dict[str, Any]) -> Generator[dict[str, Any], None, None]:
        params = {**params, "per_page": 100}
        while True:
            response = self._request_with_retry(url, params)
            data = response.json()
            yield data
            if "next" not in response.links:
                break
            url = response.links["next"]["url"]
            params = {}

    def _search_with_count(self, url: str, query: str) -> tuple[int, list[dict[str, Any]]]:
        results: list[dict[str, Any]] = []
        total_count = 0
        for page in self._paginate(url, {"q": query}):
            total_count = page.get("total_count", 0)
            results.extend(page.get("items", []))
        return total_count, results

    def _search_chunked(
        self,
        url: str,
        user: str,
        start_date: date,
        end_date: date,
        org: str | None,
        query_builder: Callable[[str, str, str | None], str],
    ) -> list[dict[str, Any]]:
        date_range = f"{start_date.isoformat()}..{end_date.isoformat()}"
        query = query_builder(user, date_range, org)

        total_count, results = self._search_with_count(url, query)

        if total_count >= MAX_SEARCH_RESULTS and start_date < end_date:
            mid_date = start_date + (end_date - start_date) // 2
            first_half = self._search_chunked(url, user, start_date, mid_date, org, query_builder)
            second_half = self._search_chunked(url, user, mid_date + timedelta(days=1), end_date, org, query_builder)
            seen_ids: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for item in first_half + second_half:
                item_id = str(item.get("id") or item.get("sha"))
                if item_id not in seen_ids:
                    seen_ids.add(item_id)
                    deduped.append(item)
            return deduped

        return results

    def search_prs(
        self,
        user: str,
        start_date: date,
        end_date: date,
        org: str | None = None,
    ) -> list[dict[str, Any]]:
        def build_query(user: str, date_range: str, org: str | None) -> str:
            query = f"author:{user} type:pr created:{date_range}"
            if org:
                query += f" org:{org}"
            return query

        return self._search_chunked("/search/issues", user, start_date, end_date, org, build_query)

    def search_commits(
        self,
        user: str,
        start_date: date,
        end_date: date,
        org: str | None = None,
    ) -> list[dict[str, Any]]:
        def build_query(user: str, date_range: str, org: str | None) -> str:
            query = f"author:{user} committer-date:{date_range}"
            if org:
                query += f" org:{org}"
            return query

        return self._search_chunked("/search/commits", user, start_date, end_date, org, build_query)

    def get_user_orgs(self, user: str) -> list[dict[str, Any]]:
        response = self.client.get(f"/users/{user}/orgs")
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "GitHubClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()
