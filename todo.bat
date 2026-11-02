@echo off
rem Double-click this file in Explorer to run a todo.md check on the server PC.
rem Nothing to paste and no PowerShell: it pulls the latest code, asks for a section number
rem (tools\todo_run.py), runs that check and waits so the screen can be captured.
rem Keep this file ASCII only, and keep the body inside the one ( ) block below: cmd reads
rem the whole block before running it, so git pull can safely rewrite this file meanwhile.
(
  setlocal
  cd /d "%~dp0"
  cls
  set "TODO_PULL=ok"
  git pull -q || set "TODO_PULL=fail"
  where py >nul 2>nul
  if errorlevel 1 (python tools\todo_run.py) else (py -3 tools\todo_run.py)
  echo.
  pause
  exit /b
)
