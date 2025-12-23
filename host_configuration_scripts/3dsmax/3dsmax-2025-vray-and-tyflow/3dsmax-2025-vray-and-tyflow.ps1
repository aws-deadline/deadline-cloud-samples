<#
This is an example host configuration script that downloads and installs 3dsMax 2025,
V-Ray for 3dsMax 2025 and tyFlow for 3dsMax 2025
You can configure a Windows Service-Managed Fleet to use this host configuration to
render your 3dsMax 2025 + V-Ray + tyFlow jobs.
This script was tested with the 3dsMax 2025.2, V-Ray 7 update 1, tyFlow for 3dsMax 2025 installers.

Requirements:
- S3 bucket to host 3ds Max 2025, V-Ray and tyFlow installers
- Your fleet role must have permissions to s3:GetObject both the installer files from your S3 bucket.
#>

# TODO: Replace the below value with your bucket name
$BUCKET_NAME="your-bucket-name"

# TODO: Replace this with your 3dsMax folder name
$3DS_MAX_FOLDER_NAME="3ds Max 2025.2 Update - (EN)"

# TODO: Replace this with your 3dsMax zip file name
$3DS_MAX_ZIP_FILE="$3DS_MAX_FOLDER_NAME.zip"

# TODO: Replace this with your V-Ray for 3dsMax 2025 installer file name
$VRAY_FOR_3DSMAX2025_INSTALLER_FILE="vray_adv_71000_max2025_x64.exe"

# TODO: Replace this with your tyFlow plugin file name
$TYFLOW_PLUGIN_FILE="tyFlow_2025_render.dlo"

# Optional: Replace this with your preferred V-Ray for 3dsMax 2025 installation root
$VRAY_FOR_3DSMAX2025_INSTALL_ROOT="C:\Program Files\Chaos\V-Ray\3ds Max 2025"

Write-Host ' --- Installing 3dsMax 2025 --- '

mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "s3://$BUCKET_NAME/$3DS_MAX_ZIP_FILE" C:\3dsmax_setup\3dsmax.zip
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\
Start-Process "C:\3dsmax_setup\$3DS_MAX_FOLDER_NAME\Setup.exe" -ArgumentList '-q' -Wait

Write-Host ' --- Installing V-Ray for 3dsMax 2025 --- '

aws s3 cp --no-progress "s3://$BUCKET_NAME/$VRAY_FOR_3DSMAX2025_INSTALLER_FILE" C:\3dsmax_setup\
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
Start-Process "C:\3dsmax_setup\$VRAY_FOR_3DSMAX2025_INSTALLER_FILE" -ArgumentList '-gui=0','-configFile=C:\3dsmax_setup\config.xml','-quiet=1' -Wait

Write-Host ' --- Installing tyFlow Plugin --- '

aws s3 cp --no-progress "s3://$BUCKET_NAME/$TYFLOW_PLUGIN_FILE" C\3dsmax_setup\
$pluginsDir = "C:\Program Files\Autodesk\3ds Max 2025\plugins"
New-Item -ItemType Directory -Path $pluginsDir -Force
Copy-Item "C:\3dsmax_setup\$TYFLOW_PLUGIN_FILE" "$pluginsDir\"
Write-Host "tyFlow plugin installed to $pluginsDir"

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