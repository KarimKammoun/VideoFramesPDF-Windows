@echo off
REM ===================================================================
REM  VideoFramesPDF - lanceur automatique
REM  Installe les dependances si necessaire, puis demarre le logiciel.
REM ===================================================================
title VideoFramesPDF
cd /d "%~dp0"

echo.
echo   ============================================
echo      VIDEOFRAMES PDF - installation
echo   ============================================
echo.

REM --- 1. verifier Python -------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe sur ce PC.
    echo.
    echo   ==> Telechargez Python depuis https://www.python.org/downloads/
    echo       Cochez "Add Python to PATH" pendant l'installation.
    echo.
    pause
    exit /b 1
)

REM --- 2. creer l'environnement virtuel ------------------------------------
if not exist "venv" (
    echo [1/3] Creation de l'environnement...
    python -m venv venv
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer l'environnement.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

REM --- 3. installer les dependances ----------------------------------------
echo [2/3] Installation des composants (une seule fois)...
python -m pip install --upgrade pip --quiet
python -m pip install "numpy==1.26.4" opencv-python-headless pillow --quiet
if errorlevel 1 (
    echo [ERREUR] L'installation a echoue. Verifiez votre connexion Internet.
    pause
    exit /b 1
)

REM --- 4. lancer ----------------------------------------------------------
echo [3/3] Demarrage du logiciel...
echo.
python app.py
if errorlevel 1 pause
