rem To install the plugin we copy it into the Cinema 4D plugins dir
set "C4D_PLUGINS_DIRECTORY=%PREFIX%\cinema4d\plugins"
mkdir "%C4D_PLUGINS_DIRECTORY%"

rem /E recursive, /I assume destintion dir, /H copy hidden, /Y suppress prompt
xcopy "%SRC_DIR%" "%C4D_PLUGINS_DIRECTORY%" /E /I /H /Y

