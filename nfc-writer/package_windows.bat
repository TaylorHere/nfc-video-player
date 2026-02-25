@echo off
echo Installing requirements...
pip install -r requirements.txt
pip install pyinstaller

echo Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo Building EXE...
pyinstaller --onefile --noconsole --add-data "ntag424_manager.py;." gui_writer.py --name "NFC_Writer_Tool"

echo.
echo ========================================
echo BUILD COMPLETE!
echo You can find your tool here: dist\NFC_Writer_Tool.exe
echo ========================================
pause
