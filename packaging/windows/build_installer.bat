@echo off
setlocal

REM Ejecuta este archivo EN UNA COMPUTADORA WINDOWS con Python 3.10+.
REM El instalador resultante no requerirá Python ni conexión a Internet en la
REM computadora final.

set "ROOT=%~dp0..\.."
pushd "%ROOT%"

py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt "pyinstaller>=6.0"

py -3 -m PyInstaller --noconfirm --clean --windowed --name "Quiz Studio" ^
  --add-data "web_ui.html;." ^
  --add-data "desktop_ui.js;." ^
  --add-data "game_data.json;." ^
  --add-data "config.example.json;." ^
  --add-data "seed;seed" ^
  --collect-all PyQt5.QtWebEngineWidgets ^
  main.py

where iscc >nul 2>nul
if errorlevel 1 (
  echo.
  echo Falta Inno Setup 6. Instalala desde https://jrsoftware.org/isdl.php
  echo Luego vuelve a ejecutar este archivo para crear el instalador.
  popd
  exit /b 1
)

iscc "packaging\windows\QuizStudio.iss"
echo.
echo Instalador creado: dist\installer\QuizStudio-Setup.exe
popd
endlocal
