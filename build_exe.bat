@echo off
setlocal
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pyinstaller --noconsole --onefile --name sh-masivo app\show_runner_gui.py
pause
