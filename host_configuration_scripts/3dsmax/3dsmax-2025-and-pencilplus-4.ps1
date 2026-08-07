<#
This is an example host configuration script that downloads and installs
3ds Max 2025 and Pencil+ 4 for 3ds Max 2025.

You can configure a Windows Service-Managed Fleet to use this host configuration
to render your 3ds Max 2025 + Pencil+ jobs via 3dsmaxcmd.exe.

Pencil+ (NTR) renders watermark-free without consuming a license when 3ds Max
runs as a render server, which 3dsmaxcmd.exe is. No license server configuration
is therefore required for the command-line render path.

Pencil+ installer notes:
- The Pencil+ 4 for 3ds Max installer is built with Inno Setup. Its silent-install
  switches are /VERYSILENT (no wizard UI), /SUPPRESSMSGBOXES (no blocking dialogs),
  /NORESTART (don't reboot the worker), and /SP- (skip the initial prompt).
- Do NOT use /S — that is the NSIS silent switch and is ignored by Inno Setup.
  Using it makes the installer show its GUI wizard, which hangs a headless worker
  until the host configuration script times out.

This script was tested with the 3ds Max 2025.3 installer.

Requirements:
- S3 bucket to host the 3ds Max 2025 and Pencil+ installers
- Your fleet role must have permissions to s3:GetObject all the installer files
  from your S3 bucket.
#>

# TODO: Replace the below values with your S3 URIs
# Guide on how to create the 3ds Max installer zip file:
# https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket-name/path/to/3ds-Max-2025.zip"
# TODO: Replace with the Pencil+ 4 installer S3 URI
# Download the NTR edition from PSOFT: https://www.psoft.co.jp/en/download/
$PENCILPLUS_INSTALLER_S3_URI="s3://your-bucket-name/path/to/setup_Pencil+_4.2.7_for_3dsMax_ntr.exe"

# Derive the installer filename from the URI so changes stay in sync.
$PENCIL_INSTALLER_FILE = Split-Path $PENCILPLUS_INSTALLER_S3_URI -Leaf

# The Pencil+ installer is built with Inno Setup, whose silent switches are
# /VERYSILENT (no wizard UI) and /SUPPRESSMSGBOXES (no blocking dialogs).
# NOTE: '/S' is the NSIS switch and is IGNORED by Inno Setup — using it makes the
# installer show its GUI wizard and hang a headless worker until the HC times out.
$PENCIL_SILENT_ARGS = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-")

Write-Host ' --- Installing 3ds Max 2025 --- '
mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "$3DS_MAX_INSTALLER_ZIP_S3_URI" C:\3dsmax_setup\3dsmax.zip
if ($LASTEXITCODE -ne 0) { throw "Failed to download 3ds Max installer from S3. Check the URI and fleet IAM role." }

Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\

if (-not (Test-Path "C:\3dsmax_setup\Setup.exe")) {
    throw "Setup.exe not found at C:\3dsmax_setup\Setup.exe after extracting the zip. Ensure the zip contains files at the root (not nested in a subfolder)."
}
Start-Process "C:\3dsmax_setup\Setup.exe" -ArgumentList '-q' -Wait -PassThru

Write-Host ' --- Downloading Pencil+ installer --- '
aws s3 cp --no-progress "$PENCILPLUS_INSTALLER_S3_URI" C:\3dsmax_setup\
if ($LASTEXITCODE -ne 0) { throw "Failed to download Pencil+ installer from S3. Check the URI and fleet IAM role." }

Write-Host ' --- Installing Pencil+ 4 for 3ds Max 2025 --- '
# Inno Setup exit codes: 0 = installed successfully. 5 = "Setup was cancelled",
# which in /VERYSILENT mode also occurs when the same Pencil+ version is already
# installed (silent maintenance mode can't prompt, so it aborts) — treat that as
# already-provisioned, not a failure. The exit code is intentionally not checked
# here so re-runs / warm workers don't fail host configuration.
Start-Process "C:\3dsmax_setup\$PENCIL_INSTALLER_FILE" -ArgumentList $PENCIL_SILENT_ARGS -Wait -PassThru

Write-Host ' --- Configuring environment for 3ds Max 2025 --- '
[Environment]::SetEnvironmentVariable('Path',
    'C:\Program Files\Autodesk\3ds Max 2025;' +
    [Environment]::GetEnvironmentVariable('Path', 'Machine'),
    'Machine')

# The command-line render path invokes 3dsmaxcmd.exe (the render server), which
# is what lets Pencil+ render without a watermark.
[Environment]::SetEnvironmentVariable('MAXCMD_EXECUTABLE',
    'C:\Program Files\Autodesk\3ds Max 2025\3dsmaxcmd.exe',
    'Machine')
[Environment]::SetEnvironmentVariable('3DSMAX_EXECUTABLE',
    'C:\Program Files\Autodesk\3ds Max 2025\3dsmaxbatch.exe',
    'Machine')
[Environment]::SetEnvironmentVariable('PYTHONPATH',
    'C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts',
    'Machine')
[Environment]::SetEnvironmentVariable('Path',
    'C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts;' +
    [Environment]::GetEnvironmentVariable('Path', 'Machine'),
    'Machine')

Write-Host ' --- Verifying Pencil+ installation --- '
$pluginsDir = "C:\Program Files\Autodesk\3ds Max 2025\plugins"
$found = Get-ChildItem $pluginsDir -Filter "*Pencil*" -ErrorAction SilentlyContinue
if ($found) {
    Write-Host "Pencil+ plugin files detected:"
    $found | ForEach-Object { Write-Host "  $($_.Name)" }
} else {
    # Hard-fail host configuration if Pencil+ did not install. Without this the
    # worker would come online missing the plugin, and every render of a scene
    # with a Pencil+ render element would crash with an opaque "unexpected
    # exception has occurred in the network renderer" error. Failing here makes
    # the missing plugin obvious at provision time instead.
    throw "Pencil+ plugin not found in $pluginsDir after install. Check the installer file name and silent-install flags."
}

Write-Host ' --- Installing Deadline Cloud for 3ds Max --- '
& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m pip install deadline-cloud-for-3ds-max

Exit 0
