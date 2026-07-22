# AEC Plugins Add-on

Common architectural visualization plugins for 3ds Max: Forest Pack and RailClone (by iToo Software),
and FloorGenerator and MultiTexture (by CG-Source). Use any combination as needed.

## Reference Script

See `host_configuration_scripts/3dsmax/3dsmax-2025-vray-and-aec-plugins/3dsmax-2025-vray-and-aec-plugins.ps1` for a working example.

## What to add to the script

Only include the sections for plugins you are actually installing. The reference script downloads all installers first then installs sequentially. You can follow the same pattern or download and install each plugin one at a time.

**Forest Pack**
1. Add a TODO variable for the Forest Pack installer file name
2. Download the installer from S3 into `C:\3dsmax_setup\`
3. Run the installer silently with `/S`, `MAXVER=max<YEAR>-64`, `/MAXDIR`, and `/LICMODE=rendernode`
4. Set `ITOO_SOFTWARE_FOREST_PACK_PRO_MAINDIR` and `ITOO_SOFTWARE_FOREST_PACK_PRO_USELICSERVER=0`

**RailClone**
1. Add a TODO variable for the RailClone installer file name
2. Download the installer from S3 into `C:\3dsmax_setup\`
3. Run the installer silently with `/S` and `/LICMODE=rendernode`
4. Set `ITOO_SOFTWARE_RAILCLONE_PRO_MAINDIR` and `ITOO_SOFTWARE_RAILCLONE_PRO_USELICSERVER=0`

**FloorGenerator and MultiTexture**
1. Add TODO variables for the `.dlm` and `.dlt` plugin file names
2. Download both files from S3 into `C:\3dsmax_setup\`
3. Copy both files into `C:\Program Files\Autodesk\3ds Max <YEAR>\plugins\`
4. No environment variables needed

## Important notes

- Forest Pack and RailClone: `/LICMODE=rendernode` installs without a UI license, which is required for fleet workers
- Forest Pack: `MAXVER` format is `max<YEAR>-64` (e.g. `max2026-64`)
- FloorGenerator and MultiTexture plugin file names include the 3ds Max year, so update them to match your version
