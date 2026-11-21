# Gera app\dist\Delphos.exe (um arquivo, sem console). Roda os testes antes.
# Embute: interface (delphos\ui), avrdude e o firmware compilado (delphos_3x4_default.hex).
$ErrorActionPreference = 'Continue'  # PS 5.1 trata stderr de exe como erro; checamos $LASTEXITCODE
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) {
    py -3.12 -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
}

# Ferramentas embutidas: avrdude do QMK MSYS + firmware do repo.
New-Item -ItemType Directory -Force tools | Out-Null
foreach ($f in 'avrdude.exe', 'avrdude.conf') {
    if (-not (Test-Path "tools\$f")) { Copy-Item "C:\QMK_MSYS\opt\qmk\bin\$f" tools -ErrorAction Stop }
}
$hex = Join-Path (Split-Path $PSScriptRoot -Parent) 'delphos_3x4_default.hex'
if (-not (Test-Path $hex)) { throw 'firmware nao compilado: rode ..\scripts\build.ps1' }
Copy-Item $hex tools\delphos.hex -Force

.venv\Scripts\python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'testes falharam' }
.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --noconsole --name Delphos `
    --add-data "delphos\ui;delphos\ui" --add-data "tools;tools" --add-data "assets;assets" `
    --icon assets\delphos.ico `
    --hidden-import pystray._win32 main.py
if ($LASTEXITCODE -ne 0) { throw 'pyinstaller falhou' }
Write-Host "OK: $PSScriptRoot\dist\Delphos.exe"
