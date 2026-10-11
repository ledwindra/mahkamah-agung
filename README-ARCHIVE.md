# Decision PDF archive (local-first, experimental)

This adds a second workflow to the historical Mahkamah Agung scraping repository. The original 2021 aggregations and metadata scraper are **not replaced**. The new command line tool downloads original decision PDFs, extracts text where possible, and records the result in a resumable local SQLite index.

**Important status (10 October 2026):** case listings and PDF attachment labels have been observed in search indexes, and the official site uses download endpoints under /direktori/download_file/. A real PDF download has **not** been verified from the authoring environment: access to putusan3.mahkamahagung.go.id was blocked there. The included offline tests verify the code's behavior against fixtures, not site availability or end-to-end live access.

## Quick start: macOS / Linux

Requires git and Python 3.10 or newer.

    git clone --branch feature/decision-pdf-archive https://github.com/ledwindra/mahkamah-agung.git
    cd mahkamah-agung
    bash scripts/setup-archive.sh

The setup script creates .venv, installs only the archive dependencies, and runs the offline unit tests.

Test one published decision (metadata, PDF bytes, and extracted text):

    .venv/bin/python -m rulings.archive crawl \
      --url https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html \
      --download --text

If successful, inspect archive/index.sqlite3, archive/pdf/ and archive/text/. A valid downloaded file starts with %PDF-; an HTML 403 page is never accepted as a PDF.

## Quick start: Windows PowerShell

Requires git and Python 3.10+ (py launcher or python executable).

    git clone --branch feature/decision-pdf-archive https://github.com/ledwindra/mahkamah-agung.git
    cd mahkamah-agung
    .\scripts\setup-archive.ps1

If local PowerShell script-execution policy blocks the script, manually create the venv and run the three setup commands rather than changing machine-wide policy:

    py -3 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements-archive.txt
    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Then download and process a decision:

    .\.venv\Scripts\python.exe -m rulings.archive crawl --url https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html --download --text

## Crawl and resume

Use a **small, explicit sample first**. The command below walks two listing pages, processing at most ten distinct decision pages:

    .venv/bin/python -m rulings.archive crawl --start-page 1 --pages 2 --max-cases 10 --download --text

Resume or expand by running the same command with more pages or a different start page. Completed cases are skipped automatically. The default only indexes case metadata and attachment URLs; add --download to fetch PDFs and --text for text extraction (which also enables downloading). Use --force to revisit a stale page or re-fetch an already completed case. The minimum per-request delay defaults to 3 seconds.

For focused batches, put complete decision URLs in a text file (one per line):

    .venv/bin/python -m rulings.archive crawl --input urls.txt --download --text

A custom official listing URL pattern can be supplied with --listing-template; it must contain the literal {page} token and stay on the official host. This can support a particular classification or year *if the website actually exposes compatible page routes*. Do not assume any filter endpoint exists without checking it.

    .venv/bin/python -m rulings.archive stats
    .venv/bin/python -m rulings.archive export --file archive/decisions.jsonl

Use --output PATH on crawl/stats/export to choose another storage directory (prefer a drive with available space). For export choose a separate --file path if needed.

## File structure

- archive/index.sqlite3: primary key = official decision page URL; metadata JSON, case number, PDF URL, local paths, hash, pages, text length, status, last error, updated timestamp.
- archive/pdf/<stable-url-hash>.pdf: raw PDF bytes validated by PDF signature.
- archive/text/<stable-url-hash>.txt: extractable PDF text with page boundaries.
- archive/decisions.jsonl: optional newline-delimited export with all metadata and links.

The local archive directory is excluded from git; do not commit downloaded PDFs, potentially sensitive litigant information, or a giant SQLite database to a public repository. Back up archive/ separately.

Statuses: metadata_only, no_pdf, pdf_saved, text_extracted, scanned_pdf, error. A scanned_pdf means pypdf found zero substantive text; OCR is **not** automatically applied (OCR would need a separate, carefully validated pipeline). Some online records do not provide a working PDF link.

## Access limitations and responsible operation

- HTTP 401, 403, or 429 **stops the crawler**. It does not rotate identities, circumvent restrictions, or claim that a forbidden file is available.
- The code is low-rate and resumable; the delay cannot be set lower than one second.
- File size limits, timeouts, and bounded retries protect local resources. Use --max-mb, --timeout, or --retries as required.
- If you receive 403, first test the case page in a normal browser and check official portal terms and robots guidance. Contact the operator or use an approved bulk data route rather than assuming the server is merely weak.
- Publication is not proof that every judgment is public or that redistribution is unrestricted. Handle personal information appropriately.

## Research scale and known caveats

The legacy dataset contains 2021 snapshots of category counts and case metadata. It is *not* a complete current PDF archive, and its records do not automatically map to known PDF download URLs.

A full national archive can involve millions of decisions and very large storage/transfer costs. This tool is a verified **offline implementation** with a local smoke-test pathway, not a verified mass downloader. Before any broad collection, verify at least one live decision PDF, confirm the site permits collection, sample missing-document rates, audit duplicate rulings and changes to the HTML, and plan storage/backup and court/period partitioning.

## Development

    .venv/bin/python -m unittest discover -s tests -v

All unit tests use constructed HTML and generated PDF bytes: they do not hit the court website. The original scraper can still be used as documented in the root README; its dependencies remain in requirements.txt.

If you see a redirect or changed attachment layout, collect a sanitized HTML sample and add a regression fixture before changing the parser.
