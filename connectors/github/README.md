# GitHub

Tracks **commits you authored** on the repositories you choose, from each repository's default
branch.

| | |
| --- | --- |
| Auth | Personal access token in `.env` as `GITHUB_TOKEN` |
| Config | `repos`: a list of `owner/name` |
| Event kind | `commit`: one commit you authored (merge commits are skipped) |
| Rule fields | `repo` (e.g. `goalpost`), `branch`, `path` (the changed files), `message` (first line) |

Each event also carries `full_repo`, `sha` and `url`. Its date is when the commit was written, in
your timezone. Example rule: at least 1 `commit` where `repo` equals `goalpost` and `path`
matches `backend/auth/*`.

## Getting a token

Create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens)
with read-only **Contents** access to the repositories you'll track (public repositories need
no extra permission), then add it to `.env`:

```sh
GITHUB_TOKEN=github_pat_...
```

Secrets stay in `.env`; Goalpost never stores them in its database. For a second account, put
its token under another key and set that key as the connector's `secret_ref`.

## Known limits

- **Default branch only.** Commits on a feature branch appear once they're merged. They keep the
  date they were written, so each sync looks back 7 days to catch late merges. The cursor
  remembers commits already fetched.
- The first sync reaches back 14 days. Each sync fetches at most 500 commits.
- API use per sync: one call per repository, one per page of commits, and one per new commit (to
  read its changed files). Well within GitHub's 5,000 requests an hour.

## Try it

```sh
uv run python -m goalpost.cli dry-run github --config repos=owner/name --config repos=owner/other
```
