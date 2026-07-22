# Houdini 20.5 Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains a conda build recipe for Houdini 20.5.654, configured for use with AWS Deadline Cloud. Use the package to run Houdini rendering and processing jobs on Deadline Cloud service-managed fleets.

## Package Information

- **Application**: Houdini 20.5.654
- **Supported Platforms**: linux-64
- **Source**: SideFX Houdini downloads page
- **License**: SideFXEULA
- **Build Tool**: rattler-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building. See https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/cloudformation/farm_templates/starter_farm for instructions to create a Farm.
   - A queue named "Package Build Queue". See https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html for instructions on creating a package building queue. 
   - Linux-64 fleet for building linux packages

2. **Deadline Cloud CLI** installed on your workstation

3. **SideFX account** for downloading Houdini installer

4. **Source archive** (see [Archive File Instructions](#archive-file-instructions) below)

## Archive File Instructions

### Linux

#### Download from SideFX
1. Download the `houdini-20.5.654-linux_x86_64_gcc11.2.tar.gz` from SideFX Houdini's downloads page
2. Verify the SHA256 hash matches: `05e877c06216e102a040e11b6b7fd8364dc699ed01b9386fc407564ce722c454`
3. Clone this repository locally.
4. Place the downloaded file in the `conda_recipes/archive_files` directory 
 

## Plugin Integration

### Plugins

Houdini supports plugins through the use of package files. A package is a json file that tells Houdini where to find plugins. 
[Houdini Plugin Reference](https://www.sidefx.com/docs/houdini/ref/plugins.html).

Create your package files in `$PREFIX/opt/houdini/packages` and point them to the location of your plugins. See our Redshift for
Houdini recipe as [an example](../houdini-redshift-2025/).

### Plugin Installation Paths

The conda recipe configures the following environment variables and paths for plugin discovery:

```bash
# Environment variables set by this package
export HOUDINI_LOCATION=$PREFIX/opt/houdini

# Plugin search paths (in order of precedence)
$PREFIX/opt/houdini/packages
```

### Creating Plugin Packages

1. **Plugin Package Structure**
   ```
   my-houdini-plugin/
   ├── recipe/
   │   ├── recipe.yaml
   │   ├── build.sh
   │   └── bld.bat
   ├── deadline-cloud.yaml
   └── README.md
   ```

2. **Plugin Installation Script Example**

   NOTE: Your plugin files can be anywhere as long as your package file points to their directory.

   ```bash
   # In build.sh
   mkdir -p $PREFIX/opt/houdini/packages
   cp my-plugin.json $PREFIX/opt/houdini/packages/
   cp -r plugin-files/ $PREFIX/opt/houdini/plugin/
   ```

3. **Plugin Dependencies**
   - Add this Houdini package as a dependency in your plugin's `recipe.yaml`
   - Specify version constraints: `houdini >=20.5,<21`

## Application-Specific Requirements

### Licensing

See the [AWS Deadline Cloud licensing documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/license.html) for detailed guidance on license configuration. Houdini requires proper licensing configuration for rendering operations.

### System Requirements

- Linux x86_64 with GCC 11.2 compatibility
- Sufficient memory for scene processing
- Optional: GPU acceleration may be needed for certain workloads

## Adapting to Other Versions

### Version Update Checklist

To adapt this recipe for Houdini 20.0 or 19.5:

1. **Update Version Information**
   ```yaml
   # In recipe/recipe.yaml
   context:
     version: "20.0.xxx"  # or desired version
   
   # In deadline-cloud.yaml
   sourceArchiveFilename: houdini-[version]-linux_x86_64_gcc11.2.tar.gz
   ```

2. **Update Source Archives**
   - Download new version archives from SideFX
   - Update SHA256 hashes in `recipe.yaml`
   - Update source filename in `deadline-cloud.yaml`

3. **Check Dependencies**
   - Review and update dependency versions
   - Update minimum system requirements

4. **Update Build Scripts**
   - Check for changes in installation directory structure
   - Update file copy operations in build scripts
   - Verify environment variable paths

5. **Test Plugin Compatibility**
   - Verify plugin paths haven't changed
   - Test with existing plugin packages like Redshift
   - Update plugin integration documentation


### Common Version Migration Issues

- **Path Changes**: Installation directories may change between versions
- **Dependency Updates**: New versions may require different dependencies
- **Plugin API Changes**: Plugin interfaces may be incompatible between major versions
- **License Changes**: Licensing requirements may change

## Recipe Structure

```
houdini-20.5/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── recipe.yaml             # Rattler-build recipe
    └── build.sh                # Linux build script
```

## Resources

- **Houdini Documentation**: https://www.sidefx.com/docs/houdini/
- **AWS Deadline Cloud Developer Guide**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- **Rattler Build Documentation**: https://prefix-dev.github.io/rattler-build/
- **Plugin Development**: https://www.sidefx.com/docs/houdini/ref/plugins.html

---

This recipe is configured for Houdini 20.5.654 on Linux x86_64 platforms.
