# OctaneRender Standalone job bundle

Render exported `.orbx` or `.ocs` scenes with [OctaneRender Standalone](https://home.otoy.com/render/octane-render/) on AWS Deadline Cloud.

## Prerequisites

This bundle requires a Linux fleet with an NVIDIA GPU and `python` on `PATH`. OctaneRender Standalone must be licensed and available as `octane` on `PATH`, or `OCTANE_STANDALONE_BINARY` must contain the path to its executable. The bundle does not install OctaneRender.

## Scene files

ORBX files contain their referenced assets. When submitting an OCS file, add its referenced geometry, textures, volumes, and other files as job attachments.

## Frame numbers

Enter the same frame numbers used by the exported scene. Set **Frame Rate** to `0` to read it from the scene.

## Output files

Rendered images are written under **Output Directory** using **Filename Template**. Discrete multipass output requires `%p` in the filename template so each pass gets a different path. The default template includes it.

Rendering uses the fleet's GPU capacity and an OctaneRender license for the duration of the session.
