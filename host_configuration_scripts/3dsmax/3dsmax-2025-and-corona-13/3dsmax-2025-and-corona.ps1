<#
This is an example host configuration script that downloads and installs 3dsMax 2025 and Corona 13 for 3dsMax 2025.
You can configure a Windows Service-Managed Fleet to use this host configuration to render your 3dsMax 2025 + Corona jobs.
This script was tested with the 3dsMax 2025.2 and Corona 13 installers.

Requirements:
- S3 bucket to host both the 3ds Max 2025 and Corona installers
- Your fleet role must have permissions to s3:GetObject both the installer files from your S3 bucket.
#>

# TODO: Replace the below values with the S3 URIs from your bucket
# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket-name/path/to/3ds-max-2025.zip"
# TODO: Replace the below values with the S3 URIs from your bucket
$CORONA_INSTALLER_EXE_S3_URI="s3://your-bucket-name/path/to/chaos-corona-13-3dsmax-hotfix1.exe"

Write-Host " --- Installing 3dsMax 2025 --- "

mkdir C:\3dsmax_setup -Force
aws s3 cp --no-progress "$3DS_MAX_INSTALLER_ZIP_S3_URI" C:\3dsmax_setup\3dsmax.zip
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\
Start-Process -FilePath "C:\3dsmax_setup\Setup.exe" -ArgumentList "-q" -Wait -PassThru

Write-Host " --- Installing Corona --- " 
aws s3 cp --no-progress "$CORONA_INSTALLER_EXE_S3_URI" C:\3dsmax_setup\corona.exe

Write-Host " --- Starting Corona Install --- " 
& "C:\3dsmax_setup\corona.exe" -gui=0 -auto

$content = @"
<VRLClient>
        <LicServer>
                <Host>127.0.0.1</Host>
                <Port>30304</Port>
                <Host1>localhost</Host1>
                <Port1>30304</Port1>
                <Host2></Host2>
                <Port2>30304</Port2>
                <User></User>
                <Pass></Pass>
        </LicServer>
</VRLClient>
"@

# Create the file with elevated privileges due to Program Files location
$path = "C:\Program Files\Common Files\ChaosGroup\vrlclient.xml"
Set-Content -Path $path -Value $content -Force

Write-Host " --- Post install setup --- " 

# This needs to point to the directory, not the file itself. Corona uses the same licensing structure as V-Ray
[Environment]::SetEnvironmentVariable("VRAY_AUTH_CLIENT_FILE_PATH", "C:\Program Files\Common Files\ChaosGroup", "Machine")

[Environment]::SetEnvironmentVariable("Path", "C:\Program Files\Autodesk\3ds Max 2025;" + [Environment]::GetEnvironmentVariable("Path", "Machine"), "Machine") 

& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m ensurepip 

& "C:\Program Files\Autodesk\3ds Max 2025\Python\python.exe" -m pip install deadline-cloud-for-3ds-max 

[Environment]::SetEnvironmentVariable("3DSMAX_EXECUTABLE", "C:\Program Files\Autodesk\3ds Max 2025\3dsmaxbatch.exe", "Machine")

[Environment]::SetEnvironmentVariable("PYTHONPATH", "C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts", "Machine") 

[Environment]::SetEnvironmentVariable("Path", "C:\Program Files\Autodesk\3ds Max 2025\Python;C:\Program Files\Autodesk\3ds Max 2025\Python\Scripts;" + [Environment]::GetEnvironmentVariable("Path", "Machine"), "Machine")

Exit 0
