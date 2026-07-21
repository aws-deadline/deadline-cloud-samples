# Blender 5.0 Conda Recipe for AWS Deadline Cloud

This directory contains a conda build recipe for Blender 5.0, specifically configured for use with AWS Deadline Cloud.

## Package Information

- **Application**: Blender 5.0.1
- **Platform**: Windows 64-bit (win-64) & Linux 
- **Source**: https://download.blender.org/release/Blender5.0/blender-5.0.1-windows-x64.zip & https://download.blender.org/release/Blender5.0/blender-5.0.1-linux-x64.tar.xz
- **License**: GPL3
- **Build Tool**: conda-build/rattler-build

## Prerequisites

Before building this package, ensure you have:

1. **AWS Deadline Cloud infrastructure** set up with:
   - A farm configured for package building
   - A queue for building the package (specify with `-q` option)

2. **Deadline Cloud CLI** installed on your workstation

3. **Source archive** downloaded

## Building the  Package

### Using the submit-package-job command

From the `conda_recipes` directory in deadline-cloud-samples:

```bash
# Build for Windows 64-bit (default)
./submit-package-job blender-5.0

# Specify platform explicitly
./submit-package-job blender-5.0 -p win-64

# Submit to a specific queue
./submit-package-job blender-5.0 -q "My Package Build Queue"

# Build to a different S3 channel
./submit-package-job blender-5.0 --s3-channel MyChannel
```

### Manual conda-build (for local testing)

```bash
# Build the package locally (requires conda-build)
conda build recipe/ --platform <linux-64, win-64>
```

### Manual rattler-build (for local testing)

```bash
# Build the package locally (requires rattler-build)
rattler-build build --recipe-dir recipe/ --target-platform <linux-64, win-64> --allow-symlinks-on-windows
```

## Usage After Installation

Once installed in a conda environment:

```bash
# Activate environment with Blender
conda activate my-blender-env

# Run Blender
blender

# Run Blender with command line options
blender --help
blender --background --python my_script.py
```

## Using Addons

To use a Blender addon, place the `.py` or `.zip` file into a known location in the $INSTALL_DIR folder.
Create a Python file that uses the [Blender API](https://docs.blender.org/api/current/bpy.ops.preferences.html#bpy.ops.preferences.addon_install) that installs the addon and saves the user preferences. 

Modify the activate script to run your python file with Blender's Python.

```bash
"\$BLENDER_LOCATION/blender" --background --python "$INSTALL_DIR/install_addon.py"
```

Next, create a Python file that uninstalls the addon. Remember to also save the user preferences. 
Modify the deactivate script to run the uninstall script too.

```bash
"\$BLENDER_LOCATION/blender" --background --python "$INSTALL_DIR/uninstall_addon.py"
```

If you decide to make a separate conda package for your addon and you're addon requires any additional Python dependencies, place them in a known location in your $INSTALL_DIR.
Have the activate script move them into Blender's Python. Likewise, change the deactivate to remove them. This way, you can make use of the environment variables that this recipe 
sets for the location of Blender and it's Python.

### Examples Blender Addons

- [Blender - Flip Fluids](../blender-flipfluids/)
- [Blender - Plugin Bundle](../blender-plugin-bundle/)


## Troubleshooting

### Common Issues

1. **Build fails with missing source archive**
   - Ensure the source archive is downloaded to the `archive_files` directory
   - Check that the URL in `deadline-cloud.yaml` is accessible

2. **Package not found after build**
   - Verify the S3 conda channel configuration
   - Check that the build completed successfully in Deadline Cloud

3. **Blender won't start after installation**
   - Check that the conda environment is properly activated

### Getting Help

- Check the [Deadline Cloud Developer Guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/)
- Review the [conda-build documentation](https://docs.conda.io/projects/conda-build/)
- Examine build logs in the Deadline Cloud console

## Recipe Structure

```
blender-5.0/
├── README.md                    # This file
├── deadline-cloud.yaml          # Deadline Cloud configuration
└── recipe/
    ├── recipe.yaml             # Rattler package metadata
    ├── build_win.sh            # Windows bash script 
    └── build.sh                # Linux build script 
```

## License

This recipe is provided under the same license terms as the deadline-cloud-samples repository. Blender itself is licensed under GPL3.

## Contributing

To modify this recipe:

1. Update version numbers in `recipe.yaml` and `deadline-cloud.yaml`
2. Update SHA256 hash for new source archives in `recipe.yaml`.
3. Test the build process
4. Update this README with any changes

For questions or issues, please refer to the AWS Deadline Cloud documentation or community forums.
