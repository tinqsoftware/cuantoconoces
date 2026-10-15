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

set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo No se encontro el compilador de .NET Framework para el archivo portable.
  popd
  exit /b 1
)
if not exist "dist\portable" mkdir "dist\portable"
"%CSC%" /nologo /target:winexe /out:"dist\portable\QuizStudioLauncher.exe" /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll /r:System.Windows.Forms.dll "packaging\windows\PortableLauncher.cs"
if errorlevel 1 (
  echo No se pudo crear el lanzador portable.
  popd
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "packaging\windows\build_portable.ps1" -RuntimeDirectory "dist\Quiz Studio" -LauncherPath "dist\portable\QuizStudioLauncher.exe" -OutputPath "dist\portable\QuizStudio-Portable.exe"
echo.
echo Instalador creado: dist\installer\QuizStudio-Setup.exe
echo Archivo portable creado: dist\portable\QuizStudio-Portable.exe
popd
endlocal
