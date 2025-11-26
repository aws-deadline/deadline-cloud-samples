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

# TODO: Replace the below value with your bucket name
$BUCKET_NAME="your-bucket-name"

# TODO: Replace this with your 3ds Max folder name
$3DS_MAX_FOLDER_NAME="3ds Max 2025.2 Update - (EN)"

# TODO: Replace this with your 3ds Max zip file name
$3DS_MAX_ZIP_FILE="$3DS_MAX_FOLDER_NAME.zip"

# TODO: Replace this with your V-Ray for 3ds Max 2025 installer file name
$VRAY_FOR_3DSMAX2025_INSTALLER_FILE="vray_adv_71000_max2025_x64.exe"

# TODO: Replace this with your Forest Pack installer file name
$FOREST_PACK_INSTALLER_FILE="ForestPackPro921_x64.exe"

# TODO: Replace this with your RailClone installer file name
$RAILCLONE_INSTALLER_FILE="RailClonePro642.exe"

# TODO: Replace this with your FloorGenerator plugin file name
$FLOORGENERATOR_PLUGIN_FILE="FloorGenerator_max2025_64bit.dlm"

# TODO: Replace this with your MultiTexture plugin file name
$MULTITEXTURE_PLUGIN_FILE="MultiTexture_max2025_ver2.04_64bit.dlt"

# Optional: Replace this with your preferred V-Ray for 3ds Max 2025 installation root
$VRAY_FOR_3DSMAX2025_INSTALL_ROOT="C:\Program Files\Chaos\V-Ray\3ds Max 2025"

Write-Host ' --- Installing 3ds Max 2025 --- '

mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "s3://$BUCKET_NAME/$3DS_MAX_ZIP_FILE" C:\3dsmax_setup\3dsmax.zip
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\
Start-Process "C:\3dsmax_setup\$3DS_MAX_FOLDER_NAME\Setup.exe" -ArgumentList '-q' -Wait

Write-Host ' --- Downloading all installers and plugins --- '

# Download all files sequentially for PowerShell 5.1 compatibility
Write-Host 'Downloading V-Ray installer...'
aws s3 cp --no-progress "s3://$BUCKET_NAME/$VRAY_FOR_3DSMAX2025_INSTALLER_FILE" C:\3dsmax_setup\
Write-Host 'Downloading Forest Pack installer...'
aws s3 cp --no-progress "s3://$BUCKET_NAME/$FOREST_PACK_INSTALLER_FILE" C:\3dsmax_setup\
Write-Host 'Downloading RailClone installer...'
aws s3 cp --no-progress "s3://$BUCKET_NAME/$RAILCLONE_INSTALLER_FILE" C:\3dsmax_setup\
Write-Host 'Downloading FloorGenerator plugin...'
aws s3 cp --no-progress "s3://$BUCKET_NAME/$FLOORGENERATOR_PLUGIN_FILE" C:\3dsmax_setup\
Write-Host 'Downloading MultiTexture plugin...'
aws s3 cp --no-progress "s3://$BUCKET_NAME/$MULTITEXTURE_PLUGIN_FILE" C:\3dsmax_setup\

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
Start-Process "C:\3dsmax_setup\$VRAY_FOR_3DSMAX2025_INSTALLER_FILE" -ArgumentList '-gui=0','-configFile=C:\3dsmax_setup\config.xml','-quiet=1' -Wait

Write-Host ' --- Installing Forest Pack --- '

# Install Forest Pack in render node mode
Start-Process -FilePath "C:\3dsmax_setup\$FOREST_PACK_INSTALLER_FILE" -ArgumentList "/S", "MAXVER=max2025-64", "/MAXDIR=C:\Program Files\Autodesk\3ds Max 2025", "/LICMODE=rendernode" -Wait

Write-Host ' --- Installing RailClone --- '

# Install RailClone Pro in render node mode
Start-Process "C:\3dsmax_setup\$RAILCLONE_INSTALLER_FILE" -ArgumentList "/S", "/LICMODE=rendernode" -Wait

Write-Host ' --- Installing Additional Plugins --- '

# Create plugins directory and install additional plugins
$pluginsDir = "C:\Program Files\Autodesk\3ds Max 2025\plugins"
New-Item -ItemType Directory -Path $pluginsDir -Force
Copy-Item "C:\3dsmax_setup\$FLOORGENERATOR_PLUGIN_FILE" "$pluginsDir\"
Copy-Item "C:\3dsmax_setup\$MULTITEXTURE_PLUGIN_FILE" "$pluginsDir\"
Write-Host "Additional plugins installed to $pluginsDir"

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