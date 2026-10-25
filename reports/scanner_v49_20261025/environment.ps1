$ErrorActionPreference = 'Stop'
$ntpEnvironment = [ordered]@{}
$ntpEnvironment.at = (Get-Date).ToString('o')
$ntpEnvironment.service = Get-Service W32Time | Select-Object Name,@{Name='State';Expression={$_.Status.ToString()}},@{Name='StartMode';Expression={$_.StartType.ToString()}}
$ntpEnvironment.timezone = Get-TimeZone | Select-Object Id
$ntpEnvironment.scanners = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name)
try { $ntpEnvironment.adapter = @(Get-NetAdapterStatistics | Select-Object Name,ReceivedPacketErrors,OutboundPacketErrors,ReceivedDiscardedPackets,OutboundDiscardedPackets) } catch { $ntpEnvironment.adapterError = $_.Exception.Message }
try { $ntpEnvironment.profiles = @(Get-NetFirewallProfile | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction,LogBlocked,LogAllowed) } catch { $ntpEnvironment.profilesError = $_.Exception.Message }
try { $ntpEnvironment.udp123 = @(Get-NetUDPEndpoint | Where-Object LocalPort -eq 123 | Select-Object LocalAddress,LocalPort,OwningProcess) } catch { $ntpEnvironment.udpError = $_.Exception.Message }
try {
    $ntpEnvironment.udpBlockFilters = @(Get-NetFirewallRule -PolicyStore ActiveStore -Enabled True -Action Block | Get-NetFirewallPortFilter | Where-Object { $_.Protocol -in @('UDP','17','Any') -and ($_.RemotePort -contains '123' -or $_.RemotePort -contains 'Any') } | Select-Object -First 40 Protocol,LocalPort,RemotePort,InstanceID)
} catch { $ntpEnvironment.filtersError = $_.Exception.Message }
try { $ntpEnvironment.timeEvents = @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Time-Service';StartTime=(Get-Date).AddHours(-2)} -MaxEvents 20 | Select-Object Id,Level,@{Name='Time';Expression={$_.TimeCreated.ToString('o')}},Message) } catch { $ntpEnvironment.timeEventsError = $_.Exception.Message }
try { $ntpEnvironment.jumps = @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Kernel-General';Id=1;StartTime=(Get-Date).AddHours(-2)} -MaxEvents 8 | Select-Object Id,@{Name='Time';Expression={$_.TimeCreated.ToString('o')}},Message) } catch { $ntpEnvironment.jumpsError = $_.Exception.Message }
$ntpEnvironment.noSystemChanges = $true
$ntpEnvironment | ConvertTo-Json -Depth 6
