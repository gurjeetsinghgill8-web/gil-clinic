"""Audit helper 2: scan every template for internal links and classify them.

Cross-references each link against the route inventory (exact, path-param, and
prefix matches) and against files on disk. Outputs a JSON report of:

  * DEAD links — point at a path that is no route and no file.
  * PARAM links — fine, but listed so a path-param route is not mistaken for dead.
  * UNREACHABLE templates — a template that no route ever renders.
  * EXTERNAL asset fetches — icons/fonts from another origin (often a PWA/install
    or reliability problem).

Run:  python scripts/audit_links.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

routes = json.loads((ROOT / "scripts" / ".audit_routes.json").read_text(encoding="utf-8"))
templates = json.loads((ROOT / "scripts" / ".audit_templates.json").read_text(encoding="utf-8"))

# Build a matcher: a list of (regex, raw_path) for every route path.
def path_to_regex(path: str):
    parts = path.split("/")
    out = []
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            out.append("[^/]+")
        else:
            out.append(re.escape(part))
    return "^" + "/".join(out) + "/?$"

route_specs = []
for r in routes:
    p = str(r["path"])
    if p is None or not p.startswith("/"):
        continue
    route_specs.append((path_to_regex(p), p, r))

# Also the raw path set for exact matches.
exact_paths = {str(r["path"]) for r in routes if r["path"]}

# Static / mounted prefixes (a link under /static should resolve to a file).
def static_resolves(url_path: str) -> bool:
    if not url_path.startswith("/static/"):
        return False
    rel = url_path.lstrip("/")
    return (ROOT / rel).exists()


# ── extract internal links from a template ──
HREF = re.compile(r'(?:href|src|action)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
FETCH = re.compile(r'fetch\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
LOC = re.compile(r'(?:window\.location(?:\.href)?|location\.href)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
ASSIGN = re.compile(r'location\.assign\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
REDIRECT = re.compile(r'RedirectResponse\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
# fetch('...' + var + '...') — capture the static prefix portion
FETCH_PREFIX = re.compile(r'fetch\s*\(\s*["\']([^"\']+?)(?:\$\{|")', re.IGNORECASE)


def classify(url: str) -> tuple[str, str]:
    """Classify one internal URL. Returns (kind, detail)."""
    if not url:
        return ("empty", "")
    if url.startswith(("http://", "https://", "//", "mailto:", "tel:", "javascript:", "#")):
        return ("external", url[:40])
    if url.startswith("data:"):
        return ("data-uri", "")
    if url.startswith("{"):  # a jinja variable like {{ url }}
        return ("dynamic", url[:30])

    parsed = urlparse(url)
    path = parsed.path or "/"
    if not path.startswith("/"):
        # Relative — cannot resolve without the template's mount context; flag it
        # separately because relative links are a common source of dead nav.
        return ("relative", url[:60])

    # exact route
    if path in exact_paths:
        return ("route-exact", path)
    # path-param route
    for regex, raw, _r in route_specs:
        if re.match(regex, path):
            return ("route-param", raw)
    # static file
    if static_resolves(path):
        return ("static", path)
    return ("DEAD", path)


report = {
    "dead": [],          # {template, link, kind}
    "relative": [],      # {template, link}
    "external_assets": [],  # {template, url}
    "dynamic": [],       # jinja-interpolated links, listed for eyeballing
    "templates": {},
}

# ── 1. link scan ──
for tpl in templates:
    rel_path = tpl["path"]
    p = ROOT / rel_path
    text = p.read_text(encoding="utf-8", errors="replace")

    found: dict[str, set[str]] = {"dead": set(), "relative": set(), "external_assets": set(), "dynamic": set()}

    for pattern, kind in ((HREF, None), (FETCH, None), (FETCH_PREFIX, None),
                          (LOC, None), (ASSIGN, None), (REDIRECT, None)):
        for m in pattern.finditer(text):
            url = m.group(1).strip()
            if not url:
                continue
            k, detail = classify(url)
            if k == "DEAD":
                found["dead"].add(url)
            elif k == "relative":
                found["relative"].add(url)
            elif k == "external" and url.startswith(("http://", "https://", "//")):
                # external image/font assets matter; external links are fine
                lower = url.lower()
                if any(ext in lower for ext in (".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff", ".woff2", ".ttf")):
                    found["external_assets"].add(url)
            elif k == "dynamic":
                found["dynamic"].add(url)

    report["templates"][rel_path] = {
        "dead": sorted(found["dead"]),
        "relative": sorted(found["relative"]),
        "external_assets": sorted(found["external_assets"]),
        "dynamic": sorted(found["dynamic"]),
    }

# ── 2. which templates are actually rendered? ──
# grep every Python file for the template name (as a string literal).
py_files = list(ROOT.glob("**/*.py"))
rendered: dict[str, set[str]] = {}
for tpl in templates:
    name = Path(tpl["path"]).name
    rel = tpl["path"].replace("\\", "/")
    rendered[rel] = set()

for py in py_files:
    if "__pycache__" in str(py):
        continue
    try:
        text = py.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for tpl in templates:
        name = Path(tpl["path"]).name
        rel = tpl["path"].replace("\\", "/")
        if name in text or rel in text:
            rendered[rel].add(str(py.relative_to(ROOT)).replace("\\", "/"))

unreachable = [
    rel for rel, owners in rendered.items()
    if not owners and not rel.endswith("base.html")  # base templates are inherited
]

# ── summary ──
dead_total = sum(len(v["dead"]) for v in report["templates"].values())
rel_total = sum(len(v["relative"]) for v in report["templates"].values())

out = {
    "summary": {
        "templates_scanned": len(templates),
        "routes": len(routes),
        "dead_links_total": dead_total,
        "relative_links_total": rel_total,
        "unreachable_templates": len(unreachable),
    },
    "unreachable_templates": unreachable,
    "templates": report["templates"],
    "route_count_by_prefix": {},
}

(ROOT / "scripts" / ".audit_links.json").write_text(
    json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
)

print(f"templates scanned: {len(templates)}")
print(f"routes:            {len(routes)}")
print(f"DEAD links:        {dead_total}")
print(f"relative links:    {rel_total}")
print(f"unreachable tpls:  {len(unreachable)}")
print("\n== DEAD LINKS BY TEMPLATE ==")
for rel, v in sorted(report["templates"].items()):
    if v["dead"]:
        print(f"\n{rel}")
        for url in v["dead"]:
            print(f"    {url}")
print("\n== UNREACHABLE TEMPLATES ==")
for rel in unreachable:
    print(f"    {rel}")
