@echo off
rem CT Test Automation Toolkit entry point. Usage: ct.bat <command> [options]
rem Keep this file ASCII only: cmd reads .bat files in the console code page.
setlocal
set "CT_TOOLKIT_ROOT=%~dp0"
set "PYTHONPATH=%CT_TOOLKIT_ROOT%src;%PYTHONPATH%"
set "PYTHONUTF8=1"

where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -m ct_toolkit %*
goto done

:try_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -m ct_toolkit %*
goto done

:no_python
echo [ERROR] Python 3.8+ not found (neither "py" nor "python" is on PATH).
exit /b 9009

:done
exit /b %ERRORLEVEL%
