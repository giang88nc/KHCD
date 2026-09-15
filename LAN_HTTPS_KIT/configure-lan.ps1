param([switch]$Server, [switch]$Elevated)
$ErrorActionPreference = 'Stop'
$ServerIp = '192.168.1.6'
$Domain = 'tiemvangkimhanh2'
$ExpectedThumbprint = '9D56B37905DB737F3365703B0087EC233AA52D12'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$admin = ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (!$admin) {
    if ($Elevated) { throw 'Windows Administrator permission was not granted.' }
    $arguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$PSCommandPath+'"'),'-Elevated')
    if ($Server) { $arguments += '-Server' }
    $process = Start-Process -FilePath 'powershell.exe' -Verb RunAs -WindowStyle Hidden -ArgumentList $arguments -Wait -PassThru
    exit $process.ExitCode
}
$logPath = Join-Path $PSScriptRoot 'install-result.txt'
try {
    # Only the already-used KHBL public CA is distributed. Never download an unverified CA.
    $certPath = Join-Path $PSScriptRoot 'kimhanh-lan-root-ca.crt'
    $certificate = New-Object Security.Cryptography.X509Certificates.X509Certificate2($certPath)
    if ($certificate.Thumbprint -ne $ExpectedThumbprint) { throw 'LAN CA certificate does not match the verified Kim Hanh 2 CA.' }
    $hostsPath = Join-Path $env:SystemRoot 'System32\drivers\etc\hosts'
    $original = [IO.File]::ReadAllText($hostsPath)
    $updated = New-Object 'System.Collections.Generic.List[string]'
    foreach ($line in ($original -split '\r?\n')) {
        $entry = ($line -split '#',2)[0].Trim()
        $parts = @($entry -split '\s+')
        if ($parts.Length -ge 2 -and $parts[0] -notmatch '^#' -and $parts[1..($parts.Length-1)] -contains $Domain) {
            $otherNames = @($parts[1..($parts.Length-1)] | Where-Object { $_ -ne $Domain })
            if ($otherNames.Count -gt 0) { $updated.Add($parts[0]+"`t"+($otherNames -join ' ')) }
        } else { $updated.Add($line) }
    }
    $updated.Add($ServerIp+"`t"+$Domain+' # Kim Hanh 2 LAN')
    $backup = Join-Path $PSScriptRoot ('hosts-before-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.bak')
    [IO.File]::WriteAllText($backup,$original,[Text.Encoding]::UTF8)
    [IO.File]::WriteAllText($hostsPath,($updated -join "`r`n"),[Text.Encoding]::ASCII)
    Clear-DnsClientCache
    if (!(Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $ExpectedThumbprint)) {
        Import-Certificate -FilePath $certPath -CertStoreLocation 'Cert:\LocalMachine\Root' | Out-Null
    }
    if ($Server) {
        $ruleName='KHCD-HTTPS-8200-LAN'
        $existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
        if (!$existing) {
            New-NetFirewallRule -Name $ruleName -DisplayName 'KHCD HTTPS 8200 - LAN only' -Direction Inbound -Action Allow -Enabled True -Profile Any -Protocol TCP -LocalPort 8200 -RemoteAddress LocalSubnet | Out-Null
        } else {
            Set-NetFirewallRule -Name $ruleName -Direction Inbound -Action Allow -Enabled True -Profile Any | Out-Null
            $existing | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort 8200 | Out-Null
            $existing | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress LocalSubnet | Out-Null
        }
    }
    $response=Invoke-WebRequest -Uri ('https://'+$Domain+':8200/health') -UseBasicParsing -TimeoutSec 15
    if (($response.Content | ConvertFrom-Json).app -ne 'KHCD') { throw 'Unexpected application at HTTPS :8200.' }
    @("OK: https://tiemvangkimhanh2:8200","Name: $Domain -> $ServerIp",("CA: "+$ExpectedThumbprint),"Server firewall configured: $Server",("Hosts backup: "+$backup)) | Set-Content -LiteralPath $logPath -Encoding UTF8
} catch {
    ('FAILED: '+$_.Exception.Message) | Set-Content -LiteralPath $logPath -Encoding UTF8
    exit 1
}
