rem Copy staged plugin to the user plugins_x dir
setlocal
set "DST=%APPDATA%\Maxon\cinema4d_CF59E837_x\plugins"
if not exist "%DST%" mkdir "%DST%"
xcopy /E /I /H /Y "%PREFIX%\insydium_staging" "%DST%"
echo %DST%
dir %DST%
endlocal
