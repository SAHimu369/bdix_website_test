@echo off
echo ==============================
echo Installing Python dependencies
echo ==============================
python -m pip install --upgrade pip
python -m pip install --user -r "%~dp0requirements.txt"
echo.
echo ==============================
echo Installation completed.
echo Press any key to exit.
pause >nul
