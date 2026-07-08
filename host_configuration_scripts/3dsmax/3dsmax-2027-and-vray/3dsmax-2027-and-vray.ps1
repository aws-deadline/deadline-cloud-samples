<#
This is an example host configuration script that downloads and installs 3ds Max 2027 and V-Ray for 3ds Max 2027.
You can configure a Windows Service-Managed Fleet to use this host configuration to render your 3ds Max 2027 + V-Ray jobs.
This script was tested with the 3ds Max 2027 and V-Ray for 3ds Max 2027 installers.

Requirements:
- S3 bucket to host both the 3ds Max 2027 and V-Ray installers
- Your fleet role must have permissions to s3:GetObject all the installer files from your S3 bucket.
#>

# TODO: Replace the below value with your S3 URI from your bucket
# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket-name/path/to/3ds-max-2027.zip"

# TODO: Replace the below value with your S3 URI from your bucket
$VRAY_FOR_3DSMAX2027_INSTALLER_EXE_S3_URI="s3://your-bucket-name/path/to/vray_adv_max2027_x64.exe"

# Optional: Replace this with your preferred V-Ray for 3ds Max 2027 installation root
$VRAY_FOR_3DSMAX2027_INSTALL_ROOT="C:\Program Files\Chaos\V-Ray\3ds Max 2027"

Write-Host ' --- Installing 3ds Max 2027 --- '

mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "$3DS_MAX_INSTALLER_ZIP_S3_URI" C:\3dsmax_setup\3dsmax.zip
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\
Start-Process "C:\3dsmax_setup\Setup.exe" -ArgumentList '-q' -Wait

Write-Host ' --- Installing V-Ray for 3ds Max 2027 --- '

$VRAY_INSTALLER = Split-Path "$VRAY_FOR_3DSMAX2027_INSTALLER_EXE_S3_URI" -Leaf
aws s3 cp --no-progress "$VRAY_FOR_3DSMAX2027_INSTALLER_EXE_S3_URI" "C:\3dsmax_setup\$VRAY_INSTALLER"
@"
<DefValues>
<Value Name="INSTALL_TYPE" DataType="value">1</Value>
<Value Name="ANONYMOUS_TELEMETRY" DataType="value">0</Value>
<Value Name="PERSONALIZED_TELEMETRY" DataType="value">0</Value>
<Value Name="PKGROOT_SELECT" DataType="value">0</Value>
<Value Name="INSTALLROOT" DataType="value">$VRAY_FOR_3DSMAX2027_INSTALL_ROOT</Value>
<Value Name="REMOTE_LICENSE" DataType="value">1</Value>
<Value Name="AUTO_INSTALL_UIMENUS" DataType="value">1</Value>
<Value Name="SHOULDUNINSTALL" DataType="value">0</Value>
<Value Name="VISIT_SPOT3D" DataType="value">0</Value>
</DefValues>
"@ | Out-File -FilePath "C:\3dsmax_setup\config.xml" -Encoding UTF8
Start-Process "C:\3dsmax_setup\$VRAY_INSTALLER" -ArgumentList '-gui=0','-configFile=C:\3dsmax_setup\config.xml','-quiet=1' -Wait

Write-Host ' --- Configuring environment for 3ds Max 2027 --- '

[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2027;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')
[Environment]::SetEnvironmentVariable('3DSMAX_EXECUTABLE', 'C:\Program Files\Autodesk\3ds Max 2027\3dsmaxbatch.exe', 'Machine')
[Environment]::SetEnvironmentVariable('PYTHONPATH', 'C:\Program Files\Autodesk\3ds Max 2027\Python;C:\Program Files\Autodesk\3ds Max 2027\Python\Scripts', 'Machine')
[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2027\Python;C:\Program Files\Autodesk\3ds Max 2027\Python\Scripts;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')

Write-Host ' --- Configuring environment for V-Ray for 3ds Max 2027 --- '

[System.Environment]::SetEnvironmentVariable('VRAY_FOR_3DSMAX2027_MAIN', 'C:\ProgramData\Autodesk\ApplicationPlugins\VRay3dsMax2027\bin\', 'Machine')
[System.Environment]::SetEnvironmentVariable('VRAY_FOR_3DSMAX2027_PLUGINS', 'C:\ProgramData\Autodesk\ApplicationPlugins\VRay3dsMax2027\bin\plugins\', 'Machine')
[System.Environment]::SetEnvironmentVariable('VRAY_MDL_PATH_3DSMAX2027', "$VRAY_FOR_3DSMAX2027_INSTALL_ROOT\mdl", 'Machine')

# V-Ray introduced Cloud Licensing in 7.30.02 which must be disabled for UBL to work
Start-Process "C:\ProgramData\Autodesk\ApplicationPlugins\VRay3dsMax2027\utils\setvrlservice.exe" -ArgumentList '-cloud-server=0' -Wait -ErrorAction SilentlyContinue

Write-Host ' --- Installing Deadline Cloud for 3ds Max --- '

& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -m pip install deadline-cloud-for-3ds-max

Exit 0
