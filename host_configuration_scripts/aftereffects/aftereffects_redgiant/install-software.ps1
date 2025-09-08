# Sequential Software Installation Script
# Downloads installers from S3 and installs Adobe After Effects, Red Giant, and Universe in order
$ErrorActionPreference = "Stop"

# Script Configuration Variables - Update these for your environment
$is_cmf = $false  # Set to $true for Customer Managed Fleet (CMF), $false for Service Managed Fleet (SMF)
$vpc_endpoint = "<vpc_endpoint>"  # Replace with actual VPC endpoint for CMF Red Giant license server
$AE_VERSION = "2025"  # After Effects version year
$INSTALLER_S3_BUCKET = "<your-installer-bucket>"  # Your S3 bucket name
$AE_INSTALLER = "After Effects_en_US_WIN_64.zip"
$REDGIANT_INSTALLER = "RedGiant-2025.6.0-Win.exe"
$UNIVERSE_INSTALLER = "Universe-2025.3.3_Win.exe"
$MAXON_APP_INSTALLER = "Maxon_App_2025.4.2_Win.exe"
$WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"

# Derived paths (do not modify)
$AE_LOCATION = "C:\Program Files\Adobe\Adobe After Effects $AE_VERSION\Support Files"
$downloadsPath = "C:\Temp"

# Start overall timing
$scriptStartTime = Get-Date

# Set render-only env variable for Maxon One to pick up and aerender.exe path variable for submitter
Write-Host "Setting environment variables for rendering..."
[System.Environment]::SetEnvironmentVariable("AERENDER_EXECUTABLE", "$AE_LOCATION\aerender.exe", [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable("MAXON_RENDERONLY", "true", [System.EnvironmentVariableTarget]::Machine)

# Download installers from S3
$downloadStartTime = Get-Date
Write-Host "Downloading installers from S3..."
aws s3 cp --no-progress "s3://$INSTALLER_S3_BUCKET/Installers/$AE_INSTALLER" "$downloadsPath\$AE_INSTALLER"
if (-not (Test-Path "$downloadsPath\$AE_INSTALLER")) { throw "After Effects download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$REDGIANT_INSTALLER $downloadsPath\$REDGIANT_INSTALLER
if (-not (Test-Path "$downloadsPath\$REDGIANT_INSTALLER")) { throw "Red Giant download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$MAXON_APP_INSTALLER $downloadsPath\$MAXON_APP_INSTALLER
if (-not (Test-Path "$downloadsPath\$MAXON_APP_INSTALLER")) { throw "Maxon App download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$UNIVERSE_INSTALLER $downloadsPath\$UNIVERSE_INSTALLER
if (-not (Test-Path "$downloadsPath\$UNIVERSE_INSTALLER")) { throw "Universe download failed" }
aws s3 cp --no-progress s3://$INSTALLER_S3_BUCKET/Installers/$WEBVIEW2_INSTALLER $downloadsPath\$WEBVIEW2_INSTALLER
if (-not (Test-Path "$downloadsPath\$WEBVIEW2_INSTALLER")) { throw "WebView2 Runtime download failed" }
$downloadEndTime = Get-Date
$downloadDuration = $downloadEndTime - $downloadStartTime
Write-Host "Downloads completed in: $($downloadDuration.ToString('hh\:mm\:ss'))"

# Microsoft Edge WebView2 Runtime Installation
$webview2StartTime = Get-Date
Write-Host "Starting Microsoft Edge WebView2 Runtime installation..."
Start-Process -FilePath "$downloadsPath\$WEBVIEW2_INSTALLER" -ArgumentList "/silent", "/install" -Wait
$webview2EndTime = Get-Date
$webview2Duration = $webview2EndTime - $webview2StartTime
Write-Host "Microsoft Edge WebView2 Runtime installation completed in: $($webview2Duration.ToString('hh\:mm\:ss'))"

# After Effects Installation
$aeStartTime = Get-Date
Write-Host "Extracting After Effects zip file..."
Expand-Archive -Path "$downloadsPath\$AE_INSTALLER" -DestinationPath $downloadsPath -Force
Write-Host "Starting After Effects installation..."
if (-not (Test-Path "$downloadsPath\After Effects\Build\setup.exe")) { throw "After Effects installer not found" }
Start-Process -FilePath "$downloadsPath\After Effects\Build\setup.exe" -ArgumentList "--silent" -Wait
$aeEndTime = Get-Date
$aeDuration = $aeEndTime - $aeStartTime
Write-Host "After Effects installation completed in: $($aeDuration.ToString('hh\:mm\:ss'))"

# Maxon App Installation
$maxonStartTime = Get-Date
Write-Host "Starting Maxon App installation..."
Start-Process -FilePath "$downloadsPath\$MAXON_APP_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
$maxonEndTime = Get-Date
$maxonDuration = $maxonEndTime - $maxonStartTime
Write-Host "Maxon App installation completed in: $($maxonDuration.ToString('hh\:mm\:ss'))"

# Red Giant Installation
$rgStartTime = Get-Date
Write-Host "Starting Red Giant installation..."
Start-Process -FilePath "$downloadsPath\$REDGIANT_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
$rgEndTime = Get-Date
$rgDuration = $rgEndTime - $rgStartTime
Write-Host "Red Giant installation completed in: $($rgDuration.ToString('hh\:mm\:ss'))"

# Universe Installation
$universeStartTime = Get-Date
Write-Host "Starting Universe installation..."
Start-Process -FilePath "$downloadsPath\$UNIVERSE_INSTALLER" -ArgumentList "--mode", "unattended", "--unattendedmodeui", "none" -Wait
$universeEndTime = Get-Date
$universeDuration = $universeEndTime - $universeStartTime
Write-Host "Universe installation completed in: $($universeDuration.ToString('hh\:mm\:ss'))"

# Set Red Giant license server for Customer Managed Fleet (CMF)
if ($is_cmf) {
    Write-Host "Setting Red Giant license server for CMF..."
    [System.Environment]::SetEnvironmentVariable("redshift_LICENSE", "7055@$vpc_endpoint", [System.EnvironmentVariableTarget]::Machine)
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
Write-Host "Total Time: $($totalDuration.ToString('hh\:mm\:ss'))"
Write-Host "All installations completed!"
