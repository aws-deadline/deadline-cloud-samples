# Downloads installers from S3 and installs Maxon App and Red Giant
$ErrorActionPreference = "Stop"

# Script Configuration Variables - Update these for your environment
$INSTALLER_S3_BUCKET = "<your-installer-bucket>"  # Wour S3 bucket name
$REDGIANT_INSTALLER = "RedGiant-2026.0.0-Win.exe"
$MAXON_APP_INSTALLER = "Maxon_App_2026.0.0_Win.exe"
$WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"

$DOWNLOADS_PATH = "C:\Temp"

# Start overall timing
$scriptStartTime = Get-Date

# Download installers from S3
$downloadStartTime = Get-Date
Write-Host "Downloading installers from S3..."
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$REDGIANT_INSTALLER $DOWNLOADS_PATH\$REDGIANT_INSTALLER
if (-not (Test-Path "$DOWNLOADS_PATH\$REDGIANT_INSTALLER")) { throw "Red Giant download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$MAXON_APP_INSTALLER $DOWNLOADS_PATH\$MAXON_APP_INSTALLER
if (-not (Test-Path "$DOWNLOADS_PATH\$MAXON_APP_INSTALLER")) { throw "Maxon App download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$WEBVIEW2_INSTALLER $DOWNLOADS_PATH\$WEBVIEW2_INSTALLER
if (-not (Test-Path "$DOWNLOADS_PATH\$WEBVIEW2_INSTALLER")) { throw "WebView2 Runtime download failed" }
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

# Calculate and display total time
$scriptEndTime = Get-Date
$totalDuration = $scriptEndTime - $scriptStartTime
Write-Host "=== Installation Summary ==="
Write-Host "Downloads: $($downloadDuration.ToString('hh\:mm\:ss'))"
Write-Host "WebView2 Runtime: $($webview2Duration.ToString('hh\:mm\:ss'))"
Write-Host "Maxon App: $($maxonDuration.ToString('hh\:mm\:ss'))"
Write-Host "Red Giant: $($rgDuration.ToString('hh\:mm\:ss'))"
Write-Host "Total Time: $($totalDuration.ToString('hh\:mm\:ss'))"
Write-Host "All installations completed!"
