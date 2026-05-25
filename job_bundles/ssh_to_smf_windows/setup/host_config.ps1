<#
.SYNOPSIS
    One-time Windows host config for Deadline Cloud workers running the ssh_to_smf_windows job bundle.

.DESCRIPTION
    Runs with no arguments. All values are hardcoded so the script can be dropped
    onto a Windows worker and executed as-is.

    - Creates a local user 'RDP' (password: ChangeMe2026!!@@##) in the
      Administrators and Remote Desktop Users groups. Idempotent: rotates the
      password if the user already exists.
    - Disables the UAC consent prompt (ConsentPromptBehaviorAdmin = 0) so
      scripted admin actions don't block on a prompt.
    - Enables RDP (fDenyTSConnections = 0), enables the Remote Desktop firewall
      rule group, and starts + automates TermService.
    - Grants the Deadline worker service account 'job-user' local-administrator
      rights so the job template can restart the AmazonSSMAgent service.

    Run as Administrator, once per worker host, BEFORE submitting jobs.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\setup\host_config.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Hardcoded config - change here if you need different values.
$RdpUsername = 'RDP'
$RdpPassword = 'ChangeMe2026!!@@##'
$JobUser     = 'job-user'

function Set-RdpUser {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$PlainPassword
    )
    $secure = ConvertTo-SecureString -AsPlainText -Force $PlainPassword
    $existing = Get-LocalUser -Name $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Local user '$Name' already exists; rotating password."
        Set-LocalUser -Name $Name -Password $secure
        $user = $existing
    } else {
        Write-Host "Creating local user '$Name'..."
        $user = New-LocalUser `
            -Name $Name `
            -FullName $Name `
            -Description 'RDP / Deadline Cloud SSM-managed-node access' `
            -Password $secure `
            -AccountNeverExpires `
            -PasswordNeverExpires
    }

    foreach ($group in 'Administrators', 'Remote Desktop Users') {
        $isMember = Get-LocalGroupMember -Group $group -Member $Name -ErrorAction SilentlyContinue
        if (-not $isMember) {
            Add-LocalGroupMember -Group $group -Member $user
            Write-Host "  Added '$Name' to '$group'."
        } else {
            Write-Host "  '$Name' is already a member of '$group'."
        }
    }
}

function Disable-UacConsentPrompt {
    Write-Host 'Disabling UAC consent prompt (ConsentPromptBehaviorAdmin = 0)...'
    Set-ItemProperty `
        -Path  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' `
        -Name  'ConsentPromptBehaviorAdmin' `
        -Value 0 `
        -Type  DWord
}

function Enable-RdpAndFirewall {
    Write-Host 'Enabling RDP (fDenyTSConnections = 0)...'
    Set-ItemProperty `
        -Path  'HKLM:\System\CurrentControlSet\Control\Terminal Server' `
        -Name  'fDenyTSConnections' `
        -Value 0 `
        -Type  DWord

    Write-Host 'Enabling Remote Desktop firewall group...'
    Enable-NetFirewallRule -DisplayGroup 'Remote Desktop'

    Write-Host 'Starting + automating TermService...'
    Set-Service   -Name TermService -StartupType Automatic
    Start-Service -Name TermService
}

function Grant-JobUserAdmin {
    param([Parameter(Mandatory)][string]$User)
    $exists = $null -ne (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)
    if (-not $exists) {
        Write-Warning "Deadline worker account '$User' not found. Install the Deadline worker agent first, then re-run this script."
        return $false
    }
    $isAdmin = Get-LocalGroupMember -Group 'Administrators' -Member $User -ErrorAction SilentlyContinue
    if ($isAdmin) {
        Write-Host "'$User' is already a local Administrator."
    } else {
        Write-Host "Adding '$User' to Administrators (required to restart AmazonSSMAgent)..."
        Add-LocalGroupMember -Group 'Administrators' -Member $User
    }
    return $true
}

function Install-SsmElevatedTask {
    <#
    .SYNOPSIS
        Installs infrastructure so the job template can invoke ssm-setup-cli.exe
        (and other admin-only tools) with a genuine elevated/unfiltered token.

    .DESCRIPTION
        job-user is a member of Administrators, but on Windows a non-SYSTEM
        process spawned by the Deadline worker gets a UAC-filtered token and
        IsUserAnAdmin() returns false, so ssm-setup-cli refuses to run.

        This function creates a fixed scheduled task 'DeadlineSsmElevated' that
        runs as SYSTEM (Highest run level). The task reads a small JSON spec
        (exe + args) from a shared directory, runs it, captures stdout/stderr
        to a log, and writes the exit code to a file. The job's run.ps1 writes
        the spec, triggers the task with schtasks.exe /Run, polls for
        completion, then reads the log + exit code.

        The task's DACL is rewritten so job-user can trigger it (GENERIC_READ +
        GENERIC_EXECUTE); SYSTEM and Administrators retain full control.
    #>
    param([Parameter(Mandatory)][string]$JobUser)

    $dir         = 'C:\ProgramData\Amazon\Deadline\SsmElevated'
    $wrapperPath = Join-Path $dir 'run-elevated.ps1'
    $taskName    = 'DeadlineSsmElevated'

    Write-Host "Installing scheduled task '$taskName' (runs as SYSTEM, triggered by '$JobUser')..."

    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    # Allow job-user to write args.json / read run.log + exit.code in the shared dir.
    $acl = Get-Acl $dir
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $JobUser, 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.SetAccessRule($rule)
    Set-Acl -Path $dir -AclObject $acl
    Write-Host "  Granted '$JobUser' Modify on $dir"

    # Wrapper script that the task runs. Reads args.json -> invokes exe -> writes run.log + exit.code.
    $wrapper = @'
$ErrorActionPreference = 'Continue'
$dir       = 'C:\ProgramData\Amazon\Deadline\SsmElevated'
$argsPath  = Join-Path $dir 'args.json'
$logPath   = Join-Path $dir 'run.log'
$exitPath  = Join-Path $dir 'exit.code'

# Always start with fresh log + exit artifacts.
Remove-Item $logPath, $exitPath -Force -ErrorAction SilentlyContinue

try {
    if (-not (Test-Path $argsPath)) {
        "ERROR: args.json not found at $argsPath" | Out-File -FilePath $logPath -Encoding UTF8
        '99' | Out-File -FilePath $exitPath -Encoding ASCII -NoNewline
        exit 99
    }
    $spec = Get-Content -Raw $argsPath | ConvertFrom-Json
    $exe  = [string]$spec.exe
    $argv = @()
    foreach ($a in $spec.args) { $argv += [string]$a }

    "=== Invoking: $exe $($argv -join ' ') ===" | Out-File -FilePath $logPath -Append -Encoding UTF8
    & $exe @argv *>> $logPath
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
} catch {
    "ERROR during elevated run: $_" | Out-File -FilePath $logPath -Append -Encoding UTF8
    $code = 99
}

"$code" | Out-File -FilePath $exitPath -Encoding ASCII -NoNewline
'@
    Set-Content -Path $wrapperPath -Value $wrapper -Encoding UTF8
    Write-Host "  Wrote wrapper: $wrapperPath"

    # Re-register the task (idempotent).
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    $action = New-ScheduledTaskAction `
        -Execute 'powershell.exe' `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`""
    $principal = New-ScheduledTaskPrincipal `
        -UserId 'NT AUTHORITY\SYSTEM' `
        -LogonType ServiceAccount `
        -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null
    Write-Host "  Registered task as SYSTEM (Highest run level)."

    # Grant job-user the right to trigger the task. The default DACL only
    # lets SYSTEM + Administrators run it, but Administrators is deny-only
    # in job-user's filtered token, so we need an explicit ACE for job-user.
    try {
        $jobSid = (New-Object System.Security.Principal.NTAccount($JobUser)).Translate(
                   [System.Security.Principal.SecurityIdentifier]).Value
        $sched = New-Object -ComObject Schedule.Service
        $sched.Connect()
        $folder = $sched.GetFolder('\')
        $regTask = $folder.GetTask($taskName)
        # GA = full, GRGX = Read + Execute. Flag 0 = DACL_SECURITY_INFORMATION (replace DACL only).
        $sddl = "D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GRGX;;;$jobSid)"
        $regTask.SetSecurityDescriptor($sddl, 0)
        Write-Host "  Set task DACL allowing '$JobUser' (Read + Execute)."
    } catch {
        Write-Warning "Could not set task DACL for '$JobUser': $_"
    }
}

# --- main -----------------------------------------------------------------
Write-Host '=============================================================='
Write-Host 'ssh_to_smf_windows - Windows worker host config'
Write-Host '=============================================================='

Set-RdpUser -Name $RdpUsername -PlainPassword $RdpPassword
Disable-UacConsentPrompt
Enable-RdpAndFirewall
$jobUserOk = Grant-JobUserAdmin -User $JobUser
if ($jobUserOk) {
    Install-SsmElevatedTask -JobUser $JobUser
}

Write-Host ''
Write-Host '=============================================================='
Write-Host 'Host config complete.'
Write-Host "  RDP user:    $RdpUsername  (Administrators + Remote Desktop Users)"
Write-Host '  RDP pass:    (hardcoded - see script source)'
Write-Host '  UAC:         ConsentPromptBehaviorAdmin = 0'
Write-Host '  RDP:         fDenyTSConnections = 0, firewall group enabled'
Write-Host '  TermService: Automatic + Running'
if ($jobUserOk) {
    Write-Host "  job-user:    $JobUser added to Administrators"
} else {
    Write-Host "  job-user:    NOT configured (run again after Deadline worker install)"
}
Write-Host '=============================================================='

Get-Service TermService | Format-Table -AutoSize

# Force clean exit. The Deadline worker treats any non-zero exit from the
# host-config script as a fatal failure and shuts the host down, and some
# final-stage cmdlets (e.g. Format-Table under StrictMode) can leave a
# non-zero $LASTEXITCODE even when all the real work succeeded.
exit 0
