@echo off
REM =========================================================================
REM Script de build reproductible pour Windows (Sinistres App v4.0.0)
REM Exécute tout le pipeline de compilation, test et création de l'installateur.
REM =========================================================================

echo.
echo =========================================================
echo       BUILD REPRODUCTIBLE - SINISTRES APP V4
echo =========================================================
echo.

python build_release.py all

echo.
echo =========================================================
echo Build termine. Verifiez le livrable dans le dossier release\
echo =========================================================
pause
