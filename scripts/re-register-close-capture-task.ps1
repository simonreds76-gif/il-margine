param(
    [string]$TaskName = "IlMargine-Tennis-Close-Capture",
    [string]$UserName = "$env:USERDOMAIN\$env:USERNAME"
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Get-PlainTextFromSecureString([Security.SecureString]$SecureString) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureString)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Set-ScheduledTaskXmlSetting {
    param(
        [Parameter(Mandatory = $true)]
        [xml]$Xml,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $node = $Xml.Task.Settings.$Name
    if ($null -ne $node) {
        $node.InnerText = $Value
        return
    }

    $newNode = $Xml.CreateElement($Name, $Xml.Task.NamespaceURI)
    $newNode.InnerText = $Value
    [void] $Xml.Task.Settings.AppendChild($newNode)
}

function Set-ScheduledTaskBridgeHardening {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskName
    )

    $xmlText = schtasks /Query /TN $TaskName /XML
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($xmlText)) {
        throw "Unable to read scheduled task XML for $TaskName"
    }

    $xml = [xml]$xmlText
    $principal = $xml.Task.Principals.Principal
    if ($null -eq $principal) {
        throw "Scheduled task XML for $TaskName is missing a Principal node."
    }

    if ($null -eq $principal.LogonType) {
        $logonTypeNode = $xml.CreateElement("LogonType", $xml.Task.NamespaceURI)
        $principal.AppendChild($logonTypeNode) | Out-Null
    }
    $principal.LogonType = "Password"

    if ($null -eq $principal.RunLevel) {
        $runLevelNode = $xml.CreateElement("RunLevel", $xml.Task.NamespaceURI)
        $principal.AppendChild($runLevelNode) | Out-Null
    }
    $principal.RunLevel = "HighestAvailable"

    Set-ScheduledTaskXmlSetting -Xml $xml -Name "DisallowStartIfOnBatteries" -Value "false"
    Set-ScheduledTaskXmlSetting -Xml $xml -Name "StopIfGoingOnBatteries" -Value "false"
    Set-ScheduledTaskXmlSetting -Xml $xml -Name "MultipleInstancesPolicy" -Value "IgnoreNew"
    Set-ScheduledTaskXmlSetting -Xml $xml -Name "WakeToRun" -Value "true"
    Set-ScheduledTaskXmlSetting -Xml $xml -Name "StartWhenAvailable" -Value "true"
    Set-ScheduledTaskXmlSetting -Xml $xml -Name "ExecutionTimeLimit" -Value "PT10M"

    $restartOnFailure = $xml.Task.Settings.RestartOnFailure
    if ($null -eq $restartOnFailure) {
        $restartOnFailure = $xml.CreateElement("RestartOnFailure", $xml.Task.NamespaceURI)
        [void] $xml.Task.Settings.AppendChild($restartOnFailure)
    } else {
        while ($restartOnFailure.HasChildNodes) {
            [void]$restartOnFailure.RemoveChild($restartOnFailure.FirstChild)
        }
    }

    $intervalNode = $xml.CreateElement("Interval", $xml.Task.NamespaceURI)
    $intervalNode.InnerText = "PT5M"
    [void]$restartOnFailure.AppendChild($intervalNode)

    $countNode = $xml.CreateElement("Count", $xml.Task.NamespaceURI)
    $countNode.InnerText = "2"
    [void]$restartOnFailure.AppendChild($countNode)

    $tmpPath = Join-Path ([System.IO.Path]::GetTempPath()) "$TaskName.bridge.xml"
    try {
        $utf16 = New-Object System.Text.UnicodeEncoding($false, $true)
        [System.IO.File]::WriteAllText($tmpPath, $xml.OuterXml, $utf16)
        schtasks /Create /TN $TaskName /XML $tmpPath /F | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "schtasks failed while importing the hardened XML for $TaskName"
        }
    } finally {
        Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-IsAdministrator)) {
    throw "Run this script from an elevated PowerShell window. Task re-registration with stored credentials needs administrator rights."
}

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$closeCaptureScript = Join-Path $root "scripts\pinnacle-close-capture.ps1"
$psExe = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"

if (!(Test-Path $closeCaptureScript)) {
    throw "Missing close-capture wrapper: $closeCaptureScript"
}

$taskExists = (& cmd.exe /c "schtasks /Query /TN `"$TaskName`" >nul 2>&1"; $LASTEXITCODE -eq 0)
if (-not $taskExists) {
    throw "Scheduled task '$TaskName' does not exist. Create it first, then rerun this bridge script."
}

$backupDir = Join-Path $root "data\task-backups"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $backupDir "$TaskName.$timestamp.xml"
$currentXml = schtasks /Query /TN $TaskName /XML
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($currentXml)) {
    throw "Unable to read the existing XML for $TaskName"
}

$utf16 = New-Object System.Text.UnicodeEncoding($false, $true)
[System.IO.File]::WriteAllText($backupPath, $currentXml, $utf16)
Write-Host "Backed up current task XML to $backupPath"

$credential = Get-Credential -UserName $UserName -Message "Enter the Windows password to re-register $TaskName with stored credentials."
if ($null -eq $credential) {
    throw "Credential prompt was cancelled."
}

$password = Get-PlainTextFromSecureString $credential.Password
if ([string]::IsNullOrWhiteSpace($password)) {
    throw "A non-empty password is required to register the task with LogonType=Password."
}

$closeCaptureCmd = "$psExe -ExecutionPolicy Bypass -NoProfile -File `"$closeCaptureScript`""

try {
    schtasks /Create /TN $TaskName /SC DAILY /ST 08:00 /RI 30 /DU 16:00 /TR "$closeCaptureCmd" /RU $credential.UserName /RP $password /RL HIGHEST /F | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "schtasks failed while recreating $TaskName with stored credentials."
    }

    Set-ScheduledTaskBridgeHardening -TaskName $TaskName

    Write-Host ""
    Write-Host "Close-capture task re-registered."
    Write-Host "Backup XML: $backupPath"
    Write-Host ""
    Write-Host "Quick checks:"
    Write-Host "  schtasks /Query /TN `"$TaskName`" /V /FO LIST"
    Write-Host "  schtasks /Run /TN `"$TaskName`""
    Write-Host ""
    Write-Host "The task should now be stored-credential based instead of Interactive only."
} finally {
    $password = $null
}
