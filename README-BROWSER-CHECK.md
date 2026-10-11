# One-decision browser access test (for your local computer)

Direct HTTP from GitHub-hosted Ubuntu is currently blocked with 403 for both the Mahkamah Agung decision page and download endpoint. That does **not** establish what happens on a home, campus, or Indonesian network, using a normal visible browser.

This script opens **stock Chromium** visibly on your computer and checks only one selected official decision page. It looks for the PDF attachment in the rendered DOM and downloads a candidate using the same browser context's normal session cookies. It does **not** spoof a browser fingerprint, rotate proxies, evade anti-bot challenges, scrape at scale, or bypass 403.

## macOS/Linux (from repository root)

    git pull origin main
    .venv/bin/python -m pip install -r requirements-browser.txt
    .venv/bin/python -m playwright install chromium

    .venv/bin/python -m rulings.browser_probe --interactive \
      --url 'https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html'

## Windows PowerShell

    git pull origin main
    .\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
    .\.venv\Scripts\python.exe -m playwright install chromium

    .\.venv\Scripts\python.exe -m rulings.browser_probe --interactive --url 'https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html'

If this is a fresh clone, first install the dependencies via scripts/setup-archive.sh (macOS/Linux) or scripts/setup-archive.ps1 (Windows), as described in README-ARCHIVE.md.

The local diagnostic writes:
- archive/diagnostics/browser-diagnostic.json (page HTTP status, PDF-link count, download response and failure, without the case page body)
- archive/diagnostics/<SHA256>.pdf (only after checking that the body is an actual PDF)

If the page returns 403, the script **stops** and prints this status. If the page loads but the attachment fails, its separate status is recorded. No false PDF output is written.

**Important:** Even if one decision works, it does not establish nationwide feasibility. Next verify a random sample from multiple courts and years, measure missing PDFs, and obtain explicit permission for any bulk collection. MA disclosed large-scale PDF loss in April 2024; some listed cases might not have a retrievable document.

Official data route: https://eppid.mahkamahagung.go.id/web/standar-layanan/prosedur-permohonan-informasi . If the local browser test also returns 403, an institutional research request for bulk public decisions (metadata plus redacted PDFs) is more realistic than continued automated retries.

## Useful outcomes to report

- page_status=200, success=true: one real PDF retrievable with a browser session.
- page_status=200, success=false: listing works, PDF link or attachment delivery is the problem.
- page_status=403: direct automated access is denied on this network too.
- page_status=200 but no links: likely changed layout or missing file; inspect before assuming it is a universal failure.

This is a narrow diagnostic, not a production Playwright crawler.
