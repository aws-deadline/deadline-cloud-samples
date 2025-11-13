# Redshift for Houdini 2026 Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains a conda build recipe for Redshift for Houdini 2026.1.1, specifically configured for use with AWS Deadline Cloud. This package enables you to run Redshift rendering jobs with Houdini on Deadline Cloud service-managed fleets.

## Package Information

- **Application**: Redshift for Houdini redshift_2026.1.1_2105803004
- **Supported Platforms**: linux-64
- **Source**: Maxon website
- **License**: LicenseRef-MaxonEULA
- **Build Tool**: rattler-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building
   - A queue named "Package Build Queue" (or specify with `-q` option)
   - Linux-64 fleet for building linux packages

2. **Deadline Cloud CLI** installed on your workstation

3. **Source archive** (see [Archive File Instructions](#archive-file-instructions) below)

4. **Maxon account** for downloading Redshift installer

5. **A Houdini conda package** as this is a plugin dependency

## Archive File Instructions

### Linux

#### Download from Maxon
1. Download the `redshift_2026.1.1_2105803004_linux_x64.run` installer from the Maxon website
2. Place the downloaded file in the `conda_recipes/archive_files` directory
3. Verify the SHA256 hash matches: `3af69b23a5b4bff88ba85017e2992f3d6fd38036857c67e03284e4bcddce670c`

## Plugin Integration

### Plugin Architecture

Redshift integrates with Houdini through a plugin system that requires version-specific compatibility. This package automatically detects the installed Houdini version and configures the appropriate Redshift plugin version.
This recipe creates a package in `"$PREFIX/opt/houdini/packages"` which points to the plugin. For more information about Houdini packages, see the [Houdini Packages documentation](https://www.sidefx.com/docs/houdini/ref/plugins.html).

### Plugin Installation Paths

The conda recipe configures Redshift to integrate with Houdini installations:

```bash
# Environment variables set by this package
export REDSHIFT_LOCATION=$PREFIX/opt/redshift

# Integration with Houdini
# Redshift plugins are installed to match Houdini version requirements
```

### Version Compatibility Logic

This package implements intelligent version matching:

1. **Exact Match**: Looks for an exact match between the Houdini version and available Redshift plugin versions
2. **Major.Minor Match**: If no exact match is found, uses a plugin version that matches the major.minor version of Houdini
3. **Fallback**: If no matching major.minor version is found, the package will exit and not configure Redshift
4. **Version Detection**: If the `houdini --version` call doesn't print a valid version string, the package will exit

### Creating Related Plugin Packages

1. **Plugin Package Structure**
   ```
   my-redshift-extension/
   ├── recipe/
   │   ├── recipe.yaml
   │   ├── build.sh
   │   └── bld.bat
   ├── deadline-cloud.yaml
   └── README.md
   ```

2. **Plugin Dependencies**
   - Add both Houdini and Redshift packages as dependencies in your plugin's `recipe.yaml`
   - Specify version constraints: `houdini >=21.0,<21.5` and `houdini-redshift >=2026.1.0`

## Application-Specific Requirements

### Licensing

See the [AWS Deadline Cloud licensing documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/license.html) for detailed guidance on license configuration. Redshift requires proper licensing configuration for rendering operations.

### GPU Requirements

Redshift is a GPU-accelerated renderer with specific requirements. See the [Redshift documentation](https://www.maxon.net/en/requirements/redshift-requirements) for full list.:
- NVIDIA GPU with CUDA support
- Minimum 8GB VRAM 
- CUDA compute capability 6.0 or higher

### System Requirements

- Linux x86_64 compatibility
- Compatible Houdini installation (21.0+, <21.5)
- NVIDIA drivers with CUDA support

## Adapting to Other Versions

### Version Update Checklist

To adapt this recipe for other Redshift versions:

1. **Update Version Information**
   ```yaml
   # In recipe/recipe.yaml
   context:
     version: "2026.x.x_xxxxxxxx"  # new version
   
   # In deadline-cloud.yaml
   sourceArchiveFilename: redshift_[version]_linux_x64.run
   ```

2. **Update Source Archives**
   - Download new version installer from Maxon
   - Update SHA256 hash in `recipe.yaml`
   - Update source filename in `deadline-cloud.yaml`

3. **Check Houdini Compatibility**
   - Verify supported Houdini versions for the new Redshift release
   - Update dependency constraints in `recipe.yaml`
   - Test version detection logic

4. **Update Build Scripts**
   - Check for changes in installer structure
   - Update file extraction and installation paths

5. **Test Integration**
   - Verify Redshift loads correctly in Houdini
   - Test rendering functionality
   - Validate version matching logic

6. **Update Documentation**
   - Update version numbers throughout README
   - Update Houdini compatibility information
   - Update any version-specific requirements

### Common Version Migration Issues

- **Houdini Compatibility**: New Redshift versions may drop support for older Houdini versions
- **Plugin Structure Changes**: Installation directory structure may change
- **Dependency Updates**: New versions may require different system dependencies
- **License Changes**: Licensing requirements may change between versions

## Recipe Structure

```
houdini-redshift-2026/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── recipe.yaml             # Rattler-build recipe
    └── build.sh                # Linux build script with version detection
```

## Resources

- **Redshift Documentation**: https://help.maxon.net/r3d/houdini/en-us/
- **Houdini Plugin Configuration**: https://help.maxon.net/r3d/houdini/en-us/Content/html/Houdini+Plugin+Configuration.html
- **AWS Deadline Cloud Developer Guide**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- **Rattler Build Documentation**: https://prefix-dev.github.io/rattler-build/
- **Maxon Redshift**: https://www.maxon.net/en/redshift

---

**Warning**: When changing the Redshift version, be sure to check what versions of Houdini it supports due to the strict version compatibility requirements. This package includes automatic version detection to prevent incompatible combinations.
