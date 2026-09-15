param([switch]$Direct)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$taskMarker = Join-Path $projectRoot 'instance\windows-host.enabled'
if (!$Direct -and (Test-Path -LiteralPath $taskMarker)) {
    Remove-Item -LiteralPath (Join-Path $projectRoot 'instance\host.stop') -ErrorAction SilentlyContinue
    & schtasks.exe /Run /TN 'KHCD Web Host' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot start KHCD Web Host in Windows Task Scheduler.' }
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $health=Invoke-RestMethod 'https://localhost:8200/health' -TimeoutSec 2
            if ($health.app -eq 'KHCD' -and $health.https -and $health.customer_service -eq 'ok') { Write-Output 'KHCD Windows host: https://localhost:8200 | https://tiemvangkimhanh2:8200'; return }
        } catch { }
    }
    throw 'KHCD Windows host is not ready. See instance/host.log.'
}
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runPath = Join-Path $projectRoot 'run.py'
$caddyPath = Join-Path $projectRoot 'ops\caddy\caddy.exe'
$caddyConfig = Join-Path $projectRoot 'ops\caddy\Caddyfile'
function Get-Listener($port) { @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) }
function Test-OwnedListener($listeners, $kind) {
    foreach ($processId in ($listeners.OwningProcess | Select-Object -Unique)) {
        $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
        if ($kind -eq 'backend') {
            if (!$owner.CommandLine -or !$owner.CommandLine.Contains($runPath) -or $owner.Name -ne 'python.exe') { return $false }
        } else {
            if ($owner.ExecutablePath -ne $caddyPath -or !$owner.CommandLine.Contains($caddyConfig)) { return $false }
        }
    }
    return $true
}
$backend = @(Get-Listener 8201)
$front = @(Get-Listener 8200)
if ($backend.Count -gt 0 -and !(Test-OwnedListener $backend 'backend')) { throw 'Port 8201 belongs to another application; no process was changed.' }
if ($front.Count -gt 0 -and !(Test-OwnedListener $front 'caddy')) { throw 'Port 8200 belongs to another application/old HTTP server. Stop KHCD first.' }
if (!(Test-Path -LiteralPath $caddyPath)) { throw 'Missing ops/caddy/caddy.exe.' }
if (!(Test-Path -LiteralPath (Join-Path $projectRoot 'instance\caddy-data\pki\authorities\local\root.key'))) { throw 'Shared LAN CA is not configured.' }
Remove-Item Env:\KHCD_ENV_FILE -ErrorAction SilentlyContinue
$bridgeManage = 'D:\PYTHON\KHBL\manage.py'
$bridgeKey = Join-Path $projectRoot 'instance\customer-bridge.key'
$bridge = @(Get-Listener 18202)
foreach ($processId in ($bridge.OwningProcess | Select-Object -Unique)) {
    $owner=Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
    if (!$owner.CommandLine -or !$owner.CommandLine.Contains($bridgeManage) -or !$owner.CommandLine.Contains('run_customer_bridge') -or !$owner.CommandLine.Contains($bridgeKey)) { throw 'Port 18202 belongs to another process.' }
}
if ($bridge.Count -eq 0) {
    if (!(Test-Path -LiteralPath $bridgeKey)) { throw 'Missing private customer bridge key.' }
    Start-Process -FilePath 'D:\PYTHON\KHBL\venv\Scripts\python.exe' -ArgumentList '-X','utf8',('"'+$bridgeManage+'"'),'run_customer_bridge','--key-file',('"'+$bridgeKey+'"') -WorkingDirectory 'D:\PYTHON\KHBL' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'instance\bridge-out.log') -RedirectStandardError (Join-Path $projectRoot 'instance\bridge-error.log')
}
if ($backend.Count -eq 0) {
    $process = Start-Process -FilePath $pythonPath -ArgumentList '-X','utf8',('"' + $runPath + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'instance\server-out.log') -RedirectStandardError (Join-Path $projectRoot 'instance\server-error.log') -PassThru
    Set-Content -LiteralPath (Join-Path $projectRoot 'instance\server.pid') -Value $process.Id
}
if ($front.Count -eq 0) {
    $proxy = Start-Process -FilePath $caddyPath -ArgumentList 'run','--config',('"' + $caddyConfig + '"'),'--adapter','caddyfile' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $projectRoot 'instance\caddy-out.log') -RedirectStandardError (Join-Path $projectRoot 'instance\caddy-error.log') -PassThru
    Set-Content -LiteralPath (Join-Path $projectRoot 'instance\caddy.pid') -Value $proxy.Id
}
for ($attempt = 0; $attempt -lt 12; $attempt++) {
    Start-Sleep -Milliseconds 400
    try {
        $health = Invoke-RestMethod -Uri 'https://localhost:8200/health' -TimeoutSec 2
        if ($health.app -eq 'KHCD' -and $health.https -and $health.customer_service -eq 'ok') { Write-Output 'KHCD: https://tiemvangkimhanh2:8200 | https://localhost:8200'; return }
    } catch { }
}
throw 'KHCD HTTPS is not ready. Check instance/server-error.log and instance/caddy-error.log.'
