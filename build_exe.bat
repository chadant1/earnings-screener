@echo off
REM Builds a standalone Windows app (no Python needed to run it) in dist\EarningsScreener\
REM and puts a shortcut on your Desktop.  Run run.bat once first so the .venv exists.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Run run.bat once first to create the Python environment.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed ^
    --name EarningsScreener ^
    --icon assets\icon.ico ^
    --add-data "assets;assets" ^
    --collect-all yfinance ^
    --collect-all curl_cffi ^
    --collect-data certifi ^
    --hidden-import scipy.stats ^
    --exclude-module tkinter ^
    main.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Earnings Screener.lnk');" ^
  "$s.TargetPath='%~dp0dist\EarningsScreener\EarningsScreener.exe';" ^
  "$s.WorkingDirectory='%~dp0dist\EarningsScreener';" ^
  "$s.IconLocation='%~dp0dist\EarningsScreener\EarningsScreener.exe';$s.Save()"

echo.
echo Done!  App: dist\EarningsScreener\EarningsScreener.exe  (a Desktop shortcut was created)
echo You can copy the whole dist\EarningsScreener folder anywhere.
pause
