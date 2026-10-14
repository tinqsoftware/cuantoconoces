# Instalador para Windows

En una computadora Windows de 64 bits, instala una sola vez:

1. Python 3.10 o superior.
2. Inno Setup 6.

Luego haz doble clic en `build_installer.bat`.

El resultado será `dist\installer\QuizStudio-Setup.exe`. Ese es el único
archivo que se comparte con la persona usuaria final: lo abre con doble clic,
acepta el asistente y podrá abrir Quiz Studio desde Inicio o desde el acceso
directo. No tendrá que instalar Python, dependencias ni usar Internet para
jugar.

Los juegos e historiales del usuario se almacenan en
`%LOCALAPPDATA%\Quiz Studio\storage`, fuera de la carpeta del programa. Por
ello no se pierden al actualizar o desinstalar la aplicación.
