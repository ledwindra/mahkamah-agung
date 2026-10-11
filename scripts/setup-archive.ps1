$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .venv
} else {
    python -m venv .venv
}
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $python -m pip install -r requirements-archive.txt
if ($LASTEXITCODE -ne 0) { throw "dependency install failed" }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "unit tests failed" }
Write-Host "Setup finished. Example:"
Write-Host ".\.venv\Scripts\python.exe -m rulings.archive crawl --url https://putusan3.mahkamahagung.go.id/direktori/putusan/11f1acd8ace2d8248c03313233303033.html --download --text"
