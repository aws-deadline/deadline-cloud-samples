# Corona Add-on

Corona is a photorealistic rendering engine by Chaos that integrates as a plugin with 3ds Max.
It shares the same licensing structure as V-Ray.

## Reference Script

See `host_configuration_scripts/3dsmax/3dsmax-2025-and-corona-13.ps1` for a working example.

## What to add to the script

1. Add a TODO variable for the Corona installer file name at the top of the script
2. After installing 3ds Max, download the Corona installer from S3 into `C:\3dsmax_setup\`
3. Run the Corona installer silently with `-gui=0 -auto`
4. Write the `vrlclient.xml` license file to `C:\Program Files\Common Files\ChaosGroup\`. This step requires elevated privileges, which the host config script already runs with
5. Set `VRAY_AUTH_CLIENT_FILE_PATH` to the directory (not the file itself)

## Important notes

- `VRAY_AUTH_CLIENT_FILE_PATH` must point to the directory `C:\Program Files\Common Files\ChaosGroup`, not to `vrlclient.xml` directly
- Corona uses the same `vrlclient.xml` licensing as V-Ray. If both are installed, only one copy of the file is needed
