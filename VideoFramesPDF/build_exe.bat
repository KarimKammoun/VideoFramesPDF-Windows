@echo off
REM ===================================================================
REM  VideoFramesPDF - construction de l'executable Windows (.exe)
REM  Necessite Python 3.9+ installe sur le PC.
REM ===================================================================
title Construction de VideoFramesPDF.exe
cd /d "%~dp0"

echo.
echo   ============================================
echo      CONSTRUCTION DE VideoFramesPDF.exe
echo   ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installe.
    echo Telechargez-le sur https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] Preparation de l'environnement...
python -m venv buildenv
if errorlevel 1 ( echo [ERREUR] Echec de la creation de l'environnement. & pause & exit /b 1 )
call buildenv\Scripts\activate.bat

echo [2/3] Installation des composants (plusieurs minutes)...
python -m pip install --upgrade pip
python -m pip install "numpy==1.26.4" pyinstaller pillow opencv-python-headless

echo [3/3] Construction de l'executable...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name VideoFramesPDF ^
    --hidden-import=tkinter ^
    --hidden-import=cv2 ^
    --hidden-import=PIL.ImageTk ^
    --collect-all=cv2 ^
    --collect-all=tkinter ^
    app.py

echo.
if exist dist\VideoFramesPDF.exe (
    echo   ============================================
    echo      TERMINE !
    echo      Fichier : dist\VideoFramesPDF.exe
    echo   ============================================
    copy /Y dist\VideoFramesPDF.exe . >nul
    explorer /select,VideoFramesPDF.exe
) else (
    echo [ERREUR] La construction a echoue. Lisez le message ci-dessus.
)
pause
