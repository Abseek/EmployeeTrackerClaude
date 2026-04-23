@echo off
echo =====================================================
echo  Employee Tracker - Build Script
echo =====================================================

echo.
echo [1/3] Generating icon assets...
venv\Scripts\python assets\generate_icon.py
if errorlevel 1 (
    echo ERROR: Icon generation failed. Make sure Pillow is installed in venv.
    pause
    exit /b 1
)

echo.
echo [2/3] Running PyInstaller...
venv\Scripts\pyinstaller --clean build.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo Output: dist\EmployeeTracker.exe
echo.
pause
