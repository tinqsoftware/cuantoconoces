# Cuánto conoces

Aplicación de escritorio para crear, configurar y jugar trivias. No depende de las animaciones ni de las pantallas de PowerPoint: cada juego es una configuración independiente que puedes reutilizar cuando quieras.

## Ejecutar

```bash
cd cuanto_conoces_app
python3 -m pip install -r requirements.txt
python3 main.py
```

`main.py` abre una ventana nativa de escritorio llamada **Quiz Studio**. No
abre Safari, Chrome ni ningún navegador externo; no utiliza puertos locales y
no requiere Internet. El diseño HTML/CSS se renderiza dentro de la ventana de
la propia aplicación para conseguir la apariencia definida en los mockups.

Como alternativa técnica de compatibilidad queda el modo antiguo de Tk con
`python3 main.py --legacy-tk`.

## Flujo de uso

1. En **Mis juegos**, crea un juego o edita uno existente.
2. Configura su nombre, título visible, colores, tipografía y una imagen de fondo opcional.
3. Define los equipos predeterminados, sus nombres y colores.
4. Crea categorías y sus preguntas, alternativas, respuesta, valor e imagen opcional.
5. Pulsa **Jugar**. Antes de iniciar puedes ajustar los equipos solo para esa partida.

La pantalla de juego muestra directamente el tablero, la pregunta y la respuesta. Cada carta usada queda bloqueada y puedes otorgar sus puntos a cualquier equipo o ajustar el marcador manualmente.

## Biblioteca e historial

- Puedes crear tantos juegos como necesites, duplicarlos o eliminarlos desde su menú.
- El historial conserva cada partida, incluso las que se dejaron en curso, junto con equipos, puntajes, cartas usadas y ganador.
- El botón **Historial** está disponible también durante la partida.

La primera vez se importa el banco actual de preguntas como **Trivia inicial**. Los juegos y el historial nuevos se guardan localmente en `storage/games.json` y `storage/history.json`; `config.example.json` y `game_data.json` quedan solo como fuente de esa importación inicial.

Las imágenes se guardan como rutas locales. Mantén esos archivos en el mismo lugar —o vuelve a seleccionarlos desde el editor— si mueves la aplicación a otra computadora.

Pulsa `F11` para entrar o salir de pantalla completa y `Esc` para salir de ella.

## Instalador para Windows

La distribución para usuarios finales será `QuizStudio-Setup.exe`: se abre con
doble clic, sigue el asistente de instalación y luego se ejecuta desde Inicio
sin instalar Python ni conectarse a Internet. Los archivos para construirlo en
Windows están en [packaging/windows/README.md](packaging/windows/README.md).

El instalador debe compilarse en Windows (PyInstaller empaqueta los binarios y
el motor WebEngine específicos de ese sistema); no es posible generar un `.exe`
Windows funcional directamente desde macOS.

El contenido de `seed/` es la edición inicial que verá quien instale la app:
incluye el juego configurado, sus equipos, preguntas y recursos visuales. El
historial de partidas no se distribuye ni se comparte.

### Generarlo gratis con GitHub Actions

También se incluye el flujo
[`Crear instalador Windows`](.github/workflows/build-windows.yml). Tras subir
esta carpeta a un repositorio de GitHub, entra a **Actions → Crear instalador
Windows → Run workflow**. GitHub compilará en una máquina Windows y ofrecerá
`QuizStudio-Setup.exe` como artefacto descargable durante 14 días. Es gratuito
en repositorios públicos; las cuentas gratuitas también incluyen una cuota
mensual para repositorios privados.

## Documentación para diseño de frontend

- [Brief de producto y reglas](FRONTEND_BRIEF.md): contexto, datos, recorridos y criterios de aceptación.
- [Catálogo de pantallas y casuísticas](FRONTEND_SCREEN_CATALOG.md): todas las pantallas, modales, estados vacíos, errores y variaciones que debe contemplar una IA de frontend.
