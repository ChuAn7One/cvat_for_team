$ErrorActionPreference = 'Stop'
$ruleName = 'CVAT-LAN-8080-WLAN'
try {
    $rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    if ($rule) {
        Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound -Action Allow -Profile Any
    } else {
        New-NetFirewallRule -Name $ruleName -DisplayName 'CVAT LAN 8080 (WLAN local subnet)' `
            -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080 `
            -Profile Any -InterfaceAlias WLAN -RemoteAddress LocalSubnet | Out-Null
    }
    'OK: WLAN local subnet can access TCP 8080.' | Set-Content (Join-Path $PSScriptRoot 'firewall-status.log')
} catch {
    $_.Exception.Message | Set-Content (Join-Path $PSScriptRoot 'firewall-status.log')
    throw
}
