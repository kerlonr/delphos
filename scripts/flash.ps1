# Grava o firmware no Delphos (Pro Micro / Caterina).
# Uso: .\scripts\flash.ps1 [-Hex caminho.hex]
# Pede o bootloader pelo comando 0x43 do Delphos. Firmware antigo não tem esse comando:
# nesse caso aperte o reset do Pro Micro ou plugue segurando a tecla (0,0) (bootmagic).
param([string]$Hex = (Join-Path (Split-Path $PSScriptRoot -Parent) 'delphos_3x4_default.hex'))
$ErrorActionPreference = 'Continue'  # PS 5.1 trata stderr de exe como erro; checamos $LASTEXITCODE
$Hex = (Resolve-Path $Hex -ErrorAction Stop).Path
$py = Join-Path (Split-Path $PSScriptRoot -Parent) 'app\.venv\Scripts\python.exe'

# O app segura a conexão com o teclado; fecha antes de gravar.
Get-Process Delphos -ErrorAction SilentlyContinue | Stop-Process -Force

# D:\a\b.hex -> /d/a/b.hex (caminho do MSYS)
$hexUnix = '/' + $Hex.Substring(0, 1).ToLower() + ($Hex.Substring(2) -replace '\\', '/')

# qmk flash fica esperando o bootloader aparecer; dispara ele em paralelo.
$job = Start-Job {
    param($h)
    $env:MSYSTEM = 'MINGW64'; $env:CHERE_INVOKING = '1'
    & C:\QMK_MSYS\usr\bin\bash.exe -lc "qmk flash '$h'" 2>&1
    "QMK_EXIT=$LASTEXITCODE"
} -ArgumentList $hexUnix
Start-Sleep -Seconds 3
if (Test-Path $py) { & $py (Join-Path $PSScriptRoot 'bootloader.py') }
Write-Host 'Aguardando gravacao (ate 5 min)...'
Wait-Job $job -Timeout 300 | Out-Null
$out = Receive-Job $job
$out | Select-Object -Last 15
if ($job.State -ne 'Completed') { Stop-Job $job; throw 'timeout esperando o bootloader' }
if (-not ($out -match 'QMK_EXIT=0')) { throw 'qmk flash falhou' }
