$ErrorActionPreference = 'Stop'
$environmentEvidence = [ordered]@{}
$environmentEvidence.localNow = (Get-Date).ToString('o')
$environmentEvidence.utcNow = [DateTime]::UtcNow.ToString('o')
$environmentEvidence.timezone = Get-TimeZone | Select-Object Id,BaseUtcOffset
$environmentEvidence.service = Get-Service -Name W32Time | Select-Object Name,@{Name='State';Expression={$_.Status.ToString()}},@{Name='StartMode';Expression={$_.StartType.ToString()}}
$environmentEvidence.os = Get-CimInstance Win32_OperatingSystem | Select-Object LastBootUpTime,LocalDateTime
$environmentEvidence.domain = Get-CimInstance Win32_ComputerSystem | Select-Object PartOfDomain
try {
    $environmentEvidence.tasks = @(Get-ScheduledTask -TaskPath '\Microsoft\Windows\Time Synchronization\' | ForEach-Object {
        $taskEvidence = $_
        $taskDetail = Get-ScheduledTaskInfo -TaskName $taskEvidence.TaskName -TaskPath $taskEvidence.TaskPath
        [PSCustomObject]@{TaskName=$taskEvidence.TaskName;State=$taskEvidence.State.ToString();LastRunTime=$taskDetail.LastRunTime;LastTaskResult=$taskDetail.LastTaskResult;NextRunTime=$taskDetail.NextRunTime}
    })
} catch { $environmentEvidence.tasksError = $_.Exception.Message }
try {
    $environmentEvidence.syncEvents = @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Time-Service';Id=35,37;StartTime=(Get-Date).AddDays(-7)} -MaxEvents 6 | Select-Object Id,@{Name='Time';Expression={$_.TimeCreated.ToString('o')}},Message)
} catch { $environmentEvidence.syncEventsError = $_.Exception.Message }
try {
    $environmentEvidence.resumeEvents = @(Get-WinEvent -FilterHashtable @{LogName='System';ProviderName='Microsoft-Windows-Power-Troubleshooter';Id=1;StartTime=(Get-Date).AddDays(-7)} -MaxEvents 3 | Select-Object Id,@{Name='Time';Expression={$_.TimeCreated.ToString('o')}},Message)
} catch { $environmentEvidence.resumeEventsError = $_.Exception.Message }
$environmentEvidence.activeScannerProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" | Where-Object { $_.CommandLine -match 'coin_analysis[.]forward_scanner_v4' } | Select-Object ProcessId,Name)
$environmentEvidence.noSystemChange = $true
$environmentEvidence | ConvertTo-Json -Depth 6
