@echo off

REM This script finds the Python that is used by the Deadline Cloud CLI,
REM and then runs submit-package-job-script.py with that Python.

for /f "delims=" %%F in ('where deadline') do set DEADLINE_DIR=%%~dF%%~pF
set SCRIPT_PATH=%~d0%~p0%~n0-script.py

"%DEADLINE_DIR%..\Python.exe" "%SCRIPT_PATH%" %*
