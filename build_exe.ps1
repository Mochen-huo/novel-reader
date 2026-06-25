$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Python = $env:PYTHON
if (-not $Python) {
    $Python = "python"
}

& $Python -m pip show pyinstaller | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller is not installed. Installing it first..."
    & $Python -m pip install pyinstaller
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "NovelReader" `
    --hidden-import "win32gui" `
    --hidden-import "win32con" `
    --hidden-import "win32process" `
    main.py

Write-Host "Build finished: $ProjectRoot\dist\NovelReader\NovelReader.exe"
