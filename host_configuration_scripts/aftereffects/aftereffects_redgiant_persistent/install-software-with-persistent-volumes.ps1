Set-PSDebug -Trace 2
$ErrorActionPreference = "Stop"

# SCRIPT CONFIGURATION VARIABLES - Update these for your environment
# ------------------------------------------------------------------
$INSTALLER_S3_BUCKET = ""
$AE_VERSION = "2026"
$AE_INSTALLER = "After Effects_en_US_WIN_64.zip"

# Version identifiers - update these when upgrading software
$RED_GIANT_VERSION = "2026.3.0"
$MAXON_APP_VERSION = "2026.1.0"
$BORIS_SAPPHIRE_VERSION = "2026"
$LENSCARE_VERSION = "1.5.5"

$INSTALL_RED_GIANT = $false  # Set to $true to install Red Giant, Maxon App, and WebView2 Runtime
if ($INSTALL_RED_GIANT) {
    $WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
    $MAXON_APP_INSTALLER = "Maxon_App_${MAXON_APP_VERSION}_Win.exe"
    $RED_GIANT_INSTALLER = "RedGiant-${RED_GIANT_VERSION}-Win.exe"
    $is_cmf = $false  # Set to $true for Customer Managed Fleet (CMF)
    if ($is_cmf) { $vpc_endpoint = "" }
}

$INSTALL_BORIS_SAPPHIRE = $false  # Set to $true to install Boris FX Sapphire
if ($INSTALL_BORIS_SAPPHIRE) {
    $BORIS_SAPPHIRE_INSTALLER = "sapphire-ae-install-${BORIS_SAPPHIRE_VERSION}.exe"
    # Custom licensing required
    $BORIS_LICENSE_SERVER = "5052@"
}

$INSTALL_LENSCARE = $false  # Set to $true to install Frischluft Lenscare
if ($INSTALL_LENSCARE) {
    $LENSCARE_INSTALLER = "lenscare_ae_v${LENSCARE_VERSION}(win).zip"
    $LENSCARE_HAS_LICENSE = $true  # Set to $false to install without license (watermarked output) for dev testing
    if ($LENSCARE_HAS_LICENSE) { $LENSCARE_LICENSE = "Lenscare_ae.key" }
}

$INSTALL_RSMB = $false  # Set to $true to install RE:Vision Effects ReelSmart Motion Blur
if ($INSTALL_RSMB) {
    $RSMB_INSTALLER = "RSMB6AEInstaller.zip"
    $RSMB_HAS_LICENSE = $true  # Set to $false to install without license (watermarked output) for dev testing
    if ($RSMB_HAS_LICENSE) {
        $RSMB_LICENSING = "FloatingLicensing.zip"
        # Custom licensing required
        $RSMB_LICENSE_SERVER = ""
    }
}
# END SCRIPT CONFIGURATION SECTION
# ------------------------------------------------------------------

$AE_PLUGIN_LOCATION = "C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore"
$DOWNLOADS_PATH = "C:\Temp"
$AE_LOCATION = "C:\Program Files\Adobe\Adobe After Effects $AE_VERSION\Support Files"

# EBS Persistence - reads mount path set by EBS persistence script
$MOUNT_PATH = [Environment]::GetEnvironmentVariable("DEADLINE_PERSISTENT_MOUNT", "Machine")
if (-not $MOUNT_PATH) {
    Write-Host "WARNING: DEADLINE_PERSISTENT_MOUNT not set - no persistence"
    $PERSISTENCE_ENABLED = $false
} else {
    Write-Host "Persistent volume detected at: $MOUNT_PATH"
    $PERSISTENCE_ENABLED = $true
    $SW_PATH = "$MOUNT_PATH\Software"
    $DATA_PATH = "$MOUNT_PATH\SoftwareData"
    $SVC_BACKUP = "$MOUNT_PATH\SoftwareServices"
    $INSTALL_MARKER = "$SW_PATH\.install-complete"
}

$junctions = @()
if ($PERSISTENCE_ENABLED) {
    $junctions = @(
        @{ Link = "C:\Program Files\Adobe"; Target = "$SW_PATH\Adobe" }
        @{ Link = "C:\ProgramData\Adobe"; Target = "$DATA_PATH\Adobe" }
    )
    if ($INSTALL_RED_GIANT) {
        $junctions += @(
            @{ Link = "C:\Program Files\Maxon"; Target = "$SW_PATH\Maxon" }
            @{ Link = "C:\Program Files\Red Giant"; Target = "$SW_PATH\Red Giant" }
            @{ Link = "C:\Program Files (x86)\Microsoft\EdgeWebView"; Target = "$SW_PATH\EdgeWebView" }
            @{ Link = "C:\ProgramData\Maxon"; Target = "$DATA_PATH\Maxon" }
            @{ Link = "C:\ProgramData\Red Giant"; Target = "$DATA_PATH\Red Giant" }
        )
    }
    if ($INSTALL_BORIS_SAPPHIRE) {
        $junctions += @(
            @{ Link = "C:\Program Files\BorisFX"; Target = "$SW_PATH\BorisFX" }
            @{ Link = "C:\ProgramData\BorisFX"; Target = "$DATA_PATH\BorisFX" }
            @{ Link = "C:\ProgramData\GenArts"; Target = "$DATA_PATH\GenArts" }
        )
    }
    if ($INSTALL_RSMB) {
        $junctions += @(
            @{ Link = "C:\Program Files\REVisionEffects"; Target = "$SW_PATH\REVisionEffects" }
        )
    }
}

function Setup-Junctions {
    param([bool]$CreateTargets)
    foreach ($j in $junctions) {
        if (Test-Path $j.Link) {
            $item = Get-Item $j.Link -Force
            if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                Write-Host "Junction already exists: $($j.Link)"; continue
            }
            Remove-Item $j.Link -Recurse -Force
        }
        $parent = Split-Path $j.Link -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        if ($CreateTargets) { New-Item -ItemType Directory -Path $j.Target -Force | Out-Null }
        New-Item -ItemType Junction -Path $j.Link -Target $j.Target
        Write-Host "Junction: $($j.Link) -> $($j.Target)"
    }
}

# Snapshots Red Giant Windows service registrations to JSON on the persistent volume.
# Installers register services that are lost when a new worker boots with a fresh OS
# but reuses the same EBS volume. We save each service's binary path, start mode, and
# display name so Import-InstallerState can re-register them in seconds.
function Export-InstallerState {
    New-Item -ItemType Directory -Path $SVC_BACKUP -Force | Out-Null
    $services = Get-WmiObject Win32_Service | Where-Object {
        $_.PathName -like "*Red Giant*" -or $_.Name -like "*RedGiant*"
    }
    foreach ($svc in $services) {
        @{ Name = $svc.Name; DisplayName = $svc.DisplayName; PathName = $svc.PathName
           StartMode = $svc.StartMode; Description = $svc.Description
        } | ConvertTo-Json | Out-File "$SVC_BACKUP\$($svc.Name).json"
        Write-Host "Exported service: $($svc.Name)"
    }
}

# Re-registers Windows services from the JSON snapshots saved by Export-InstallerState.
# On subsequent boots the persistent volume already has the binaries, but the fresh OS
# has no knowledge of the services. This reads each backup, creates the service via sc.exe,
# and starts it if it was originally set to Auto start.
function Import-InstallerState {
    if (Test-Path $SVC_BACKUP) {
        foreach ($file in Get-ChildItem "$SVC_BACKUP\*.json") {
            try {
                $svcInfo = Get-Content $file.FullName | ConvertFrom-Json
                if ($svcInfo.Name -notlike "*Red Giant*") { Write-Host "Skipping service: $($svcInfo.Name)"; continue }
                $existing = Get-Service -Name $svcInfo.Name -ErrorAction SilentlyContinue
                if ($existing) { Write-Host "Service already registered: $($svcInfo.Name)" }
                else {
                    $startType = switch ($svcInfo.StartMode) { "Auto" { "auto" } "Manual" { "demand" } "Disabled" { "disabled" } default { "auto" } }
                    sc.exe create $svcInfo.Name binPath= "$($svcInfo.PathName)" start= $startType DisplayName= "$($svcInfo.DisplayName)"
                    if ($svcInfo.Description) { sc.exe description $svcInfo.Name "$($svcInfo.Description)" }
                    Write-Host "Re-registered service: $($svcInfo.Name)"
                }
                if ($svcInfo.StartMode -eq "Auto") {
                    Start-Service -Name $svcInfo.Name -ErrorAction SilentlyContinue
                    Write-Host "Started service: $($svcInfo.Name)"
                }
            } catch {
                Write-Host "WARNING: Failed to restore service $($file.Name): $_"
            }
        }
    }
}

# MAIN LOGIC
$scriptStartTime = Get-Date

Write-Host "Setting environment variables for rendering..."
[System.Environment]::SetEnvironmentVariable("AERENDER_EXECUTABLE", "$AE_LOCATION\aerender.exe", [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable("MAXON_RENDERONLY", "true", [System.EnvironmentVariableTarget]::Machine)
if ($INSTALL_RED_GIANT -and $is_cmf) {
    [System.Environment]::SetEnvironmentVariable("redshift_LICENSE", "7055@$vpc_endpoint", [System.EnvironmentVariableTarget]::Machine)
}

if ($PERSISTENCE_ENABLED -and (Test-Path $INSTALL_MARKER)) {
    Write-Host "=== SOFTWARE FOUND ON PERSISTENT VOLUME - SKIPPING INSTALL ==="
    $restoreStart = Get-Date
    Setup-Junctions -CreateTargets $false
    Import-InstallerState
    $restoreDuration = (Get-Date) - $restoreStart
    Write-Host "=== Restore completed in $($restoreDuration.ToString('hh\:mm\:ss')) ==="
    Write-Host "Total Time: $(((Get-Date) - $scriptStartTime).ToString('hh\:mm\:ss'))"
    exit 0
}

if ($PERSISTENCE_ENABLED) {
    Write-Host "=== FIRST BOOT - INSTALLING TO PERSISTENT VOLUME ==="
    Setup-Junctions -CreateTargets $true
}

$downloadStartTime = Get-Date
Write-Host "Downloading installers from S3..."
aws s3 cp --no-progress "s3://$INSTALLER_S3_BUCKET/Installers/$AE_INSTALLER" "$DOWNLOADS_PATH\$AE_INSTALLER"
if (-not (Test-Path "$DOWNLOADS_PATH\$AE_INSTALLER")) { throw "After Effects download failed" }
if ($INSTALL_RED_GIANT) {
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$RED_GIANT_INSTALLER $DOWNLOADS_PATH\$RED_GIANT_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$RED_GIANT_INSTALLER")) { throw "Red Giant download failed" }
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$MAXON_APP_INSTALLER $DOWNLOADS_PATH\$MAXON_APP_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$MAXON_APP_INSTALLER")) { throw "Maxon App download failed" }
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$WEBVIEW2_INSTALLER $DOWNLOADS_PATH\$WEBVIEW2_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$WEBVIEW2_INSTALLER")) { throw "WebView2 Runtime download failed" }
}
if ($INSTALL_BORIS_SAPPHIRE) {
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$BORIS_SAPPHIRE_INSTALLER $DOWNLOADS_PATH\$BORIS_SAPPHIRE_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$BORIS_SAPPHIRE_INSTALLER")) { throw "Boris Sapphire download failed" }
}
if ($INSTALL_LENSCARE) {
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$LENSCARE_INSTALLER $DOWNLOADS_PATH\$LENSCARE_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$LENSCARE_INSTALLER")) { throw "Lenscare download failed" }
    if ($LENSCARE_HAS_LICENSE) {
        aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$LENSCARE_LICENSE $DOWNLOADS_PATH\$LENSCARE_LICENSE
        if (-not (Test-Path "$DOWNLOADS_PATH\$LENSCARE_LICENSE")) { throw "Lenscare license download failed" }
    }
}
if ($INSTALL_RSMB) {
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$RSMB_INSTALLER $DOWNLOADS_PATH\$RSMB_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$RSMB_INSTALLER")) { throw "RSMB download failed" }
    if ($RSMB_HAS_LICENSE) {
        aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$RSMB_LICENSING $DOWNLOADS_PATH\$RSMB_LICENSING
        if (-not (Test-Path "$DOWNLOADS_PATH\$RSMB_LICENSING")) { throw "RSMB floating licensing download failed" }
    }
}
$downloadDuration = (Get-Date) - $downloadStartTime
Write-Host "Downloads completed in: $($downloadDuration.ToString('hh\:mm\:ss'))"

$aeStartTime = Get-Date
Write-Host "Installing After Effects..."
Expand-Archive -Path "$DOWNLOADS_PATH\$AE_INSTALLER" -DestinationPath $DOWNLOADS_PATH -Force
if (-not (Test-Path "$DOWNLOADS_PATH\After Effects\Build\setup.exe")) { throw "After Effects installer not found" }
Start-Process -FilePath "$DOWNLOADS_PATH\After Effects\Build\setup.exe" -ArgumentList "--silent" -Wait
$aeDuration = (Get-Date) - $aeStartTime

if ($INSTALL_RED_GIANT) {
    $webview2StartTime = Get-Date
    Write-Host "Installing WebView2 Runtime..."
    Start-Process -FilePath "$DOWNLOADS_PATH\$WEBVIEW2_INSTALLER" -ArgumentList "/silent", "/install" -Wait
    $webview2Duration = (Get-Date) - $webview2StartTime

    $maxonStartTime = Get-Date
    Write-Host "Installing Maxon App..."
    Start-Process -FilePath "$DOWNLOADS_PATH\$MAXON_APP_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
    $maxonDuration = (Get-Date) - $maxonStartTime

    $rgStartTime = Get-Date
    Write-Host "Installing Red Giant..."
    Start-Process -FilePath "$DOWNLOADS_PATH\$RED_GIANT_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
    $rgDuration = (Get-Date) - $rgStartTime
}

if ($INSTALL_BORIS_SAPPHIRE) {
    $bsStartTime = Get-Date
    Write-Host "Installing Boris Sapphire..."
    Start-Process -FilePath "$DOWNLOADS_PATH\$BORIS_SAPPHIRE_INSTALLER" -ArgumentList "/VERYSILENT" -Wait
    [System.Environment]::SetEnvironmentVariable("genarts_LICENSE", $BORIS_LICENSE_SERVER, [System.EnvironmentVariableTarget]::Machine)
    $bsDuration = (Get-Date) - $bsStartTime
}

if ($INSTALL_LENSCARE) {
    $lcStartTime = Get-Date
    Write-Host "Installing Lenscare..."
    $lenscareTempExtract = "$DOWNLOADS_PATH\lenscare_temp"
    Expand-Archive -Path "$DOWNLOADS_PATH\$LENSCARE_INSTALLER" -DestinationPath $lenscareTempExtract -Force
    Copy-Item -Path "$lenscareTempExtract\*" -Destination "$AE_PLUGIN_LOCATION" -Recurse -Force
    if ($LENSCARE_HAS_LICENSE) {
        Copy-Item -Path "$DOWNLOADS_PATH\$LENSCARE_LICENSE" -Destination "$AE_PLUGIN_LOCATION\$LENSCARE_LICENSE" -Force
    }
    $lcDuration = (Get-Date) - $lcStartTime
}

if ($INSTALL_RSMB) {
    $rsmbStartTime = Get-Date
    Write-Host "Installing RSMB..."
    $rsmbTempExtract = "$DOWNLOADS_PATH\rsmb_temp"
    Expand-Archive -Path "$DOWNLOADS_PATH\$RSMB_INSTALLER" -DestinationPath $rsmbTempExtract -Force
    $rsmbExe = Get-ChildItem -Path $rsmbTempExtract -Filter "*.exe" -Recurse | Select-Object -First 1
    if (-not $rsmbExe) { throw "RSMB installer executable not found in zip" }
    Start-Process -FilePath $rsmbExe.FullName -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
    if ($RSMB_HAS_LICENSE) {
        $rsmbLicenseTempExtract = "$DOWNLOADS_PATH\rsmb_licensing_temp"
        Expand-Archive -Path "$DOWNLOADS_PATH\$RSMB_LICENSING" -DestinationPath $rsmbLicenseTempExtract -Force
        $rsmbLicenseExe = Get-ChildItem -Path $rsmbLicenseTempExtract -Filter "*.exe" -Recurse | Select-Object -First 1
        if (-not $rsmbLicenseExe) { throw "RSMB floating license installer not found in zip" }
        Start-Process -FilePath $rsmbLicenseExe.FullName -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none", "--acceptEULA", "1", "--clientOrServer", "client" -Wait
        [System.Environment]::SetEnvironmentVariable("RVL_SERVER", $RSMB_LICENSE_SERVER, [System.EnvironmentVariableTarget]::Machine)
    }
    $rsmbDuration = (Get-Date) - $rsmbStartTime
}

if ($PERSISTENCE_ENABLED) {
    Export-InstallerState
    Get-Date -Format "yyyy-MM-dd HH:mm:ss" | Out-File $INSTALL_MARKER
    Write-Host "Install marker written - subsequent boots will skip installation"
}

$totalDuration = (Get-Date) - $scriptStartTime
Write-Host "=== Installation Summary ==="
Write-Host "Downloads: $($downloadDuration.ToString('hh\:mm\:ss'))"
Write-Host "After Effects: $($aeDuration.ToString('hh\:mm\:ss'))"
if ($INSTALL_RED_GIANT) { Write-Host "WebView2: $($webview2Duration.ToString('hh\:mm\:ss')), Maxon: $($maxonDuration.ToString('hh\:mm\:ss')), Red Giant: $($rgDuration.ToString('hh\:mm\:ss'))" }
if ($INSTALL_BORIS_SAPPHIRE) { Write-Host "Boris Sapphire: $($bsDuration.ToString('hh\:mm\:ss'))" }
if ($INSTALL_LENSCARE) { Write-Host "Lenscare: $($lcDuration.ToString('hh\:mm\:ss'))" }
if ($INSTALL_RSMB) { Write-Host "RSMB: $($rsmbDuration.ToString('hh\:mm\:ss'))" }
Write-Host "Total: $($totalDuration.ToString('hh\:mm\:ss'))"
Write-Host "All installations completed!"
