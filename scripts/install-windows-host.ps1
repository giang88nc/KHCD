param([switch]$Elevated,[string]$TaskUser)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if (!$TaskUser) { $TaskUser=$identity.Name }
if (!([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if ($Elevated) { throw 'Administrator permission was not granted.' }
    $argsList=@('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$PSCommandPath+'"'),'-Elevated','-TaskUser',('"'+$TaskUser+'"'))
    $child=Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList $argsList -Wait -PassThru
    exit $child.ExitCode
}
$resultPath=Join-Path $projectRoot 'instance\windows-host-install.log'
try {
    $hostPath=Join-Path $PSScriptRoot 'host.ps1'
    $existing=Get-ScheduledTask -TaskName 'KHCD Web Host' -ErrorAction SilentlyContinue
    if ($existing -and !($existing.Actions.Arguments -like ('*'+$hostPath+'*'))) { throw 'A different task already uses the name KHCD Web Host.' }
    $action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$hostPath+'"') -WorkingDirectory $projectRoot
    $principal=New-ScheduledTaskPrincipal -UserId $TaskUser -LogonType Interactive -RunLevel Limited
    $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    # Manual start only; does not enable startup at Windows sign-in without a request.
    Register-ScheduledTask -TaskName 'KHCD Web Host' -Action $action -Principal $principal -Settings $settings -Description 'KHCD local web host; independent of the launching app. Start and stop through KHCD scripts.' -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $projectRoot 'instance\windows-host.enabled') -Value 'KHCD Web Host'
    Set-Content -LiteralPath $resultPath -Value 'OK: KHCD Web Host registered. Interactive user, limited privileges, no logon trigger.'
} catch {
    Set-Content -LiteralPath $resultPath -Value ('FAILED: '+$_.Exception.Message)
    exit 1
}
