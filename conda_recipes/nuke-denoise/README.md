# Nuke DENoise 3.6.9 Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains a conda build recipe for Nuke DENoise 3.6.9, configured for use with AWS Deadline Cloud. With this package you can use the DENoise plugin for noise reduction in Nuke compositing jobs on Deadline Cloud service-managed fleets.

## Package Information

- **Application**: DENoise 3.6.9
- **Supported Platforms**: linux-64
- **Source**: Revisionfx
- **License**: Commercial
- **Build Tool**: rattler-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building
   - A queue named "Package Build Queue" (or specify with `-q` option)
   - Linux-64 fleet for building linux packages

2. **Deadline Cloud CLI** installed on your workstation

3. **Source archive** (see [Archive File Instructions](#archive-file-instructions) below)

4. **Nuke conda package**, which this plugin depends on

## Archive File Instructions

### Download from Revisionfx (Required)
1. Download the `DENoise3OFXInstaller.tar.gz` archive from the Revisionfx website
2. Extract the installer from the archive.
3. Run the installer. It will create `.bundle` files in the `/usr/OFX/Plugins/DENoise3OFX/`directory.
4. Archive that directory: `tar czf DENoise.tar.gz /usr/OFX/Plugins/DENoise3OFX/`
5. Place the archive file in the `conda_recipes/archive_files` directory
6. Conda uses the a checksum to verify the integrity of the source file. The SHA256 hash should match: `ecbe1b40a19bf6f9ec05aca3d09428386292c57d4cd968b8f1ac767778642ebc`
   In bash, you can compute the checksum by running this command `sha256sum DENoise.tar.gz`.

## Plugin Integration

### Plugin Architecture

DENoise integrates with Nuke through the OpenFX (OFX) plugin standard. This conda recipe installs DENoise as an OFX plugin that Nuke can automatically discover and load.

### OpenFX Plugin Installation Paths

The conda recipe configures the following environment variables and paths for plugin discovery:

```bash
# Environment variables set by this package
export OFX_PLUGIN_PATH=$CONDA_PREFIX/OFX/Plugins/

# Plugin installation paths
$PREFIX/OFX/Plugins/
```
## Licensing

See the [AWS Deadline Cloud licensing documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/license.html) for detailed guidance on license configuration. DENoise requires proper licensing configuration. This recipe will create a watermarked version without a license.

## Adapting to Other Versions

### Version Update Checklist

To adapt this recipe for other DENoise versions:

1. **Update Version Information**
   ```yaml
   # In recipe/meta.yaml
   {% set version = "3.7.0" %}
   
   # In deadline-cloud.yaml
   # Update if archive filename changes
   ```

2. **Update Source Archives**
   - Download new version archives from Foundry
   - Update SHA256 hashes in `meta.yaml`
   - Update source filename in `deadline-cloud.yaml` if changed

3. **Check Dependencies**
   - Review Nuke version compatibility
   - Test with target Nuke versions
   - Update system dependency requirements

4. **Update Build Scripts**
   - Check for changes in plugin bundle structure
   - Verify OFX plugin paths
   - Test RPATH settings for new binaries

### Common Version Migration Issues

- **OFX Compatibility**: Newer versions may require different OFX standards
- **Nuke Compatibility**: Plugin may require specific Nuke versions
- **Dependency Changes**: System library requirements may change
- **Bundle Structure**: Plugin bundle organization may change

## Recipe Structure

```
nuke-denoise/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── recipe.yaml               # Conda package metadata
    └── build.sh                # Linux build script
```

## Resources

- **DENoise Documentation**: https://help.revisionfx.com/album/25/
- **OpenFX Standard**: http://openeffects.org/
- **AWS Deadline Cloud Developer Guide**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- **Conda Build Documentation**: https://docs.conda.io/projects/conda-build/
- **Nuke Documentation**: https://learn.foundry.com/nuke/

---

This recipe is configured for DENoise 3.6.9 as an OFX plugin for Nuke on Linux x86_64 platforms. The plugin requires a valid Nuke/Foundry license to function.
