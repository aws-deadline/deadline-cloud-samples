<#
This is an example host configuration script that downloads and installs 3ds Max 2025,
V-Ray for 3ds Max 2025, Forest Pack, RailClone, and additional plugins.
You can configure a Windows Service-Managed Fleet to use this host configuration to
render your 3ds Max 2025 + V-Ray + Forest Pack + RailClone jobs.
This script was tested with the 3ds Max 2025.2, V-Ray 7 update 2, Forest Pack Pro 9.2.1, and RailClone Pro 6.4.2 installers.

Requirements:
- S3 bucket to host 3ds Max 2025, V-Ray, Forest Pack, RailClone, and plugin installers
- Your fleet role must have permissions to s3:GetObject all the installer files from your S3 bucket.
#>

# TODO: Replace the below value with your S3 URI from your bucket
# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket-name/path/to/3ds-max-2025.zip"
# TODO: Replace the below value with your S3 URI from your bucket
$VRAY_FOR_3DSMAX2025_INSTALLER_EXE_S3_URI="s3://your-bucket-name/path/to/vray_adv_71000_max2025_x64.exe"
# TODO: Replace the below value with your S3 URI from your bucket
$FOREST_PACK_INSTALLER_EXE_S3_URI="s3://your-bucket-name/path/to/ForestPackPro921_x64.exe"
# TODO: Replace the below value with your S3 URI from your bucket
$RAILCLONE_INSTALLER_EXE_S3_URI="s3://your-bucket-name/path/to/RailClonePro642.exe"
# TODO: Replace the below value with your S3 URI from your bucket
$FLOORGENERATOR_PLUGIN_S3_URI="s3://your-bucket-name/path/to/FloorGenerator_max2025_64bit.dlm"
# TODO: Replace the below value with your S3 URI from your bucket
$MULTITEXTURE_PLUGIN_S3_URI="s3://your-bucket-name/path/to/MultiTexture_max2025_ver2.04_64bit.dlt"

# Optional: Replace this with your preferred V-Ray for 3ds Max 2025 installation root
$VRAY_FOR_3DSMAX2025_INSTALL_ROOT="C:\Program Files\Chaos\V-Ray\3ds Max 2025"

Write-Host ' --- Installing 3ds Max 2025 --- '

mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "$3DS_MAX_INSTALLER_ZIP_S3_URI" C:\3dsmax_setup\3dsmax.zip
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\
Start-Process "C:\3dsmax_setup\Setup.exe" -ArgumentList '-q' -Wait


Write-Host ' --- Creating plugins directory --- '
$pluginsDir = "C:\Program Files\Autodesk\3ds Max 2025\plugins"
New-Item -ItemType Directory -Path $pluginsDir -Force

Write-Host ' --- Downloading all installers and plugins --- '

# Download all files sequentially for PowerShell 5.1 compatibility
Write-Host 'Downloading V-Ray installer...'
aws s3 cp --no-progress "$VRAY_FOR_3DSMAX2025_INSTALLER_EXE_S3_URI" C:\3dsmax_setup\vray.exe
Write-Host 'Downloading Forest Pack installer...'
aws s3 cp --no-progress "$FOREST_PACK_INSTALLER_EXE_S3_URI" C:\3dsmax_setup\forestpack.exe
Write-Host 'Downloading RailClone installer...'
aws s3 cp --no-progress "$RAILCLONE_INSTALLER_EXE_S3_URI" C:\3dsmax_setup\railclone.exe
Write-Host 'Downloading FloorGenerator plugin...'
aws s3 cp --no-progress "$FLOORGENERATOR_PLUGIN_S3_URI" "$pluginsDir\"
Write-Host 'Downloading MultiTexture plugin...'
aws s3 cp --no-progress "$MULTITEXTURE_PLUGIN_S3_URI" "$pluginsDir\"

Write-Host ' --- All downloads completed --- '

Write-Host ' --- Installing V-Ray for 3ds Max 2025 --- '

# Create V-Ray configuration file for silent installation
@"
<DefValues>
<Value Name="INSTALL_TYPE" DataType="value">1</Value>
<Value Name="ANONYMOUS_TELEMETRY" DataType="value">0</Value>
<Value Name="PERSONALIZED_TELEMETRY" DataType="value">0</Value>
<Value Name="PKGROOT_SELECT" DataType="value">0</Value>
<Value Name="INSTALLROOT" DataType="value">$VRAY_FOR_3DSMAX2025_INSTALL_ROOT</Value>
<Value Name="REMOTE_LICENSE" DataType="value">1</Value>
<Value Name="AUTO_INSTALL_UIMENUS" DataType="value">1</Value>
<Value Name="SHOULDUNINSTALL" DataType="value">0</Value>
<Value Name="VISIT_SPOT3D" DataType="value">0</Value>
</DefValues>
"@ | Out-File -FilePath "C:\3dsmax_setup\config.xml" -Encoding UTF8

# Install V-Ray with render server configuration
Start-Process "C:\3dsmax_setup\vray.exe" -ArgumentList '-gui=0','-configFile=C:\3dsmax_setup\config.xml','-quiet=1' -Wait

Write-Host ' --- Installing Forest Pack --- '

# Install Forest Pack in render node mode
Start-Process -FilePath "C:\3dsmax_setup\forestpack.exe" -ArgumentList "/S", "MAXVER=max2025-64", "/MAXDIR=C:\Program Files\Autodesk\3ds Max 2025", "/LICMODE=rendernode" -Wait

Write-Host ' --- Installing RailClone --- '

# Install RailClone Pro in render node mode
Start-Process "C:\3dsmax_setup\railclone.exe" -ArgumentList "/S", "/LICMODE=rendernode" -Wait

Write-Host ' --- Configuring environment for 3ds Max 2025 --- '

[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2025;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')
[Environment]::SetEnvironmentVariable('3DSMAX_EXECUTABLE', 'C:\Program Files\Autodesk\3ds Max 2025\3dsmaxbatch.exe', 'Machine')
[Environment]::SetEnvironmentVariable('PYTHONPATH', 'C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts', 'Machine')
[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')

Write-Host ' --- Configuring environment for V-Ray for 3ds Max 2025 --- '

[System.Environment]::SetEnvironmentVariable('VRAY_FOR_3DSMAX2025_MAIN', 'C:\ProgramData\Autodesk\ApplicationPlugins\VRay3dsMax2025\bin\', 'Machine')
[System.Environment]::SetEnvironmentVariable('VRAY_FOR_3DSMAX2025_PLUGINS', 'C:\ProgramData\Autodesk\ApplicationPlugins\VRay3dsMax2025\bin\plugins\', 'Machine')
[System.Environment]::SetEnvironmentVariable('VRAY_MDL_PATH_3DSMAX2025', "$VRAY_FOR_3DSMAX2025_INSTALL_ROOT\mdl", 'Machine')

Write-Host ' --- Configuring environment for Forest Pack --- '

# Forest Pack environment variables for render node mode
[System.Environment]::SetEnvironmentVariable('ITOO_SOFTWARE_FOREST_PACK_PRO_MAINDIR', 'C:\Program Files\Itoo Software\Forest Pack Pro', 'Machine')
[System.Environment]::SetEnvironmentVariable('ITOO_SOFTWARE_FOREST_PACK_PRO_USELICSERVER', '0', 'Machine')

Write-Host ' --- Configuring environment for RailClone --- '

# RailClone environment variables for render node mode
[System.Environment]::SetEnvironmentVariable('ITOO_SOFTWARE_RAILCLONE_PRO_MAINDIR', 'C:\Program Files\Itoo Software\RailClone Pro', 'Machine')
[System.Environment]::SetEnvironmentVariable('ITOO_SOFTWARE_RAILCLONE_PRO_USELICSERVER', '0', 'Machine')

Write-Host ' --- Installing Deadline Cloud for 3dsMax --- '

& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m pip install deadline-cloud-for-3ds-max

Exit 0
