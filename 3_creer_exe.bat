@echo off
echo ============================================
echo   Creation du fichier .exe autonome
echo ============================================
echo Cette operation peut prendre 1 a 3 minutes...
echo.
python -m PyInstaller --noconfirm --onefile --windowed --name "SuiviSinistres" main.py
echo.
if exist "dist\SuiviSinistres.exe" (
    echo ============================================
    echo   TERMINE !
    echo   Votre application se trouve dans :
    echo   dist\SuiviSinistres.exe
    echo   Vous pouvez la copier ou en creer un
    echo   raccourci sur le Bureau.
    echo ============================================
) else (
    echo Une erreur s'est produite. Verifiez les messages ci-dessus.
)
pause
