mkdir C:\3dsmax_setup

Write-Host " --- Downloading from S3 --- "
aws s3 cp --no-progress s3://<your-bucket-name>/resources/3ds_max_full.zip C:\3dsmax_setup\3dsmax.zip

Write-Host " --- Expanding Archive --- "
Expand-Archive C:\3dsmax_setup\3dsmax.zip C:\3dsmax_setup\

Write-Host " --- Starting Install --- "
Start-Process -FilePath "C:\3dsmax_setup\<3ds Max Version>\Setup.exe" -ArgumentList "-q" -Wait -PassThru

Write-Host " --- Post install setup --- "
[Environment]::SetEnvironmentVariable("Path", "C:\Program Files\Autodesk\<3ds Max Version>;" + [Environment]::GetEnvironmentVariable("Path", "Machine"), "Machine")

& "C:\Program Files\Autodesk\<3ds Max Version>\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\<3ds Max Version>\Python\python.exe" -m pip install deadline-cloud-for-3ds-max
[Environment]::SetEnvironmentVariable("3DSMAX_EXECUTABLE", "C:\Program Files\Autodesk\<3ds Max Version>\3dsmaxbatch.exe", "Machine")
[Environment]::SetEnvironmentVariable("PYTHONPATH", "C:\Program Files\Autodesk\<3ds Max Version>\Python;C:\Program Files\Autodesk\<3ds Max Version>\Python\Scripts", "Machine")
[Environment]::SetEnvironmentVariable("Path", "C:\Program Files\Autodesk\<3ds Max Version>\Python;C:\Program Files\Autodesk\<3ds Max Version>\Python\Scripts;" + [Environment]::GetEnvironmentVariable("Path", "Machine"), "Machine")