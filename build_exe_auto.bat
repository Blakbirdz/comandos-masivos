@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -m ensurepip --upgrade >nul 2>nul
  py -m pip install --upgrade pip
  py -m pip install -r requirements.txt
  py -m pip install pyinstaller
  py -m PyInstaller --noconsole --onefile --name SH-Masivo show_runner_gui.py
  echo.
  echo EXE generado en la carpeta dist\SH-Masivo.exe
  pause
  goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
  python -m ensurepip --upgrade >nul 2>nul
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  python -m pip install pyinstaller
  python -m PyInstaller --noconsole --onefile --name SH-Masivo show_runner_gui.py
  echo.
  echo EXE generado en la carpeta dist\SH-Masivo.exe
  pause
  goto :eof
)
echo Python no esta instalado o no esta en PATH.
pause
