# Blender 5.1 Conda Recipe for AWS Deadline Cloud

This directory contains a [rattler-build](https://prefix-dev.github.io/rattler-build/) recipe
for packaging [Blender 5.1](https://www.blender.org/) for use with AWS Deadline Cloud.

## Package Information

- **Application**: Blender 5.1.1
- **Platforms**: Linux 64-bit (linux-64), Windows 64-bit (win-64)
- **Source**: [blender.org/release/Blender5.1](https://download.blender.org/release/Blender5.1/)
- **License**: GPL-3.0-or-later
- **Build Tool**: rattler-build

## Building the Package

### Local build and test

Build and publish to a local filesystem channel:

```bash
cd conda_recipes
rattler-build publish blender-5.1/recipe/recipe.yaml \
    --to file://$HOME/my-conda-channel \
    --build-number=+1
```

### Submit a build job to Deadline Cloud

From the `conda_recipes` directory:

```bash
# Build for Linux (default)
./submit-package-job blender-5.1

# Build for a specific platform
./submit-package-job blender-5.1 -p linux-64

# Build for all platforms
./submit-package-job blender-5.1 --all-platforms

# Submit to a specific queue
./submit-package-job blender-5.1 -q "My Package Build Queue"

# Build to a different S3 channel
./submit-package-job blender-5.1 --s3-channel MyChannel
```

## Testing with a Render Job

### Local test with openjd-cli

Install the CLI if you haven't already: `pip install openjd-cli`

From the `job_bundles` directory:

```bash
openjd run blender_render/template.yaml \
    --environment ../queue_environments/conda_queue_env_pyrattler.yaml \
    -p CondaPackages=blender=5.1 \
    -p CondaChannels=file://$HOME/my-conda-channel \
    -p BlenderSceneFile=/path/to/scene.blend \
    -p Frames=1
```

### Submit a render job to Deadline Cloud

```bash
deadline bundle submit blender_render \
    -p CondaPackages=blender=5.1 \
    -p BlenderSceneFile=/path/to/scene.blend \
    -p Frames=1
```

Use the Deadline Cloud monitor to track progress. Select the task and choose
**View logs** > **Launch Conda session** to verify the package was found.

## Recipe Structure

```
blender-5.1/
├── README.md               # This file
├── deadline-cloud.yaml     # Deadline Cloud build job metadata
└── recipe/
    ├── recipe.yaml         # rattler-build package recipe
    ├── build.sh            # Linux build script
    ├── build_win.sh        # Windows build script
    ├── zzz-blender-plugins-activate.sh    # Plugin sync activate script
    └── zzz-blender-plugins-deactivate.sh  # Plugin sync deactivate script
```

## License

This recipe is provided under the same license as the deadline-cloud-samples repository.
Blender itself is licensed under [GPL-3.0-or-later](https://www.blender.org/about/license/).
