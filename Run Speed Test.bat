@echo off
echo Running Speed Test App...
python "%~dp0bdix_speed_test.py"
echo.
echo ============================
echo Program finished (or crashed).
echo Press any key to close this window.
pause >nul
