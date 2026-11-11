"""Freeze the exchange contracts.

Writes contracts/schemas/<Model>.json from the Pydantic models and, with --openapi,
contracts/openapi/p14-search.yaml from the FastAPI app. The contract tests fail if the
code drifts from these frozen files, so re-run this script only for an intended change.

Usage:
    python scripts/export_contracts.py [--openapi]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from p14_search.contracts import CONTRACT_MODELS, schema_for

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openapi", action="store_true", help="also freeze the OpenAPI spec")
    args = parser.parse_args()

    out = ROOT / "contracts" / "schemas"
    out.mkdir(parents=True, exist_ok=True)
    for name in CONTRACT_MODELS:
        (out / f"{name}.json").write_text(
            json.dumps(schema_for(name), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"schema  contracts/schemas/{name}.json")

    if args.openapi:
        from p14_search.api.app import create_app
        from p14_search.config import Settings

        spec = create_app(Settings(_env_file=None), init_services=False).openapi()
        path = ROOT / "contracts" / "openapi" / "p14-search.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n")
        print(f"openapi {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
