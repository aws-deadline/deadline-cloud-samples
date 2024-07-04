# KeyShot Standalone

## Use case for this job

This is a Windows KeyShot job bundle that allows the user to render a scene with
each frame as a separate task.

The bundle accepts the following job parameters that modify the render:
* KeyShotFile
* Frames
* OutputName
* OutputDirectoryPath
* OutputFormat

The output file paths for the rendered frames will be constructed like the following:
    `<OutputDirectoryPath>/<OutputName>.<Frame#>.<OutputFormatExtension>`

All other render settings are taken from what is set in the scene file itself.

This job bundle expects **one** of the following:

* The user to specify an input directory that contains any file references that
are required to render that will be uploaded using job attachments.
    * With KeyShot the easiest way to get the input directory is to save
    the entire scene and all external files out as a KeyShot package(ksp).
    Saving a scene to a ksp bundles all of the external files referenced
    into a single directory and changes the paths to be relative to the new
    saved scene. You can then open the ksp up and submit the entire unpacked
    directory as the input directory and use the modified scene within as the
    input KeyShot file.

**OR**

* All files referenced in the scene to be available through network storage or
some other method that isn't job attachments for the workers.
