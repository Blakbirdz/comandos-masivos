@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -m ensurepip --upgrade >nul 2>nul
  py -m pip install --upgrade pip
  py -m pip install -r requirements.txt
  py show_runner_gui.py
  goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -m ensurepip --upgrade >nul 2>nul
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  python show_runner_gui.py
  goto :eof
)
echo Python no esta instalado o no esta en PATH.
pause
