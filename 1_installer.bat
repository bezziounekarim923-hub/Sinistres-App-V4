@echo off
echo ============================================
echo   Installation des composants necessaires
echo ============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python n'est pas installe ou pas dans le PATH.
    echo Telechargez-le sur https://www.python.org/downloads/
    echo IMPORTANT : cochez "Add Python to PATH" pendant l'installation.
    pause
    exit /b 1
)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Installation terminee. Vous pouvez maintenant lancer 2_lancer_app.bat
pause
