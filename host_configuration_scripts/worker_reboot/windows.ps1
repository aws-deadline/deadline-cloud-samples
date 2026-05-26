Write-Host "=== Deadline Cloud Reboot Script Example ==="
Write-Host "Checking if host already rebooted"

if (Test-Path "C:\deadline-rebooted") { 
   Write-Host "SUCCESS: Host already rebooted. Ready to start."
   exit 0 
}

Write-Host "Host has not been rebooted yet"
Write-Host "Creating marker file: C:\deadline-rebooted"
New-Item "C:\deadline-rebooted" -ItemType File | Out-Null

Write-Host "Rebooting host..."
Restart-Computer -Force
Start-Sleep 60
exit 1
