param(
  [Parameter(Mandatory = $true)][string]$PanelUrl,
  [Parameter(Mandatory = $true)][string]$AgentId,
  [Parameter(Mandatory = $true)][string]$NodeId,
  [string]$Token = ""
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$AgentDir = Join-Path $RootDir "agent"
$VenvDir = Join-Path $AgentDir ".venv"

python -m venv $VenvDir
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $AgentDir "requirements.txt")

$envContent = @"
SENTRA_PANEL_URL=$PanelUrl
SENTRA_AGENT_ID=$AgentId
SENTRA_NODE_ID=$NodeId
SENTRA_AGENT_TOKEN=$Token
SENTRA_AGENT_DRY_RUN=true
SENTRA_AGENT_INTERVAL=3
"@

Set-Content -Path (Join-Path $AgentDir ".env") -Value $envContent -Encoding UTF8

Write-Host "Probe installed. Start with:"
Write-Host "`$env:SENTRA_PANEL_URL='$PanelUrl'; `$env:SENTRA_AGENT_ID='$AgentId'; `$env:SENTRA_NODE_ID='$NodeId'; & '$PythonExe' '$AgentDir\probe_agent.py'"
