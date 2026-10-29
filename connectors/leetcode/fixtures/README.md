Recorded LeetCode GraphQL responses, trimmed to the fields the connector asks for. Shapes match
the live API (checked October 2026); the submissions themselves are made up.

- `recent_ac.json`: `recentAcSubmissionList`. The newest is 23:50 IST on Monday 26 October,
  which must count for that Monday.
- `question_<slug>.json`: `question(titleSlug)` difficulty lookups.
- `user_found.json`, `user_missing.json`: `matchedUser`, as used by the connection test. The
  missing-user error is the real one.
