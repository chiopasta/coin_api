$ErrorActionPreference = 'Stop'
$clockEnvironment = [ordered]@{}
$clockEnvironment.at = (Get-Date).ToString('o')
$clockEnvironment.utc = [DateTime]::UtcNow.ToString('o')
$clockEnvironment.service = Get-Service W32Time | Select-Object Name,@{Name='State';Expression={$_.Status.ToString()}},@{Name='StartMode';Expression={$_.StartType.ToString()}}
$clockEnvironment.timezone = Get-TimeZone | Select-Object Id,BaseUtcOffset
$clockEnvironment.boot = Get-CimInstance Win32_OperatingSystem | Select-Object LastBootUpTime
$clockEnvironment.domain = Get-CimInstance Win32_ComputerSystem | Select-Object PartOfDomain
try {
    $clockEnvironment.timeEvents = @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Time-Service';StartTime=(Get-Date).AddHours(-6)} -MaxEvents 20 | Select-Object Id,Level,@{Name='Time';Expression={$_.TimeCreated.ToString('o')}},Message)
} catch { $clockEnvironment.timeEventsError = $_.Exception.Message }
try {
    $clockEnvironment.jumpEvents = @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Kernel-General';Id=1;StartTime=(Get-Date).AddHours(-6)} -MaxEvents 8 | Select-Object Id,@{Name='Time';Expression={$_.TimeCreated.ToString('o')}},Message)
} catch { $clockEnvironment.jumpEventsError = $_.Exception.Message }
$clockEnvironment.activeScanners = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name)
$clockEnvironment.noSystemChanges = $true
$clockEnvironment | ConvertTo-Json -Depth 6
