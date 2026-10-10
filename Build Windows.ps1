$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    python -m PyInstaller --clean --noconfirm --noupx --onefile --windowed --name 'Azurik Freecam Patcher' --icon 'assets/studio.ico' --add-data 'assets/studio.ico:assets' --version-file 'assets/windows-version.txt' patcher.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
} finally {
    Pop-Location
}
