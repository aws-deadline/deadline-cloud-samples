# V-Ray Add-on

V-Ray is a professional rendering engine by Chaos Group that integrates as a plugin with 3ds Max.

## Reference Script

See `host_configuration_scripts/3dsmax/3dsmax-2025-and-vray.ps1` for a working example.

## What to add to the script

1. Add a TODO variable for the V-Ray installer file name and optional install root at the top of the script
2. After installing 3ds Max, download the V-Ray installer from S3 into `C:\3dsmax_setup\`
3. Write a silent install config XML file to `C:\3dsmax_setup\config.xml` and run the installer with `-gui=0 -configFile -quiet=1`
4. After setting 3ds Max env vars, set three V-Ray env vars (MAIN, PLUGINS, and MDL path), all suffixed with the 3ds Max year (e.g. `VRAY_FOR_3DSMAX2026_MAIN`)

## Important notes

- The year suffix in the V-Ray env var names MUST match the 3ds Max version year. This mismatch is the most common mistake when bumping versions
- The install root variable is optional but recommended so the MDL path derives from it
