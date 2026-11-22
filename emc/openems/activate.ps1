$ErrorActionPreference = 'Stop'

$openEmsRoot = Join-Path $env:LOCALAPPDATA 'openEMS\0.37.0'
$venvActivate = Join-Path $openEmsRoot 'venv\Scripts\Activate.ps1'

if (-not (Test-Path -LiteralPath (Join-Path $openEmsRoot 'openEMS.exe'))) {
    throw "openEMS executable not found at $openEmsRoot"
}

if (-not (Test-Path -LiteralPath $venvActivate)) {
    throw "openEMS Python environment not found at $venvActivate"
}

$env:CSXCAD_INSTALL_PATH = $openEmsRoot
$env:PATH = "$openEmsRoot;$env:PATH"
. $venvActivate
