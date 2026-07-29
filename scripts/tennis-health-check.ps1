# Il Margine - Tennis automation watchdog
# Purpose: read existing tennis artifacts, detect stale output files or
# failed/missing scheduled tasks, and optionally post an alert. This watchdog
# must not rebuild model artifacts itself.

param(
    [int]$StaleHours = 15,
    [int]$AlertCooldownMinutes = 180,
    [switch]$NoNotify
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
. (Join-Path $root "scripts\use-local-python.ps1") -RepoRoot $root

$dataDir = Join-Path $root "data\backtest"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$logFile = Join-Path $dataDir "tennis-health.log"
$healthFile = Join-Path $dataDir "tennis-health-status.json"
$envFiles = @(
    (Join-Path $root ".env.local"),
    (Join-Path $root "env.local")
)

$laneConfigs = @(
    @{ Name = "Strict live control"; Path = "data\backtest\strict-policy-performance-weekly.csv" },
    @{ Name = "Volume 200 shadow"; Path = "data\backtest\strict-policy-performance-volume200-weekly.csv" },
    @{ Name = "Spread v1 shadow"; Path = "data\backtest\strict-policy-performance-spreadv1-weekly.csv" },
    @{ Name = "CPI speed shadow"; Path = "data\backtest\strict-policy-performance-cpi_speed-weekly.csv" }
)

$artifactConfigs = @(
    @{ Name = "Tennis props daily board"; Path = "data\tennis-props\player-props-board.csv"; MaxAgeHours = 30 },
    @{ Name = "Tennis props capture pipeline"; Path = "data\tennis-props\pipeline-health.json"; MaxAgeHours = 30; TimestampField = "generated_at" },
    @{ Name = "Bet365 props benchmark"; Path = "data\tennis-props\shadow\market-observations-report.txt"; MaxAgeHours = 30 },
    @{ Name = "Aces v3 weekly refit"; Path = "data\tennis-props\backtest\aces-dfs-v3-all-tour-gate.json"; MaxAgeHours = 192; TimestampField = "generated_at" }
)

$taskNames = @(
    "IlMargine-Daily",
    "IlMargine-Daily-AM",
    "IlMargine-Weekly",
    "IlMargine-Tennis-Close-Capture"
)

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Import-EnvFiles {
    foreach ($path in $envFiles) {
        if (!(Test-Path $path)) { continue }
        foreach ($rawLine in Get-Content $path) {
            $line = $rawLine.Trim()
            if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#") -or -not $line.Contains("=")) {
                continue
            }
            $parts = $line.Split("=", 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim().Trim('"').Trim("'")
            if ($key) {
                [Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }
}

function Read-JsonFile($path) {
    if (!(Test-Path $path)) { return $null }
    try {
        return Get-Content $path -Raw | ConvertFrom-Json
    } catch {
        return $null
    }
}

function To-IsoUtc([datetime]$value) {
    return $value.ToUniversalTime().ToString("o")
}

function Parse-DateTimeOffsetValue($value) {
    if ([string]::IsNullOrWhiteSpace($value)) { return $null }
    try {
        return [DateTimeOffset]::Parse($value)
    } catch {
        return $null
    }
}

function Format-Age($hours) {
    if ($null -eq $hours) { return "unknown" }
    if ($hours -lt 1) { return "<1h" }
    if ($hours -lt 24) { return ("{0:N1}h" -f $hours) }
    return ("{0:N1}d" -f ($hours / 24.0))
}

function Get-TaskFailureFreshHours([string]$taskName) {
    switch ($taskName) {
        "IlMargine-Daily" { return 6 }
        "IlMargine-Daily-AM" { return 6 }
        "IlMargine-Weekly" { return 36 }
        "IlMargine-Tennis-Close-Capture" { return 2 }
        default { return 6 }
    }
}

function Get-TaskRecoveryLogInfo([string]$taskName) {
    switch ($taskName) {
        "IlMargine-Daily" {
            return @{
                Path = "data\oncourt-daily.log"
                Pattern = "Daily Pipeline finished at (?<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
            }
        }
        "IlMargine-Daily-AM" {
            return @{
                Path = "data\oncourt-am-refresh.log"
                Pattern = "AM Tennis Refresh finished at (?<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
            }
        }
        "IlMargine-Weekly" {
            return @{
                Path = "data\oncourt-weekly.log"
                Pattern = "Weekly Full Load finished at (?<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
            }
        }
        default {
            return $null
        }
    }
}

function Get-LatestTaskRecoveryTime([string]$taskName) {
    $cfg = Get-TaskRecoveryLogInfo $taskName
    if ($null -eq $cfg) { return $null }

    $path = Join-Path $root $cfg.Path
    if (!(Test-Path $path)) { return $null }

    try {
        $recentLines = Get-Content -Path $path -Tail 400
    } catch {
        return $null
    }

    for ($i = $recentLines.Count - 1; $i -ge 0; $i--) {
        $line = "$($recentLines[$i])"
        if ($line -match $cfg.Pattern) {
            try {
                return [DateTimeOffset]::ParseExact($matches.timestamp, "yyyy-MM-dd HH:mm:ss", [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeLocal)
            } catch {
                return $null
            }
        }
    }

    return $null
}

function Get-LaneHealth($config, [datetimeoffset]$nowUtc, [int]$staleHours) {
    $path = Join-Path $root $config.Path
    if (!(Test-Path $path)) {
        return [ordered]@{
            name = $config.Name
            path = $config.Path
            status = "missing"
            generated_at = $null
            latest_signal_date = $null
            age_hours = $null
            stale = $true
            detail = "Missing file"
        }
    }

    try {
        $rows = Import-Csv -Path $path
    } catch {
        return [ordered]@{
            name = $config.Name
            path = $config.Path
            status = "invalid_csv"
            generated_at = $null
            latest_signal_date = $null
            age_hours = $null
            stale = $true
            detail = "Invalid CSV: $($_.Exception.Message)"
        }
    }

    $latest = $rows | Select-Object -Last 1
    if ($null -eq $latest) {
        return [ordered]@{
            name = $config.Name
            path = $config.Path
            status = "empty"
            generated_at = $null
            latest_signal_date = $null
            age_hours = $null
            stale = $true
            detail = "CSV has no rows"
        }
    }

    $generated = Parse-DateTimeOffsetValue $latest.generated_utc
    $ageHours = $null
    if ($generated) {
        $ageHours = [Math]::Max(0, ($nowUtc - $generated).TotalHours)
    }
    $isStale = ($null -eq $generated) -or ($ageHours -gt $staleHours)

    return [ordered]@{
        name = $config.Name
        path = $config.Path
        status = if ($isStale) { "stale" } else { "ok" }
        generated_at = if ($generated) { $generated.ToString("o") } else { $null }
        latest_signal_date = if ([string]::IsNullOrWhiteSpace($latest.as_of_date)) { $null } else { "$($latest.as_of_date)" }
        age_hours = if ($null -eq $ageHours) { $null } else { [Math]::Round($ageHours, 2) }
        stale = $isStale
        detail = if ($generated) { $null } else { "Missing generated_utc" }
    }
}

function Get-ArtifactHealth($config, [datetimeoffset]$nowUtc) {
    $path = Join-Path $root $config.Path
    if (!(Test-Path $path)) {
        return [ordered]@{
            name = $config.Name; path = $config.Path; status = "missing"; generated_at = $null
            latest_signal_date = $null; age_hours = $null; stale = $true; detail = "Missing file"
        }
    }

    $generated = $null
    if ($config.TimestampField) {
        $payload = Read-JsonFile $path
        if ($payload) { $generated = Parse-DateTimeOffsetValue $payload.($config.TimestampField) }
    } else {
        $generated = [DateTimeOffset](Get-Item $path).LastWriteTime
    }
    $ageHours = if ($generated) { [Math]::Max(0, ($nowUtc - $generated.ToUniversalTime()).TotalHours) } else { $null }
    $isStale = ($null -eq $generated) -or ($ageHours -gt [double]$config.MaxAgeHours)
    return [ordered]@{
        name = $config.Name
        path = $config.Path
        status = if ($isStale) { "stale" } else { "ok" }
        generated_at = if ($generated) { $generated.ToUniversalTime().ToString("o") } else { $null }
        latest_signal_date = $null
        age_hours = if ($null -eq $ageHours) { $null } else { [Math]::Round($ageHours, 2) }
        stale = $isStale
        detail = if ($generated) { $null } else { "Missing or invalid timestamp" }
    }
}

function Get-TaskHealth([string]$taskName) {
    try {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    } catch {
        $message = "$($_.Exception.Message)"
        if ($message -match "Access denied") {
            return [ordered]@{
                name = $taskName
                status = "unknown"
                state = $null
                last_run_time = $null
                next_run_time = $null
                last_task_result = $null
                detail = "Task query denied"
            }
        }
        $task = $null
    }
    if ($null -eq $task) {
        return [ordered]@{
            name = $taskName
            status = "missing"
            state = $null
            last_run_time = $null
            next_run_time = $null
            last_task_result = $null
            detail = "Task not found"
        }
    }

    $info = $task | Get-ScheduledTaskInfo
    $state = "$($task.State)"
    $lastTaskResult = $info.LastTaskResult
    $lastRunDateTime = if ($info.LastRunTime -and $info.LastRunTime.Year -gt 2000) { [DateTimeOffset]$info.LastRunTime } else { $null }
    $lastRunTime = if ($lastRunDateTime) { To-IsoUtc $lastRunDateTime.UtcDateTime } else { $null }
    $nextRunTime = if ($info.NextRunTime -and $info.NextRunTime.Year -gt 2000) { To-IsoUtc $info.NextRunTime } else { $null }
    $nowUtc = [DateTimeOffset]::UtcNow
    $lastRunAgeHours = if ($lastRunDateTime) { [Math]::Max(0, ($nowUtc - $lastRunDateTime.ToUniversalTime()).TotalHours) } else { $null }
    $recoveryTime = Get-LatestTaskRecoveryTime $taskName

    $status = "ok"
    $detail = $null
    $schedulerCode = [int64]$lastTaskResult
    if ($task.State -eq "Disabled") {
        $status = "disabled"
        $detail = "Task is disabled"
    } elseif ($task.State -eq "Running" -or $schedulerCode -eq 267009) {
        $status = "running"
        $detail = if ($lastRunTime) { "Task is currently running" } else { "Task has started and is currently running" }
    } elseif ($schedulerCode -eq 267008) {
        $status = "ok"
        $detail = "Task is ready for next scheduled run"
    } elseif ($schedulerCode -eq 267011) {
        $status = "ok"
        $detail = "Task has not run yet"
    } elseif ($lastTaskResult -ne 0 -and $lastRunTime) {
        if ($recoveryTime -and (($null -eq $lastRunDateTime) -or ($recoveryTime.ToUniversalTime() -gt $lastRunDateTime.ToUniversalTime()))) {
            $status = "ok"
            $detail = "Recovered by successful run at $($recoveryTime.ToUniversalTime().ToString("o"))"
        } else {
        $freshFailureHours = Get-TaskFailureFreshHours $taskName
        if ($null -ne $lastRunAgeHours -and $lastRunAgeHours -le $freshFailureHours) {
            $status = "failed"
            $detail = "LastTaskResult=$lastTaskResult"
        } else {
            $status = "stale_failed"
            $detail = "LastTaskResult=$lastTaskResult; awaiting next scheduled run"
        }
        }
    }

    return [ordered]@{
        name = $taskName
        status = $status
        state = $state
        last_run_time = $lastRunTime
        next_run_time = $nextRunTime
        age_hours = if ($null -eq $lastRunAgeHours) { $null } else { [Math]::Round($lastRunAgeHours, 2) }
        last_task_result = $lastTaskResult
        recovery_time = if ($recoveryTime) { $recoveryTime.ToUniversalTime().ToString("o") } else { $null }
        detail = $detail
    }
}

function Get-ActiveLaneRecoveryTasks($taskHealth) {
    return @(
        $taskHealth | Where-Object {
            $_.status -eq "running" -and $_.name -in @("IlMargine-Daily", "IlMargine-Daily-AM")
        }
    )
}

function Write-HealthFile {
    param(
        [string]$State,
        [string]$Message,
        [object[]]$Lanes,
        [object[]]$Tasks,
        [string]$LastAlertedAt,
        [string]$LastAlertKey
    )

    $payload = [ordered]@{
        checked_at = (Get-Date).ToUniversalTime().ToString("o")
        state = $State
        message = $Message
        stale_hours_threshold = $StaleHours
        last_alerted_at = $LastAlertedAt
        last_alert_key = $LastAlertKey
        lanes = $Lanes
        tasks = $Tasks
    }

    ($payload | ConvertTo-Json -Depth 8) | Set-Content -Path $healthFile -Encoding UTF8
}

function Post-Telegram([string]$message) {
    $botToken = [Environment]::GetEnvironmentVariable("OPS_ALERT_TELEGRAM_BOT_TOKEN", "Process")
    $chatId = [Environment]::GetEnvironmentVariable("OPS_ALERT_TELEGRAM_CHAT_ID", "Process")
    if ([string]::IsNullOrWhiteSpace($botToken) -or [string]::IsNullOrWhiteSpace($chatId)) { return $false }

    try {
        $payload = @{
            chat_id = $chatId
            text = $message
            disable_web_page_preview = $true
        } | ConvertTo-Json
        $uri = "https://api.telegram.org/bot$botToken/sendMessage"
        Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json" -Body $payload | Out-Null
        return $true
    } catch {
        Log "Telegram post failed: $($_.Exception.Message)"
        return $false
    }
}

function Post-Webhook([string]$message) {
    $webhookUrl = [Environment]::GetEnvironmentVariable("OPS_ALERT_WEBHOOK_URL", "Process")
    if ([string]::IsNullOrWhiteSpace($webhookUrl)) { return $false }

    try {
        $payload = @{ text = $message; content = $message } | ConvertTo-Json
        Invoke-RestMethod -Uri $webhookUrl -Method Post -ContentType "application/json" -Body $payload | Out-Null
        return $true
    } catch {
        Log "Webhook post failed: $($_.Exception.Message)"
        return $false
    }
}

function Post-Alert([string]$message) {
    $sent = $false
    if (Post-Telegram $message) {
        $sent = $true
    }
    if (Post-Webhook $message) {
        $sent = $true
    }
    return $sent
}

Import-EnvFiles

$nowUtc = [DateTimeOffset]::UtcNow
$previousHealth = Read-JsonFile $healthFile
$laneHealth = @(
    $laneConfigs | ForEach-Object { Get-LaneHealth $_ $nowUtc $StaleHours }
    $artifactConfigs | ForEach-Object { Get-ArtifactHealth $_ $nowUtc }
)
$taskHealth = @($taskNames | ForEach-Object { Get-TaskHealth $_ })
$activeRecoveryTasks = @(Get-ActiveLaneRecoveryTasks $taskHealth)

$badLanes = @($laneHealth | Where-Object { $_.status -ne "ok" })
$badTasks = @($taskHealth | Where-Object { $_.status -in @("missing", "disabled", "failed", "unknown") })
$suppressedBadLanes = @()

if ($activeRecoveryTasks.Count -gt 0) {
    $suppressedBadLanes = @($badLanes | Where-Object { $_.status -eq "stale" })
    $badLanes = @($badLanes | Where-Object { $_.status -ne "stale" })
}

if ($badLanes.Count -eq 0 -and $badTasks.Count -eq 0) {
    if ($suppressedBadLanes.Count -gt 0) {
        $taskList = ($activeRecoveryTasks | ForEach-Object { $_.name }) -join ", "
        $message = "Tennis health OK. Refresh in progress via $taskList."
    } else {
        $message = "Tennis health OK. No stale lanes or failing/missing tasks."
    }
    Log $message
    Write-HealthFile -State "healthy" -Message $message -Lanes $laneHealth -Tasks $taskHealth -LastAlertedAt $previousHealth.last_alerted_at -LastAlertKey $previousHealth.last_alert_key
    exit 0
}

$issueParts = @()
foreach ($lane in $badLanes) {
    $laneRefresh = if ($lane.generated_at) { $lane.generated_at } else { "missing" }
    $laneSignal = if ($lane.latest_signal_date) { $lane.latest_signal_date } else { "n/a" }
    $issueParts += "$($lane.name): $($lane.status) (refresh $laneRefresh, latest signal $laneSignal, age $(Format-Age $lane.age_hours))"
}
foreach ($task in $badTasks) {
    $taskDetailSuffix = if ($task.detail) { " [$($task.detail)]" } else { "" }
    $issueParts += "$($task.name): $($task.status)$taskDetailSuffix"
}

$message = "Tennis health alert.`n" + ($issueParts -join "`n")
$alertKey = ($issueParts -join " | ")
$lastAlertedAt = Parse-DateTimeOffsetValue $previousHealth.last_alerted_at
$shouldAlert = $true
if ($previousHealth -and $previousHealth.last_alert_key -eq $alertKey -and $lastAlertedAt) {
    if (($nowUtc - $lastAlertedAt).TotalMinutes -lt $AlertCooldownMinutes) {
        $shouldAlert = $false
    }
}

Log $message

$nextAlertedAt = $previousHealth.last_alerted_at
$nextAlertKey = $previousHealth.last_alert_key
if ($shouldAlert -and -not $NoNotify) {
    if (Post-Alert $message) {
        $nextAlertedAt = $nowUtc.ToString("o")
        $nextAlertKey = $alertKey
        Log "Alert posted."
    }
} elseif ($shouldAlert) {
    Log "Alert suppressed by -NoNotify."
}

Write-HealthFile -State "alert" -Message $message -Lanes $laneHealth -Tasks $taskHealth -LastAlertedAt $nextAlertedAt -LastAlertKey $nextAlertKey
exit 1
