[CmdletBinding()]
param(
    [switch]$NoOpen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$BackendProcess = $null
$FrontendProcess = $null
$ExitCode = 0

function Write-StartLog {
    param([string]$Message)
    Write-Host "[start] $Message"
}

function Assert-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing command '$Name'. Install it and try again."
    }
}

function Assert-PortAvailable {
    param([int]$Port)
    $Listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    if ($Listeners.Port -contains $Port) {
        throw "Port $Port is already in use."
    }
}

function Stop-ProcessTree {
    param($Process)
    if ($null -eq $Process) {
        return
    }

    try {
        if (-not $Process.HasExited) {
            & taskkill.exe /PID $Process.Id /T /F 2>&1 | Out-Null
        }
    }
    catch {
        Write-Warning "Could not stop process $($Process.Id): $($_.Exception.Message)"
    }
}

function Wait-ForUrl {
    param(
        [string]$Name,
        [string]$Url,
        [System.Diagnostics.Process]$Process
    )

    for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 1 | Out-Null
            Write-StartLog "$Name is ready."
            return
        }
        catch {
            if ($Process.HasExited) {
                throw "$Name failed to start. Check the logs above."
            }
            Start-Sleep -Seconds 1
        }
    }

    throw "$Name was not ready within 30 seconds."
}

try {
    Assert-Command "node.exe"
    Assert-Command "npm.cmd"
    Assert-Command "taskkill.exe"
    Assert-PortAvailable 8000
    Assert-PortAvailable 5173

    $PythonCommand = $null
    $PythonArguments = @()
    if (Get-Command "py.exe" -ErrorAction SilentlyContinue) {
        $PythonCommand = (Get-Command "py.exe").Source
        $PythonArguments = @("-3")
    }
    elseif (Get-Command "python.exe" -ErrorAction SilentlyContinue) {
        $PythonCommand = (Get-Command "python.exe").Source
    }
    else {
        throw "Python 3.11 or newer is required."
    }

    & $PythonCommand @PythonArguments -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11 or newer is required."
    }

    if (-not (Test-Path $VenvPython)) {
        Write-StartLog "Creating the Python virtual environment..."
        & $PythonCommand @PythonArguments -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the Python virtual environment."
        }
    }

    & $VenvPython -c "import aiosqlite, fastapi, sqlalchemy, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-StartLog "Installing backend dependencies..."
        Push-Location $BackendDir
        try {
            & $VenvPython -m pip install -r requirements-dev.txt
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install backend dependencies."
            }
        }
        finally {
            Pop-Location
        }
    }

    $ViteCommand = Join-Path $FrontendDir "node_modules\.bin\vite.cmd"
    if (-not (Test-Path $ViteCommand)) {
        Write-StartLog "Installing frontend dependencies..."
        & npm.cmd ci --prefix $FrontendDir
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install frontend dependencies."
        }
    }

    Write-StartLog "Starting backend: http://localhost:8000"
    $BackendProcess = Start-Process `
        -FilePath $VenvPython `
        -ArgumentList "run_dev.py" `
        -WorkingDirectory $BackendDir `
        -NoNewWindow `
        -PassThru

    Write-StartLog "Starting frontend: http://localhost:5173"
    $FrontendProcess = Start-Process `
        -FilePath "npm.cmd" `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory $FrontendDir `
        -NoNewWindow `
        -PassThru

    Wait-ForUrl "Backend" "http://localhost:8000/api/health" $BackendProcess
    Wait-ForUrl "Frontend" "http://localhost:5173" $FrontendProcess

    Write-Host ""
    Write-Host "AI Tool Site is running: http://localhost:5173"
    Write-Host "Press Ctrl+C to stop both services."
    Write-Host ""

    if (-not $NoOpen) {
        Start-Process "http://localhost:5173"
    }

    while (-not $BackendProcess.HasExited -and -not $FrontendProcess.HasExited) {
        Start-Sleep -Seconds 1
    }

    throw "A service exited unexpectedly. Check the logs above."
}
catch {
    $ExitCode = 1
    Write-Host "[start] ERROR: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if ($null -ne $BackendProcess -or $null -ne $FrontendProcess) {
        Write-StartLog "Stopping services..."
    }
    Stop-ProcessTree $FrontendProcess
    Stop-ProcessTree $BackendProcess
    Write-StartLog "Services stopped."
}

exit $ExitCode
