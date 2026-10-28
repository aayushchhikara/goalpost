# Security

Goalpost is local-only by design. It has no authentication and must never be exposed to the
internet. Docker Compose binds both services to `127.0.0.1`; keep it that way.

Websites open in your browser can still send requests to `localhost`, so the API also refuses:

- requests addressed to any host other than `localhost` or `127.0.0.1` (see
  `GOALPOST_ALLOWED_HOSTS`), which blocks DNS-rebinding attacks;
- requests that change data (`POST`, `PATCH`, `PUT`, `DELETE`) sent from any browser origin other
  than the frontend's (`GOALPOST_FRONTEND_ORIGIN`). CORS alone only hides responses from other
  sites; it doesn't stop a cross-site form or `fetch` from running.

Tokens for connectors are stored encrypted with `GOALPOST_ENCRYPTION_KEY`. Never commit `.env`.

To report a vulnerability, open a private security advisory on the GitHub repository.
