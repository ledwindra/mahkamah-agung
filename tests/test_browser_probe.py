"""Offline HTML fixture checks for the local browser access probe."""
import unittest

from rulings.browser_probe import find_pdf_links

CASE = "https://putusan3.mahkamahagung.go.id/direktori/putusan/test123.html"


class BrowserProbeTests(unittest.TestCase):
    def test_prefers_direct_official_pdf(self):
        html = """
          <a href="/direktori/download_file/fileid/zip/caseid">ZIP</a>
          <a href="/direktori/download_file/fileid/pdf/caseid">Download PDF</a>
          <a href="https://evil.example/download_file/foo/pdf/bar">Fake PDF</a>
          <a href="/direktori/download_file/fileid/pdf/caseid">duplicate</a>
        """
        self.assertEqual(find_pdf_links(html, CASE), [
            "https://putusan3.mahkamahagung.go.id/direktori/download_file/fileid/pdf/caseid"
        ])

    def test_finds_other_pdf_links(self):
        html = '<a href="/content/case.pdf">PDF</a>'
        self.assertEqual(find_pdf_links(html, CASE), [
            "https://putusan3.mahkamahagung.go.id/content/case.pdf"
        ])

    def test_not_pdf_when_no_attachment(self):
        self.assertEqual(find_pdf_links('<a href="/direktori">Directory</a>', CASE), [])


if __name__ == "__main__":
    unittest.main()
