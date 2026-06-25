@echo off

REM This script finds the Python that is used by the Deadline Cloud CLI,
REM and then runs submit-package-job-script.py with that Python.
REM If the Deadline Cloud CLI doesn't have an associated Python.exe,
REM it will fall back to the bare "python" command.
REM
REM You can override the Python interpreter to use by setting the
REM DEADLINE_PYTHON environment variable. This is useful when the Deadline
REM Cloud CLI was installed via the standalone submitter installer, which does
REM not bundle a reusable Python interpreter. The interpreter you point at must
REM have the 'deadline' library installed (pip install deadline).
REM
REM     set DEADLINE_PYTHON=python
REM     submit-package-job blender-4.2

set SCRIPT_PATH=%~d0%~p0%~n0-script.py

REM Allow the user to specify their own Python interpreter.
if defined DEADLINE_PYTHON (
    set "PYTHON=%DEADLINE_PYTHON%"
    goto runpython
)

for /f "delims=" %%F in ('where deadline') do set DEADLINE_DIR=%%~dF%%~pF
for %%a in (%DEADLINE_DIR:~0,-1%) do set "DEADLINE_PARENT_DIR=%%~dpa"

set "PYTHON=%DEADLINE_PARENT_DIR%Python.exe"
where "%PYTHON%" > nul 2> nul
if %ERRORLEVEL% NEQ 0 set PYTHON=python

:runpython
where "%PYTHON%" > nul 2> nul
if %ERRORLEVEL% NEQ 0 goto nopython

"%PYTHON%" "%SCRIPT_PATH%" %*

exit /b %ERRORLEVEL%

:nopython
echo ERROR: No Python interpreter with the 'deadline' library was found to run
echo submit-package-job-script.py.
echo.
echo If you installed the Deadline Cloud CLI via the standalone submitter
echo installer, it does not bundle a reusable Python interpreter. Set the
echo DEADLINE_PYTHON environment variable to a Python that has the 'deadline'
echo library installed (pip install deadline), for example:
echo.
echo     set DEADLINE_PYTHON=python
echo     %~n0 %*
exit /b 1
