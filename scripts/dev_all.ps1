$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$Py = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvDir)) {
  Write-Host "[backend] creating venv"
  python -m venv $VenvDir
}

Write-Host "[backend] installing requirements"
& $Py -m pip install -r (Join-Path $BackendDir "requirements.txt")

$env:FLASK_DEBUG = "1"
Write-Host "[backend] http://localhost:5000"
$BackendProc = Start-Process -PassThru -WorkingDirectory $BackendDir -FilePath $Py -ArgumentList @(
  "-m", "flask",
  "--app", "app.main",
  "run",
  "--port", "5000"
) -NoNewWindow

try {
  if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "[frontend] npm install"
    Push-Location $FrontendDir
    npm install
    Pop-Location
  }

  Write-Host "[frontend] http://localhost:5173"
  Push-Location $FrontendDir
  npm run dev
  Pop-Location
} finally {
  if ($BackendProc -and -not $BackendProc.HasExited) {
    Stop-Process -Id $BackendProc.Id -Force
  }
}
