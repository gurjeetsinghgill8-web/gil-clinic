"""Audit helper 1: enumerate every route + every template in the app.

Read-only. Dumps two JSON files the rest of the audit reads, so every later
step works off the same inventory instead of re-scanning.

Run:  python scripts/audit_inventory.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main_v2  # noqa: E402


def route_info(r) -> dict:
    """Best-effort: method, path, and which module/function owns it."""
    methods = sorted(getattr(r, "methods", None) or [])
    path = getattr(r, "path", None)
    name = getattr(r, "name", "")
    endpoint = getattr(r, "endpoint", None)
    owner = ""
    if endpoint is not None:
        owner = f"{getattr(endpoint, '__module__', '')}.{getattr(endpoint, '__name__', '')}"
    return {
        "methods": methods,
        "path": path,
        "name": name,
        "owner": owner,
    }


def _walk(routes, out: list[dict], seen: set[str]) -> None:
    """Recurse through every router wrapper this app uses.

    FastAPI nests routes behind APIRouter.routes and behind this app's custom
    ``_IncludedRouter`` (which holds ``original_router``), so a shallow
    ``app.routes`` walk saw 16 routes instead of the real number.
    """
    for r in routes:
        # _IncludedRouter (custom) → its original_router's routes
        original = getattr(r, "original_router", None)
        if original is not None:
            nested = getattr(original, "routes", None)
            if nested is not None:
                _walk(nested, out, seen)
            continue

        # APIRouter nested directly
        nested = getattr(r, "routes", None)
        if nested is not None and not hasattr(r, "methods"):
            _walk(nested, out, seen)
            continue

        # Mounted StaticFiles
        if getattr(r, "path", None) is not None and not hasattr(r, "methods"):
            out.append(
                {
                    "methods": ["MOUNT"],
                    "path": str(r.path),
                    "name": getattr(r, "name", ""),
                    "owner": f"{type(getattr(r, 'app', None)).__name__}",
                }
            )
            continue

        info = route_info(r)
        key = "|".join(info["methods"]) + "|" + str(info["path"])
        if info["path"] is not None and key not in seen:
            seen.add(key)
            out.append(info)


def collect_routes(app) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    _walk(app.routes, out, seen)
    out.sort(key=lambda i: (str(i["path"]), ",".join(i["methods"])))
    return out


def collect_templates() -> list[dict]:
    out: list[dict] = []
    templates_dir = ROOT / "templates"
    if not templates_dir.exists():
        return out
    for p in sorted(templates_dir.rglob("*.html")):
        out.append(
            {
                "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                "size": p.stat().st_size,
            }
        )
    return out


def main() -> int:
    routes = collect_routes(main_v2.app)
    templates = collect_templates()

    routes_path = ROOT / "scripts" / ".audit_routes.json"
    templates_path = ROOT / "scripts" / ".audit_templates.json"

    routes_path.write_text(json.dumps(routes, indent=1, ensure_ascii=False), encoding="utf-8")
    templates_path.write_text(json.dumps(templates, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"routes:    {len(routes)}  -> {routes_path.name}")
    print(f"templates: {len(templates)}  -> {templates_path.name}")

    # Quick summary: routes grouped by prefix.
    prefixes: dict[str, int] = {}
    for r in routes:
        p = str(r["path"])
        first = "/" + p.split("/")[1] if p.startswith("/") else "(root)"
        prefixes[first] = prefixes.get(first, 0) + 1
    print("\nroute prefixes:")
    for prefix, count in sorted(prefixes.items(), key=lambda kv: -kv[1]):
        print(f"  {count:>4}  {prefix}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
