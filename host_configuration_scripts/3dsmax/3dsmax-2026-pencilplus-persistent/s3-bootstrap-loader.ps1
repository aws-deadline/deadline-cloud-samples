<#
S3 bootstrap loader for AWS Deadline Cloud host configuration.

Purpose: the inline host-configuration "scriptBody" stored on a fleet is limited to 15,000
characters. This tiny loader stays well under that limit. Paste it as the fleet's inline
host-configuration script. On every worker boot it downloads the REAL host-configuration
script from S3 and runs it, so the actual script can be any size and can be updated by simply
re-uploading the object to S3 (no fleet configuration change required).

How to use:
1. Upload your full host-configuration script to S3, for example:
     aws s3 cp 3dsmax-2026.ps1 s3://your-bucket-name/DeadlineCloud/host-config/3dsmax-2026.ps1
2. Set $HC_SCRIPT_S3_URI below to that object.
3. Paste THIS loader as the fleet's inline host-configuration script.

Requirements:
- The fleet role must have s3:GetObject on the script object (and on any installers the
  downloaded script fetches).

Notes:
- Pin/version the S3 object. A bad or missing object will fail every worker's boot, so treat
  updates to it with the same care as the fleet configuration itself.
- The downloaded script runs as SYSTEM with -ExecutionPolicy Bypass. Write access to the script
  object is therefore equivalent to SYSTEM code execution on every worker that boots afterward.
  Restrict s3:PutObject on it to your deployment or administrator principal. The fleet role needs
  s3:GetObject and must NOT have s3:PutObject on it: the fleet role is the identity every worker
  runs as, so granting it write access here would let a single compromised worker reach persistent
  SYSTEM on the whole fleet. Nothing at runtime writes this object, so it can stay read-only to
  the fleet. Enable bucket versioning.
#>

$ErrorActionPreference = "Stop"

# TODO: Replace with the S3 URI of your full host-configuration script.
$HC_SCRIPT_S3_URI = "s3://your-bucket-name/DeadlineCloud/host-config/3dsmax-2026.ps1"

# Running as SYSTEM, $env:TEMP is C:\Windows\Temp, which grants write access to any authenticated
# user. Use a dedicated directory with inheritance switched off so an unprivileged process cannot
# pre-place a script at the path this loader is about to execute.
$workDir = Join-Path $env:ProgramData "deadline-host-config"
# Refuse to reuse a reparse point. New-Item -Force is a no-op on an existing junction, and Get-Acl and
# Set-Acl follow it, so an unprivileged process could point this name at a directory it controls and
# the hardening below would be applied to that target instead. Creating a junction needs no privilege.
# Delete the link only, never recurse into the target.
$existing = Get-Item $workDir -Force -ErrorAction SilentlyContinue
if ($existing -and ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) { $existing.Delete() }
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$acl = Get-Acl $workDir
$acl.SetAccessRuleProtection($true, $false)
foreach ($rule in @($acl.Access)) { $acl.RemoveAccessRuleAll($rule) | Out-Null }
foreach ($id in "NT AUTHORITY\SYSTEM", "BUILTIN\Administrators") {
    $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
        $id, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")))
}
# Reset the owner too. C:\ProgramData lets any user create a subdirectory and grants CREATOR OWNER
# full control of it, and an owner keeps WRITE_DAC implicitly whatever the DACL says. Without this an
# unprivileged process could pre-create the directory, then re-grant itself write access after the
# DACL is reset and plant a script this loader runs as SYSTEM.
$acl.SetOwner((New-Object System.Security.Principal.NTAccount("NT AUTHORITY\SYSTEM")))
Set-Acl -Path $workDir -AclObject $acl

$dest = Join-Path $workDir "deadline-host-config.ps1"
$part = "$dest.part"

Write-Host " --- Downloading host configuration script from S3 --- "
# Download to a temporary name, then move into place, so a truncated transfer never runs. A partial
# PowerShell script parses and executes the part that arrived, which would silently do half the work
# and exit 0. Clearing both paths first means no earlier copy can be mistaken for this boot's.
Remove-Item $dest, $part -Force -ErrorAction SilentlyContinue
aws s3 cp --no-progress "$HC_SCRIPT_S3_URI" "$part"
if ($LASTEXITCODE -ne 0) { throw "Failed to download host configuration script from $HC_SCRIPT_S3_URI (exit $LASTEXITCODE)" }
if (-not (Test-Path $part)) { throw "Host configuration script was not downloaded to $part" }
if ((Get-Item $part).Length -eq 0) { throw "Downloaded host configuration script is empty: $HC_SCRIPT_S3_URI" }
Move-Item $part $dest -Force

Write-Host " --- Running downloaded host configuration script --- "
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$dest"
$code = $LASTEXITCODE

Write-Host " --- Downloaded host configuration script exited with code $code --- "
exit $code
