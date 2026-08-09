@echo off
echo =============================================================
echo   CREATION DE L'INSTALLATEUR WINDOWS OFFICIEL (Setup.exe)
echo =============================================================
echo.
python build_release.py all
echo.
if exist "release\Sinistres-App-Setup.exe" (
    echo =============================================================
    echo   TERMINE AVEC SUCCES !
    echo   Votre installateur unique pour distribution se trouve ici :
    echo   release\Sinistres-App-Setup.exe
    echo =============================================================
) else (
    echo NOTE : Verifiez les messages ci-dessus. Le dossier dist\windows\Sinistres App
    echo est pret, et Inno Setup peut etre lance pour generer Sinistres-App-Setup.exe.
)
pause
