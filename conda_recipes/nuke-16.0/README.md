# Nuke 16.0 Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains a conda build recipe for Nuke 16.0.1, specifically configured for use with AWS Deadline Cloud. With this package you can run Nuke compositing and processing jobs on Deadline Cloud service-managed fleets.

## Package Information

- **Application**: Nuke 16.0.1
- **Supported Platforms**: linux-64
- **Source**: Foundry website downloads
- **License**: Commercial
- **Build Tool**: rattler-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building
   - A queue. If you followed the [setup instructions](../README.md#infrastructure-setup-prerequisites) it will be named "Package Build Queue"  (or specify the queue name with `-q`)
   - Linux-64 fleet for building linux packages

2. **Deadline Cloud CLI** installed on your workstation

3. **Source archive** (see [Archive File Instructions](#archive-file-instructions) below)

4. **Foundry account** for downloading Nuke installer

## Archive File Instructions

### Download from Foundry (Required)
1. Download the `Nuke16.0v1-linux-x86_64.tgz` from the Foundry website.
2. You will need a Foundry account to access the Nuke downloads.
3. Place the downloaded file in the `conda_recipes/archive_files` directory.
4. Conda uses the a checksum to verify the integrity of the source file. The SHA256 hash should match: `61b570ea6d4f8a7e2f0647952c8e039fc02df6f6649e9de1d2ee0543398ed92f`.
   In bash, you can compute the checksum by running this command `sha256sum Nuke16.0v1-linux-x86_64.tgz`.

## Plugins

### OpenFX Plugins
To use OpenFX Plugins with Nuke, place the `.bundle` files into a known directory in $PREFIX. Set the OFX_PLUGIN_PATH environment variable to that directory and install any required dependencies. 

#### Example OFX Plugin
- [Nuke - De:Noise](../nuke-denoise/)

## Adapting to Other Versions

### Version Update Checklist

To adapt this recipe for Nuke 15.x or 17.x:

1. **Update Version Information**
   ```yaml
   # In recipe/meta.yaml
   {% set version_partial = "17.0" %}
   {% set version_minor = "1" %}
   
   # In deadline-cloud.yaml
   sourceArchiveFilename: Nuke17.0v1-linux-x86_64.tgz
   ```

2. **Update Source Archives**
   - Download new version archives from Foundry
   - Update SHA256 hashes in `meta.yaml`
   - Update source filename in `deadline-cloud.yaml`

3. **Check Dependencies**
   - Review and update system dependency versions
   - Test compatibility with existing plugins
   - Update minimum system requirements

4. **Update Build Scripts**
   - Check for changes in installation directory structure
   - Update file copy operations in build scripts
   - Verify environment variable paths in activation scripts

### Common Version Migration Issues

- **Path Changes**: Installation directories may change between versions
- **Dependency Updates**: New versions may require different system libraries
- **Plugin API Changes**: Plugin interfaces may be incompatible between major versions
- **License Changes**: Licensing requirements may change

## Recipe Structure

```
nuke-16.0/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── recipe.yaml               # Conda package metadata
    └── build.sh                # Linux build script
```

## Resources

- **Nuke Documentation**: https://learn.foundry.com/nuke/
- **AWS Deadline Cloud Developer Guide**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- **Conda Build Documentation**: https://docs.conda.io/projects/conda-build/
- **Plugin Development**: https://learn.foundry.com/nuke/developers/

---

**Note**: This recipe is specifically configured for Nuke 16.0.1 on Linux x86_64 platforms. The build process automatically handles EULA acceptance and system dependency installation.
