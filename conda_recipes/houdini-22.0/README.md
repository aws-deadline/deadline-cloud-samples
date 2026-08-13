# Houdini 22.0 Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains a conda build recipe for Houdini 22.0.368, configured for use with AWS Deadline Cloud. The package runs Houdini rendering and processing jobs on Deadline Cloud service-managed fleets.

## Package Information

- **Application**: Houdini 22.0.368
- **Supported Platforms**: linux-64
- **Source**: SideFX Houdini downloads page
- **License**: SideFXEULA
- **Build Tool**: rattler-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building. See https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/cloudformation/farm_templates/starter_farm for instructions to create a Farm.
   - A queue for building packages. The submit command looks for a queue whose name starts with "Package". See https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html for instructions on creating one.
   - Linux-64 fleet for building linux packages

2. **Deadline Cloud CLI** installed on your workstation

3. **SideFX account** for downloading Houdini installer

4. **Source archive** (see [Archive File Instructions](#archive-file-instructions) below)

## Archive File Instructions

### Linux

#### Download from SideFX
1. Download the `houdini-22.0.368-linux_x86_64_gcc14.2.tar.gz` from SideFX Houdini's downloads page
2. Clone this repository locally.
3. Place the downloaded file in the `conda_recipes/archive_files` directory

Note that Houdini 22.0 builds are compiled with GCC 14.2, whereas Houdini 21.0 and
earlier used GCC 11.2. Make sure you download the `gcc14.2` archive, or the build
will fail to find the installer.

## Plugin Integration

### Plugins

Houdini supports plugins through the use of package files. A package is a json file that tells Houdini where to find plugins.
[Houdini Plugin Reference](https://www.sidefx.com/docs/houdini/ref/plugins.html).

Create your package files in `$PREFIX/opt/houdini/packages` and point them to the location of your plugins. See our Redshift for
Houdini recipe as [an example](../houdini-redshift-2026/).

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
   - Specify version constraints: `houdini >=22.0,<22.5`

### Plugin Sync

This recipe includes Plugin Sync support, which allows customers to deliver plugins
to workers via S3 without building a separate conda package.

To use Plugin Sync, upload your plugin files and a Houdini package descriptor
(`.json` file) to the S3 path:

```
s3://<job-attachments-bucket>/<root-prefix>/plugins/linux/houdini/22.0/
```

The `.json` package descriptor should reference `$DEADLINE_CLOUD_HOUDINI_PLUGIN_SYNC_DIR`
for plugin file paths. At activation time, the conda package downloads plugins from S3
and copies `.json` files to `~/houdini22.0/packages/` for Houdini's native discovery.

See the [Plugin Sync documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/plugin-sync.html)
for more details.

## Application-Specific Requirements

### Licensing

See the [AWS Deadline Cloud licensing documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/license.html) for detailed guidance on license configuration. Houdini requires proper licensing configuration for rendering operations.

### Adaptor Compatibility

Jobs submitted with the Deadline Cloud Houdini submitter use the `houdini-openjd`
adaptor package. The adaptor's `houdini >=19.5,<22.5` version constraint already
covers Houdini 22.0, so no separate adaptor change is needed to run 22.0 jobs.

### System Requirements

- Linux x86_64 with GCC 14.2 compatibility
- Sufficient memory for scene processing
- Optional: a GPU to render with Karma XPU

## Adapting to Other Versions

### Version Update Checklist

To adapt this recipe for Houdini 21.0, 20.5 or 20.0:

1. **Update Version Information**
   ```yaml
   # In recipe/recipe.yaml
   context:
     version_partial: "21.0"
     version_minor: "596"
     gcc_version: "gcc11.2"   # 22.0 and later use gcc14.2

   # In deadline-cloud.yaml
   sourceArchiveFilename: houdini-[version]-linux_x86_64_[gcc_version].tar.gz
   ```

2. **Update Source Archives**
   - Download new version archives from SideFX
   - Update SHA256 hashes in `recipe.yaml`
   - Update source filename in `deadline-cloud.yaml`

3. **Check Dependencies**
   - Review and update dependency versions
   - Houdini 22.0 needs `libatomic` from the system package manager, which 21.0 did not

4. **Update Build Scripts**
   - Check for changes in installation directory structure
   - Update file copy operations in build scripts
   - Verify environment variable paths

5. **Update the Plugin Sync scripts**
   - The activate and deactivate scripts hard-code the `houdini22.0` version in
     both the S3 plugin prefix and the `~/houdiniXX.X/packages` directory

6. **Test Plugin Compatibility**
   - Verify plugin paths haven't changed
   - Test with existing plugin packages like Redshift
   - Update plugin integration documentation

### Common Version Migration Issues

- **Path Changes**: Installation directories may change between versions
- **Compiler Version**: The archive filename encodes the GCC version, which changed from `gcc11.2` to `gcc14.2` in Houdini 22.0
- **Dependency Updates**: New versions may require different dependencies
- **Plugin API Changes**: Plugin interfaces may be incompatible between major versions
- **License Changes**: Licensing requirements may change

## Recipe Structure

```
houdini-22.0/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── recipe.yaml                             # Rattler-build recipe
    ├── build.sh                                # Linux build script
    ├── zzz-houdini-plugin-sync-activate.sh     # Plugin Sync activation script
    └── zzz-houdini-plugin-sync-deactivate.sh   # Plugin Sync deactivation script
```

## Resources

- **Houdini Documentation**: https://www.sidefx.com/docs/houdini/
- **AWS Deadline Cloud Developer Guide**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- **Rattler Build Documentation**: https://prefix-dev.github.io/rattler-build/
- **Plugin Development**: https://www.sidefx.com/docs/houdini/ref/plugins.html
- **Plugin Sync**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/plugin-sync.html

---

This recipe is configured for Houdini 22.0.368 on Linux x86_64 platforms.
