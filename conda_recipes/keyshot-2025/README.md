# KeyShot 2025.2 Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains a conda build recipe for KeyShot 2025.2, configured for use with AWS Deadline Cloud. The package runs KeyShot 3D visualization and rendering jobs on Deadline Cloud service-managed fleets.

## Package Information

- **Application**: KeyShot 2025.2
- **Supported Platforms**: win-64
- **Source**: KeyShot installer executable
- **License**: Commercial
- **Build Tool**: conda-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building
   - A queue named "Package Build Queue" (or specify with `-q` option)
   - Windows-64 fleet for building Windows packages

2. **Deadline Cloud CLI** installed on your workstation

3. **Source archive** Download the Keyshot Studio installer

4. **Keyshot account** for downloading Keyshot installer

5. **KeyShot license** for rendering operations. Available through Deadline Cloud Usage-Based Licensing

## Application-Specific Information

### Licensing

See the [AWS Deadline Cloud licensing documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/license.html) for detailed guidance on license configuration. KeyShot requires proper licensing configuration for rendering operations.

### Headless Rendering

- KeyShot headless executable is available as `keyshot_headless.bat` in the conda environment
- Registry configuration ensures proper resource discovery in headless mode
- GPU acceleration may be beneficial for complex rendering tasks

## Adapting to Other Versions

### Version Update Checklist

To adapt this recipe for KeyShot 2024 or 2026:

1. **Update Version Information**
   ```yaml
   # In recipe/meta.yaml
   {% set version_partial = "2026" %}
   {% set version_minor = "1" %}
   
   # In deadline-cloud.yaml
   sourceArchiveFilename: keyshot-2026.1-windows_x86_64.exe
   ```

2. **Update Source Archives**
   - Download new version installer from Luxion
   - Update SHA256 hash in `meta.yaml`
   - Update source filename in `deadline-cloud.yaml`

3. **Check Dependencies**
   - Review system requirements for new version
   - Test compatibility with existing materials and plugins
   - Update minimum Windows version if required

4. **Update Build Scripts**
   - Check for changes in installation directory structure
   - Verify registry key paths haven't changed
   - Update executable names if changed

### Common Version Migration Issues

- **Registry Changes**: Registry key paths may change between versions
- **Installation Structure**: Directory layout may be reorganized
- **Plugin API Changes**: Plugin interfaces may be incompatible
- **License Changes**: Licensing requirements may change

## Recipe Structure

```
keyshot-2025/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── meta.yaml               # Conda package metadata
    ├── bld.bat                 # Windows build script
    └── run_test.py             # Optional test script
```

## Resources

- **KeyShot Documentation**: https://www.keyshot.com/resources/
- **KeyShot Scripting**: https://manual.keyshot.com/manual/scripting-2/
- **AWS Deadline Cloud Developer Guide**: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- **Conda Build Documentation**: https://docs.conda.io/projects/conda-build/
- **KeyShot Network Rendering**: https://www.keyshot.com/network-rendering/

---

This recipe is configured for KeyShot 2025.2 on Windows x86_64 platforms. The build process handles registry configuration for headless rendering environments and creates appropriate wrapper scripts for command-line access.
