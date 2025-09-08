# Maya to Arnold 2026 conda build recipe

This recipe needs the same source archives as the [Maya 2026 recipe](../maya-2026).
See the [README from the maya-2026 package recipe](../maya-2026/README.md) for
instructions on how to acquire or create them, and details about how a conda package
for a Maya plugin can integrate.

## Build Notes
The build script uses patchelf to set relative paths (RPATH) for shared libraries. The paths 
(e.g., '$ORIGIN/../../maya2026/lib') are relative to the Maya installation directory structure. 
If the Maya installation directory layout is modified, these paths in build.sh may need to be updated accordingly.

Symlinks are created to make utilities accessible from the command line. 
Additional symlinks may be needed if new utilities are added in future versions.