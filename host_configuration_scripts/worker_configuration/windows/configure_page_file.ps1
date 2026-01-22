Write-Host "=== Deadline Cloud Page File Configuration Script ==="
Write-Host "Checking if host already rebooted after page file configuration"

if (Test-Path "C:\deadline-pagefile-configured") { 
   Write-Host "SUCCESS: Page file already configured and rebooted. Ready to start."
   Write-Host "=== Current Page File Configuration (After Reboot) ==="
   Get-WmiObject Win32_PageFileSetting | ForEach-Object {
       Write-Host "  Location: $($_.Name)"
       Write-Host "  Initial Size: $($_.InitialSize)MB"
       Write-Host "  Maximum Size: $($_.MaximumSize)MB"
   }
   exit 0 
}

Write-Host "Host has not been rebooted yet. Starting page file configuration..."

# Show BEFORE state
Write-Host "=== BEFORE: Current Page File Configuration ==="
$cs = Get-WmiObject Win32_ComputerSystem
Write-Host "  Automatic Management: $($cs.AutomaticManagedPagefile)"
$existingPageFiles = Get-WmiObject Win32_PageFileSetting
if ($existingPageFiles) {
   foreach ($pf in $existingPageFiles) {
       Write-Host "  Location: $($pf.Name)"
       Write-Host "  Initial Size: $($pf.InitialSize)MB"
       Write-Host "  Maximum Size: $($pf.MaximumSize)MB"
   }
} else {
   Write-Host "  No page files configured"
}

# Get RAM info
$ram = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB
$pageFileSizeMB = [math]::Round($ram * 2)
Write-Host "Detected RAM: $([math]::Round($ram))MB"
Write-Host "Target page file size: ${pageFileSizeMB}MB (2x RAM)"

# Find best drive
Write-Host "Scanning drives for page file placement..."
$drives = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Free -gt 0 }
foreach ($d in $drives) {
   $freeGB = [math]::Round($d.Free / 1GB, 2)
   Write-Host "  Drive $($d.Name): ${freeGB}GB free"
}

$bestDrive = $drives | 
   Where-Object { $_.Free -gt ($pageFileSizeMB * 1MB * 1.1) } | 
   Sort-Object Free -Descending | 
   Select-Object -First 1

if (-not $bestDrive) {
   Write-Error "ERROR: No drive with sufficient space for ${pageFileSizeMB}MB page file"
   exit 1
}

$drive = $bestDrive.Name
Write-Host "Selected drive: ${drive}: ($([math]::Round($bestDrive.Free / 1GB, 2))GB free)"

# Disable automatic page file management
Write-Host "Disabling automatic page file management..."
$cs.AutomaticManagedPagefile = $false
$cs.Put() | Out-Null

# Remove existing page files
Write-Host "Removing existing page files..."
if ($existingPageFiles) {
   foreach ($pf in $existingPageFiles) {
       Write-Host "  Removing: $($pf.Name)"
       $pf.Delete()
   }
}

# Create new page file
Write-Host "Creating new page file: ${drive}:\pagefile.sys"
$newPf = ([wmiclass]"Win32_PageFileSetting").CreateInstance()
$newPf.Name = "${drive}:\pagefile.sys"
$newPf.InitialSize = $pageFileSizeMB
$newPf.MaximumSize = $pageFileSizeMB
$newPf.Put() | Out-Null

# Show AFTER state (before reboot)
Write-Host "=== AFTER: New Page File Configuration (Pending Reboot) ==="
Get-WmiObject Win32_PageFileSetting | ForEach-Object {
   Write-Host "  Location: $($_.Name)"
   Write-Host "  Initial Size: $($_.InitialSize)MB"
   Write-Host "  Maximum Size: $($_.MaximumSize)MB"
}

# Create marker file
Write-Host "Creating marker file: C:\deadline-pagefile-configured"
New-Item "C:\deadline-pagefile-configured" -ItemType File | Out-Null

Write-Host "=== Configuration Complete - Rebooting ==="
Restart-Computer -Force
Start-Sleep 60
exit 0