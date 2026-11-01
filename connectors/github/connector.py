"""GitHub: your commits on chosen repositories, as `commit` events.

Reads each repository's default branch with a personal access token. Commits made on a feature
branch appear once they're merged, still dated when they were written, so every sync looks back
a week and the cursor remembers which commits it has already seen.
"""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
from goalpost.sdk import (
    SDK_VERSION,
    AuthError,
    AuthKind,
    Connector,
    ConnectorError,
    Event,
    EventKind,
    FetchResult,
    Manifest,
    PartialResult,
    RateLimited,
    SyncHints,
    TransientError,
)
from pydantic import BaseModel, Field, StringConstraints

API = "https://api.github.com"
FIRST_SYNC_DAYS = 14  # how far back the first sync reaches
OVERLAP_DAYS = 7  # how far before the last sync each later sync looks again, for late merges
SEEN_LIMIT = 500  # commit SHAs remembered per repo, to skip refetching their details
MAX_COMMITS = 500  # per sync, across all repos


Repo = Annotated[str, StringConstraints(pattern=r"^[\w.-]+/[\w.-]+$")]


class GitHubConfig(BaseModel):
    repos: list[Repo] = Field(min_length=1, description="Repositories to track, as owner/name")


class Commit(BaseModel):
    repo: str = Field(description="Repository name, e.g. goalpost")
    full_repo: str = Field(description="owner/name")
    branch: str
    path: list[str] = Field(description="Files the commit changed")
    message: str = Field(description="First line of the commit message")
    sha: str
    url: str


class GitHubConnector(Connector[GitHubConfig]):
    manifest = Manifest(
        id="github",
        name="GitHub",
        version="0.1.0",
        sdk_version=SDK_VERSION,
        description="Your commits on the repositories you choose, from their default branch.",
        icon="code",
        auth=AuthKind.TOKEN,
        config=GitHubConfig,
        secrets=["GITHUB_TOKEN"],
        event_kinds=[
            EventKind(
                name="commit",
                description="A commit you authored",
                payload=Commit,
                rule_fields=["repo", "branch", "path", "message"],
                title_field="message",
            )
        ],
        sync_hints=SyncHints(min_interval=timedelta(minutes=30), max_items=MAX_COMMITS),
    )

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=API, timeout=20.0)

    def test_connection(self, config: GitHubConfig, secrets: Mapping[str, str]) -> str:
        token = secrets["GITHUB_TOKEN"]
        login = self._get(token, "/user")["login"]
        for repo in config.repos:
            self._get(token, f"/repos/{repo}")
        repos = ", ".join(config.repos)
        return f"Signed in as {login}; can read {repos}"

    def fetch(
        self, config: GitHubConfig, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> FetchResult:
        token = secrets["GITHUB_TOKEN"]
        login = self._get(token, "/user")["login"]
        state: dict[str, Any] = dict(cursor or {})
        events: list[Event] = []
        now = datetime.now(UTC)
        for repo in config.repos:
            try:
                events.extend(self._repo_commits(token, login, repo, state, now, len(events)))
            except (TransientError, RateLimited) as exc:
                if not events:
                    raise
                # Keep what earlier repos returned; this repo is retried next sync.
                raise PartialResult(
                    f"{repo}: {exc}", FetchResult(events=events, cursor=state)
                ) from exc
        return FetchResult(events=events, cursor=state)

    def _repo_commits(
        self, token: str, login: str, repo: str, state: dict[str, Any], now: datetime, fetched: int
    ) -> list[Event]:
        repo_state = state.get(repo) or {}
        last = repo_state.get("last_sync")
        since = (
            datetime.fromisoformat(last) - timedelta(days=OVERLAP_DAYS)
            if last
            else now - timedelta(days=FIRST_SYNC_DAYS)
        )
        seen: list[str] = list(repo_state.get("seen", []))
        info = self._get(token, f"/repos/{repo}")
        branch = info.get("default_branch", "main")
        name = info.get("name", repo.split("/")[-1])

        events: list[Event] = []
        page = 1
        while fetched + len(events) < MAX_COMMITS:
            commits = self._get(
                token,
                f"/repos/{repo}/commits",
                params={
                    "author": login,
                    "since": since.isoformat(),
                    "sha": branch,
                    "per_page": 100,
                    "page": page,
                },
                empty_ok=True,
            )
            if not commits:
                break
            for item in commits:
                sha = item["sha"]
                if sha in seen or len(item.get("parents", [])) > 1:  # known, or a merge commit
                    continue
                detail = self._get(token, f"/repos/{repo}/commits/{sha}")
                events.append(
                    Event(
                        source_id=sha,
                        kind="commit",
                        occurred_at=datetime.fromisoformat(detail["commit"]["author"]["date"]),
                        payload=Commit(
                            repo=name,
                            full_repo=repo,
                            branch=branch,
                            path=[f["filename"] for f in detail.get("files", [])],
                            message=detail["commit"]["message"].splitlines()[0],
                            sha=sha,
                            url=detail.get("html_url", f"https://github.com/{repo}/commit/{sha}"),
                        ).model_dump(),
                    )
                )
                seen.append(sha)
            if len(commits) < 100:
                break
            page += 1
        state[repo] = {"last_sync": now.isoformat(), "seen": seen[-SEEN_LIMIT:]}
        return events

    def _get(
        self, token: str, path: str, *, params: dict[str, Any] | None = None, empty_ok: bool = False
    ) -> Any:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            response = self._client.get(path, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise TransientError("GitHub timed out") from exc
        except httpx.TransportError as exc:
            raise TransientError(f"Couldn't reach GitHub: {exc}") from exc

        status = response.status_code
        if status == 401:
            raise AuthError("GitHub rejected the token; check GITHUB_TOKEN")
        if status in (403, 429) and (
            response.headers.get("X-RateLimit-Remaining") == "0" or status == 429
        ):
            reset = response.headers.get("X-RateLimit-Reset")
            wait = max(float(reset) - datetime.now(UTC).timestamp(), 1.0) if reset else 60.0
            raise RateLimited("GitHub rate limit reached", retry_after=wait)
        if status == 403:
            raise AuthError("The token isn't allowed to read this; give it repository read access")
        if status == 404:
            repo = path.split("/")[2:4]
            raise ConnectorError(
                f"Repository {'/'.join(repo)} not found, or the token can't see it"
            )
        if status == 409 and empty_ok:
            return []  # an empty repository
        if status >= 500:
            raise TransientError(f"GitHub returned HTTP {status}")
        if status >= 400:
            raise ConnectorError(f"GitHub returned HTTP {status}")
        return response.json()
