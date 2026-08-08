@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python n'est pas installé. Installez Python 3.10+ puis relancez ce script.
    pause
    exit /b 1
)
python -m pip install -r requirements.txt
python build_exe.py
pause
