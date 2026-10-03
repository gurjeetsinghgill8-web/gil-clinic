#!/usr/bin/env python
"""Verify the OPD dashboard template split is byte-identical when rendered.

Renders the ORIGINAL dashboard.html (saved to scripts/.opd_dashboard_orig.html)
and the NEW include-shell with the SAME context, then diffs. Exits 1 on any
difference so the split is never deployed unverified.
"""
from pathlib import Path

import jinja2

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
ORIG = ROOT / "scripts" / ".opd_dashboard_orig.html"
NEW = TEMPLATES / "opd" / "dashboard.html"

if not ORIG.exists():
    raise SystemExit("missing scripts/.opd_dashboard_orig.html — copy the original first")

env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATES)), auto_reload=False)

context = {
    "request": None,
    "session": {"role": "chief", "name": "Dr Test"},
    "role": "chief",
    "doctor_id": "clinic_default",
    "doc_name": "Dr Test",
    "settings": {},
    "raw_ai_keys": {},
    "build_stamp": "test-build",
    "tab": "rx",
    "today_count": 0,
    "today_revenue": 0,
    "is_chief": True,
    "is_owner": True,
    "templates": [],
}

orig_rendered = env.from_string(ORIG.read_text(encoding="utf-8")).render(**context)
new_rendered = env.get_template("opd/dashboard.html").render(**context)

if orig_rendered == new_rendered:
    print(f"IDENTICAL: original ({len(orig_rendered)} chars) == split ({len(new_rendered)} chars)")
else:
    import difflib
    print(f"DIFF: original {len(orig_rendered)} chars vs split {len(new_rendered)} chars")
    diff = list(difflib.unified_diff(
        orig_rendered.splitlines(), new_rendered.splitlines(),
        lineterm="", fromfile="original", tofile="split",
    ))
    for line in diff[:120]:
        print(line)
    if len(diff) > 120:
        print(f"... {len(diff) - 120} more diff lines")
    raise SystemExit(1)
