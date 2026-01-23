# =============================================================================
# CONFIGURATION - Adjust these values based on your workload requirements
# =============================================================================
$RAM_MULTIPLIER = 2              # Page file size as multiple of RAM (e.g., 2 = 2x RAM)
$NVME_SPACE_PERCENTAGE = 0.75    # Max percentage of NVMe space to use for the page file (e.g., 0.75 = 75%)
$MIN_DISK_SIZE_GB = 1            # Minimum disk size in GB to consider for storing page file
$MARKER_FILE_PATH = "C:\deadline-pagefile-configured"
# =============================================================================

Write-Host "=== Deadline Cloud Page File Configuration Script ==="
Write-Host "Checking if host already rebooted after page file configuration"

if (Test-Path $MARKER_FILE_PATH) { 
   Write-Host "SUCCESS: Page file already configured and rebooted. Ready to start."
   Write-Host "=== Current Page File Configuration (After Reboot) ==="
   $cs = Get-WmiObject Win32_ComputerSystem
   Write-Host "  Automatic Management: $($cs.AutomaticManagedPagefile)"
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
$targetPageFileSizeMB = [math]::Round($ram * $RAM_MULTIPLIER)
Write-Host "Detected RAM: $([math]::Round($ram))MB"
Write-Host "Target page file size: ${targetPageFileSizeMB}MB (${RAM_MULTIPLIER}x RAM)"

# Scan all disks (including unformatted)
Write-Host "Scanning all disks for page file placement..."
$allDisks = Get-Disk | Where-Object { !$_.IsBoot -and $_.Size -gt ($MIN_DISK_SIZE_GB * 1GB) }
Write-Host "Found $($allDisks.Count) non-boot disks larger than ${MIN_DISK_SIZE_GB}GB"

$nvmeDisk = $null
$largestDisk = $null

foreach ($disk in $allDisks) {
   $sizeGB = [math]::Round($disk.Size / 1GB, 2)
   
   try {
       $diskInfo = Get-WmiObject -Class Win32_DiskDrive | Where-Object { $_.Index -eq $disk.Number }
       
       if ($diskInfo) {
           $isLocalNVMe = $diskInfo.Model -like "*Amazon EC2 NVMe*"
           Write-Host "  Disk $($disk.Number): ${sizeGB}GB, Model: $($diskInfo.Model), PartitionStyle: $($disk.PartitionStyle), Local NVMe: $isLocalNVMe"
           
           if ($isLocalNVMe -and !$nvmeDisk) {
               $nvmeDisk = $disk
               Write-Host "    -> Detected as local NVMe instance storage (preferred)"
           }
       } else {
           Write-Host "  Disk $($disk.Number): ${sizeGB}GB, PartitionStyle: $($disk.PartitionStyle), Model: Unknown"
       }
   } catch {
       Write-Host "  Disk $($disk.Number): ${sizeGB}GB, Could not determine disk type"
   }
   
   if (!$largestDisk -or $disk.Size -gt $largestDisk.Size) {
       $largestDisk = $disk
   }
}

# Select disk and calculate page file size
$selectedDisk = $null
$pageFileSizeMB = $targetPageFileSizeMB

if ($nvmeDisk) {
   $nvmeMaxPageFileMB = [math]::Round(($nvmeDisk.Size / 1MB) * $NVME_SPACE_PERCENTAGE)
   $pageFileSizeMB = [math]::Min($targetPageFileSizeMB, $nvmeMaxPageFileMB)
   $selectedDisk = $nvmeDisk
   $nvmePercentDisplay = [math]::Round($NVME_SPACE_PERCENTAGE * 100)
   Write-Host "Using local NVMe: min(${RAM_MULTIPLIER}x RAM: ${targetPageFileSizeMB}MB, ${nvmePercentDisplay}% NVMe: ${nvmeMaxPageFileMB}MB) = ${pageFileSizeMB}MB"
} elseif ($largestDisk) {
   Write-Host "No local NVMe instance storage found - using largest available non-boot disk with ${RAM_MULTIPLIER}x RAM"
   $selectedDisk = $largestDisk
   $pageFileSizeMB = $targetPageFileSizeMB
} else {
   # Fall back to boot drive if no non-boot drives available
   Write-Host "No non-boot disks found - falling back to boot drive (C:)"
   $driveLetter = 'C'
   $pageFileSizeMB = $targetPageFileSizeMB
}

if (!$selectedDisk -and !$driveLetter) {
   Write-Error "ERROR: No suitable disk found for page file"
   exit 1
}

# Initialize and format disk if needed (skip if using boot drive)
if ($selectedDisk) {
   Write-Host "Selected disk: Disk $($selectedDisk.Number) ($([math]::Round($selectedDisk.Size / 1GB, 2))GB)"
   
   if ($selectedDisk.PartitionStyle -eq 'RAW') {
       Write-Host "Disk $($selectedDisk.Number) is RAW - initializing and formatting..."
       
       # Find available drive letter (prefer D, then E, F, etc.)
       $usedLetters = Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Name
       $availableLetters = 68..90 | ForEach-Object { [char]$_ } | Where-Object { $_ -notin $usedLetters }
       $driveLetter = $availableLetters[0]
       
       Write-Host "Using drive letter: ${driveLetter}:"
       
       Initialize-Disk -Number $selectedDisk.Number -PartitionStyle GPT -Confirm:$false
       $partition = New-Partition -DiskNumber $selectedDisk.Number -UseMaximumSize -DriveLetter $driveLetter
       Format-Volume -Partition $partition -FileSystem NTFS -NewFileSystemLabel "PageFile" -Confirm:$false
       Write-Host "Disk formatted successfully as ${driveLetter}:"
   } else {
       Write-Host "Disk already initialized - checking for drive letter..."
       $partition = Get-Partition -DiskNumber $selectedDisk.Number | Where-Object { $_.Type -eq 'Basic' } | Select-Object -First 1
       
       if ($partition.DriveLetter) {
           $driveLetter = $partition.DriveLetter
           Write-Host "Using existing drive letter: ${driveLetter}:"
       } else {
           # Assign drive letter
           $usedLetters = Get-PSDrive -PSProvider FileSystem | Select-Object -ExpandProperty Name
           $availableLetters = 68..90 | ForEach-Object { [char]$_ } | Where-Object { $_ -notin $usedLetters }
           $driveLetter = $availableLetters[0]
           
           Write-Host "Assigning drive letter: ${driveLetter}:"
           Set-Partition -DiskNumber $selectedDisk.Number -PartitionNumber $partition.PartitionNumber -NewDriveLetter $driveLetter
       }
   }
}

Write-Host "Final page file size: ${pageFileSizeMB}MB on ${driveLetter}:"

# Disable automatic page file management
Write-Host "Disabling automatic page file management..."
$cs.AutomaticManagedPagefile = $false
$cs.Put() | Out-Null

# Show page file settings after disabling automatic management
Write-Host "=== Page File Settings After Disabling Automatic Management ==="
$pageFilesAfterDisable = Get-WmiObject Win32_PageFileSetting
if ($pageFilesAfterDisable) {
   foreach ($pf in $pageFilesAfterDisable) {
       Write-Host "  Location: $($pf.Name)"
       Write-Host "  Initial Size: $($pf.InitialSize)MB"
       Write-Host "  Maximum Size: $($pf.MaximumSize)MB"
   }
} else {
   Write-Host "  No page files configured"
}

# Remove existing page files
Write-Host "Removing existing page files..."
if ($pageFilesAfterDisable) {
   foreach ($pf in $pageFilesAfterDisable) {
       Write-Host "  Removing: $($pf.Name)"
       $pf.Delete()
   }
}

# Create new page file
Write-Host "Creating new page file: ${driveLetter}:\pagefile.sys"
$newPf = ([wmiclass]"Win32_PageFileSetting").CreateInstance()
$newPf.Name = "${driveLetter}:\pagefile.sys"
$newPf.InitialSize = $pageFileSizeMB
$newPf.MaximumSize = $pageFileSizeMB
$newPf.Put() | Out-Null

# Show AFTER state (before reboot)
Write-Host "=== AFTER: New Page File Configuration (Pending Reboot) ==="
$cs = Get-WmiObject Win32_ComputerSystem
Write-Host "  Automatic Management: $($cs.AutomaticManagedPagefile)"
Get-WmiObject Win32_PageFileSetting | ForEach-Object {
   Write-Host "  Location: $($_.Name)"
   Write-Host "  Initial Size: $($_.InitialSize)MB"
   Write-Host "  Maximum Size: $($_.MaximumSize)MB"
}

# Create marker file
Write-Host "Creating marker file: $MARKER_FILE_PATH"
New-Item $MARKER_FILE_PATH -ItemType File | Out-Null

Write-Host "=== Configuration Complete - Rebooting ==="
Restart-Computer -Force
Start-Sleep 60
exit 1
