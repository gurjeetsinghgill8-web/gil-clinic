"""Generate the PWA icon set (reproducible).

Why this file exists
--------------------
Chrome will not offer "Install app" unless the manifest declares a valid
192x192 **and** 512x512 icon, and both must actually resolve. The manifests
pointed at `/static/icons/icon-192.png`, which returned 404 — so installability
failed at the very first requirement, and nothing else about the PWA mattered
until that was fixed.

Committed as a script rather than as loose binary blobs so the icon can be
regenerated at any size later (a new brand colour, an iOS splash, a store
listing) without reverse-engineering a PNG.

Design rules:
  * **`any` variant** — the mark bleeds to the edges; Android rounds it itself.
  * **`maskable` variant** — the mark sits inside the central 80% safe zone,
    because a maskable icon is cropped to whatever shape the launcher wants
    (circle, squircle, teardrop). A mark that touches the edge gets its corners
    cut off on a circular launcher.
  * Background is opaque everywhere: a transparent icon on a white launcher is
    an invisible icon.

Run:  python scripts/make_pwa_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "static" / "icons"

#: Brand gradient endpoints — same pair the whole UI uses (--brand / --brand2).
BRAND_START = (102, 126, 234)   # #667eea
BRAND_END = (118, 75, 162)      # #764ba2
WHITE = (255, 255, 255)

#: Sizes Chrome/Android ask for, plus the iOS touch icon.
SIZES = {
    "icon-192.png": (192, 192, "any"),
    "icon-512.png": (512, 512, "any"),
    "icon-maskable-192.png": (192, 192, "maskable"),
    "icon-maskable-512.png": (512, 512, "maskable"),
    "apple-touch-icon.png": (180, 180, "any"),
    "favicon-32.png": (32, 32, "any"),
}


def _gradient(size: int) -> Image.Image:
    """Diagonal two-stop gradient, filled edge to edge.

    Drawn per-pixel once per size rather than by scaling a small image, because
    a scaled-up gradient bands badly on the 512 icon.
    """
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            # 0 at top-left → 1 at bottom-right.
            t = (x + y) / (2 * (size - 1)) if size > 1 else 0.0
            pixels[x, y] = tuple(
                int(BRAND_START[i] + (BRAND_END[i] - BRAND_START[i]) * t)
                for i in range(3)
            )
    return image


def _draw_mark(image: Image.Image, size: int, variant: str) -> Image.Image:
    """Draw the clinic mark: a medical cross with an ECG pulse through it.

    The cross is the universal "medical" read at 32px, and the pulse line makes
    it specifically a *clinic queue* product rather than a generic pharmacy.
    """
    draw = ImageDraw.Draw(image)

    # Safe zone: maskable icons get cropped to the launcher's shape, so the mark
    # is kept well inside. `any` can use more of the canvas.
    scale = 0.56 if variant == "maskable" else 0.70
    box = size * scale
    left = (size - box) / 2
    top = (size - box) / 2

    # ── the cross ──
    arm = box * 0.34                      # thickness of each bar
    cx, cy = size / 2, size / 2
    radius = max(2, int(size * 0.045))
    draw.rounded_rectangle(
        [cx - arm / 2, top, cx + arm / 2, top + box],
        radius=radius, fill=WHITE,
    )
    draw.rounded_rectangle(
        [left, cy - arm / 2, left + box, cy + arm / 2],
        radius=radius, fill=WHITE,
    )

    # ── the pulse, punched back through the cross in brand colour ──
    # A single mid-tone rather than the gradient: at 32px a gradient line
    # disappears, and the mark must read at favicon size too.
    punch = tuple((BRAND_START[i] + BRAND_END[i]) // 2 for i in range(3))
    line_w = max(2, int(size * 0.055))
    y = cy
    seg = box / 6.0
    points = [
        (left + seg * 0.15, y),
        (left + seg * 1.05, y),
        (left + seg * 1.45, y - box * 0.20),
        (left + seg * 1.95, y + box * 0.20),
        (left + seg * 2.35, y),
        (left + seg * 3.30, y),
    ]
    draw.line(points, fill=punch, width=line_w, joint="curve")
    # Round the line ends so the stroke does not look chopped.
    r = line_w / 2
    for px, py in (points[0], points[-1]):
        draw.ellipse([px - r, py - r, px + r, py + r], fill=punch)

    return image


def build(name: str, size: tuple[int, int, str]) -> Path:
    width, height, variant = size
    image = _gradient(max(width, height))
    image = image.resize((width, height), Image.LANCZOS)
    if width != height:  # pragma: no cover - all current icons are square
        image = image.crop((0, 0, width, height))
    _draw_mark(image, width, variant)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    image.save(path, "PNG", optimize=True)
    return path


def main() -> int:
    print(f"writing icons to {OUT_DIR}")
    total = 0
    for name, spec in SIZES.items():
        path = build(name, spec)
        total += path.stat().st_size
        print(f"  {name:<28} {spec[0]}x{spec[1]}  {spec[2]:<9} {path.stat().st_size:>7} bytes")
    print(f"total {total} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
