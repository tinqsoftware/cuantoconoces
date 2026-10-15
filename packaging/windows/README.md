# Instalador para Windows

En una computadora Windows de 64 bits, instala una sola vez:

1. Python 3.10 o superior.
2. Inno Setup 6.

Luego haz doble clic en `build_installer.bat`.

El proceso genera tanto el instalador como el archivo portable descritos abajo.
En ambos casos, la persona usuaria final no necesita Python, dependencias ni
Internet para jugar.
# Versiones de Windows

La compilación genera dos opciones:

- `QuizStudio-Setup.exe`: instalador tradicional. Los datos quedan en la computadora donde se instala.
- `QuizStudio-Portable.exe`: un único archivo portable. Ábrelo, crea o modifica juegos, ciérralo y comparte **ese mismo archivo**. Al cerrarse, Quiz Studio guarda juegos, historial e imágenes dentro del `.exe`.

Para el formato portable, conserva el archivo en una carpeta escribible, como Descargas, Escritorio o Documentos. Si se abre directamente desde un adjunto de correo o una ubicación temporal, Quiz Studio lo copiará automáticamente a `Documentos\Quiz Studio\Juegos portátiles` para poder guardar los cambios.

Windows puede mostrar una advertencia de SmartScreen al recibir ejecutables sin firma digital; es normal en una distribución privada. Para enviarlo, USB, Google Drive o un `.zip` suelen ser más fiables que correo, que normalmente bloquea `.exe`.
