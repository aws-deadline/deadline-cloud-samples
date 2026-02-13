# Sequential Software Installation Script
# Downloads installers from S3 and installs Adobe After Effects, Red Giant, Universe, Boris Sapphire (optional), and Lenscare (optional) in order

# Stop after first failing command
$ErrorActionPreference = "Stop"

# Script Configuration Variables - Update these for your environment
$is_cmf = $false  # Set to $true for Customer Managed Fleet (CMF), $false for Service Managed Fleet (SMF)
$vpc_endpoint = "<vpc_endpoint>"  # Replace with actual VPC endpoint for CMF Red Giant license server
$AE_VERSION = "2025"  # After Effects version year
$INSTALLER_S3_BUCKET = "<your-installer-bucket>"  # Your S3 bucket name
$AE_INSTALLER = "After Effects_en_US_WIN_64.zip"
$REDGIANT_INSTALLER = "RedGiant-2026.3.0-Win.exe"
$UNIVERSE_INSTALLER = "Universe-2026.0.1_Win.exe"
$MAXON_APP_INSTALLER = "Maxon_App_2026.1.0_Win.exe"
$WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"

# Optional Plugin Configuration
$INSTALL_BORIS_SAPPHIRE = $false  # Set to $true to install Boris FX Sapphire
$BORIS_SAPPHIRE_INSTALLER = "sapphire-ae-install-2026.exe"
# custom licensing is required for Boris FX, as it is not currently supported by Deadline Cloud Usage Based Licensing
$BORIS_LICENSE_SERVER = "5053@<license-server-hostname>"

$INSTALL_LENSCARE = $false  # Set to $true to install Frischluft Lenscare
$LENSCARE_INSTALLER = "lenscare_ae_v1.5.5(win).zip"
$LENSCARE_LICENSE = "Lenscare_ae.key"

$AE_PLUGIN_LOCATION = "C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore"
$DOWNLOADS_PATH = "C:\Temp"

# Derived paths (do not modify)
$AE_LOCATION = "C:\Program Files\Adobe\Adobe After Effects $AE_VERSION\Support Files"

# Start overall timing
$scriptStartTime = Get-Date

# Set render-only env variable for Maxon One to pick up and aerender.exe path variable for submitter
Write-Host "Setting environment variables for rendering..."
[System.Environment]::SetEnvironmentVariable("AERENDER_EXECUTABLE", "$AE_LOCATION\aerender.exe", [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable("MAXON_RENDERONLY", "true", [System.EnvironmentVariableTarget]::Machine)

# Download installers from S3
$downloadStartTime = Get-Date
Write-Host "Downloading installers from S3..."
aws s3 cp --no-progress "s3://$INSTALLER_S3_BUCKET/Installers/$AE_INSTALLER" "$DOWNLOADS_PATH\$AE_INSTALLER"
if (-not (Test-Path "$DOWNLOADS_PATH\$AE_INSTALLER")) { throw "After Effects download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$REDGIANT_INSTALLER $DOWNLOADS_PATH\$REDGIANT_INSTALLER
if (-not (Test-Path "$DOWNLOADS_PATH\$REDGIANT_INSTALLER")) { throw "Red Giant download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$MAXON_APP_INSTALLER $DOWNLOADS_PATH\$MAXON_APP_INSTALLER
if (-not (Test-Path "$DOWNLOADS_PATH\$MAXON_APP_INSTALLER")) { throw "Maxon App download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$UNIVERSE_INSTALLER $DOWNLOADS_PATH\$UNIVERSE_INSTALLER
if (-not (Test-Path "$DOWNLOADS_PATH\$UNIVERSE_INSTALLER")) { throw "Universe download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$WEBVIEW2_INSTALLER $DOWNLOADS_PATH\$WEBVIEW2_INSTALLER
if (-not (Test-Path "$DOWNLOADS_PATH\$WEBVIEW2_INSTALLER")) { throw "WebView2 Runtime download failed" }

if ($INSTALL_BORIS_SAPPHIRE) {
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$BORIS_SAPPHIRE_INSTALLER $DOWNLOADS_PATH\$BORIS_SAPPHIRE_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$BORIS_SAPPHIRE_INSTALLER")) { throw "Boris Sapphire download failed" }
}

if ($INSTALL_LENSCARE) {
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$LENSCARE_INSTALLER $DOWNLOADS_PATH\$LENSCARE_INSTALLER
    if (-not (Test-Path "$DOWNLOADS_PATH\$LENSCARE_INSTALLER")) { throw "Lenscare download failed" }
    aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$LENSCARE_LICENSE $DOWNLOADS_PATH\$LENSCARE_LICENSE
    if (-not (Test-Path "$DOWNLOADS_PATH\$LENSCARE_LICENSE")) { throw "Lenscare license download failed" }
}

$downloadEndTime = Get-Date
$downloadDuration = $downloadEndTime - $downloadStartTime
Write-Host "Downloads completed in: $($downloadDuration.ToString('hh\:mm\:ss'))"

# Microsoft Edge WebView2 Runtime Installation
$webview2StartTime = Get-Date
Write-Host "Starting Microsoft Edge WebView2 Runtime installation..."
Start-Process -FilePath "$DOWNLOADS_PATH\$WEBVIEW2_INSTALLER" -ArgumentList "/silent", "/install" -Wait
$webview2EndTime = Get-Date
$webview2Duration = $webview2EndTime - $webview2StartTime
Write-Host "Microsoft Edge WebView2 Runtime installation completed in: $($webview2Duration.ToString('hh\:mm\:ss'))"

# After Effects Installation
$aeStartTime = Get-Date
Write-Host "Extracting After Effects zip file..."
Expand-Archive -Path "$DOWNLOADS_PATH\$AE_INSTALLER" -DestinationPath $DOWNLOADS_PATH -Force
Write-Host "Starting After Effects installation..."
if (-not (Test-Path "$DOWNLOADS_PATH\After Effects\Build\setup.exe")) { throw "After Effects installer not found" }
Start-Process -FilePath "$DOWNLOADS_PATH\After Effects\Build\setup.exe" -ArgumentList "--silent" -Wait
$aeEndTime = Get-Date
$aeDuration = $aeEndTime - $aeStartTime
Write-Host "After Effects installation completed in: $($aeDuration.ToString('hh\:mm\:ss'))"

# Maxon App Installation
$maxonStartTime = Get-Date
Write-Host "Starting Maxon App installation..."
Start-Process -FilePath "$DOWNLOADS_PATH\$MAXON_APP_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
$maxonEndTime = Get-Date
$maxonDuration = $maxonEndTime - $maxonStartTime
Write-Host "Maxon App installation completed in: $($maxonDuration.ToString('hh\:mm\:ss'))"

# Red Giant Installation
$rgStartTime = Get-Date
Write-Host "Starting Red Giant installation..."
Start-Process -FilePath "$DOWNLOADS_PATH\$REDGIANT_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
$rgEndTime = Get-Date
$rgDuration = $rgEndTime - $rgStartTime
Write-Host "Red Giant installation completed in: $($rgDuration.ToString('hh\:mm\:ss'))"

# Set Red Giant license servers for Customer Managed Fleets (CMF)
if ($is_cmf) {
    Write-Host "Setting Red Giant license server for CMF..."
    [System.Environment]::SetEnvironmentVariable("redshift_LICENSE", "7055@$vpc_endpoint", [System.EnvironmentVariableTarget]::Machine)
}

# Universe Installation
$universeStartTime = Get-Date
Write-Host "Starting Universe installation..."
Start-Process -FilePath "$DOWNLOADS_PATH\$UNIVERSE_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
$universeEndTime = Get-Date
$universeDuration = $universeEndTime - $universeStartTime
Write-Host "Universe installation completed in: $($universeDuration.ToString('hh\:mm\:ss'))"

if ($INSTALL_BORIS_SAPPHIRE) {
    # Boris FX Sapphire Installation
    $bsStartTime = Get-Date
    Write-Host "Starting Boris Sapphire installation..."
    if (-not (Test-Path "$DOWNLOADS_PATH\$BORIS_SAPPHIRE_INSTALLER")) { throw "Boris Sapphire installer not found" }
    Start-Process -FilePath "$DOWNLOADS_PATH\$BORIS_SAPPHIRE_INSTALLER" -ArgumentList "/VERYSILENT" -Wait

    Write-Host "Setting Boris FX license server..."
    [System.Environment]::SetEnvironmentVariable("genarts_LICENSE", $BORIS_LICENSE_SERVER, [System.EnvironmentVariableTarget]::Machine)

    $bsEndTime = Get-Date
    $bsDuration = $bsEndTime - $bsStartTime
    Write-Host "Boris Sapphire installation completed in: $($bsDuration.ToString('hh\:mm\:ss'))"
}

if ($INSTALL_LENSCARE) {
    # Lenscare Installation
    $lenscareStartTime = Get-Date
    Write-Host "Extracting Lenscare zip file..."
    if (-not (Test-Path "$DOWNLOADS_PATH\$LENSCARE_INSTALLER")) { throw "Lenscare zip file not found" }
    $lenscareTempExtract = "$DOWNLOADS_PATH\lenscare_temp"
    Expand-Archive -Path "$DOWNLOADS_PATH\$LENSCARE_INSTALLER" -DestinationPath $lenscareTempExtract -Force
    Write-Host "Starting Lenscare installation..."
    Copy-Item -Path "$lenscareTempExtract\*" -Destination "$AE_PLUGIN_LOCATION" -Recurse -Force
    Write-Host "Copying Lenscare license file..."
    if (-not (Test-Path "$DOWNLOADS_PATH\$LENSCARE_LICENSE")) { throw "Lenscare license file not found" }
    Copy-Item -Path "$DOWNLOADS_PATH\$LENSCARE_LICENSE" -Destination "$AE_PLUGIN_LOCATION\$LENSCARE_LICENSE" -Force
    $lenscareEndTime = Get-Date
    $lenscareDuration = $lenscareEndTime - $lenscareStartTime
    Write-Host "Lenscare installation completed in: $($lenscareDuration.ToString('hh\:mm\:ss'))"
}

# Calculate and display total time
$scriptEndTime = Get-Date
$totalDuration = $scriptEndTime - $scriptStartTime
Write-Host "=== Installation Summary ==="
Write-Host "Downloads: $($downloadDuration.ToString('hh\:mm\:ss'))"
Write-Host "WebView2 Runtime: $($webview2Duration.ToString('hh\:mm\:ss'))"
Write-Host "After Effects: $($aeDuration.ToString('hh\:mm\:ss'))"
Write-Host "Maxon App: $($maxonDuration.ToString('hh\:mm\:ss'))"
Write-Host "Red Giant: $($rgDuration.ToString('hh\:mm\:ss'))"
Write-Host "Universe: $($universeDuration.ToString('hh\:mm\:ss'))"
if ($INSTALL_BORIS_SAPPHIRE) {
    Write-Host "Boris Sapphire: $($bsDuration.ToString('hh\:mm\:ss'))"
}
if ($INSTALL_LENSCARE) {
    Write-Host "Lenscare: $($lenscareDuration.ToString('hh\:mm\:ss'))"
}
Write-Host "Total Time: $($totalDuration.ToString('hh\:mm\:ss'))"
Write-Host "All installations completed!"
