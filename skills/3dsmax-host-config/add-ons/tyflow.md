# tyFlow Add-on

tyFlow is a particle system and physics simulation plugin for 3ds Max. It comes as a single
`.dlo` file, with no installer needed.

## Reference Script

See `host_configuration_scripts/3dsmax/3dsmax-2025-vray-and-tyflow.ps1` for a working example.

## What to add to the script

1. Add a TODO variable for the tyFlow `.dlo` plugin file name at the top of the script
2. Download the `.dlo` file from S3 into `C:\3dsmax_setup\`
3. Copy the `.dlo` file into `C:\Program Files\Autodesk\3ds Max <YEAR>\plugins\`

## Important notes

- No environment variables are needed. 3ds Max loads plugins automatically from the plugins directory
- The `.dlo` file name includes the 3ds Max year, so make sure it matches the version being installed
