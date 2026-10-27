@echo off
cd /d "%~dp0"
python tools\make_icon.py
python -m PyInstaller --noconfirm --clean --windowed --name 押金记账 --icon app\assets\icon.ico --add-data "app\assets;app\assets" launch.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
echo Built: dist\押金记账\押金记账.exe
