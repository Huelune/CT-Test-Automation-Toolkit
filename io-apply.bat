@echo off
rem Double-click this file in Explorer to set CT test inputs/outputs from a list (ct.bat io-apply).
rem No typing and no PowerShell: it pulls the latest code, then tools\io_run.py asks you to drag the
rem list XLSX and the CT export folder into this window, runs io-apply and waits for a key.
rem Keep this file ASCII only, and keep the body inside the one ( ) block below: cmd reads
rem the whole block before running it, so git pull can safely rewrite this file meanwhile.
(
  setlocal
  cd /d "%~dp0"
  cls
  set "TODO_PULL=ok"
  git pull -q || set "TODO_PULL=fail"
  where py >nul 2>nul
  if errorlevel 1 (python tools\io_run.py) else (py -3 tools\io_run.py)
  echo.
  pause
  exit /b
)
