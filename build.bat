@echo off
REM ============================================================
REM  MyGym Installer — build to a single .exe
REM ============================================================
setlocal

echo.
echo === MyGym Installer build script ===
echo.

REM 1. Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Install from https://www.python.org/downloads/windows/ ^(check "Add to PATH"^).
    pause
    exit /b 1
)

REM 2. Install / upgrade PyInstaller
echo [1/3] Installing PyInstaller...
python -m pip install --upgrade pyinstaller
if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )

REM 3. Clean previous build
echo [2/3] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist
if exist MyGymInstaller.spec del /q MyGymInstaller.spec

REM 4. Build single-file, no-console, admin-elevated EXE
echo [3/3] Building EXE...
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --uac-admin ^
    --name MyGymInstaller ^
    --clean ^
    installer.py
if errorlevel 1 ( echo [ERROR] PyInstaller failed. & pause & exit /b 1 )

echo.
echo ============================================================
echo  BUILD COMPLETE
echo ============================================================
echo  Your EXE is here:
echo      %CD%\dist\MyGymInstaller.exe
echo.
echo  NEXT:
echo   1. Copy MyGymInstaller.exe into the SAME folder as:
echo        - wampserver3.3.0_x64.exe
echo        - mygym.zip
echo        - mygym.sql
echo   2. Double-click MyGymInstaller.exe
echo ============================================================
echo.
pause