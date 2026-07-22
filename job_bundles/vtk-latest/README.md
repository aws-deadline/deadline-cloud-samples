# VTK Visualization Job Template

This OpenJD job template allows users to run VTK (Visualization Toolkit) Python scripts using AWS Deadline Cloud.

## Overview

This job template is designed to be generalizable for any VTK-based Python script that:
1. Accepts command-line parameters for output path, width, and height
2. Saves visualization output to a specified location

The template accepts a user-provided Python script and runs it with the specified parameters, saving the visualization output to the designated location.

## Parameters

### Input Parameters
- **InputDir**: Directory containing the VTK script and any additional required files
- **InputScript**: Name of the Python script to run (must be in the input directory)

### Output Parameters
- **OutputDir**: Directory where the visualization output will be saved
- **OutputFilename**: Name of the output image file

### Render Parameters
- **Width**: Width of the output image in pixels (default: "1280")
- **Height**: Height of the output image in pixels (default: "720")

### Software Parameters
- **CondaPackages**: Conda packages to install (default: "vtk numpy"). These packages must be available in the Conda Channels configured in the queue environment

### Additional Parameters
- **ExtraParams**: Additional parameters to pass to the script (format: `--param1 value1 --param2 value2`)

## Usage

1. Prepare a VTK Python script that includes command-line arguments for:
   - `--output`: Output file path
   - `--width`: Image width
   - `--height`: Image height

2. Submit the job with:
   - **InputDir**: Directory containing your VTK script
   - **InputScript**: Filename of your script
   - **OutputDir**: Where to save the visualization
   - **OutputFilename**: Name for the output file
   - Any other parameters your script requires via ExtraParams

## Script Requirements

Your VTK script should:
1. Accept the parameters `--output`, `--width`, and `--height`
2. Save output to the location specified by `--output`
3. Use VTK for visualization

## Sample Script

A sample VTK script (`flow_simulation_visualization.py`) is provided in the `sample` directory that demonstrates:
- Creating a 3D airfoil geometry
- Generating a flow field
- Calculating pressure distribution
- Visualizing the simulation with streamlines
- Saving the output as an image file
This script is sourced from [here](https://github.com/djeada/Vtk-Examples/blob/main/src/02_advanced_shapes/flow_simulation_visualization.py#L4) and is licensed under the MIT license.