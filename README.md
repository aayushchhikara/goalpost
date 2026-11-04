# goalpost

A local-first planner that tracks your goals with real evidence. Plan weekly tasks and loose monthly or quarterly goals, then let connectors suggest what you've actually done: a LeetCode submission or a GitHub commit becomes proof in your Proof Inbox, and nothing counts until you accept it.

## Quick start

Requires Docker with Compose.

```sh
git clone https://github.com/aayushchhikara/goalpost.git && cd goalpost
cp .env.example .env
```

Edit `.env`:

- `GOALPOST_TIMEZONE`: your IANA timezone, e.g. `Asia/Kolkata`. It decides what "today" means, so set it before the first start.
- `GOALPOST_ENCRYPTION_KEY`: generate one with
  `python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`
- `GITHUB_TOKEN` (optional): a fine-grained token with read-only Contents access, for the GitHub connector.

Then:

```sh
docker compose up --build -d
```

Open <http://localhost:3000>, go to **Connectors**, and add LeetCode (your public username) or GitHub (repositories as `owner/name`). Syncs run on startup, every 4 hours, and when you press **Sync now**. Give a task a completion rule in its drawer, and matching activity shows up in the Proof Inbox.

Both services bind to `127.0.0.1` only; never expose them to the internet. Your data lives in the `goalpost-data` Docker volume. Upgrade with `git pull && docker compose up --build -d`; migrations run on startup.

For development without Docker, see [CONTRIBUTING.md](CONTRIBUTING.md).
