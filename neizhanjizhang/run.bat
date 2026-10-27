@echo off
cd /d "%~dp0"
python -m app.main
if errorlevel 1 (
  echo Failed to start. Install dependencies with: python -m pip install -r requirements.txt
  pause
)
