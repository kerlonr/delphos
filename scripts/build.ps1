# Compila o firmware do Delphos com o QMK MSYS.
# Uso: .\scripts\build.ps1            (gera delphos_3x4_default.hex na raiz do repo)
$ErrorActionPreference = 'Continue'  # PS 5.1 trata stderr de exe como erro; checamos $LASTEXITCODE
$repo = Split-Path $PSScriptRoot -Parent
$qmkHome = if ($env:QMK_HOME) { $env:QMK_HOME } else { "$env:USERPROFILE\qmk_firmware" }
$link = Join-Path $qmkHome 'keyboards\delphos_3x4'

if (-not (Test-Path 'C:\QMK_MSYS\usr\bin\bash.exe')) { throw 'QMK MSYS nao encontrado em C:\QMK_MSYS' }
if (-not (Test-Path $qmkHome)) { throw "qmk_firmware nao encontrado em $qmkHome (rode 'qmk setup')" }

# O QMK so enxerga teclados dentro de qmk_firmware/keyboards: liga a pasta do repo la (junction, sem copiar).
if (Test-Path $link) {
    $item = Get-Item $link -Force
    if ($item.LinkType -ne 'Junction' -or $item.Target -ne $repo) { throw "$link ja existe e nao aponta para $repo" }
} else {
    New-Item -ItemType Junction -Path $link -Target $repo | Out-Null
}

# SKIP_VERSION fixa a data do build. O VIA usa essa data para validar a EEPROM: com ela mudando,
# toda atualização de firmware apagava o mapa de teclas e as macros do usuário.
# Se um dia mudar o formato da EEPROM (número de camadas, tamanho das macros), use "Restaurar teclas padrão".
$env:MSYSTEM = 'MINGW64'; $env:CHERE_INVOKING = '1'
Push-Location $repo
try {
    & C:\QMK_MSYS\usr\bin\bash.exe -lc "cd '$($qmkHome -replace '\\','/')' && qmk compile -kb delphos_3x4 -km default -e SKIP_VERSION=yes"
    if ($LASTEXITCODE -ne 0) { throw "qmk compile falhou ($LASTEXITCODE)" }
    Copy-Item (Join-Path $qmkHome 'delphos_3x4_default.hex') $repo -Force
    Write-Host "OK: $repo\delphos_3x4_default.hex"
} finally { Pop-Location }
