$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$stopPath=Join-Path $projectRoot 'instance\host.stop'
$logPath=Join-Path $projectRoot 'instance\host.log'
$startPath=Join-Path $PSScriptRoot 'start.ps1'
Set-Location -LiteralPath $projectRoot
function Write-HostLog($message) {
    if ((Test-Path -LiteralPath $logPath) -and (Get-Item -LiteralPath $logPath).Length -gt 1048576) {
        Move-Item -LiteralPath $logPath -Destination ($logPath+'.previous') -Force
    }
    Add-Content -LiteralPath $logPath -Value ((Get-Date -Format o)+' '+$message)
}
Write-HostLog 'Windows host started.'
while (!(Test-Path -LiteralPath $stopPath)) {
    $healthy=$false
    try {
        $response=Invoke-RestMethod 'https://localhost:8200/health' -TimeoutSec 3
        $healthy=$response.app -eq 'KHCD' -and $response.https -and $response.customer_service -eq 'ok'
    } catch { }
    if (!$healthy) {
        Write-HostLog 'HTTPS unavailable; ensuring KHCD processes are running.'
        try {
            $result=& $startPath -Direct 2>&1
            Write-HostLog ($result -join ' ')
        } catch { Write-HostLog $_.Exception.Message }
    }
    for ($i=0; $i -lt 15 -and !(Test-Path -LiteralPath $stopPath); $i++) { Start-Sleep -Seconds 1 }
}
Write-HostLog 'Windows host stopped by operator.'
