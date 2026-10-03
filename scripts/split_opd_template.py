#!/usr/bin/env python
"""Mechanically split the 380KB OPD dashboard template into Jinja partials.

Reads templates/opd/dashboard.html and extracts four contiguous chunks into
templates/opd/partials/ (head, sidebar, main, scripts), then rewrites
dashboard.html as a thin shell that {% include %}s them. Output must be
byte-identical — verified separately by scripts/verify_opd_split.py.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "templates" / "opd" / "dashboard.html"
DEST = ROOT / "templates" / "opd" / "partials"

# 1-indexed, inclusive line ranges (must match the current file exactly).
CHUNKS = {
    "_head.html":     (1, 512),
    "_sidebar.html":  (515, 557),
    "_main.html":     (559, 1743),
    "_scripts.html":  (1749, 6758),
}

SHELL = '''{% include "opd/partials/_head.html" %}
<body>
<div class="app">
{% include "opd/partials/_sidebar.html" %}

{% include "opd/partials/_main.html" %}
</div>

<!-- ─── Toast ─── -->
<div class="toast" id="toast"></div>

{% include "opd/partials/_scripts.html" %}
</body>
</html>
'''


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.split("\n")  # each element has no trailing newline

    DEST.mkdir(parents=True, exist_ok=True)

    for name, (start, end) in CHUNKS.items():
        chunk = "\n".join(lines[start - 1:end])  # exact lines, no trailing newline
        (DEST / name).write_text(chunk, encoding="utf-8")
        print(f"wrote partials/{name}: lines {start}-{end} ({len(chunk.splitlines())} lines)")

    SRC.write_text(SHELL, encoding="utf-8")
    print(f"rewrote {SRC.name} as a thin include shell ({len(SHELL.splitlines())} lines)")


if __name__ == "__main__":
    main()
