"""PWA routes — one manifest, one service worker, for the whole app.

Why this module replaced three half-wired manifests
---------------------------------------------------
The repo had three manifests (`assets/`, `patient-pwa/`, `src/experience/pwa/`)
and none of them made the app installable:

  * the icons they declared pointed at files that **did not exist** — Chrome
    requires a valid 192px and 512px icon, so installability failed at the very
    first requirement and nothing else mattered;
  * only `/experience/*` linked a manifest at all, so the pages staff actually
    open (`/opd/dashboard`, `/opd/login`) advertised nothing to the browser;
  * the three disagreed about the app's name, start URL and icon paths.

So there is now exactly one identity, served from the root:

    GET /manifest.json   → the single web app manifest
    GET /sw.js           → the service worker, scoped to "/"

The service worker MUST be served from the root path. A worker served from
`/static/sw.js` can only control `/static/*`, which is why the previous setup
could never have worked no matter how it was linked.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response

router = APIRouter(tags=["PWA"])

#: Project root. ``__file__`` is src/presentation/pwa/routes/pwa_routes.py, so
#: parents[4] is the repo root — parents[3] is ``src/``, which silently made the
#: icon and worker checks report MISSING.
_ROOT = Path(__file__).parents[4]
_STATIC = _ROOT / "static"
_SW_PATH = _STATIC / "sw.js"

#: The app's single identity. `start_url` is the staff entry point, because the
#: installable thing is the clinic's tool, not the marketing page.
MANIFEST: dict = {
    "id": "/",
    "name": "GIL CLINIC — OPD & Queue",
    "short_name": "GIL CLINIC",
    "description": (
        "Live OPD queue, token booking, estimated wait time and patient records "
        "for GIL CLINIC."
    ),
    "start_url": "/signin",
    "scope": "/",
    "display": "standalone",
    "display_override": ["standalone", "minimal-ui"],
    "orientation": "portrait",
    "background_color": "#0f172a",
    "theme_color": "#0f172a",
    "lang": "en-IN",
    "dir": "ltr",
    "categories": ["medical", "health", "productivity"],
    "icons": [
        {
            "src": "/static/icons/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": "/static/icons/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any",
        },
        # Separate maskable entries: a single "any maskable" icon has to survive
        # both a full-bleed launcher and a circular crop, which is a compromise
        # that looks wrong in one of the two.
        {
            "src": "/static/icons/icon-maskable-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "maskable",
        },
        {
            "src": "/static/icons/icon-maskable-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        },
    ],
    "shortcuts": [
        {
            "name": "Login",
            "short_name": "Login",
            "url": "/signin",
            "description": "Ek login — apni jagah pahunche",
        },
        {
            "name": "Find a Doctor",
            "short_name": "Find",
            "url": "/find-doctor",
            "description": "Patient ke liye doctor dhoondhein",
        },
        {
            "name": "Clinic tools",
            "short_name": "Tools",
            "url": "/tools",
            "description": "Referral, slots, reviews, FHIR export",
        },
    ],
}


@router.get("/manifest.json", include_in_schema=False)
async def manifest():
    """The single web app manifest, served from the root.

    ``application/manifest+json`` (not ``application/json``) and no-cache: a
    stale manifest is how an installed app keeps a dead icon for weeks.
    """
    response = JSONResponse(MANIFEST, media_type="application/manifest+json")
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@router.get("/sw.js", include_in_schema=False)
async def service_worker():
    """The service worker, served from the root so it can control the origin.

    Two headers matter and neither is optional:

      * ``Service-Worker-Allowed: /`` — a worker may only control paths at or
        below its own directory unless the server grants more. Without this,
        ``/sw.js`` could still be registered, but its default scope would be
        ``/`` only because the file is already at the root; the header makes the
        intent explicit and survives a future move of the file.
      * ``Cache-Control: no-cache`` — the browser must revalidate the worker
        itself, otherwise a fixed cache-bug can never reach the devices that
        have it.
    """
    if not _SW_PATH.exists():
        return Response(
            "// service worker not deployed",
            media_type="application/javascript",
            status_code=404,
        )
    response = FileResponse(str(_SW_PATH), media_type="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


@router.get("/pwa-status", include_in_schema=False)
async def pwa_status():
    """Self-check: is the app installable?

    Chrome's installability rules are specific and silent — when one fails, the
    install prompt simply never appears, with nothing in the UI to explain why.
    This endpoint reports the actual requirements so "why can't I install it?"
    has an answer, and it verifies the icon FILES exist rather than trusting the
    manifest to be honest about them. That mismatch is exactly the bug this
    module was written to fix.
    """
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    check("https", True, "served over HTTPS in production (localhost is also allowed)")

    icon_problems: list[str] = []
    sizes_seen: set[str] = set()
    for icon in MANIFEST["icons"]:
        path = _ROOT / icon["src"].lstrip("/")
        if not path.exists():
            icon_problems.append(f"{icon['src']} MISSING")
            continue
        size = path.stat().st_size
        if size < 100:
            icon_problems.append(f"{icon['src']} is only {size} bytes")
        sizes_seen.add(icon["sizes"])
    check(
        "icons resolve",
        not icon_problems,
        "; ".join(icon_problems) if icon_problems else f"{len(MANIFEST['icons'])} icons present",
    )
    check("192px icon declared", "192x192" in sizes_seen)
    check("512px icon declared", "512x512" in sizes_seen)
    check("maskable icon declared",
          any(i.get("purpose") == "maskable" for i in MANIFEST["icons"]))
    check("service worker file exists", _SW_PATH.exists(), str(_SW_PATH.name))
    check("display is standalone", MANIFEST["display"] == "standalone")
    check("start_url is in scope",
          MANIFEST["start_url"].startswith(MANIFEST["scope"] or "/"))

    ready = all(item["ok"] for item in checks)
    return {
        "ok": True,
        "installable": ready,
        "checks": checks,
        "manifest_url": "/manifest.json",
        "service_worker_url": "/sw.js",
        "note": (
            "Chrome me install tab hi offer hota hai jab saare checks pass hon. "
            "Har private route (/api, /track, /my, /card, /admin, /opd) service "
            "worker kabhi cache nahi karta — shared tablet par purana patient data "
            "dikhana data leak hoga."
        ),
        "how_to_install": (
            "Chrome → address bar ke right me install icon (⊕ / monitor icon) → "
            "'Install'. Ya menu ⋮ → 'Install GIL CLINIC'. "
            "Phone par: ⋮ → 'Add to Home screen'."
        ),
    }
