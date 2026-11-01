Recorded GitHub REST API responses (API version 2022-11-28), trimmed to the fields the connector
reads. The commits are made up.

- `user.json`: `GET /user`
- `repo.json`: `GET /repos/{owner}/{repo}`
- `commits.json`: `GET /repos/{owner}/{repo}/commits`, with one merge commit that must be skipped.
  The last commit is at 23:50 IST on Monday 26 October.
- `commit_<sha>.json`: `GET /repos/{owner}/{repo}/commits/{sha}`, with the changed files
