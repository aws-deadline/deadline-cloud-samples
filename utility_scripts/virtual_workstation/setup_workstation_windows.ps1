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

# The Deadline Cloud submitter supports specific Blender versions. This is the
# installer component for the version above; see "Adapting to another DCC".
$BlenderComponent = "blender_45"

# download.blender.org rejects some automated clients, so this points at an
# official mirror. See https://mirror.blender.org/ for alternatives.
$BlenderMirror = "https://mirrors.iu13.net/blender/release"

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
#   1. $BlenderComponent above. Run "<installer> --help" for the current
#      --enable-components values, for example deadline_cloud_for_maya or
#      deadline_cloud_for_houdini plus a version component like houdini_20_5.
#   2. The "Install Blender" step. Commercial DCCs need a vendor installer and
#      usually a license server, so replace that block entirely.
#   3. The "Enable the add-on in Blender" step. It is Blender-specific. Other
#      DCCs are wired up by the installer itself or by an environment variable
#      such as MAYA_MODULE_PATH or NUKE_PATH, so you can often delete it.

function Write-Step { param([string]$Message) Write-Information "[setup-workstation] $Message" }
function Write-Fatal { param([string]$Message) throw "[setup-workstation] ERROR: $Message" }

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

# The Region segment is required. The monitor accepts a URL without it and then
# writes a profile with a wrong region, so reject that here instead.
$monitorHost = ([System.Uri]$MonitorUrl).Host
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

if (Test-Path $BlenderPrefix) { Remove-Item -Recurse -Force $BlenderPrefix }
$extractDir = Join-Path $WorkDir "blender-extract"
if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
Expand-Archive -Path $blenderZip -DestinationPath $extractDir -Force

# The archive contains a single blender-<version>-windows-x64\ directory.
Move-Item -Path (Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1).FullName -Destination $BlenderPrefix
$blenderExe = Join-Path $BlenderPrefix "blender.exe"
if (-not (Test-Path $blenderExe)) {
    Write-Fatal "expected blender.exe at $blenderExe after extraction"
}
Write-Step "Blender installed at $BlenderPrefix"

# ---------------------------------------------------------------------------
# Install the Deadline Cloud submitter
# ---------------------------------------------------------------------------

# The manifest maps "latest" to a concrete version, so the download is a pinned,
# checksummed artifact rather than a moving target.
Write-Step "resolving the latest submitter from the manifest"
$manifest = Get-RemoteText -Uri "$DownloadsBase/submitters/manifest.json" | ConvertFrom-Json
$root = $manifest.DeadlineCloudSubmitter
$submitterVersion = $root.latest.windows
$node = $root.versions
foreach ($part in $submitterVersion.Split(".")) { $node = $node.$part }
$node = $node.windows
Write-Step "submitter version: $submitterVersion"

$installer = Join-Path $WorkDir "submitter-installer.exe"
Get-VerifiedFile -Uri "$DownloadsBase/submitters$($node.installer)" -OutFile $installer `
    -ChecksumUri "$DownloadsBase/submitters$($node.sha256)"

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
    "--enable-components", "deadline_cloud_for_blender,$BlenderComponent"
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
& $blenderExe --background --python $addonScript -- --deadline_cloud_install_path $addonPath | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fatal "failed to enable the Blender add-on (exit code $LASTEXITCODE)"
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
& $blenderExe --background --python $checkScript | Out-Null
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

# Resolve the executable from the uninstall registry entry the installer writes.
# Guessing paths is unreliable: the installer normally lands in
# %LOCALAPPDATA%\DeadlineCloudMonitor, but under a 32-bit host process it
# redirects into the SysWOW64 view of the profile. The registry records where it
# actually went.
$monitorBin = $null
foreach ($key in @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*")) {
    $entry = Get-ItemProperty $key -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -eq "DeadlineCloudMonitor" -and $_.InstallLocation } |
        Select-Object -First 1
    if ($entry) {
        $candidate = Join-Path $entry.InstallLocation.Trim('"') "DeadlineCloudMonitor.exe"
        if (Test-Path $candidate) { $monitorBin = $candidate; break }
    }
}
if (-not $monitorBin) {
    Write-Fatal "cannot find DeadlineCloudMonitor.exe after install"
}
Write-Step "monitor installed: $monitorBin"

# create-profile is a non-GUI subcommand: it writes the profile and exits without
# needing a display.
#
# --monitor-id is required but is left empty here. The monitor overwrites it, along
# with the user and identity store IDs, using authoritative values from the portal
# on the artist's first sign-in. Looking it up in advance needs AWS credentials and
# deadline:ListMonitors permission, so this example does without.
Write-Step "creating monitor profile '$ProfileName'"
$profileOutput = & $monitorBin create-profile `
    --profile $ProfileName `
    --monitor-id "" `
    --monitor-url $MonitorUrl `
    --enable-auto-login `
    --set-as-deadline-default 2>&1 | Out-String

# create-profile exits 0 even when it fails, so confirm from its output and then
# from the file it should have written.
if ($profileOutput -notmatch [regex]::Escape("Created profile $ProfileName")) {
    Write-Fatal "failed to create the monitor profile: $profileOutput"
}
$awsConfig = Join-Path $env:USERPROFILE ".aws\config"
if (-not (Select-String -Path $awsConfig -SimpleMatch -Pattern "[profile $ProfileName]" -Quiet)) {
    Write-Fatal "profile $ProfileName is missing from $awsConfig"
}
Write-Step "profile created and verified in $awsConfig"

Write-Information @"

[setup-workstation] Done.

  Blender:    $BlenderPrefix ($BlenderVersion)
  Submitter:  $SubmitterPrefix
  Monitor:    $monitorBin
  Profile:    $ProfileName ($MonitorUrl)

$env:USERNAME can now open Deadline Cloud monitor, sign in to the
'$ProfileName' profile, and submit from Blender.

"@
