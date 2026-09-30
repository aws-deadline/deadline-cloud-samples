# Maya to Arnold 2027 conda build recipe

This recipe needs the same source archives as the [Maya 2027 recipe](../maya-2027).
See the [README from the maya-2027 package recipe](../maya-2027/README.md) for
instructions on how to acquire or create them, and details about how a conda package
for a Maya plugin can integrate.

## Build Notes
The build script uses patchelf to set relative paths (RPATH) for shared libraries. The paths 
(e.g., '$ORIGIN/../../maya2027/lib') are relative to the Maya installation directory structure. 
If the Maya installation directory layout is modified, these paths in build.sh may need to be updated to match the new layout.

Symlinks are created to make utilities accessible from the command line. 
Additional symlinks may be needed if new utilities are added in future versions.
