"""Module 6 ingestion worker — crawl public rosters → structured doctor profiles.

This file is intentionally dependency-thin at import time: ``crawl4ai`` and
``playwright`` are imported inside the functions that need them, so the profile
validation logic can be unit-tested (and imported by the app's test suite)
without a 400 MB browser installed.

Run:
    python main.py --config targets.json --dry-run
    python main.py --config targets.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Iterable

logger = logging.getLogger("crawl_doctors")

DEFAULT_API_BASE = "https://gillhopitalsoftware1.pythonanywhere.com"

#: Field limits, mirroring src/infrastructure/clinic/models/crawl_model.py.
#: Duplicated only as a *fallback*: the real contract is fetched from the API
#: (see fetch_remote_schema) so the two cannot drift.
FALLBACK_LIMITS: dict[str, int] = {
    "doctor_name": 200, "clinic_name": 200, "specialty": 100, "degree": 500,
    "reg_no": 100, "phone": 20, "email": 200, "address": 1000, "city": 100,
    "state": 100, "source_url": 500, "opd_timing": 200, "notes": 2000,
}

FALLBACK_INSTRUCTION = (
    "Extract every doctor listed on this page as a separate object with these "
    "fields: doctor_name, clinic_name, specialty, degree, reg_no, phone, email, "
    "address, city, state, opd_timing. Use only text present on the page. Leave "
    "a field empty rather than guessing it — never invent a phone number, a "
    "registration number, or a qualification. Do not merge two doctors into one "
    "object."
)

#: Mobile numbers in India start 6-9 and are 10 digits.
_PHONE_RE = re.compile(r"^[6-9]\d{9}$")


@dataclass
class Target:
    """One roster page to crawl."""

    url: str
    city: str = ""
    state: str = ""
    label: str = ""
    wait_for: str = ""
    notes: str = ""


@dataclass
class RunStats:
    urls_attempted: int = 0
    urls_failed: int = 0
    profiles_found: int = 0
    profiles_valid: int = 0
    rejections: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.rejections[reason] = self.rejections.get(reason, 0) + 1


# ── Profile validation (mirrors the server, enforced locally too) ───────────


def validate_profile(raw: Any, index: int = -1) -> dict[str, Any] | None:
    """Clean one profile, or return None when it must not be sent.

    The server validates again. This exists so the worker's OWN logs say why a
    profile was dropped — otherwise a run reports "3 profiles" and nobody can
    tell whether the other 40 were duplicates or garbage.
    """
    stats_holder: list[str] = []
    if not isinstance(raw, dict):
        stats_holder.append("not_an_object")
        return None

    clean: dict[str, Any] = {}
    for key, limit in FALLBACK_LIMITS.items():
        value = raw.get(key)
        if value in (None, ""):
            continue
        if key in ("latitude", "longitude"):
            continue
        text = str(value).strip()
        if text:
            clean[key] = text[:limit]

    name = clean.get("doctor_name", "")
    if not name or not any(ch.isalpha() for ch in name):
        return None

    # A fabricated-looking phone is worse than a missing one: a blank is
    # visibly unknown, a wrong number sends a patient to a stranger.
    phone = clean.get("phone")
    if phone:
        digits = re.sub(r"\D", "", phone)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        clean["phone"] = digits if _PHONE_RE.match(digits) else ""

    # Strip a leading "Dr."/"Dr" so the directory is consistent.
    clean["doctor_name"] = re.sub(r"^\s*dr\.?\s+", "", clean["doctor_name"], flags=re.I).strip()
    if not clean["doctor_name"]:
        return None

    return clean


def dedupe(profiles: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse profiles that describe the same doctor.

    The same doctor is usually listed on several pages, and one page often
    lists several doctors, so identity is name+city+clinic rather than URL.
    First wins: pages are crawled in the order the config lists them, which is
    the operator's own priority.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for profile in profiles:
        key = "|".join(
            str(profile.get(k) or "").strip().lower()
            for k in ("doctor_name", "city", "clinic_name")
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(profile)
    return out


# ── API contract ────────────────────────────────────────────────────────────


def fetch_remote_schema(api_base: str, token: str, timeout: float = 30.0) -> tuple[dict | None, str]:
    """Fetch the schema + extraction instruction the server actually validates.

    Fetched rather than hard-coded so a contract change on the server cannot
    leave the worker silently sending fields nobody checks.
    """
    import httpx

    try:
        response = httpx.get(
            f"{api_base}/api/v1/ingest/schema",
            params={"token": token},
            timeout=timeout,
        )
        if response.status_code != 200:
            logger.warning("schema fetch returned %s — using fallback", response.status_code)
            return None, FALLBACK_INSTRUCTION
        payload = response.json()
        return payload.get("schema"), payload.get("instruction") or FALLBACK_INSTRUCTION
    except Exception as exc:
        logger.warning("schema fetch failed (%s) — using fallback", exc)
        return None, FALLBACK_INSTRUCTION


def post_profiles(
    api_base: str,
    token: str,
    profiles: list[dict[str, Any]],
    run_label: str,
    urls_attempted: int,
    dry_run: bool = False,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Send a batch to the ingest endpoint. Returns the server's response."""
    if dry_run:
        logger.info("[dry-run] would post %d profiles", len(profiles))
        return {"ok": True, "dry_run": True, "received": len(profiles)}

    import httpx

    response = httpx.post(
        f"{api_base}/api/v1/ingest/doctors",
        params={"token": token},
        json={
            "run_label": run_label,
            "triggered_by": "github-actions",
            "urls_attempted": urls_attempted,
            "profiles": profiles,
        },
        timeout=timeout,
    )
    try:
        return response.json()
    except Exception:
        return {"ok": False, "error": f"HTTP {response.status_code}: {response.text[:300]}"}


# ── Crawl + extract ─────────────────────────────────────────────────────────


def crawl_and_extract(
    target: Target,
    api_key: str,
    instruction: str,
    schema: dict | None,
) -> list[dict[str, Any]]:
    """Crawl one roster page and return the extracted raw profiles.

    Imports crawl4ai lazily so the validation logic above stays testable in an
    environment without a browser.
    """
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import LLMExtractionStrategy

    strategy = LLMExtractionStrategy(
        # ``google/gemini-2.0-flash`` per the blueprint; the provider string is
        # configurable because the sandbox key may be a different model.
        provider=os.getenv("EXTRACTION_PROVIDER", "google/gemini-2.0-flash"),
        api_token=api_key,
        schema=schema,
        extraction_type="schema" if schema else "block",
        instruction=instruction,
    )

    async def _run() -> Any:
        kwargs: dict[str, Any] = {
            "url": target.url,
            "extraction_strategy": strategy,
            "bypass_cache": True,
        }
        if target.wait_for:
            # JS-rendered rosters need an explicit wait, or we extract an empty
            # shell and report "0 doctors" for a page that has plenty.
            kwargs["wait_for"] = target.wait_for
            kwargs["delay_before_return_html"] = 2.0
        async with AsyncWebCrawler(headless=True, verbose=False) as crawler:
            return await crawler.arun(**kwargs)

    import asyncio

    result = asyncio.run(_run())
    if not getattr(result, "success", False):
        logger.error("crawl failed for %s: %s", target.url, getattr(result, "error_message", "?"))
        return []

    return _coerce(getattr(result, "extracted_content", None))


def _coerce(payload: Any) -> list[dict[str, Any]]:
    """Unwrap whatever shape the extractor returned.

    LLM extraction is not deterministic: the same instruction returns a bare
    list, a ``{"doctors": [...]}`` wrapper, a single object, or a JSON string of
    any of those. Rejecting the wrappers would make the pipeline flaky for no
    reason; inventing a profile would be far worse.
    """
    if payload is None:
        return []
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return []
        try:
            return _coerce(json.loads(text))
        except (ValueError, TypeError):
            return []
    if isinstance(payload, dict):
        for key in ("doctors", "profiles", "data", "results", "items", "records"):
            if isinstance(payload.get(key), list):
                return _coerce(payload[key])
        if "doctor_name" in payload or "name" in payload:
            return [payload]
        return []
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, str):
                out.extend(_coerce(item))
        return out
    return []


def load_targets(path: str) -> list[Target]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    entries = data.get("targets") if isinstance(data, dict) else data
    targets: list[Target] = []
    for entry in entries or []:
        if isinstance(entry, str):
            targets.append(Target(url=entry))
        elif isinstance(entry, dict) and entry.get("url"):
            targets.append(
                Target(
                    url=entry["url"],
                    city=entry.get("city", ""),
                    state=entry.get("state", ""),
                    label=entry.get("label", ""),
                    wait_for=entry.get("wait_for", ""),
                    notes=entry.get("notes", ""),
                )
            )
    return targets


def stamp_target(profile: dict[str, Any], target: Target) -> dict[str, Any]:
    """Fill city/state/source_url from the target when the page did not.

    Only for fields the page left EMPTY — never overwrite extracted text with
    config, because the page is the authority on what the page says.
    """
    profile.setdefault("source_url", target.url)
    if not profile.get("city") and target.city:
        profile["city"] = target.city
    if not profile.get("state") and target.state:
        profile["state"] = target.state
    return profile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GHOS Module 6 doctor ingestion worker")
    parser.add_argument("--config", default="targets.json", help="targets JSON file")
    parser.add_argument("--api-base", default=os.getenv("API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--token", default=os.getenv("INGEST_TOKEN", ""))
    parser.add_argument("--dry-run", action="store_true", help="extract but do not post")
    parser.add_argument("--limit", type=int, default=0, help="max profiles to post")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not args.token:
        logger.error("INGEST_TOKEN is required (the app fails closed without it)")
        return 2

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("EXTRACTION_API_KEY") or ""
    if not api_key:
        logger.error("GEMINI_API_KEY is required for schema-guided extraction")
        return 2

    try:
        targets = load_targets(args.config)
    except FileNotFoundError:
        logger.error("config not found: %s", args.config)
        return 2
    if not targets:
        logger.error("no targets in %s", args.config)
        return 2

    schema, instruction = fetch_remote_schema(args.api_base, args.token)
    logger.info(
        "schema: %s · %d target(s)",
        "fetched from API" if schema else "local fallback",
        len(targets),
    )

    stats = RunStats()
    collected: list[dict[str, Any]] = []

    for target in targets:
        stats.urls_attempted += 1
        logger.info("crawling %s", target.label or target.url)
        try:
            raw = crawl_and_extract(target, api_key, instruction, schema)
        except Exception as exc:
            stats.urls_failed += 1
            logger.exception("crawl error for %s: %s", target.url, exc)
            continue

        stats.profiles_found += len(raw)
        for index, item in enumerate(raw):
            clean = validate_profile(item, index)
            if clean is None:
                stats.reject("invalid_or_nameless")
                continue
            collected.append(stamp_target(clean, target))

    stats.profiles_valid = len(collected)
    unique = dedupe(collected)
    dropped_dupes = stats.profiles_valid - len(unique)
    if dropped_dupes:
        stats.reject("duplicate_in_batch")
        stats.rejections["duplicate_in_batch"] = dropped_dupes

    if args.limit and len(unique) > args.limit:
        unique = unique[: args.limit]

    logger.info(
        "found=%d valid=%d unique=%d failed_urls=%d rejections=%s",
        stats.profiles_found, stats.profiles_valid, len(unique),
        stats.urls_failed, stats.rejections or "{}",
    )

    if not unique:
        # Not an error: a roster page that genuinely lists nobody is a real
        # outcome, and reporting success with 0 profiles is honest.
        logger.warning("no profiles to post")
        return 0

    result = post_profiles(
        api_base=args.api_base,
        token=args.token,
        profiles=unique,
        run_label=os.getenv("RUN_LABEL", "gh-actions"),
        urls_attempted=stats.urls_attempted,
        dry_run=args.dry_run,
    )
    logger.info("server response: %s", json.dumps(result, ensure_ascii=False)[:600])

    if not result.get("ok"):
        logger.error("ingest rejected the batch")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
