@echo off

REM This script finds the Python that is used by the Deadline Cloud CLI,
REM and then runs submit-package-job-script.py with that Python.
REM If the Deadline Cloud CLI doesn't have an associated Python.exe,
REM it will fall back to the bare "python" command.

for /f "delims=" %%F in ('where deadline') do set DEADLINE_DIR=%%~dF%%~pF
set SCRIPT_PATH=%~d0%~p0%~n0-script.py
for %%a in (%DEADLINE_DIR:~0,-1%) do set "DEADLINE_PARENT_DIR=%%~dpa"

set "PYTHON=%DEADLINE_PARENT_DIR%Python.exe"
where "%PYTHON%" > nul 2> nul
if %ERRORLEVEL% NEQ 0 set PYTHON=python

where "%PYTHON%" > nul 2> nul
if %ERRORLEVEL% NEQ 0 goto nopython

"%PYTHON%" "%SCRIPT_PATH%" %*

exit /b 0

:nopython
echo No Python interpreter was found to run submit-package-job-script.py.
exit /b 1