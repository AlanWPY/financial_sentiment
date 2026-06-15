$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = $ScriptDir
$Url = "http://127.0.0.1:5000/#dashboard"
$HealthUrl = "http://127.0.0.1:5000/api/stats"

function Test-AppReady {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $HealthUrl -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
    }
    catch {
        return $false
    }
}

function Get-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @{ Path = $python.Source; Args = @("run.py") }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @{ Path = $py.Source; Args = @("-3", "run.py") }
    }

    return $null
}

Write-Host "Financial Sentiment Analysis System launcher"
Write-Host "Project: $ProjectDir"

if (-not (Test-AppReady)) {
    $python = Get-PythonCommand
    if (-not $python) {
        Write-Host "Python was not found. Please install Python or add it to PATH." -ForegroundColor Red
        exit 1
    }

    $projectLiteral = $ProjectDir.Replace("'", "''")
    $pythonLiteral = $python.Path.Replace("'", "''")
    $argText = ($python.Args | ForEach-Object { "'" + $_.Replace("'", "''") + "'" }) -join " "
    $serverCommand = "Set-Location -LiteralPath '$projectLiteral'; & '$pythonLiteral' $argText"

    Write-Host "Starting backend server..."
    Start-Process powershell.exe -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $serverCommand
    ) -WindowStyle Normal

    Write-Host "Waiting for http://127.0.0.1:5000 ..."
    for ($i = 1; $i -le 90; $i++) {
        Start-Sleep -Seconds 1
        if (Test-AppReady) {
            Write-Host "Backend is ready."
            Start-Process $Url
            exit 0
        }
    }

    Write-Host "The backend did not become ready within 90 seconds." -ForegroundColor Yellow
    Write-Host "A server window has been opened. Please check it for MySQL/Python errors."
    exit 1
}

Write-Host "Backend is already running."
Start-Process $Url
exit 0
