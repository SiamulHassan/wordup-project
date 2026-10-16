$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".venv\Scripts\python.exe" -m pytest
& ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean WordUpVocabularyImporter.spec

Write-Host "Built: $projectRoot\dist\WordUpVocabularyImporter.exe"
