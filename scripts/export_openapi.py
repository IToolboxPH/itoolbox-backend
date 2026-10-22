#!/usr/bin/env python
"""Export the FastAPI OpenAPI schema to contract/.

contract/openapi.api.json is the source of truth for the TypeScript types in
itoolbox-frontend. It is committed so the frontend can regenerate its types
without a running backend.

No database or Zetaris is required: importing the app builds its routes and
Pydantic models, and the lifespan hook (migrations, admin bootstrap) only runs on
real server startup.

Usage:
    python scripts/export_openapi.py           # write the schema
    python scripts/export_openapi.py --check   # exit 1 if it is out of date
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "apps" / "api"
TARGET = REPO_ROOT / "contract" / "openapi.api.json"

# Placeholders, applied unconditionally so the output is identical on a laptop
# with a populated .env and on a clean CI runner. Nothing connects on import.
PLACEHOLDER_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://placeholder:placeholder@localhost:5432/placeholder",
    "JWT_SECRET": "placeholder",
}


def build_schema() -> dict:
    # apps/api uses flat imports (`from config import get_settings`), so its own
    # directory has to be on sys.path, and the working directory must not supply
    # a .env that changes settings defaults.
    sys.path.insert(0, str(APP_DIR))
    os.environ.update(PLACEHOLDER_ENV)
    os.chdir(APP_DIR)
    module = importlib.import_module("main")
    return module.app.openapi()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the committed schema; do not write")
    args = parser.parse_args()

    # sort_keys keeps the diff stable across runs, so an unchanged API produces no churn.
    rendered = json.dumps(build_schema(), indent=2, sort_keys=True) + "\n"

    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != rendered:
            print("STALE  contract/openapi.api.json  (apps/api has changed)")
            print("\nRun:  python scripts/export_openapi.py", file=sys.stderr)
            return 1
        print("ok     contract/openapi.api.json")
        return 0

    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"wrote  contract/openapi.api.json  ({len(json.loads(rendered).get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
