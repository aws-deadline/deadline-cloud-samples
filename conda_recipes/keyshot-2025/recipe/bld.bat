if not exist "%PREFIX%\keyshot\" mkdir "%PREFIX%\keyshot" || exit /b 1
if not exist "%PREFIX%\keyshot_resources\" mkdir "%PREFIX%\keyshot_resources" || exit /b 1

start /wait /b cmd /c "%SRC_DIR%\installer\keyshot_studio_win64_%PKG_VERSION%_%BUILD_NUMBER%.exe /S /USERNAME=%PREFIX%\keyshot_resources\ /D=%PREFIX%\keyshot\" || exit /b 1

REM Symlinks on Windows require Admin privileges to create. So create batch files in the PATH instead.
if not exist "%SCRIPTS%\" mkdir "%SCRIPTS%" || exit /b 1
(
    echo start /wait /b cmd /c "%%CONDA_PREFIX%%\keyshot\bin\keyshot_headless.exe %%*"
) > "%SCRIPTS%\keyshot_headless.bat"

if not exist "%PREFIX%\etc\conda\activate.d\" mkdir "%PREFIX%\etc\conda\activate.d" || exit /b 1
if not exist "%PREFIX%\etc\conda\deactivate.d\" mkdir "%PREFIX%\etc\conda\deactivate.d" || exit /b 1

(
    echo set KEYSHOT_LOCATION="%%CONDA_PREFIX%%\keyshot"
    echo set KEYSHOT_VERSION="%PKG_VERSION%"
    echo reg add "HKCU\SOFTWARE\Luxion\KeyShot" /t REG_SZ /v Resources /d "%%CONDA_PREFIX%%\keyshot\resources" /f
    echo reg add "HKCU\SOFTWARE\Luxion\KeyShot" /t REG_SZ /v ResourceFolder /d "%%CONDA_PREFIX%%\keyshot\resources" /f
) > "%PREFIX%\etc\conda\activate.d\%PKG_NAME%-%PKG_VERSION%-vars.bat" || exit /b 1
(
    echo export KEYSHOT_LOCATION="$CONDA_PREFIX\\keyshot"
    echo export KEYSHOT_VERSION="%PKG_VERSION%"
    echo MSYS_NO_PATHCONV=1 reg add 'HKCU\SOFTWARE\Luxion\KeyShot' /t REG_SZ /v Resources /d "$CONDA_PREFIX\keyshot\resources" /f
    echo MSYS_NO_PATHCONV=1 reg add 'HKCU\SOFTWARE\Luxion\KeyShot' /t REG_SZ /v ResourceFolder /d "$CONDA_PREFIX\keyshot\resources" /f
) > "%PREFIX%\etc\conda\activate.d\%PKG_NAME%-%PKG_VERSION%-vars.sh" || exit /b 1

(
    echo set KEYSHOT_LOCATION=
    echo set KEYSHOT_VERSION=
    echo reg delete "HKCU\SOFTWARE\Luxion\KeyShot" /v Resources /f
    echo reg delete "HKCU\SOFTWARE\Luxion\KeyShot" /v ResourceFolder /f
) > "%PREFIX%\etc\conda\deactivate.d\%PKG_NAME%-%PKG_VERSION%-vars.bat" || exit /b 1
(
    echo unset KEYSHOT_LOCATION
    echo unset KEYSHOT_VERSION
    echo MSYS_NO_PATHCONV=1 reg delete 'HKCU\SOFTWARE\Luxion\KeyShot' /v Resources /f
    echo MSYS_NO_PATHCONV=1 reg delete 'HKCU\SOFTWARE\Luxion\KeyShot' /v ResourceFolder /f
) > "%PREFIX%\etc\conda\deactivate.d\%PKG_NAME%-%PKG_VERSION%-vars.sh" || exit /b 1
