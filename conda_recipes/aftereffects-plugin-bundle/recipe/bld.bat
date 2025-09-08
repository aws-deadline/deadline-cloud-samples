
REM The package build recipe for After Effects installs into %PREFIX%\aftereffects.
set "AE_PLUGINS_DIRECTORY=%PREFIX%\aftereffects\Plug-ins"
mkdir "%AE_PLUGINS_DIRECTORY%"

REM In order to keep this recipe as easy and simple to build as possible, we directly
REM use that value here. Alternatively, we could add a build dependency to aftereffects
REM and use %AE_LOCATION% value defined by the After Effects package.

REM Copy all .aex plugin files.
copy "%SRC_DIR%\*.aex" "%AE_PLUGINS_DIRECTORY%"

REM Verify that at least one .aex file was copied
if exist "%AE_PLUGINS_DIRECTORY%\*.aex" (
    exit /b 0
) else (
    echo No *.aex plugin files were copied into the After Effects %AE_PLUGINS_DIRECTORY%
    echo Check that the input directory for plugins contains at least one .aex file.
    exit /b 1
)