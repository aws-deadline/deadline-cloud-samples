<#
.SYNOPSIS
    Pre-configure a Windows virtual workstation for AWS Deadline Cloud submission.

.DESCRIPTION
    Installs Blender, the Deadline Cloud submitter for Blender, and Deadline Cloud
    monitor, then creates a monitor profile so an artist only has to sign in.

    Run as Administrator during instance provisioning (user data, AMI bake, or by
    hand).

    Deadline Cloud monitor, its profile, and Blender's add-on preferences are all
    per user. Run this script in an elevated session as the artist's own account so
    they land in the right home directory. To install only the machine-wide parts
    from a different admin account, pass -SkipMonitor.

.PARAMETER WorkstationUser
    Local user who signs in to the monitor. Must match the account running the
    script for the per-user steps to apply. Defaults to the invoking user.

.PARAMETER MonitorUrl
    Monitor URL, for example https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/

.PARAMETER ProfileName
    AWS profile name to create. Defaults to <subdomain>-<region> from the monitor URL.

.PARAMETER MonitorId
    Monitor ID (monitor-<32 hex characters>). When omitted, the script calls
    deadline:ListMonitors to discover it. See "Monitor ID discovery" in the README.

.PARAMETER BlenderVersion
    Blender version to install. Default: 4.5.0

.PARAMETER BlenderMirror
    Base URL for Blender downloads. Default: https://download.blender.org/release

.EXAMPLE
    .\setup_workstation_windows.ps1 -MonitorUrl https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/
#>

#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$MonitorUrl,

    [string]$ProfileName,
    [string]$MonitorId,
    [string]$WorkstationUser,
    [string]$BlenderVersion = "4.5.0",
    [string]$BlenderMirror = "https://download.blender.org/release",

    [switch]$SkipBlender,
    [switch]$SkipSubmitter,
    [switch]$SkipMonitor
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Much faster Invoke-WebRequest downloads
$InformationPreference = "Continue"       # Show progress messages during provisioning

$DownloadsBase = "https://downloads.deadlinecloud.amazonaws.com"
$SubmitterManifest = "$DownloadsBase/submitters/manifest.json"
$MonitorSetupUrl = "$DownloadsBase/dcm/latest/DeadlineCloudMonitor_x64-setup.exe"

$BlenderPrefix = "C:\Program Files\Blender"
$SubmitterPrefix = "C:\Program Files\DeadlineCloudSubmitter"

function Write-Step { param([string]$Message) Write-Information "[setup-workstation] $Message" }
function Write-Warn { param([string]$Message) Write-Warning "[setup-workstation] $Message" }
function Write-Fatal { param([string]$Message) throw "[setup-workstation] ERROR: $Message" }

if (-not $SkipMonitor -and [string]::IsNullOrWhiteSpace($MonitorUrl)) {
    Write-Fatal "-MonitorUrl is required unless -SkipMonitor is given"
}

# ---------------------------------------------------------------------------
# Resolve the workstation user
# ---------------------------------------------------------------------------

if ([string]::IsNullOrWhiteSpace($WorkstationUser)) {
    $WorkstationUser = $env:USERNAME
}
Write-Step "workstation user: $WorkstationUser"

# ---------------------------------------------------------------------------
# Parse the monitor URL into subdomain and region
# ---------------------------------------------------------------------------

$MonitorSubdomain = ""
$MonitorRegion = ""

if (-not [string]::IsNullOrWhiteSpace($MonitorUrl)) {
    # Monitor URLs are https://<subdomain>.<region>.deadlinecloud.amazonaws.com/
    $monitorHost = ([System.Uri]$MonitorUrl).Host
    if ($monitorHost -match '^([a-z0-9-]+)\.([a-z0-9-]+)\.deadlinecloud\.amazonaws\.com$') {
        $MonitorSubdomain = $Matches[1]
        $MonitorRegion = $Matches[2]
    }
    else {
        Write-Fatal "monitor URL must look like https://<subdomain>.<region>.deadlinecloud.amazonaws.com/ (got: $MonitorUrl)"
    }
    if ([string]::IsNullOrWhiteSpace($ProfileName)) {
        $ProfileName = "$MonitorSubdomain-$MonitorRegion"
    }
    Write-Step "monitor: subdomain=$MonitorSubdomain region=$MonitorRegion profile=$ProfileName"
}

$WorkDir = Join-Path $env:TEMP "deadline-workstation-setup"
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

function Get-RemoteFile {
    param([string]$Uri, [string]$OutFile)
    Write-Step "downloading $(Split-Path -Leaf $Uri)"
    Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing
}

# Fetch a URL as text. Windows PowerShell 5.1 returns Content as a Byte[] for
# -UseBasicParsing, while PowerShell 7 returns a String, so decode when needed.
# Treating the byte array as text yields the first byte value instead of the body.
function Get-RemoteText {
    param([string]$Uri)
    $content = (Invoke-WebRequest -Uri $Uri -UseBasicParsing).Content
    if ($content -is [byte[]]) {
        $content = [System.Text.Encoding]::UTF8.GetString($content)
    }
    return $content
}

# The submitter publishes "<sha256>  <filename>" alongside each installer.
function Assert-Sha256 {
    param([string]$Path, [string]$ChecksumUri)
    try {
        $expected = ((Get-RemoteText -Uri $ChecksumUri).Trim() -split '\s+')[0]
    }
    catch {
        Write-Warn "no checksum published at $ChecksumUri, skipping verification"
        return
    }
    # The published checksum is lowercase but Get-FileHash returns uppercase, so
    # compare case-insensitively. -ne on strings is already case-insensitive in
    # PowerShell, but normalize both sides to make that independent of the operator.
    $actual = (Get-FileHash -Path $Path -Algorithm SHA256).Hash
    if ($actual.ToLower() -ne $expected.ToLower()) {
        Write-Fatal "checksum mismatch for $Path (expected $expected, got $actual)"
    }
    Write-Step "checksum verified: $(Split-Path -Leaf $Path)"
}

# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

# The submitter installer expects a Blender install path per version, and only
# supports specific versions. Map "4.5.0" to the installer's blender-45 flags.
$BlenderSeries = ""
$BlenderComponent = ""
if (-not $SkipBlender -or -not $SkipSubmitter) {
    $versionParts = $BlenderVersion.Split(".")
    $BlenderSeries = "$($versionParts[0]).$($versionParts[1])"
    $BlenderComponent = switch ($BlenderSeries) {
        "3.6" { "blender_36" }
        "4.0" { "blender_4" }
        "4.1" { "blender_41" }
        "4.2" { "blender_42" }
        "4.3" { "blender_43" }
        "4.4" { "blender_44" }
        "4.5" { "blender_45" }
        "5.0" { "blender_5" }
        "5.1" { "blender_51" }
        default { Write-Fatal "the Deadline Cloud submitter does not support Blender $BlenderSeries" }
    }
}

if (-not $SkipBlender) {
    Write-Step "installing Blender $BlenderVersion"
    $blenderArchive = "blender-$BlenderVersion-windows-x64.zip"
    $blenderZip = Join-Path $WorkDir $blenderArchive
    Get-RemoteFile -Uri "$BlenderMirror/Blender$BlenderSeries/$blenderArchive" -OutFile $blenderZip

    if (Test-Path $BlenderPrefix) {
        Remove-Item -Recurse -Force $BlenderPrefix
    }
    $extractDir = Join-Path $WorkDir "blender-extract"
    if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
    Expand-Archive -Path $blenderZip -DestinationPath $extractDir -Force

    # The archive contains a single blender-<version>-windows-x64\ directory.
    $inner = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
    Move-Item -Path $inner.FullName -Destination $BlenderPrefix

    $blenderExe = Join-Path $BlenderPrefix "blender.exe"
    if (-not (Test-Path $blenderExe)) {
        Write-Fatal "expected blender.exe at $blenderExe after extraction"
    }
    Write-Step "Blender installed at $BlenderPrefix"
}

# ---------------------------------------------------------------------------
# Deadline Cloud submitter
# ---------------------------------------------------------------------------

if (-not $SkipSubmitter) {
    Write-Step "resolving the latest submitter installer from the manifest"
    # The manifest records the latest version per platform and the installer path
    # under each version. Resolve both so the download is a pinned, checksummed
    # artifact rather than a moving "latest" URL.
    $manifest = Get-RemoteText -Uri $SubmitterManifest | ConvertFrom-Json
    $root = $manifest.DeadlineCloudSubmitter
    $submitterVersion = $root.latest.windows

    $node = $root.versions
    foreach ($part in $submitterVersion.Split(".")) {
        $node = $node.$part
    }
    $node = $node.windows
    Write-Step "submitter version: $submitterVersion"

    $installer = Join-Path $WorkDir "DeadlineCloudSubmitter-windows-x64-installer.exe"
    Get-RemoteFile -Uri "$DownloadsBase/submitters$($node.installer)" -OutFile $installer
    if ($node.sha256) {
        Assert-Sha256 -Path $installer -ChecksumUri "$DownloadsBase/submitters$($node.sha256)"
    }

    Write-Step "installing the submitter for Blender $BlenderSeries (unattended)"
    # --mode unattended runs without a GUI. Enabling only the Blender components
    # keeps the install to the submitter this workstation needs; deadline_client
    # (the Deadline Cloud CLI and libraries) is always installed.
    #
    # On Windows the --blender-<version>-path flag expects the full path to
    # blender.exe, not the install directory. The installer's own default is
    # "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe". The Linux
    # installer takes the directory instead, so the two scripts differ here.
    #
    # Values containing spaces must be double-quoted. Start-Process joins
    # -ArgumentList with spaces without quoting, so an unquoted
    # "C:\Program Files\..." reaches the installer as two arguments.
    $blenderPathFlag = "--" + $BlenderComponent.Replace("_", "-") + "-path"
    $blenderExePath = Join-Path $BlenderPrefix "blender.exe"
    $installerArgs = @(
        "--mode", "unattended"
        "--unattendedmodeui", "none"
        "--installscope", "system"
        "--prefix", "`"$SubmitterPrefix`""
        "--enable-components", "deadline_cloud_for_blender,$BlenderComponent"
        $blenderPathFlag, "`"$blenderExePath`""
    )
    $process = Start-Process -FilePath $installer -ArgumentList $installerArgs -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) {
        Write-Fatal "the submitter installer exited with code $($process.ExitCode)"
    }
    Write-Step "submitter installed at $SubmitterPrefix"

    # The unattended install stages the add-on under the submitter prefix but does
    # not enable it: the add-on lives in Blender's per-user preferences, which the
    # system-scope installer cannot write. Register it by running the installer's
    # own script through Blender in background mode. This writes the preferences of
    # the account running the script, so it must be the artist's account.
    if (-not $SkipBlender) {
        $addonScript = Join-Path $SubmitterPrefix "Submitters\Blender\add_submitter_to_pref.py"
        $addonPath = Join-Path $SubmitterPrefix "Submitters\Blender\python"
        if ($WorkstationUser -ne $env:USERNAME) {
            Write-Warn ("skipping add-on registration: Blender preferences are per user and " +
                "this session runs as '$env:USERNAME', not '$WorkstationUser'")
            Write-Warn "run the following in an elevated session as ${WorkstationUser}:"
            Write-Warn ("  & '$(Join-Path $BlenderPrefix "blender.exe")' --background " +
                "--python '$addonScript' -- --deadline_cloud_install_path '$addonPath'")
        }
        elseif (Test-Path $addonScript) {
            Write-Step "enabling the Blender add-on"
            # add_submitter_to_pref.py appends to Blender's script directory list
            # without checking for an existing entry, so running this script more
            # than once leaves duplicate paths in the artist's preferences. The
            # add-on still loads correctly; the duplicates are cosmetic.
            $blenderExe = Join-Path $BlenderPrefix "blender.exe"
            & $blenderExe --background --python $addonScript -- --deadline_cloud_install_path $addonPath
            if ($LASTEXITCODE -ne 0) {
                Write-Fatal "failed to enable the Blender add-on (exit code $LASTEXITCODE)"
            }

            # Confirm the add-on is enabled rather than trusting the exit code above.
            # Use a script file rather than --python-expr: PowerShell does not preserve
            # the inner double quotes of an expression passed on the command line, so
            # Blender receives a bare identifier and raises NameError. Blender does
            # propagate the script's sys.exit status, so the exit code is meaningful.
            $checkScript = Join-Path $WorkDir "check_addon.py"
            Set-Content -Path $checkScript -Encoding ASCII -Value @'
import bpy
import sys

enabled = "deadline_cloud_blender_submitter" in bpy.context.preferences.addons.keys()
print("deadline_cloud_blender_submitter enabled:", enabled)
sys.exit(0 if enabled else 1)
'@
            & $blenderExe --background --python $checkScript | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Fatal "the Blender add-on did not register in Blender preferences"
            }
            Write-Step "Blender add-on enabled"
        }
        else {
            Write-Warn "$addonScript not found; enable the add-on manually"
        }
    }
    else {
        Write-Warn "Blender was skipped, so the add-on was not enabled in Blender preferences"
    }
}

# ---------------------------------------------------------------------------
# Deadline Cloud monitor
# ---------------------------------------------------------------------------

if (-not $SkipMonitor) {
    # The monitor installs per user under %LOCALAPPDATA% and create-profile writes
    # into %USERPROFILE%, so both act on whichever account runs this script. Windows
    # cannot run them as another local user without that user's password, so refuse
    # to continue rather than write the profile into the wrong home directory.
    if ($WorkstationUser -ne $env:USERNAME) {
        Write-Fatal ("the monitor and its profile install per user, so run this script " +
            "in an elevated session as '$WorkstationUser' (currently '$env:USERNAME'), " +
            "or use -SkipMonitor and create the profile in that user's session")
    }

    Write-Step "installing Deadline Cloud monitor"
    $monitorSetup = Join-Path $WorkDir "DeadlineCloudMonitor_x64-setup.exe"
    Get-RemoteFile -Uri $MonitorSetupUrl -OutFile $monitorSetup

    # /S is the monitor installer's silent switch.
    $process = Start-Process -FilePath $monitorSetup -ArgumentList "/S" -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) {
        Write-Fatal "the monitor installer exited with code $($process.ExitCode)"
    }

    $userProfilePath = $env:USERPROFILE

    # Resolve the executable from the uninstall registry entry the installer writes.
    # Guessing paths is unreliable: the installer normally lands in
    # %LOCALAPPDATA%\DeadlineCloudMonitor, but under a 32-bit host process it
    # redirects into the SysWOW64 view of the profile, and an MSI install goes to
    # Program Files. The registry records wherever it actually went.
    $monitorBin = $null
    $uninstallKeys = @(
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($key in $uninstallKeys) {
        $entry = Get-ItemProperty $key -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName -eq "DeadlineCloudMonitor" -and $_.InstallLocation } |
            Select-Object -First 1
        if ($entry) {
            $candidate = Join-Path $entry.InstallLocation.Trim('"') "DeadlineCloudMonitor.exe"
            if (Test-Path $candidate) { $monitorBin = $candidate; break }
        }
    }

    if (-not $monitorBin) {
        # Fall back to the documented locations, including the SysWOW64 profile view.
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA "DeadlineCloudMonitor\DeadlineCloudMonitor.exe"),
            "C:\Program Files\DeadlineCloudMonitor\DeadlineCloudMonitor.exe",
            "$env:SystemRoot\SysWOW64\config\systemprofile\AppData\Local\DeadlineCloudMonitor\DeadlineCloudMonitor.exe",
            "$env:SystemRoot\System32\config\systemprofile\AppData\Local\DeadlineCloudMonitor\DeadlineCloudMonitor.exe"
        )
        $monitorBin = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    }

    if (-not $monitorBin) {
        Write-Fatal "cannot find DeadlineCloudMonitor.exe after install"
    }
    Write-Step "monitor installed: $monitorBin"

    # -----------------------------------------------------------------------
    # Monitor ID discovery
    # -----------------------------------------------------------------------
    # create-profile requires a monitor ID. It stores whatever it is given and
    # replaces it with the authoritative value on the artist's first sign-in, so
    # a placeholder still produces a working profile. Prefer the real ID when
    # credentials are available so the profile is correct before anyone signs in.
    if ([string]::IsNullOrWhiteSpace($MonitorId)) {
        if (Get-Command aws -ErrorAction SilentlyContinue) {
            Write-Step "looking up the monitor ID with deadline:ListMonitors"
            try {
                $query = "monitors[?subdomain=='$MonitorSubdomain'].monitorId | [0]"
                $discovered = (& aws deadline list-monitors --region $MonitorRegion --query $query --output text 2>$null)
                if ($discovered -and $discovered -ne "None") {
                    $MonitorId = $discovered.Trim()
                }
            }
            catch {
                Write-Warn "deadline:ListMonitors lookup failed: $($_.Exception.Message)"
            }
        }
    }
    if ([string]::IsNullOrWhiteSpace($MonitorId)) {
        # 32 zeros is a syntactically valid placeholder that first sign-in replaces.
        $MonitorId = "monitor-00000000000000000000000000000000"
        Write-Warn "monitor ID not discovered; using a placeholder"
        Write-Warn "the artist's first sign-in replaces it with the real monitor ID"
    }
    Write-Step "monitor ID: $MonitorId"

    # -----------------------------------------------------------------------
    # Create the profile
    # -----------------------------------------------------------------------
    # create-profile is a non-GUI subcommand: it writes the profile and exits
    # without needing a desktop session.
    Write-Step "creating monitor profile '$ProfileName'"
    $createArgs = @(
        "create-profile"
        "--profile", $ProfileName
        "--monitor-id", $MonitorId
        "--monitor-url", $MonitorUrl
        "--enable-auto-login"
        "--set-as-deadline-default"
    )
    $profileOutput = & $monitorBin @createArgs 2>&1 | Out-String

    # create-profile exits 0 even when it fails, so confirm from its output.
    if ($profileOutput -notmatch [regex]::Escape("Created profile $ProfileName")) {
        Write-Information $profileOutput
        Write-Fatal "failed to create the monitor profile"
    }
    Write-Step $profileOutput.Trim()

    $awsConfig = Join-Path $userProfilePath ".aws\config"
    if (-not (Test-Path $awsConfig)) {
        Write-Fatal "expected $awsConfig after create-profile"
    }
    if (-not (Select-String -Path $awsConfig -Pattern ([regex]::Escape("[profile $ProfileName]")) -Quiet)) {
        Write-Fatal "profile $ProfileName missing from $awsConfig"
    }
    Write-Step "verified the profile in $awsConfig"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

$blenderSummary = if ($SkipBlender) { "skipped" } else { "$BlenderPrefix (blender $BlenderVersion)" }
$submitterSummary = if ($SkipSubmitter) { "skipped" } else { "$SubmitterPrefix (Blender $BlenderSeries)" }
$monitorSummary = if ($SkipMonitor) { "skipped" } else { $monitorBin }
$profileSummary = if ($SkipMonitor) { "skipped" } else { "$ProfileName ($MonitorUrl)" }

$nextSteps = if ($SkipMonitor) {
    @"
No monitor profile was created. Re-run without -SkipMonitor, passing
-MonitorUrl, before the artist can submit jobs.
"@
}
else {
    @"
What the artist does next:
  1. Open Deadline Cloud monitor and sign in to the '$ProfileName' profile.
  2. Open Blender. The Deadline Cloud add-on submits to the farm using that profile.
"@
}

Write-Information @"

[setup-workstation] Workstation setup complete.

  Blender:    $blenderSummary
  Submitter:  $submitterSummary
  Monitor:    $monitorSummary
  Profile:    $profileSummary

$nextSteps

"@
