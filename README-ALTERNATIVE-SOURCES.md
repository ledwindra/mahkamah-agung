# Alternative court-decision sources (when putusan3 returns 403)

The national Mahkamah Agung decision portal currently returns HTTP 403 for HTTP clients on our GitHub-hosted Linux tests (October 2026). The separate JDIH Mahkamah Agung domain also returned 403 on the same runner, even though a PDF was indexed and could be opened by a web-index tool. This is *not* evidence that a user on a residential/Indonesian connection will receive the same response.

**Do not mistake the following research subsets for a complete national archive.** These independent sources let you build, test and analyze an archive locally while establishing approved access to the national source.

## A. Already archived, original PDF decisions (831 available files)

The publicly readable [xrenxf dataset](https://github.com/xrenxf/Dataset-Kasasi-Perdata-Kasus-Perbuatan-Melawan-Hukum-Tahun-2023-2024) has 831 PDF files in "Putusan Pengadilan", narrowly covering 2023–2024 civil cassation cases concerning unlawful acts (perbuatan melawan hukum).

Make a **separate** local checkout, then import the PDFs:

    git clone --depth 1 https://github.com/xrenxf/Dataset-Kasasi-Perdata-Kasus-Perbuatan-Melawan-Hukum-Tahun-2023-2024.git ../ma-civil-pdf
    .venv/bin/python -m rulings.import_corpus '../ma-civil-pdf/Putusan Pengadilan' \
      --output archive --source 'xrenxf/PMH-2023-2024' --text --limit 10

For the complete 831-file subset, replace --limit 10 with --limit 0.

The importer validates PDF signatures, copies files under archive/pdf/, creates text under archive/text/, computes checksums, and stores provenance in archive/index.sqlite3. Scan-only or image-only PDFs are tagged scanned_pdf: no OCR is fabricated. These records use the stable ID local-pdf:<sha256> because the original case URL is not guaranteed by PDF filenames.

**Note:** The external GitHub repository does not visibly declare an open-data license. Respect the rights and restrictions of the publisher; do not republish someone else's documents or the imported archive without checking permissions.

## B. Independently released legal-text collection (22,630 XML records)

[ir-nlp-csui/indo-law](https://github.com/ir-nlp-csui/indo-law) includes 22,630 XML files of extracted and annotated court decisions, with original official case URLs, legal labels and sections.

    git clone --depth 1 https://github.com/ir-nlp-csui/indo-law.git ../indo-law
    .venv/bin/python -m rulings.import_corpus '../indo-law/dataset' \
      --output archive --source 'ir-nlp-csui/indo-law' --limit 10

For the whole XML corpus:

    .venv/bin/python -m rulings.import_corpus '../indo-law/dataset' \
      --output archive --source 'ir-nlp-csui/indo-law' --limit 0

XML records are stored with status text_imported and their exact original official decision URL as a database key, if available. Each decision's annotated sections are saved under archive/text/indolaw/.

This is **extracted text**, not original PDF bytes; it is useful for natural-language research, classifications and record linkage. Cite the dataset's authors and inspect its license before reusing it.

## C. JDIH Mahkamah Agung — a partial public catalog

- Official indexed list: https://jdih.mahkamahagung.go.id/dokumen?jenis=putusan
- One 82-page original decision was retrievable via a separate indexing path: https://jdih.mahkamahagung.go.id/download-file-satker/putusan
- The JDIH listing has hundreds of pages (seen as 465 at testing), but individual record pages often link to PDF files on the **blocked** putusan3 host. No automatic collection from JDIH is claimed to be reliable. The unparameterized download-file-satker/putusan URL displayed the **same particular decision**, not an arbitrary PDF chosen by case number.

## D. National direct retrieval

For a public 2026 decision in a local browser:

    https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html

Test the original archival CLI with a single record first:

    .venv/bin/python -m rulings.archive crawl --url \
      'https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html' \
      --download --text

A 403 is a blocker, not proof that extraction succeeded. On such a response, the archiver stops instead of storing an HTML error. When the operator permits data access, use a standard low-rate collection process and consider requesting official research/bulk access.

## Auditing the combined archive

    .venv/bin/python -m rulings.archive stats
    .venv/bin/python -m rulings.archive export --file archive/decisions.jsonl

Key distinctions:

- text_extracted: real PDF is saved and nonempty text extracted.
- scanned_pdf: real PDF is saved but extracted text is blank (OCR needed).
- text_imported: text is from XML/secondary source, **not** a verified PDF.
- pdf_saved: real PDF saved but no text-extraction operation performed.
- error/no_pdf: no confirmed PDF content.

No single available source covers every Indonesian judicial decision. Keep source provenance and measure selection bias before empirical research.
