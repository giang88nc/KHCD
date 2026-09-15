$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (Test-Path -LiteralPath (Join-Path $projectRoot 'instance\windows-host.enabled')) {
    Set-Content -LiteralPath (Join-Path $projectRoot 'instance\host.stop') -Value 'Stopped by operator'
    & schtasks.exe /End /TN 'KHCD Web Host' | Out-Null
}
$runPath = Join-Path $projectRoot 'run.py'
$caddyPath = Join-Path $projectRoot 'ops\caddy\caddy.exe'
$caddyConfig = Join-Path $projectRoot 'ops\caddy\Caddyfile'
$bridgeKey = Join-Path $projectRoot 'instance\customer-bridge.key'
# Exact checkout command paths also identify the venv's child Python process.
$owned = @(Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine.Contains($runPath)) -or
    ($_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine.Contains('D:\PYTHON\KHBL\manage.py') -and $_.CommandLine.Contains('run_customer_bridge') -and $_.CommandLine.Contains($bridgeKey)) -or
    ($_.ExecutablePath -eq $caddyPath -and $_.CommandLine -and $_.CommandLine.Contains($caddyConfig))
})
foreach ($process in $owned) {
    if (Get-Process -Id $process.ProcessId -ErrorAction SilentlyContinue) { Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue }
}
foreach ($name in @('server.pid','caddy.pid')) {
    $file = Join-Path $projectRoot ('instance\'+$name)
    if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file }
}
Write-Output 'Stopped KHCD only.'
