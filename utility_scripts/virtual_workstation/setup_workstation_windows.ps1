<#
.SYNOPSIS
    Example: pre-configure a Windows workstation for AWS Deadline Cloud submission.

.DESCRIPTION
    Installs Blender, the Deadline Cloud submitter, and Deadline Cloud monitor,
    then creates a monitor profile so an artist only has to sign in.

    This is a worked example rather than a general-purpose tool. Edit the
    constants below for your environment.

    Deadline Cloud monitor, its profile, and Blender's add-on preferences are all
    per user, and Windows cannot write them for another account without that
    account's password. Run this in an elevated PowerShell session as the
    artist's own account.

.PARAMETER MonitorUrl
    https://<subdomain>.<region>.deadlinecloud.amazonaws.com/

.EXAMPLE
    .\setup_workstation_windows.ps1 https://mystudio.us-west-2.deadlinecloud.amazonaws.com/
#>

#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$MonitorUrl
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Much faster Invoke-WebRequest downloads
$InformationPreference = "Continue"       # Show progress messages during provisioning

# ---------------------------------------------------------------------------
# Edit these for your environment
# ---------------------------------------------------------------------------

$BlenderVersion = "4.5.0"

# The submitter's installer components for this DCC: the submitter plug-in itself,
# and the specific DCC version it integrates with. Both change together when you
# switch DCC; see "Adapting to another DCC".
$SubmitterComponent = "deadline_cloud_for_blender"
$BlenderComponent = "blender_45"

# download.blender.org rejects some automated clients, so this points at
# Blender's official mirror redirector, which forwards to a nearby mirror.
# Point it at an internal mirror if you host the archives yourself.
$BlenderMirror = "https://mirror.blender.org/release"

$BlenderPrefix = "C:\Program Files\Blender"
$SubmitterPrefix = "C:\Program Files\DeadlineCloudSubmitter"

$DownloadsBase = "https://downloads.deadlinecloud.amazonaws.com"

# ---------------------------------------------------------------------------
# Adapting to another DCC
# ---------------------------------------------------------------------------
#
# Blender stands in for whichever DCC you run. It is used here because it
# installs unattended from a public archive with no license server, which keeps
# this example runnable as-is. Everything Deadline Cloud does is identical for
# every DCC, so switching to Maya, Nuke, Houdini, 3ds Max, Cinema 4D, After
# Effects, or VRED means changing three things:
#
#   1. $SubmitterComponent and $BlenderComponent above, for example
#      deadline_cloud_for_houdini plus houdini_20_5. Run "<installer> --help" for
#      the current --enable-components values. The --<dcc>-path flag is derived
#      from $BlenderComponent, so it follows automatically.
#   2. The "Install Blender" step. Commercial DCCs need a vendor installer and
#      usually a license server, so replace that block entirely.
#   3. The "Enable the add-on in Blender" step. It is Blender-specific. Other
#      DCCs are wired up by the installer itself or by an environment variable
#      such as MAYA_MODULE_PATH or NUKE_PATH, so you can often delete it.

function Write-Step { param([string]$Message) Write-Information "[setup-workstation] $Message" }
function Write-Fatal { param([string]$Message) throw "[setup-workstation] ERROR: $Message" }

# Run a native command, returning its merged output and leaving $LASTEXITCODE for
# the caller. Windows PowerShell 5.1 turns a native command's stderr into error
# records, which $ErrorActionPreference = "Stop" escalates to a terminating
# NativeCommandError -- so a Blender that prints a driver warning would fail the
# script instead of reaching the exit-code check. Relax it for the call only.
function Get-NativeOutput {
    param([scriptblock]$Command)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Command 2>&1 } finally { $ErrorActionPreference = $previous }
}

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

# The profile and Blender's add-on preferences are per user, so this must run as
# the account that signs in. #Requires -RunAsAdministrator is satisfied by SYSTEM,
# which Run Command and EC2 user data both use, and everything would then land in
# a service profile no artist logs in to.
if ([System.Security.Principal.WindowsIdentity]::GetCurrent().IsSystem) {
    Write-Fatal "running as SYSTEM. The profile and Blender preferences are per user, so they would be written to a service profile the artist never logs in to. Run this as the artist's own account in an elevated session."
}

# The URL must carry its Region segment: the monitor accepts one without it and
# then writes a profile with the wrong region. Check the scheme separately, since
# [System.Uri] parses a host out of any scheme, http:// included.
$monitorUri = [System.Uri]$MonitorUrl
if ($monitorUri.Scheme -ne "https") {
    Write-Fatal "monitor URL must use https (got: $MonitorUrl)"
}
$monitorHost = $monitorUri.Host
if ($monitorHost -notmatch '^([a-z0-9-]+)\.([a-z0-9-]+)\.deadlinecloud\.amazonaws\.com$') {
    Write-Fatal "monitor URL must be https://<subdomain>.<region>.deadlinecloud.amazonaws.com/ (got: $MonitorUrl)"
}
$MonitorSubdomain = $Matches[1]
$MonitorRegion = $Matches[2]
$ProfileName = "$MonitorSubdomain-$MonitorRegion"

Write-Step "workstation user: $env:USERNAME"
Write-Step "monitor: $MonitorSubdomain in $MonitorRegion, profile '$ProfileName'"

$WorkDir = Join-Path $env:TEMP "deadline-workstation-setup"
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

# Fetch a URL as text. Windows PowerShell 5.1 returns Content as a Byte[] for
# -UseBasicParsing while PowerShell 7 returns a String, so decode when needed.
# Treating the byte array as text yields the first byte value, not the body.
function Get-RemoteText {
    param([string]$Uri)
    $content = (Invoke-WebRequest -Uri $Uri -UseBasicParsing).Content
    if ($content -is [byte[]]) {
        $content = [System.Text.Encoding]::UTF8.GetString($content)
    }
    return $content
}

# Download a file and verify it against a published sha256. Verification is not
# optional: an unreachable checksum is an error, not a reason to skip the check.
# Pass -MatchName to select one line from a multi-file checksum manifest.
function Get-VerifiedFile {
    param([string]$Uri, [string]$OutFile, [string]$ChecksumUri, [string]$MatchName)

    Write-Step "downloading $(Split-Path -Leaf $Uri)"
    Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing

    try {
        $body = Get-RemoteText -Uri $ChecksumUri
    }
    catch {
        Write-Fatal "cannot fetch the checksum for $(Split-Path -Leaf $OutFile) from ${ChecksumUri}: $($_.Exception.Message)"
    }

    $expected = $null
    if ($MatchName) {
        foreach ($line in ($body -split "`n")) {
            $fields = $line.Trim() -split '\s+'
            if ($fields.Count -ge 2 -and ($fields[1] -eq $MatchName -or $fields[1] -eq "./$MatchName")) {
                $expected = $fields[0]
                break
            }
        }
    }
    else {
        $expected = ($body.Trim() -split '\s+')[0]
    }
    if ($expected -notmatch '^[0-9a-fA-F]{64}$') {
        Write-Fatal "no usable sha256 for $(Split-Path -Leaf $OutFile) in $ChecksumUri"
    }

    $actual = (Get-FileHash -Path $OutFile -Algorithm SHA256).Hash
    if ($actual.ToLower() -ne $expected.ToLower()) {
        Write-Fatal "checksum mismatch for $OutFile (expected $expected, got $actual)"
    }
    Write-Step "verified $(Split-Path -Leaf $OutFile)"
}

# ---------------------------------------------------------------------------
# Install Blender
# ---------------------------------------------------------------------------

$blenderSeries = $BlenderVersion.Substring(0, $BlenderVersion.LastIndexOf("."))
$blenderArchive = "blender-$BlenderVersion-windows-x64.zip"
$blenderZip = Join-Path $WorkDir $blenderArchive

Get-VerifiedFile -Uri "$BlenderMirror/Blender$blenderSeries/$blenderArchive" -OutFile $blenderZip `
    -ChecksumUri "$BlenderMirror/Blender$blenderSeries/blender-$BlenderVersion.sha256" `
    -MatchName $blenderArchive

# Expand into a staging directory beside the prefix and move it into place, so an
# interrupted run cannot leave a half-extracted prefix behind. Beside the prefix,
# not in $WorkDir: a cross-volume Move-Item copies rather than renames.
$extractDir = "$BlenderPrefix.staging"
if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
Expand-Archive -Path $blenderZip -DestinationPath $extractDir -Force

# The archive holds a single blender-<version>-windows-x64\ directory. Capture it
# before the move: .FullName on $null makes Move-Item throw a parameter-binding
# error before any message here could explain why.
$extracted = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
if (-not $extracted) {
    Write-Fatal "the Blender archive did not expand to a top-level directory in $extractDir"
}
if (-not (Test-Path (Join-Path $extracted.FullName "blender.exe"))) {
    Write-Fatal "the Blender archive did not contain blender.exe"
}

# Only delete a prefix that looks like one of ours: $BlenderPrefix is a constant
# you are meant to edit, and a blind recursive delete is unforgiving.
if (Test-Path $BlenderPrefix) {
    if (-not (Test-Path (Join-Path $BlenderPrefix "blender.exe"))) {
        Write-Fatal "$BlenderPrefix exists but holds no blender.exe. Refusing to delete it; check `$BlenderPrefix, and see Troubleshooting in the README if a previous run was interrupted."
    }
    Remove-Item -Recurse -Force $BlenderPrefix
}
Move-Item -Path $extracted.FullName -Destination $BlenderPrefix
Remove-Item -Recurse -Force $extractDir -ErrorAction SilentlyContinue
$blenderExe = Join-Path $BlenderPrefix "blender.exe"

# Run Blender, so one that unpacked but cannot start fails here. Capture the
# output before narrowing it: Select-Object -First 1 halts the upstream pipeline,
# which can terminate the still-running native command and leave $LASTEXITCODE
# reflecting that rather than Blender's own exit.
$blenderOutput = Get-NativeOutput { & $blenderExe --version }
if ($LASTEXITCODE -ne 0) {
    Write-Fatal "Blender installed to $BlenderPrefix but will not run: $($blenderOutput | Select-Object -First 1)"
}
Write-Step "Blender installed: $($blenderOutput | Select-Object -First 1)"

# ---------------------------------------------------------------------------
# Install the Deadline Cloud submitter
# ---------------------------------------------------------------------------

# The "latest" path always serves the current release, and its .sha256 alongside.
$submitterUrl = "$DownloadsBase/submitters/latest/windows/DeadlineCloudSubmitter-windows-x64-installer.exe"

$installer = Join-Path $WorkDir "submitter-installer.exe"
Get-VerifiedFile -Uri $submitterUrl -OutFile $installer -ChecksumUri "$submitterUrl.sha256"

# --mode unattended runs without a GUI. deadline_client (the Deadline Cloud CLI
# and libraries) is always installed; enable only the DCC components needed here.
#
# On Windows the --<dcc>-path flag takes the executable, not the install
# directory as on Linux. Values with spaces must be quoted: Start-Process joins
# -ArgumentList without quoting, so "C:\Program Files\..." would split in two.
Write-Step "installing the submitter (unattended)"
$installerArgs = @(
    "--mode", "unattended"
    "--unattendedmodeui", "none"
    "--installscope", "system"
    "--prefix", "`"$SubmitterPrefix`""
    "--enable-components", "$SubmitterComponent,$BlenderComponent"
    ("--" + $BlenderComponent.Replace("_", "-") + "-path"), "`"$blenderExe`""
)
$process = Start-Process -FilePath $installer -ArgumentList $installerArgs -Wait -PassThru -NoNewWindow
if ($process.ExitCode -ne 0) {
    Write-Fatal "the submitter installer exited with code $($process.ExitCode)"
}
Write-Step "submitter installed at $SubmitterPrefix"

# ---------------------------------------------------------------------------
# Enable the add-on in Blender
# ---------------------------------------------------------------------------

# The unattended install stages the add-on but cannot enable it, because add-ons
# live in Blender's per-user preferences while the install runs at system scope.
# Run the installer's own script to register it for this account.
$addonScript = Join-Path $SubmitterPrefix "Submitters\Blender\add_submitter_to_pref.py"
$addonPath = Join-Path $SubmitterPrefix "Submitters\Blender\python"

Write-Step "enabling the Blender add-on"
$addonOutput = Get-NativeOutput {
    & $blenderExe --background --python $addonScript -- --deadline_cloud_install_path $addonPath
}
if ($LASTEXITCODE -ne 0) {
    Write-Fatal "failed to enable the Blender add-on (exit code $LASTEXITCODE): $($addonOutput | Out-String)"
}

# Confirm from Blender's preferences rather than trusting the exit code. Use a
# script file, not --python-expr: PowerShell does not preserve the inner quotes
# of an expression passed on the command line, so Blender raises NameError.
$checkScript = Join-Path $WorkDir "check_addon.py"
Set-Content -Path $checkScript -Encoding ASCII -Value @'
import bpy
import sys

sys.exit(0 if "deadline_cloud_blender_submitter" in bpy.context.preferences.addons.keys() else 1)
'@
Get-NativeOutput { & $blenderExe --background --python $checkScript } | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fatal "the Blender add-on did not register in Blender preferences"
}
Write-Step "Blender add-on enabled"

# ---------------------------------------------------------------------------
# Install Deadline Cloud monitor and create the profile
# ---------------------------------------------------------------------------

$monitorSetupUrl = "$DownloadsBase/dcm/latest/DeadlineCloudMonitor_x64-setup.exe"
$monitorSetup = Join-Path $WorkDir "DeadlineCloudMonitor_x64-setup.exe"
Get-VerifiedFile -Uri $monitorSetupUrl -OutFile $monitorSetup -ChecksumUri "$monitorSetupUrl.sha256"

# /S is the monitor installer's silent switch.
$process = Start-Process -FilePath $monitorSetup -ArgumentList "/S" -Wait -PassThru -NoNewWindow
if ($process.ExitCode -ne 0) {
    Write-Fatal "the monitor installer exited with code $($process.ExitCode)"
}

# Find the installed executable. The installer is 32-bit, so its writes can be
# redirected into the SysWOW64 view of the profile while the InstallLocation it
# records still names System32. Neither is reliable alone, so try both.
$monitorCandidates = [System.Collections.Generic.List[string]]::new()

foreach ($key in @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*")) {
    Get-ItemProperty $key -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -eq "DeadlineCloudMonitor" -and $_.InstallLocation } |
        ForEach-Object {
            $location = $_.InstallLocation.Trim('"')
            $monitorCandidates.Add((Join-Path $location "DeadlineCloudMonitor.exe"))
            # The same path under the other WOW64 view of the profile.
            $monitorCandidates.Add((Join-Path ($location -replace '\\[Ss]ystem32\\', '\SysWOW64\') "DeadlineCloudMonitor.exe"))
        }
}
$monitorCandidates.Add((Join-Path $env:LOCALAPPDATA "DeadlineCloudMonitor\DeadlineCloudMonitor.exe"))
$monitorCandidates.Add("C:\Program Files\DeadlineCloudMonitor\DeadlineCloudMonitor.exe")

$monitorBin = $monitorCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $monitorBin) {
    Write-Fatal "cannot find DeadlineCloudMonitor.exe after install. Looked in:`n  $($monitorCandidates -join "`n  ")"
}
Write-Step "monitor installed: $monitorBin"

# create-profile needs no display. --monitor-id is required but need not be
# correct: the real ID cannot be found without AWS credentials, and the monitor
# overwrites it, along with the user and identity store IDs, at first sign-in. It
# must be non-empty though -- an empty value makes the monitor drop the profile
# from its picker and ask for the URL instead. It shows verbatim until first
# sign-in, so make it self-explanatory.
$monitorIdPlaceholder = "pending-first-login"

Write-Step "creating monitor profile '$ProfileName'"

# A direct pipeline into Out-String, not Get-NativeOutput like the calls above:
# DeadlineCloudMonitor.exe is a GUI-subsystem binary and PowerShell does not wait
# for one, so it is this pipe that forces the wait and captures the output. In a
# scriptblock the call returns instantly with nothing. The 5.1 stderr concern still
# applies, so relax $ErrorActionPreference around just this call.
$previousEap = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $profileOutput = & $monitorBin create-profile `
        --profile $ProfileName `
        --monitor-id $monitorIdPlaceholder `
        --monitor-url $MonitorUrl `
        --enable-auto-login `
        --set-as-deadline-default 2>&1 | Out-String
}
finally {
    $ErrorActionPreference = $previousEap
}

# create-profile exits 0 even when it fails, so check its output and the file.
# Report whether the file appeared: it says whether the command ran at all.
if ($profileOutput -notmatch [regex]::Escape("Created profile $ProfileName")) {
    $configPath = Join-Path $env:USERPROFILE ".aws\config"
    $configState = if (Test-Path $configPath) { "$configPath exists" } else { "$configPath does not exist" }
    Write-Fatal "failed to create the monitor profile ($configState). Output was: '$($profileOutput.Trim())'"
}

# Test for the file first: Select-String on a missing path throws
# ItemNotFoundException, so the message below would never be reached.
$awsConfig = Join-Path $env:USERPROFILE ".aws\config"
if (-not (Test-Path $awsConfig)) {
    Write-Fatal "profile $ProfileName is missing from $awsConfig (the file does not exist)"
}
if (-not (Select-String -Path $awsConfig -SimpleMatch -Pattern "[profile $ProfileName]" -Quiet)) {
    Write-Fatal "profile $ProfileName is missing from $awsConfig"
}
Write-Step "profile created and verified in $awsConfig"

# Remove the ~1 GB of downloads on success. A failed run keeps them on purpose,
# so the installer logs survive.
Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue
Write-Step "removed temporary downloads from $WorkDir"

Write-Information @"

[setup-workstation] Done.

  Blender:    $BlenderPrefix ($BlenderVersion)
  Submitter:  $SubmitterPrefix
  Monitor:    $monitorBin
  Profile:    $ProfileName ($MonitorUrl)

$env:USERNAME can now open Deadline Cloud monitor, sign in to the
'$ProfileName' profile, and submit from Blender.

"@
