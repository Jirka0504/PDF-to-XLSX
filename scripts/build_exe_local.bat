@echo off
python -m pip install -e . pyinstaller
pyinstaller --onefile --noconsole -n pdf2xlsx-gui src/pdf2xlsx_enterprise/gui.py
echo EXE in dist\pdf2xlsx-gui.exe
pause
