"""Import already downloaded PDF decisions and Indo-Law XML into the local SQLite archive.

This is a source-independent fallback when online court PDF endpoints return 403.
Nothing in this module fetches or bypasses a blocked website.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from rulings.archive import (
    database, digest_for_url, extract_text, official_url, is_case_url,
    pdf_signature, record,
)

LOG = logging.getLogger("import_corpus")


def fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_list(path: Path, recursive: bool):
    if path.is_file():
        if path.suffix.lower() in (".pdf", ".xml"):
            yield path
        return
    walker = path.rglob("*") if recursive else path.glob("*")
    for item in sorted(walker):
        if item.is_file() and item.suffix.lower() in (".pdf", ".xml"):
            yield item


def atomic_copy(src: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    try:
        with src.open("rb") as source, temporary.open("wb") as dest:
            shutil.copyfileobj(source, dest, 1024 * 1024)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def import_pdf(db, src: Path, archive: Path, origin: str, make_text: bool):
    with src.open("rb") as stream:
        if not pdf_signature(stream.read(1024)):
            raise ValueError("Not a genuine PDF: " + str(src))
    sha = fingerprint(src)
    key = "local-pdf:" + sha
    pdf_rel = Path("pdf") / (sha + ".pdf")
    dest = archive / pdf_rel
    if not dest.exists():
        atomic_copy(src, dest)
    if not pdf_signature(dest.open("rb").read(1024)):
        raise ValueError("Copied file has invalid PDF signature")
    metadata = {"source": origin, "source_file": str(src.resolve()),
                "original_filename": src.name, "import_type": "pdf"}
    fields = dict(metadata_json=json.dumps(metadata, ensure_ascii=False),
                  pdf_path=str(pdf_rel), pdf_sha256=sha, status="pdf_saved",
                  error=None)
    # Re-importing a file should not erase a previous valid text extraction.
    old = db.execute("SELECT status,text_path FROM decisions WHERE detail_url=?", (key,)).fetchone()
    if make_text:
        txt_rel = Path("text") / (digest_for_url(key) + ".txt")
        count, chars = extract_text(dest, archive / txt_rel)
        fields.update(text_path=str(txt_rel), page_count=count, text_chars=chars,
                      status="text_extracted" if chars else "scanned_pdf")
    elif old and old["status"] in ("text_extracted", "scanned_pdf") and old["text_path"]:
        fields["status"] = old["status"]
    record(db, key, **fields)
    return key, fields["status"]


def import_xml(db, src: Path, archive: Path, origin: str):
    # Public Indo-Law XML has a <putusan> root with metadata attributes and
    # annotated legal sections. No external network reads are performed.
    root = ET.parse(src).getroot()
    if root.tag != "putusan":
        raise ValueError("Expected <putusan> root in " + str(src))
    url = root.attrib.get("url", "")
    if url:
        url = official_url(url)
        if not is_case_url(url):
            raise ValueError("Unexpected source case URL: " + url)
    else:
        url = "local-xml:" + fingerprint(src)
    metadata = dict(root.attrib)
    metadata.update({"source": origin, "source_file": str(src.resolve()),
                     "original_filename": src.name, "import_type": "indo-law-xml"})
    # Section names retained for downstream legal NLP tasks.
    sections = []
    for element in root:
        body = " ".join((element.text or "").split())
        if body:
            sections.append(element.tag + "\n" + body)
    fulltext = "\n\n".join(sections)
    if not fulltext:
        raise ValueError("XML contains no extracted decision text: " + str(src))
    txt_rel = Path("text") / (digest_for_url(url) + ".txt")
    dest = archive / txt_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".txt.part")
    try:
        temp.write_text(fulltext, encoding="utf-8")
        os.replace(temp, dest)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    # Do not override an existing downloaded and validated PDF.
    previous = db.execute("SELECT * FROM decisions WHERE detail_url=?", (url,)).fetchone()
    preserve = previous and previous["status"] in ("pdf_saved", "text_extracted", "scanned_pdf")
    if preserve:
        # Existing PDFs take precedence; only enrich metadata when possible.
        former = json.loads(previous["metadata_json"] or "{}")
        former["supplementary_xml_source"] = metadata
        record(db, url, metadata_json=json.dumps(former, ensure_ascii=False))
        return url, "already_has_pdf"
    record(db, url,
           metadata_json=json.dumps(metadata, ensure_ascii=False),
           status="text_imported", text_path=str(txt_rel),
           text_chars=len(fulltext), error=None)
    return url, "text_imported"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("path", help="An existing PDF/XML file or directory")
    p.add_argument("--output", default="archive")
    p.add_argument("--source", default="local-files", help="Provenance of the collection")
    p.add_argument("--limit", type=int, default=10, help="Maximum files (0 = all)")
    p.add_argument("--recursive", action="store_true", help="Search subdirectories")
    p.add_argument("--text", action="store_true", help="Extract text from each PDF")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.limit < 0:
        p.error("--limit must be >= 0")
    directory = Path(args.path).expanduser()
    if not directory.exists():
        p.error("Input file/directory does not exist")
    archive = Path(args.output)
    archive.mkdir(parents=True, exist_ok=True)
    counts = {}
    failures = 0
    processed = 0
    with database(archive / "index.sqlite3") as db:
        for src in file_list(directory, args.recursive):
            if args.limit and processed >= args.limit:
                break
            try:
                if src.suffix.lower() == ".xml":
                    key, status = import_xml(db, src, archive, args.source)
                else:
                    key, status = import_pdf(db, src, archive, args.source, args.text)
                counts[status] = counts.get(status, 0) + 1
                LOG.info("[%s] %s (%s)", status, src.name, key)
            except Exception as exc:
                failures += 1
                LOG.error("FAILED %s: %s", src, exc)
            processed += 1
    print("Processed:", processed, "statuses:", counts, "failures:", failures,
          "archive:", archive)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
