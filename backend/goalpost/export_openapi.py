"""Write the OpenAPI schema to a file (default: frontend/lib/api/openapi.json)."""

import json
import sys
from pathlib import Path

from goalpost.main import app


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/lib/api/openapi.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
