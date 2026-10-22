# Security

Goalpost is local-only by design. It has no authentication and must never be exposed to the
internet. Docker Compose binds both services to `127.0.0.1`; keep it that way.

Tokens for connectors are stored encrypted with `GOALPOST_ENCRYPTION_KEY`. Never commit `.env`.

To report a vulnerability, open a private security advisory on the GitHub repository.
