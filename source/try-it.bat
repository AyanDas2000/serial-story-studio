@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.14 try_it.py --open
  if errorlevel 1 python try_it.py --open
) else (
  python try_it.py --open
)
pause
