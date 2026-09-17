"""
Public base URL — "patient ka link kabhi toota hua na jaye".

Problem jo asli me hui: `.env` me `APP_BASE_URL` purane tunnel
(`xxx.trycloudflare.com`) ya band Railway domain ka pada rehta hai. Uske baad
jo bhi patient link / share link banta hai, wo **dead URL** hota hai — patient
kholta hai to "site not found". Isliye ab:

  1. `APP_BASE_URL` set hai → pehle usko use karo (permanent domain/VM ke liye sahi)
  2. Lekin agar us host ka **DNS resolve hi nahi hota** (tunnel band, Railway band,
     domain expire) → usko 5 minute ke liye "dead" mark karo aur **request ke apne
     host** se link banao (jo abhi kaam kar raha hai)
  3. Sab kuch Hinglish me log hota hai, taaki doctor/admin ko pata chale

DNS check jaan-boojh kar chuna gaya (HTTP nahi): sasta, fast, aur tunnel/Railway
band hone par DNS turant fail hone lagta hai.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

#: host → is timestamp tak "dead" maana jayega (monotonic seconds)
_dead_until: Dict[str, float] = {}
DEAD_TTL_SEC = 300.0
DNS_TIMEOUT_SEC = 2.0

#: localhost/sirf-local host ko public base URL kabhi nahi maanenge
_LOCAL_PREFIXES = ("http://localhost", "http://127.", "http://0.0.0.0", "http://[::1]")


def configured_base_url() -> str:
    """`.env` ka APP_BASE_URL (khali ho sakta hai)."""
    return (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")


def is_local_url(url: str) -> bool:
    return any((url or "").startswith(p) for p in _LOCAL_PREFIXES)


def host_is_alive(url: str) -> bool:
    """Host ka DNS resolve hota hai? (5 min cache ke saath)"""
    try:
        host = urlparse(url).hostname
    except Exception:
        host = None
    if not host:
        return False
    now = time.monotonic()
    if _dead_until.get(host, 0.0) > now:
        return False
    try:
        socket.setdefaulttimeout(DNS_TIMEOUT_SEC)
        socket.getaddrinfo(host, None)
        return True
    except OSError:
        _dead_until[host] = now + DEAD_TTL_SEC
        logger.warning(
            "APP_BASE_URL ka host '%s' resolve nahi ho raha (tunnel/Railway band?) — "
            "agle 5 minute ke liye request ke host se link banaya jayega",
            host,
        )
        return False


def public_base_url(request=None) -> str:
    """Is waqt ka sabse bharosemand public base URL.

    Order: APP_BASE_URL (agar zinda ho) → request ka host → localhost fallback.
    """
    cfg = configured_base_url()
    if cfg and not is_local_url(cfg) and host_is_alive(cfg):
        return cfg
    if request is not None:
        try:
            base = str(request.base_url).rstrip("/")
            if base:
                return base
        except Exception:
            pass
    if cfg:
        return cfg
    return "http://localhost:8000"


def base_url_status(request=None) -> Dict[str, Optional[object]]:
    """Doctor/admin ke liye diagnostic — kaun sa URL use ho raha hai aur kyun."""
    cfg = configured_base_url()
    alive = host_is_alive(cfg) if cfg else None
    effective = public_base_url(request)
    warning = ""
    if cfg and is_local_url(cfg):
        warning = (
            "APP_BASE_URL localhost par set hai — patient ke phone se link nahi khulega. "
            "Public URL (VM IP / domain / tunnel) daalein."
        )
    elif cfg and alive is False:
        warning = (
            f"APP_BASE_URL ({cfg}) ab zinda nahi hai (tunnel/Railway band). "
            "Abhi ke liye request ka host use ho raha hai — permanent URL set karein."
        )
    elif not cfg:
        warning = "APP_BASE_URL set nahi hai — link current host se banega (asthayi)."
    return {
        "configured": cfg,
        "configured_alive": alive,
        "effective": effective,
        "warning": warning,
    }


def reset_cache() -> None:
    """Tests ke liye."""
    _dead_until.clear()
