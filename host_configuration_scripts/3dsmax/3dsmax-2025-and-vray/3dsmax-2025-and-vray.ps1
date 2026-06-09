<#
This is an example host configuration script that downloads and installs 3dsMax 2025 and V-Ray for 3dsMax 2025.
You can configure a Windows Service-Managed Fleet to use this host configuration to render your 3dsMax 2025 + V-Ray jobs.
This script was tested with the 3dsMax 2025.2 and V-Ray 7 update 1 installers.

Requirements:
- S3 bucket to host both the 3ds Max 2025 and V-Ray installers
- Your fleet role must have permissions to s3:GetObject both the installer files from your S3 bucket.
#>

# TODO: Replace the below value with your S3 URI from your bucket
# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket-name/path/to/3ds-max-2025.zip"
# TODO: Replace the below values with the S3 URI from your bucket
$VRAY_FOR_3DSMAX2025_INSTALLER_EXE_S3_URI="s3://your-bucket-name/path/to/vray_adv_71000_max2025_x64.exe"

# Optional: Replace this with your preferred V-Ray for 3dsMax 2025 installation root
$VRAY_FOR_3DSMAX2025_INSTALL_ROOT="C:\Program Files\Chaos\V-Ray\3ds Max 2025"

Write-Host ' --- Installing 3dsMax 2025 --- '

mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "$3DS_MAX_INSTALLER_ZIP_S3_URI" C:\3dsmax_setup\3dsmax.zip
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\
Start-Process "C:\3dsmax_setup\Setup.exe" -ArgumentList '-q' -Wait

Write-Host ' --- Installing V-Ray for 3dsMax 2025 --- '

aws s3 cp --no-progress "$VRAY_FOR_3DSMAX2025_INSTALLER_EXE_S3_URI" C:\3dsmax_setup\vray.exe
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
Start-Process "C:\3dsmax_setup\vray.exe" -ArgumentList '-gui=0','-configFile=C:\3dsmax_setup\config.xml','-quiet=1' -Wait

Write-Host ' --- Configuring environment for 3dsMax 2025 --- '

[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2025;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')
[Environment]::SetEnvironmentVariable('3DSMAX_EXECUTABLE', 'C:\Program Files\Autodesk\3ds Max 2025\3dsmaxbatch.exe', 'Machine')
[Environment]::SetEnvironmentVariable('PYTHONPATH', 'C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts', 'Machine')
[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')

Write-Host ' --- Configuring environment for V-Ray for 3dsMax 2025 --- '

[System.Environment]::SetEnvironmentVariable('VRAY_FOR_3DSMAX2025_MAIN', 'C:\ProgramData\Autodesk\ApplicationPlugins\VRay3dsMax2025\bin\', 'Machine')
[System.Environment]::SetEnvironmentVariable('VRAY_FOR_3DSMAX2025_PLUGINS', 'C:\ProgramData\Autodesk\ApplicationPlugins\VRay3dsMax2025\bin\plugins\', 'Machine')
[System.Environment]::SetEnvironmentVariable('VRAY_MDL_PATH_3DSMAX2025', "$VRAY_FOR_3DSMAX2025_INSTALL_ROOT\mdl", 'Machine')

Write-Host ' --- Installing Deadline Cloud for 3dsMax --- '

& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m pip install deadline-cloud-for-3ds-max

Exit 0
