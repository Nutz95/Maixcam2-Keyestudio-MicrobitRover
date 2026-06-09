# Lance le menu de test rover (venv + dependances + script Python)
# Usage:
#   .\run_test_rover.ps1
#   .\run_test_rover.ps1 -Port COM12 -Speed 80

param(
    [string]$Port,
    [int]$Speed = 100
)

$ErrorActionPreference = "Stop"
$ToolsDir = $PSScriptRoot
$RepoRoot = Split-Path -Parent $ToolsDir
$VenvDir = Join-Path $RepoRoot ".venv"
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
$Requirements = Join-Path $ToolsDir "requirements.txt"
$Script = Join-Path $ToolsDir "test_rover_menu.py"

if (-not (Test-Path $PythonExe)) {
    Write-Host "Creation de l'environnement virtuel dans $VenvDir ..."
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        & "$($pythonCmd.Source)" -m venv "$VenvDir"
    } else {
        & py -3 -m venv "$VenvDir"
    }
}

Write-Host "Installation des dependances ..."
& "$PipExe" install -q -r "$Requirements"

$argsList = @()
if ($Port) { $argsList += @("-p", $Port) }
if ($Speed -ne 100) { $argsList += @("-s", "$Speed") }

Write-Host "Lancement du menu de test ..."
Write-Host "Commande J (joystick) : deadzone firmware 12% (~3932). Valeurs faibles = ACK sans mouvement." -ForegroundColor Yellow
& "$PythonExe" "$Script" @argsList
