# LeetCode

Tracks your **accepted submissions** from your public LeetCode profile. No login or token is needed;
the only setting is your username.

| | |
| --- | --- |
| Auth | None (public profile) |
| Config | `username` |
| Event kind | `submission`: one accepted submission |
| Rule fields | `status`, `difficulty` (`Easy` / `Medium` / `Hard`), `problem`, `language` |

Each event also carries the problem's `slug` and `url`. Its date is when you submitted, in your
timezone, so a submission at 11:50 pm counts for that day even if the sync runs at 3 am.

## Known limits

- **Best-effort.** It uses LeetCode's unofficial GraphQL endpoint (`https://leetcode.com/graphql`),
  which can change or be blocked without notice. If it stops working, mark tasks done by hand
  until the connector is fixed.
- **Only the last ~20 accepted submissions.** That's all the endpoint returns, so syncs must run
  at least daily (Goalpost syncs on startup and every 4 hours) or older submissions are missed.
- **Polite by default:** one request for the list, plus one difficulty lookup per problem that's
  new since the last sync. The minimum interval between scheduled syncs is one hour.
- The profile must be public.

## Try it

```sh
uv run python -m goalpost.cli dry-run leetcode --config username=<your-username>
```

That fetches once and prints the events with their local dates, without saving anything.
