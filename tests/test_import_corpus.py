"""Offline import tests using synthetic decision PDF and Indo-Law XML fixtures."""
import io
import tempfile
import unittest
from pathlib import Path
from pypdf import PdfWriter

from rulings.archive import database
from rulings.import_corpus import import_pdf, import_xml, main

CASE = "https://putusan3.mahkamahagung.go.id/direktori/putusan/00035681c8d944203f25d2e8215ae2bf.html"
XML = """<putusan id="00035681c8d944203f25d2e8215ae2bf" klasifikasi="pidana-umum"
url="https://putusan3.mahkamahagung.go.id/direktori/putusan/00035681c8d944203f25d2e8215ae2bf.html">
<kepala_putusan>PUTUSAN Nomor 45/Pid.B/2014/PN Kds</kepala_putusan>
<amar_putusan>Menjatuhkan pidana</amar_putusan>
</putusan>"""


class CorpusTests(unittest.TestCase):
    def create_fixtures(self, location: Path):
        pdf = location / "sample.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with pdf.open("wb") as f:
            writer.write(f)
        xml = location / "sample.xml"
        xml.write_text(XML, encoding="utf-8")
        return pdf, xml

    def test_import_pdf_preserves_raw_and_flags_scanned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src, _ = self.create_fixtures(root)
            output = root / "archive"
            with database(output / "index.sqlite3") as db:
                key, status = import_pdf(db, src, output, "test-research-pdf", True)
                self.assertEqual(status, "scanned_pdf")
                row = db.execute("SELECT * FROM decisions WHERE detail_url=?", (key,)).fetchone()
                self.assertEqual(row["page_count"], 1)
                self.assertEqual(row["text_chars"], 0)
                self.assertTrue((output / row["pdf_path"]).exists())
                self.assertTrue((output / row["text_path"]).exists())
                # A second import is idempotent and does not downgrade status.
                _, another = import_pdf(db, src, output, "test-research-pdf", False)
                self.assertEqual(another, "scanned_pdf")

    def test_import_indo_law_xml_with_official_source_url(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, xml = self.create_fixtures(root)
            output = root / "archive"
            with database(output / "index.sqlite3") as db:
                key, status = import_xml(db, xml, output, "indo-law")
                self.assertEqual(key, CASE)
                self.assertEqual(status, "text_imported")
                row = db.execute("SELECT * FROM decisions WHERE detail_url=?", (CASE,)).fetchone()
                self.assertEqual(row["status"], "text_imported")
                text = (output / row["text_path"]).read_text(encoding="utf-8")
                self.assertIn("PUTUSAN Nomor 45", text)
                self.assertIn("amar_putusan", text)
                self.assertGreater(row["text_chars"], 35)

    def test_reject_invalid_pdf_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake = root / "invalid.pdf"
            fake.write_text("<html>403 Forbidden</html>")
            with database(root / "archive" / "index.sqlite3") as db:
                with self.assertRaises(ValueError):
                    import_pdf(db, fake, root / "archive", "test", True)

    def test_cli_limit_and_record_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src, xml = self.create_fixtures(root)
            output = root / "archive"
            self.assertEqual(main([str(root), "--output", str(output), "--limit", "1"]), 0)
            with database(output / "index.sqlite3") as db:
                n = db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
                self.assertEqual(n, 1)


if __name__ == "__main__":
    unittest.main()
