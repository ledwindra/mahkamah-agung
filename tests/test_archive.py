"""Offline regression tests: no requests to court servers are made."""
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter
from rulings.archive import (
    DownloadError, database, discover_cases, digest_for_url, is_case_url,
    official_url, parse_detail, pdf_signature, process,
)

CASE = "https://putusan3.mahkamahagung.go.id/direktori/putusan/abc123.html"
PDF = "https://putusan3.mahkamahagung.go.id/direktori/download_file/abc/pdf/def"

DETAIL = """
<html><h2>Putusan Nomor 123 K/AG/2026</h2>
<table><tr><td>Nomor</td><td>123 K/AG/2026</td></tr>
<tr><td>Amar</td><td>Tolak</td></tr></table>
<a href="/direktori/download_file/abc/zip/def">Download ZIP</a>
<a href="/direktori/download_file/abc/pdf/def">Download PDF</a>
<a href="https://evil.example/f.pdf">PDF mirror</a>
</html>
"""

class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def iter_content(self, chunk_size=65536):
        yield self.payload


class FakeClient:
    def __init__(self):
        self.html_requests = 0
        self.pdf_requests = 0
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        self.buffer = io.BytesIO()
        writer.write(self.buffer)

    def html(self, url):
        self.html_requests += 1
        return DETAIL

    def get(self, url, stream=False):
        self.pdf_requests += 1
        return Response(self.buffer.getvalue())


class ArchiveTests(unittest.TestCase):
    def test_official_urls_only(self):
        self.assertEqual(official_url("/direktori/putusan/abc123.html"), CASE)
        self.assertTrue(is_case_url(CASE))
        for url in ["http://putusan3.mahkamahagung.go.id/test",
                    "https://evil.example/test",
                    "https://putusan3.mahkamahagung.go.id.evil.example/test"]:
            with self.assertRaises(ValueError):
                official_url(url)

    def test_case_discovery_and_dedup(self):
        html = """<a href="/direktori/putusan/abc123.html">1</a>
        <a href="/direktori/putusan/abc123.html">duplicate</a>
        <a href="/direktori/periode.html">other</a>"""
        self.assertEqual(discover_cases(html, CASE), [CASE])

    def test_detail_metadata_and_pdf_link(self):
        data, url = parse_detail(DETAIL, CASE)
        self.assertEqual(data["Nomor"], "123 K/AG/2026")
        self.assertEqual(data["Amar"], "Tolak")
        self.assertEqual(url, PDF)

    def test_pdf_signature_rejects_error_html(self):
        self.assertTrue(pdf_signature(b"%PDF-1.7\n"))
        self.assertFalse(pdf_signature(b"<html>403 Forbidden</html>"))

    def test_metadata_only_upgrades_to_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            client = FakeClient()
            with database(root / "index.sqlite3") as db:
                self.assertEqual(process(db, client, CASE, root, False, False, 100000), "metadata_only")
                self.assertEqual(process(db, client, CASE, root, True, False, 100000), "pdf_saved")
                self.assertEqual(process(db, client, CASE, root, True, False, 100000), "skipped")
                row = db.execute("SELECT * FROM decisions WHERE detail_url=?", (CASE,)).fetchone()
                self.assertEqual(row["case_number"], "123 K/AG/2026")
                self.assertTrue((root / row["pdf_path"]).exists())
                self.assertEqual(client.pdf_requests, 1)

    def test_extract_blank_scan_flag(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with database(root / "index.sqlite3") as db:
                self.assertEqual(process(db, FakeClient(), CASE, root, True, True, 100000), "scanned_pdf")
                row = db.execute("SELECT * FROM decisions").fetchone()
                self.assertEqual(row["page_count"], 1)
                self.assertEqual(row["text_chars"], 0)
                self.assertTrue((root / row["text_path"]).exists())

    def test_missing_pdf(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            client = FakeClient()
            client.html = lambda url: "<html><table><tr><td>Nomor</td><td>1</td></tr></table></html>"
            with database(root / "index.sqlite3") as db:
                self.assertEqual(process(db, client, CASE, root, True, True, 100000), "no_pdf")


if __name__ == "__main__":
    unittest.main()
