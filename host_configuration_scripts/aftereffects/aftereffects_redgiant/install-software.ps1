# Sequential Software Installation Script
# Downloads installers from S3 and installs Adobe After Effects, Red Giant, Boris Sapphire (optional),
# Lenscare (optional), and RSMB (optional) in order
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

# MAIN LOGIC
$scriptStartTime = Get-Date

Write-Host "Setting environment variables for rendering..."
[System.Environment]::SetEnvironmentVariable("AERENDER_EXECUTABLE", "$AE_LOCATION\aerender.exe", [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable("MAXON_RENDERONLY", "true", [System.EnvironmentVariableTarget]::Machine)
if ($INSTALL_RED_GIANT -and $is_cmf) {
    [System.Environment]::SetEnvironmentVariable("redshift_LICENSE", "7055@$vpc_endpoint", [System.EnvironmentVariableTarget]::Machine)
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
