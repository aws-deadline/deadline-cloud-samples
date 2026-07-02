<#
This is an example host configuration script that downloads and installs 3ds Max 2027.
You can configure a Windows Service-Managed Fleet to use this host configuration to render your 3ds Max 2027 jobs.
This script was tested with the 3ds Max 2027 installer.

Requirements:
- S3 bucket to host the 3ds Max 2027 installer
- Your fleet role must have permissions to s3:GetObject the installer file from your S3 bucket.
#>

# TODO: Replace the below value with your S3 URI from your bucket
# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket-name/path/to/3ds-max-2027.zip"

Write-Host ' --- Installing 3ds Max 2027 --- '

mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "$3DS_MAX_INSTALLER_ZIP_S3_URI" C:\3dsmax_setup\3dsmax.zip
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\
Start-Process "C:\3dsmax_setup\Setup.exe" -ArgumentList '-q' -Wait

Write-Host ' --- Configuring environment for 3ds Max 2027 --- '

[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2027;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')
[Environment]::SetEnvironmentVariable('3DSMAX_EXECUTABLE', 'C:\Program Files\Autodesk\3ds Max 2027\3dsmaxbatch.exe', 'Machine')
[Environment]::SetEnvironmentVariable('PYTHONPATH', 'C:\Program Files\Autodesk\3ds Max 2027\Python;C:\Program Files\Autodesk\3ds Max 2027\Python\Scripts', 'Machine')
[Environment]::SetEnvironmentVariable('Path', 'C:\Program Files\Autodesk\3ds Max 2027\Python;C:\Program Files\Autodesk\3ds Max 2027\Python\Scripts;' + [Environment]::GetEnvironmentVariable('Path', 'Machine'), 'Machine')

Write-Host ' --- Installing Deadline Cloud for 3ds Max --- '

& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -m pip install deadline-cloud-for-3ds-max

Exit 0
