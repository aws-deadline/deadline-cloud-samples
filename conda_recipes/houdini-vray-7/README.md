# V-Ray 7 for Houdini Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains a conda build recipe for V-Ray 7.10.01 (stable nightly build) for Houdini, specifically configured for use with AWS Deadline Cloud. This package enables you to run V-Ray rendering jobs with Houdini on Deadline Cloud service-managed fleets.

## Package Information

- **Application**: V-Ray 7.10.01 for Houdini 20.5
- **Supported Platforms**: linux-64
- **Source**: Chaos Group nightly builds website
- **License**: LicenseRef-ChaosEULA
- **Build Tool**: rattler-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building
   - A queue named "Package Build Queue" (or specify with `-q` option)
   - Linux-64 fleet for building linux packages

2. **Deadline Cloud CLI** installed on your workstation

3. **Source archive** (see [Archive File Instructions](#archive-file-instructions) below)

4. **Chaos Group account** for downloading V-Ray installer

5. **A Houdini conda package** as this is a plugin dependency

## Archive File Instructions

### Download from Chaos Group
1. Download the `vray_adv_71001_houdini20.5_23119_gcc11_linux.zip` installer from the Chaos Group website
  - There is no full release of V-Ray 7 that supports the latest Houdini 20.5 production builds. Instead a stable nightly build is being used in this sample. Access to the nightly builds requires a Chaos account and allowlisting from their support team [reference](https://forums.chaos.com/forum/v-ray-for-houdini-forums/v-ray-for-houdini-general/1054830-nightly-build-access)
2. Place the downloaded file in the `conda_recipes/archive_files` directory
3. Verify the SHA256 hash matches: `98437785c3c88f6c9a837d76fd413a2ed79c8ba27901572a77ed8893e958229d`

## Plugin Integration

### Plugin Architecture

V-Ray integrates with Houdini through a plugin system. This stable nightly build (7.10.01) supports specific Houdini 20.5 patch versions. The package explicitly declares compatible Houdini versions in its requirements to ensure proper compatibility.

This recipe creates a package file in `"$PREFIX/opt/houdini/packages"` which points to the plugin. For more information about Houdini packages, see the [Houdini Packages documentation](https://www.sidefx.com/docs/houdini/ref/plugins.html).

### Plugin Installation Paths

The conda recipe configures V-Ray to integrate with Houdini installations:

```bash
# Environment variables set by this package
export VRAY_ROOT=$PREFIX/opt/vray
export HOUDINI_VRAY_EULA=$VRAY_ROOT/EULA.html
export HOUDINI_VRAY_GCPP=$VRAY_ROOT/GCPP.html
```

## Application-Specific Requirements

### Licensing

See the [AWS Deadline Cloud licensing documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/license.html) for detailed guidance on license configuration. V-Ray requires proper licensing configuration for rendering operations.

### Rendering Capabilities

V-Ray is a production-proven renderer with both CPU and GPU rendering support. See the [V-Ray System Requirements](https://documentation.chaos.com/space/VRAYHOUDINI/113279265/System+Requirements) for full details:
- Minimum 8GB RAM (64GB+ recommended)

### System Requirements

- Linux x86_64 compatibility
- Compatible Houdini installation (specific 20.5 patch versions: 20.5.278, 20.5.332, 20.5.370, 20.5.410, 20.5.445, 20.5.487, 20.5.522, 20.5.550, 20.5.584, 20.5.613, 20.5.654, 20.5.684)
- For GPU rendering: NVIDIA drivers

## Adapting to Other Versions

### Adapting V-Ray Version

To update to a different V-Ray version (e.g., from 7.10.00 to 7.20.00):

**Files to modify:**
1. **recipe/recipe.yaml**
   - Update `context.version` to new V-Ray version
   - Update `source.url` filename with new V-Ray version
   - Update `source.sha256` hash after downloading new installer

2. **deadline-cloud.yaml**
   - Update `sourceArchiveFilename` with new V-Ray version

3. **Download new installer** from Chaos Group and place in `archive_files/` directory

### Adapting Compatible Houdini Version

To support a different Houdini version (e.g., from 20.5 to 20.0):

**Files to modify:**
1. **recipe/recipe.yaml**
   - Update `source.url` filename with new Houdini version
   - Update `source.sha256` hash (installer differs per Houdini version)
   - Update `requirements.run` with specific supported Houdini versions from the new installer (inspect the directory structure in the installer's `vfh_home/dso_py*` folders to find the supported versions)

2. **deadline-cloud.yaml**
   - Update `sourceArchiveFilename` with new Houdini version

3. **Download correct installer** from Chaos Group (must match target Houdini version)

### Additional Steps

5. **Test Integration**
   - Verify V-Ray loads correctly in Houdini
   - Test rendering functionality (CPU and GPU if applicable)
   - Confirm compatible Houdini versions are correctly listed in requirements

6. **Verify Compatibility**
   - Update version numbers throughout README
   - Check installer's `vfh_home` directory for supported Houdini versions

### Common Version Migration Issues

- **Houdini Compatibility**: New V-Ray versions may drop support for older Houdini versions
- **Plugin Structure Changes**: Installation directory structure may change
- **Dependency Updates**: New versions may require different system dependencies
- **License Changes**: Licensing requirements may change between versions

## Recipe Structure

```
houdini-vray-7/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── recipe.yaml             # Rattler-build recipe
    └── build.sh                # Linux build script (includes activation/deactivation scripts)
```

## Resources

- **V-Ray Documentation**: https://documentation.chaos.com/space/VRAYHOUDINI
- **Houdini Plugin Configuration**: https://documentation.chaos.com/space/VRAYHOUDINI/113279274/Installation+from+zip
- **AWS Deadline Cloud Developer Guide**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- **Rattler Build Documentation**: https://prefix-dev.github.io/rattler-build/
- **Chaos Group V-Ray**: https://www.chaos.com/vray/houdini

---

**Warning**: This stable nightly build includes plugins for multiple Houdini 20.5 patch versions. When updating to a different V-Ray version, verify which Houdini versions are supported by examining the directory structure in the installer's `vfh_home` folder.
