"""Command-line tools.

    uv run python -m goalpost.cli dry-run leetcode --config username=you

`dry-run` fetches once with your real config and .env secrets, validates the events exactly as a
sync would, and prints them with their local dates. Nothing is saved.
"""

import argparse
import json
import sys
from typing import Any

from goalpost.sdk import ConnectorError, PartialResult
from goalpost.services.connectors import installed_connectors, read_env, resolve_secrets
from goalpost.services.dates import local_date
from goalpost.services.sync import validate_events


def _parse_config(pairs: list[str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--config expects key=value, got {pair!r}")
        config[key] = value
    return config


def dry_run(args: argparse.Namespace) -> int:
    registry = installed_connectors()
    cls = registry.get(args.connector)
    if cls is None:
        print(f"No connector {args.connector!r}. Installed: {', '.join(registry.types) or 'none'}")
        return 2
    manifest = cls.manifest
    env = read_env()
    timezone = args.timezone or env.get("GOALPOST_TIMEZONE") or "UTC"
    try:
        config = manifest.config.model_validate(_parse_config(args.config))
        secrets = resolve_secrets(manifest, args.secret_ref, env)
        cursor = json.loads(args.cursor) if args.cursor else None
        try:
            result = cls().fetch(config, secrets, cursor)
        except PartialResult as exc:
            print(f"Partial result: {exc}")
            result = exc.result
    except ConnectorError as exc:
        print(f"{type(exc).__name__}: {exc}")
        return 1

    valid, rejected = validate_events(manifest, result.events)
    print(f"{manifest.name}: {len(valid)} event(s), local dates in {timezone}\n")
    for event, payload in sorted(valid, key=lambda pair: pair[0].occurred_at):
        day = local_date(event.occurred_at, timezone)
        summary = ", ".join(f"{k}={v}" for k, v in payload.items() if v is not None)
        print(f"  {day}  {event.occurred_at:%Y-%m-%d %H:%M}Z  {event.kind}  {event.source_id}")
        print(f"      {summary}")
    for reason in rejected:
        print(f"  REJECTED {reason}")
    print(f"\nNext cursor: {json.dumps(result.cursor)}")
    print("Dry run: nothing was saved.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="goalpost")
    commands = parser.add_subparsers(dest="command", required=True)
    dry = commands.add_parser("dry-run", help="Fetch once and print events without saving")
    dry.add_argument("connector", help="Connector type id, e.g. leetcode")
    dry.add_argument("--config", action="append", default=[], metavar="KEY=VALUE")
    dry.add_argument("--secret-ref", help="The .env key holding the secret, if not the default")
    dry.add_argument("--cursor", help="Start from this cursor (JSON), like a later sync would")
    dry.add_argument("--timezone", help="Defaults to GOALPOST_TIMEZONE")
    args = parser.parse_args(argv)
    return dry_run(args)


if __name__ == "__main__":
    sys.exit(main())
