# Example connector (template)

Copy this folder to `connectors/<id>/`, where `<id>` matches the manifest's `id`.

A connector folder contains:

- `connector.py`: the manifest and the `Connector` subclass (`test_connection`, `fetch`)
- `README.md`: what it tracks, how to get any credentials, and known limits
- `fixtures/`: recorded API responses used by the tests
- `test_connector.py`: tests that run against the fixtures, never the live service

Then check it against the real service without saving anything:

```sh
uv run python -m goalpost.cli dry-run <id> --config key=value
```
