# TODO replace variable with the S3 URI from your S3 bucket
# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$INSTALLER_S3_URI="s3://<3ds-max-installer-zip-archive-s3-uri>"

mkdir C:\3dsmax_setup

Write-Host " --- Downloading from S3 --- "
aws s3 cp --no-progress "$INSTALLER_S3_URI" C:\3dsmax_setup\3dsmax.zip

Write-Host " --- Expanding Archive --- "
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\

Write-Host " --- Starting Install --- "
Start-Process -FilePath "C:\3dsmax_setup\Setup.exe" -ArgumentList "-q" -Wait -PassThru

Write-Host " --- Post install setup --- "
[Environment]::SetEnvironmentVariable("Path", "C:\Program Files\Autodesk\3ds Max 2024;" + [Environment]::GetEnvironmentVariable("Path", "Machine"), "Machine")

& "C:\Program Files\Autodesk\3ds Max 2024\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max 2024\Python\python.exe" -m pip install deadline-cloud-for-3ds-max
[Environment]::SetEnvironmentVariable("3DSMAX_EXECUTABLE", "C:\Program Files\Autodesk\3ds Max 2024\3dsmaxbatch.exe", "Machine")
[Environment]::SetEnvironmentVariable("PYTHONPATH", "C:\Program Files\Autodesk\3ds Max 2024\Python;C:\Program Files\Autodesk\3ds Max 2024\Python\Scripts", "Machine")
[Environment]::SetEnvironmentVariable("Path", "C:\Program Files\Autodesk\3ds Max 2024\Python;C:\Program Files\Autodesk\3ds Max 2024\Python\Scripts;" + [Environment]::GetEnvironmentVariable("Path", "Machine"), "Machine")
