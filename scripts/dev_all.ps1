$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$Py = Join-Path $VenvDir "Scripts\python.exe"

function Stop-ProcessesOnPort {
  param([int]$Port)

  try {
    $pids = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
      Select-Object -ExpandProperty OwningProcess -Unique
  } catch {
    $pids = @()
  }

  foreach ($pid in $pids) {
    if ($pid -and $pid -ne 0) {
      try {
        Write-Host "Stopping process $pid on port $Port"
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
      } catch {
      }
    }
  }
}

function Wait-ForBackend {
  param([int]$Seconds = 15)

  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $rt = Invoke-RestMethod -Uri "http://localhost:5000/api/realtime" -TimeoutSec 2
      if ($rt -and $null -ne $rt.enabled) {
        return $true
      }
    } catch {
    }
    Start-Sleep -Milliseconds 250
  }
  return $false
}

if (-not (Test-Path $VenvDir)) {
  Write-Host "[backend] creating venv"
  python -m venv $VenvDir
}

Write-Host "[backend] installing requirements"
& $Py -m pip install -r (Join-Path $BackendDir "requirements.txt")

Stop-ProcessesOnPort -Port 5000

$env:FLASK_DEBUG = "1"
Write-Host "[backend] http://localhost:5000"
$BackendProc = Start-Process -PassThru -WorkingDirectory $BackendDir -FilePath $Py -ArgumentList @(
  "-m", "flask",
  "--app", "app.main",
  "run",
  "--port", "5000"
) -NoNewWindow

if (-not (Wait-ForBackend -Seconds 20)) {
  Write-Host "ERROR: backend did not start or /api/realtime is not reachable."
  if ($BackendProc -and -not $BackendProc.HasExited) {
    Stop-Process -Id $BackendProc.Id -Force
  }
  exit 1
}

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
