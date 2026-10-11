"""One-decision browser access check from a computer that can open the MA website.

Runs visible stock Chromium through Playwright (no stealth, proxy hopping or CAPTCHA
solving). Attempts an official PDF attachment using the browser's session cookies.
Keeps a JSON diagnostic and, if successful, a real PDF in archive/diagnostics/.

Install:
  python -m pip install -r requirements-browser.txt
  python -m playwright install chromium

Run:
  python -m rulings.browser_probe --url https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from rulings.archive import HOST, official_url, is_case_url, pdf_signature


def find_pdf_links(html: str, detail_url: str) -> list[str]:
    """Discover likely official PDF URLs, preserving order and excluding third parties."""
    doc = BeautifulSoup(html, "html.parser")
    ranked = []
    seen = set()
    for a in doc.select("a[href]"):
        href = a.get("href") or ""
        label = a.get_text(" ", strip=True).lower()
        try:
            url = official_url(urljoin(detail_url, href))
        except ValueError:
            continue
        path = urlsplit(url).path.lower()
        if ("/download_file/" in path and "/pdf/" in path):
            priority = 0
        elif path.endswith(".pdf"):
            priority = 1
        elif "/download_file/" in path and ("pdf" in label or "download" in label):
            priority = 2
        else:
            continue
        if url not in seen:
            seen.add(url)
            ranked.append((priority, len(ranked), url))
    return [url for _, _, url in sorted(ranked)]


def probe(args) -> int:
    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError:
        print("Playwright not installed. Use: python -m pip install -r requirements-browser.txt",
              file=sys.stderr)
        return 3

    case_url = official_url(args.url)
    if not is_case_url(case_url):
        print("Expected an official /direktori/putusan/<id>.html URL", file=sys.stderr)
        return 3

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    diagnostic = {
        "tested_at_utc": datetime.now(timezone.utc).isoformat(),
        "detail_url": case_url,
        "browser": "stock chromium",
        "headless": args.headless,
        "page_status": None,
        "page_url": None,
        "pdf_candidates": [],
        "attempts": [],
        "success": False,
        "error": None,
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=args.headless)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            try:
                response = page.goto(case_url, wait_until="domcontentloaded",
                                     timeout=args.timeout * 1000)
                diagnostic["page_status"] = response.status if response else None
                diagnostic["page_url"] = page.url
                if response is None or response.status in (401, 403, 429):
                    diagnostic["error"] = "Page access denied; no PDF attempted"
                    return 2
                if response.status != 200:
                    diagnostic["error"] = "Unexpected decision page status: " + str(response.status)
                    return 2

                # Allow ordinary client-side content to finish loading if present.
                page.wait_for_timeout(1250)
                if args.interactive and not args.headless:
                    input("Inspect the visible official decision page; press Enter to test its PDF link... ")

                links = find_pdf_links(page.content(), case_url)
                diagnostic["pdf_candidates"] = links
                if not links:
                    diagnostic["error"] = "No official PDF attachment link found in page DOM"
                    return 2

                # BrowserContext.request shares context cookies with Chromium.
                # It is an ordinary HTTP download within the established session.
                for pdf_url in links[:args.max_links]:
                    attempt = {"url": pdf_url, "status": None,
                               "content_type": None, "bytes": None, "pdf_valid": False}
                    diagnostic["attempts"].append(attempt)
                    try:
                        result = context.request.get(pdf_url, timeout=args.timeout * 1000,
                                                     max_redirects=3,
                                                     headers={"Referer": case_url})
                        # Requests to non-official redirected targets are disallowed by policy:
                        if urlsplit(result.url).hostname != HOST or urlsplit(result.url).scheme != "https":
                            attempt["error"] = "External redirect ignored"
                            continue
                        attempt["status"] = result.status
                        attempt["content_type"] = result.headers.get("content-type")
                        if result.status in (401, 403, 429):
                            attempt["error"] = "Attachment denied; stop"
                            break
                        if result.status != 200:
                            attempt["error"] = "Unexpected response"
                            continue
                        data = result.body()
                        attempt["bytes"] = len(data)
                        if len(data) > args.max_mb * 1024 * 1024:
                            attempt["error"] = "File exceeds limit"
                            continue
                        if not pdf_signature(data):
                            attempt["error"] = "Not PDF data"
                            continue
                        attempt["pdf_valid"] = True
                        sha = hashlib.sha256(data).hexdigest()
                        pdf_path = output / (sha + ".pdf")
                        pdf_path.write_bytes(data)
                        attempt["saved_as"] = str(pdf_path)
                        attempt["sha256"] = sha
                        diagnostic["success"] = True
                        break
                    except Exception as exc:
                        attempt["error"] = type(exc).__name__ + ": " + str(exc)[:220]
                if not diagnostic["success"]:
                    diagnostic["error"] = "No valid PDF was retrieved from listed attachments"
            finally:
                context.close()
                browser.close()
    except (PlaywrightError, OSError) as exc:
        diagnostic["error"] = type(exc).__name__ + ": " + str(exc)[:500]
    finally:
        path = output / "browser-diagnostic.json"
        path.write_text(json.dumps(diagnostic, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Decision page HTTP:", diagnostic["page_status"])
        print("Official PDF candidates:", len(diagnostic["pdf_candidates"]))
        for attempt in diagnostic["attempts"]:
            print("Attachment HTTP:", attempt["status"], "PDF:", attempt["pdf_valid"],
                  "bytes:", attempt["bytes"])
        print("Valid PDF acquired:", diagnostic["success"])
        print("Diagnostics saved:", path)
        if diagnostic["error"]:
            print("Issue:", diagnostic["error"])
    return 0 if diagnostic["success"] else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="One official MA decision detail URL")
    parser.add_argument("--output", default="archive/diagnostics")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-mb", type=int, default=80)
    parser.add_argument("--max-links", type=int, default=3)
    parser.add_argument("--headless", action="store_true",
                        help="Use invisible browser; visible is default for local diagnostics")
    parser.add_argument("--interactive", action="store_true",
                        help="Manually inspect visible browser before trying PDF link")
    args = parser.parse_args(argv)
    if args.timeout < 1 or args.max_mb < 1 or args.max_links < 1:
        parser.error("--timeout, --max-mb, and --max-links must be positive")
    if args.interactive and args.headless:
        parser.error("--interactive requires a visible browser")
    try:
        return probe(args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
