"""Friendly URLs — forgiving aliases and a helpful 404 page.

The problem this solves
-----------------------
A doctor opens the dashboard from WhatsApp, from memory, or by typing it. The
real path is ``/opd/dashboard`` — all lowercase. Type ``/opd/Dashboard``,
``/opd/dashbord`` or ``/dashboard`` and the app used to answer with the raw
JSON ``{"detail":"Not Found"}``, which looks exactly like "the site is down".
That is a support call, not a UX.

So this module adds two small, safe things:

1. **Exact aliases** — the common mistypes redirect straight to the right page.
2. **A 404 handler** that
     * keeps answering raw JSON for ``/api/...`` clients (no breakage), and
     * for a human on a browser, redirects anything that *looks like* a
       dashboard attempt to the login page, otherwise shows a plain page with
       three working buttons instead of a dead end.

Deliberately minimal: it answers 404 only, and leaves every other status
(302 redirects from the session guard, 400s, 401s …) on FastAPI's default
handler so nothing existing changes behaviour.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Friendly URLs"])

#: Exact mistype → canonical path. Only paths that do NOT exist already, so a
#: real route can never be shadowed.
ALIASES: dict[str, str] = {
    "/dashboard": "/opd/login",
    "/Dashboard": "/opd/login",
    "/opd/Dashboard": "/opd/login",
    "/opd/dashbord": "/opd/login",
    "/opd/dashboad": "/opd/login",
    "/opddashboard": "/opd/login",
    "/opd/dashboard.html": "/opd/login",
    "/opd/dashboard.php": "/opd/login",
    "/opd/doctor": "/opd/login",
    "/opd/doctors": "/opd/login",
    "/doctor": "/opd/login",
    "/doctor-dashboard": "/opd/login",
    "/doctorlogin": "/opd/login",
    "/finddoctor": "/find-doctor",
    "/find_doctor": "/find-doctor",
    "/find-a-doctor": "/find-doctor",
}

#: Path shapes (letters/digits only, lowercased) that mean "I was trying to
#: reach the doctor dashboard". Anything here gets pushed to the login page
#: instead of a dead end.
_DASHBOARD_SHAPES = {
    "opd",
    "opdhome",
    "opdlogin",
    "opddashboard",
    "opddashbord",
    "opddashboad",
    "dashboard",
    "dashbord",
    "doctordashboard",
    "doctorlogin",
    "doctor",
    "opddoctor",
    "clinic",
    "reception",
    "staff",
}


def _redirect_to(target: str):
    """Build a tiny GET handler that redirects to ``target``."""

    async def _handler() -> RedirectResponse:
        return RedirectResponse(url=target, status_code=302)

    return _handler


for _alias, _target in ALIASES.items():
    router.add_api_route(
        _alias,
        _redirect_to(_target),
        methods=["GET"],
        include_in_schema=False,
        name=f"alias{_alias.replace('/', '_')}",
    )


def _shape(path: str) -> str:
    """Reduce a path to letters+digits so '/' '_' '.' '-' cannot hide a typo."""
    return re.sub(r"[^a-z0-9]", "", path.lower())


def _friendly_page(path: str) -> str:
    """Self-contained HTML — no template lookup, so it can never itself break."""
    safe_path = (
        path.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:120]
    )
    return f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page nahi mila — GIL CLINIC</title>
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:linear-gradient(160deg,#f1f5f9,#e2e8f0);padding:22px;
       font-family:system-ui,'Segoe UI',Roboto,Arial,sans-serif;color:#0f172a}}
  .card{{background:#fff;border-radius:18px;padding:30px 26px;max-width:460px;width:100%;
        box-shadow:0 10px 40px rgba(15,23,42,.10);text-align:center}}
  .icon{{font-size:52px;line-height:1}}
  h1{{font-size:21px;margin:12px 0 6px}}
  p{{color:#475569;font-size:14.5px;line-height:1.65;margin:8px 0}}
  code{{background:#f1f5f9;border-radius:6px;padding:2px 6px;font-size:13px;color:#334155;
        word-break:break-all}}
  .btns{{display:grid;gap:10px;margin-top:20px}}
  a.btn{{display:block;text-decoration:none;padding:13px 16px;border-radius:11px;
        font-weight:700;font-size:15px}}
  a.primary{{background:#0f766e;color:#fff}}
  a.secondary{{background:#f1f5f9;color:#0f172a}}
  .hint{{margin-top:18px;font-size:12.5px;color:#94a3b8}}
</style>
</head>
<body>
  <div class="card">
    <div class="icon">🧭</div>
    <h1>Ye page nahi mila</h1>
    <p>Jo address khula hai — <code>{safe_path}</code> — wo is system me hai hi nahi.</p>
    <p style="color:#0f766e;font-weight:600">Aap shayad Doctor Dashboard kholna chahte the?</p>
    <div class="btns">
      <a class="btn primary" href="/opd/login">🩺 Doctor Login / Dashboard</a>
      <a class="btn secondary" href="/find-doctor">🔍 Find a Doctor</a>
      <a class="btn secondary" href="/">🏠 Home</a>
    </div>
    <p class="hint">Tip: dashboard ka pata <b>/opd/dashboard</b> hai (sab chhote akshar).
      Login ke baad wo apne aap khul jata hai.</p>
  </div>
</body>
</html>"""


def install_friendly_404(app: FastAPI) -> None:
    """Answer 404s kindly — JSON for APIs, a helpful page for humans.

    Only the 404 status is intercepted, so the session guard's 302 redirect and
    every other error keep FastAPI's exact default behaviour.
    """

    @app.exception_handler(404)
    async def _not_found(request: Request, exc):  # noqa: ANN001
        path = request.url.path
        accept = request.headers.get("accept", "") or ""

        # API clients must keep getting JSON — never a web page.
        if path.startswith("/api/") or (
            "application/json" in accept.lower() and "text/html" not in accept.lower()
        ):
            detail = getattr(exc, "detail", None) or "Not Found"
            return JSONResponse({"detail": detail}, status_code=404)

        # A human who was clearly aiming for the dashboard gets sent there.
        if _shape(path) in _DASHBOARD_SHAPES or _shape(path).endswith("dashboard"):
            logger.info("friendly 404: %s -> /opd/login", path)
            return RedirectResponse(url="/opd/login", status_code=302)

        return HTMLResponse(_friendly_page(path), status_code=404)
