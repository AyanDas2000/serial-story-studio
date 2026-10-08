@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.14 run_shelf_live.py --sample --default-cap 1 --open
  if errorlevel 1 python run_shelf_live.py --sample --default-cap 1 --open
) else (
  python run_shelf_live.py --sample --default-cap 1 --open
)
pause
