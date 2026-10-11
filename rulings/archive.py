"""Resumable, rate-limited local archive of Indonesian court decision PDFs.

This is intentionally separate from the original rulings.scraper API.
Only official putusan3.mahkamahagung.go.id URLs are fetched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

HOST = "putusan3.mahkamahagung.go.id"
BASE = "https://" + HOST
DEFAULT_LISTING = BASE + "/direktori/index/page/{page}.html"
LOG = logging.getLogger("mahkamah-agung")


class AccessBlocked(RuntimeError):
    """Access denied or throttled; stop the crawl, do not evade controls."""


class DownloadError(RuntimeError):
    pass


def official_url(url: str) -> str:
    """Reject redirects or scraped links to third-party domains."""
    url = urljoin(BASE + "/", url)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.username or parsed.password:
        raise ValueError("Not an HTTPS URL on the official host: " + url)
    return url


def is_case_url(url: str) -> bool:
    parts = urlsplit(url)
    return bool(re.fullmatch(r"/direktori/putusan/[^/]+\.html", parts.path))


def discover_cases(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    seen = set()
    for a in soup.select("a[href]"):
        try:
            url = official_url(urljoin(base_url, a["href"]))
        except ValueError:
            continue
        if is_case_url(url) and url not in seen:
            seen.add(url)
            found.append(url)
    return found


def parse_detail(html: str, detail_url: str) -> tuple[dict, str | None]:
    """Use label/value rows rather than brittle nth-child selectors."""
    soup = BeautifulSoup(html, "html.parser")
    metadata = {"source_url": detail_url}
    heading = soup.find(["h1", "h2"])
    if heading:
        metadata["heading"] = heading.get_text(" ", strip=True)
    for row in soup.select("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) != 2:
            continue
        key = " ".join(cells[0].stripped_strings).strip(" :")
        val = " ".join(cells[1].stripped_strings)
        if key and key not in metadata:
            metadata[key] = val

    candidates = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        label = a.get_text(" ", strip=True).lower()
        absolute = urljoin(detail_url, href)
        try:
            absolute = official_url(absolute)
        except ValueError:
            continue
        path = urlsplit(absolute).path.lower()
        if "/download_file/" in path and ("/pdf/" in path or path.endswith(".pdf")):
            candidates.append((0, absolute))
        elif (path.endswith(".pdf") or "/download_file/" in path) and "pdf" in label:
            candidates.append((1, absolute))
        elif path.endswith(".pdf"):
            candidates.append((2, absolute))
    candidates.sort()
    return metadata, candidates[0][1] if candidates else None


def pdf_signature(data: bytes) -> bool:
    return b"%PDF-" in data[:1024]


def digest_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Client:
    def __init__(self, delay: float, timeout: float, retries: int):
        self.delay, self.timeout, self.retries = delay, timeout, retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CourtDecisionResearchArchive/0.1 (public research; low-rate client)",
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.5",
        })
        self.last_request = 0.0

    def get(self, url: str, stream: bool = False) -> requests.Response:
        url = official_url(url)
        for attempt in range(self.retries + 1):
            remaining = self.delay - (time.monotonic() - self.last_request)
            if remaining > 0:
                time.sleep(remaining)
            self.last_request = time.monotonic()
            try:
                response = self.session.get(url, timeout=self.timeout, stream=stream, allow_redirects=False)
            except requests.RequestException as exc:
                if attempt == self.retries:
                    raise DownloadError(str(exc)) from exc
                time.sleep(min(2 ** attempt, 30))
                continue
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                response.close()
                if not location:
                    raise DownloadError("Redirect without Location")
                # A redirect is followed only when it remains on the official host.
                redirected = official_url(urljoin(url, location))
                if redirected == url:
                    raise DownloadError("Redirect loop")
                return self.get(redirected, stream=stream)
            if response.status_code in (401, 403, 429):
                status = response.status_code
                response.close()
                raise AccessBlocked(f"HTTP {status} at {url}; stop and check access policy/server availability")
            if 500 <= response.status_code <= 599 and attempt < self.retries:
                response.close()
                time.sleep(min(2 ** attempt, 30))
                continue
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                response.close()
                raise DownloadError(str(exc)) from exc
            return response
        raise DownloadError("Retries exhausted")

    def html(self, url: str) -> str:
        with self.get(url) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            if "pdf" in content_type:
                raise DownloadError("Expected HTML, received PDF")
            return resp.content.decode(resp.encoding or "utf-8", errors="replace")


def database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
          detail_url TEXT PRIMARY KEY,
          case_number TEXT,
          metadata_json TEXT,
          pdf_url TEXT,
          pdf_path TEXT,
          text_path TEXT,
          pdf_sha256 TEXT,
          page_count INTEGER,
          text_chars INTEGER,
          status TEXT NOT NULL DEFAULT 'pending',
          error TEXT,
          updated_at TEXT NOT NULL
        )
    """)
    db.commit()
    return db


def record(db: sqlite3.Connection, url: str, **fields) -> None:
    valid = {
        "case_number", "metadata_json", "pdf_url", "pdf_path", "text_path",
        "pdf_sha256", "page_count", "text_chars", "status", "error",
    }
    if set(fields) - valid:
        raise ValueError("Unknown database fields")
    db.execute("INSERT OR IGNORE INTO decisions (detail_url,status,updated_at) VALUES (?,?,?)",
               (url, "pending", utc_now()))
    fields["updated_at"] = utc_now()
    setters = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE decisions SET {setters} WHERE detail_url = ?",
               (*fields.values(), url))
    db.commit()


def extract_text(pdf_path: Path, txt_path: Path) -> tuple[int, int]:
    reader = PdfReader(str(pdf_path), strict=False)
    page_count = len(reader.pages)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = txt_path.with_suffix(".txt.part")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, txt_path)
    return page_count, len(text.strip())


def save_pdf(client: Client, url: str, path: Path, max_bytes: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".pdf.part")
    sha = hashlib.sha256()
    size = 0
    try:
        with client.get(url, stream=True) as resp, tmp.open("wb") as handle:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise DownloadError(f"File larger than {max_bytes} bytes")
                sha.update(chunk)
                handle.write(chunk)
        with tmp.open("rb") as handle:
            if not pdf_signature(handle.read(1024)):
                raise DownloadError("Response is not a PDF (often HTML error/login page)")
        os.replace(tmp, path)
        return sha.hexdigest()
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def process(db: sqlite3.Connection, client: Client, url: str, root: Path,
            download: bool, text: bool, max_bytes: int, force: bool = False) -> str:
    url = official_url(url)
    if not is_case_url(url):
        raise ValueError("Not a decision detail URL: " + url)
    prior = db.execute("SELECT * FROM decisions WHERE detail_url=?", (url,)).fetchone()
    if prior is not None and not force:
        if prior["status"] in ("text_extracted", "scanned_pdf", "pdf_saved", "no_pdf") or (prior["status"] == "metadata_only" and not download):
            if prior["status"] in ("text_extracted", "scanned_pdf", "pdf_saved") and text and prior["pdf_path"]:
                pdf_file = root / prior["pdf_path"]
                if pdf_file.is_file() and prior["status"] == "pdf_saved":
                    txt_file = Path("text") / (digest_for_url(url) + ".txt")
                    count, chars = extract_text(pdf_file, root / txt_file)
                    status = "text_extracted" if chars else "scanned_pdf"
                    record(db, url, text_path=str(txt_file), page_count=count,
                           text_chars=chars, status=status, error=None)
                    return status
            else:
                return "skipped"

    html = client.html(url)
    metadata, pdf_url = parse_detail(html, url)
    fields = {
        "case_number": metadata.get("Nomor"),
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "pdf_url": pdf_url, "error": None,
    }
    if not pdf_url:
        record(db, url, status="no_pdf", **fields)
        return "no_pdf"
    if not download:
        record(db, url, status="metadata_only", **fields)
        return "metadata_only"

    pdf_file = Path("pdf") / (digest_for_url(url) + ".pdf")
    absolute_pdf = root / pdf_file
    if force or not absolute_pdf.is_file() or not pdf_signature(absolute_pdf.open("rb").read(1024)):
        sha = save_pdf(client, pdf_url, absolute_pdf, max_bytes=max_bytes)
    else:
        sha = hashlib.sha256(absolute_pdf.read_bytes()).hexdigest()
    record(db, url, status="pdf_saved", pdf_path=str(pdf_file), pdf_sha256=sha, **fields)
    if text:
        txt_file = Path("text") / (digest_for_url(url) + ".txt")
        count, chars = extract_text(absolute_pdf, root / txt_file)
        status = "text_extracted" if chars else "scanned_pdf"
        record(db, url, text_path=str(txt_file), page_count=count,
               text_chars=chars, status=status)
        return status
    return "pdf_saved"


def iter_input_urls(args, client: Client):
    if args.url:
        yield args.url
        return
    if args.input:
        with Path(args.input).open(encoding="utf-8") as handle:
            for line in handle:
                url = line.strip()
                if url and not url.startswith("#"):
                    yield url
        return
    for page in range(args.start_page, args.start_page + args.pages):
        page_url = official_url(args.listing_template.format(page=page))
        LOG.info("Listing page %d: %s", page, page_url)
        html = client.html(page_url)
        urls = discover_cases(html, page_url)
        LOG.info("Found %d decision links", len(urls))
        for url in urls:
            yield url


def crawl(args) -> int:
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    db = database(root / "index.sqlite3")
    client = Client(delay=args.delay, timeout=args.timeout, retries=args.retries)
    seen = set()
    processed = 0
    try:
        for url in iter_input_urls(args, client):
            url = official_url(url)
            if not is_case_url(url):
                LOG.warning("Ignoring non-decision URL: %s", url)
                continue
            if url in seen:
                continue
            seen.add(url)
            if args.max_cases and processed >= args.max_cases:
                break
            try:
                status = process(db, client, url, root, (args.download or args.text),
                                 args.text, int(args.max_mb * 1024 * 1024), args.force)
            except AccessBlocked:
                raise
            except Exception as exc:
                record(db, url, status="error", error=str(exc)[:1000])
                LOG.error("%s: %s", url, exc)
                status = "error"
            processed += 1
            LOG.info("[%d] %s %s", processed, status, url)
    except AccessBlocked as exc:
        LOG.error("STOPPED: %s", exc)
        return 2
    except (DownloadError, requests.RequestException, ValueError) as exc:
        LOG.error("STOPPED: %s", exc)
        return 2
    finally:
        db.close()
        client.session.close()
    LOG.info("Finished %d decisions. Database: %s", processed, root / "index.sqlite3")
    return 0


def show_stats(root: Path) -> int:
    with database(root / "index.sqlite3") as db:
        for row in db.execute("SELECT status,COUNT(*) AS n FROM decisions GROUP BY status ORDER BY status"):
            print(f"{row['status']}: {row['n']}")
    return 0


def export_jsonl(root: Path, target: Path) -> int:
    with database(root / "index.sqlite3") as db, target.open("w", encoding="utf-8") as out:
        for row in db.execute("SELECT * FROM decisions ORDER BY detail_url"):
            obj = dict(row)
            obj["metadata"] = json.loads(obj.pop("metadata_json") or "{}")
            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print("Wrote", target)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("crawl", help="Fetch listing or case URLs; optionally save PDFs and text")
    source = p.add_mutually_exclusive_group()
    source.add_argument("--url", help="One official decision detail URL")
    source.add_argument("--input", help="Text file containing one official decision URL per line")
    p.add_argument("--listing-template", default=DEFAULT_LISTING,
                   help="Official listing URL containing {page}")
    p.add_argument("--start-page", type=int, default=1)
    p.add_argument("--pages", type=int, default=1)
    p.add_argument("--max-cases", type=int, default=5, help="0 = unlimited")
    p.add_argument("--output", default="archive", help="Local archive directory (gitignored)")
    p.add_argument("--download", action="store_true", help="Download PDFs (off by default)")
    p.add_argument("--text", action="store_true", help="Extract text; implies --download")
    p.add_argument("--force", action="store_true", help="Re-fetch even completed decisions")
    p.add_argument("--delay", type=float, default=3, help="Minimum seconds between HTTP requests")
    p.add_argument("--timeout", type=float, default=45)
    p.add_argument("--retries", type=int, default=2)
    p.add_argument("--max-mb", type=float, default=80)
    s = sub.add_parser("stats", help="Show local database status counts")
    s.add_argument("--output", default="archive")
    e = sub.add_parser("export", help="Export the local database as JSON Lines")
    e.add_argument("--output", default="archive")
    e.add_argument("--file", default="archive/decisions.jsonl")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "crawl":
        if args.pages < 1 or args.start_page < 1 or args.max_cases < 0:
            parser.error("pages/start-page must be positive; max-cases must be >= 0")
        if args.delay < 1 or args.timeout <= 0 or args.retries < 0 or args.max_mb <= 0:
            parser.error("delay must be >= 1 and other network limits must be valid")
        return crawl(args)
    if args.command == "stats":
        return show_stats(Path(args.output))
    if args.command == "export":
        target = Path(args.file)
        target.parent.mkdir(parents=True, exist_ok=True)
        return export_jsonl(Path(args.output), target)
    return 1


if __name__ == "__main__":
    sys.exit(main())
