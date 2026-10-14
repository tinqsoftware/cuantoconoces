# Brief de frontend — Quiz Studio / Cuánto conoces

## 1. Contexto y objetivo

**Quiz Studio** es una aplicación de escritorio para crear y jugar trivias configurables. Una persona anfitriona puede guardar varios juegos y reutilizarlos en ocasiones distintas. Cada juego tiene su propia identidad visual, equipos, categorías y banco de preguntas.

El objetivo del frontend es hacer que la creación y conducción de una trivia se sientan claras, rápidas y agradables en una pantalla grande. La interfaz debe servir tanto para preparar el juego antes de un evento como para proyectarlo y jugarlo en vivo.

> No es una presentación ni debe imitar una presentación de PowerPoint. No existen diapositivas, animaciones automáticas, cronómetros obligatorios ni pantallas de “tiempo agotado”. Es un producto de juego configurable.

## 2. Usuarios y modos de uso

| Usuario | Necesidad principal | Modo |
| --- | --- | --- |
| Anfitrión / administrador | Crear y mantener juegos | Biblioteca y editor |
| Anfitrión durante el evento | Mostrar preguntas, revelar respuestas, sumar puntos | Partida en vivo |
| Participantes / audiencia | Ver tablero, pregunta, respuesta y puntaje | Vista proyectada de la partida |

La aplicación actual es de escritorio. Debe funcionar de forma cómoda desde **1120 × 680 px** en adelante; el diseño base se optimiza para **1360 × 820 px** o una pantalla/proyector 16:9.

## 3. Principios de UX

1. **Dos contextos inequívocos:** administrar juegos y jugar una partida nunca deben confundirse.
2. **El contenido primero:** categorías, preguntas, respuesta y puntaje deben ser legibles a distancia.
3. **Pocos clics en vivo:** desde el tablero se debe abrir una carta, revelar la respuesta, asignar puntos y volver al tablero sin pasos sobrantes.
4. **Configuración sin miedo:** edición autosuficiente, validaciones claras y acciones destructivas confirmadas.
5. **Persistencia visible:** los juegos y las partidas anteriores son recursos reutilizables, no pantallas desechables.
6. **Personalización real:** el estilo pertenece a cada juego, no a una configuración global.

## 4. Arquitectura de información

```text
Quiz Studio
├── Mis juegos (biblioteca)
│   ├── Crear juego
│   ├── Editar juego
│   ├── Jugar
│   └── Menú del juego
│       ├── Duplicar
│       ├── Ver historial de este juego
│       └── Eliminar
├── Historial global
└── Partida activa
    ├── Tablero
    ├── Pregunta
    ├── Respuesta / asignación de puntos
    ├── Historial de este juego (modal, sin abandonar partida)
    ├── Finalizar partida
    └── Salir y conservar partida en curso
```

## 5. Inventario completo de pantallas y estados

### A. Biblioteca: “Mis juegos”

**Propósito:** punto de inicio y catálogo de las trivias disponibles.

**Contenido:**

- Barra lateral fija con marca “Quiz Studio”.
- Navegación: `Mis juegos` y `Historial`.
- Encabezado: título “Mis juegos”, texto corto de ayuda y CTA primario `+ Crear juego`.
- Rejilla de tarjetas de juegos (3 columnas en escritorio amplio).

**Tarjeta de juego:**

- Área superior con color de fondo propio, color de acento, título visible y nombre interno.
- Resumen: cantidad de categorías y preguntas.
- Fecha de última edición.
- Acciones: `Editar`, `Jugar`, menú de más opciones (`…`).

**Estados requeridos:**

- Biblioteca con juegos.
- Biblioteca vacía con ilustración/ícono, explicación y CTA para crear el primer juego.
- Menú contextual abierto para un juego.
- Confirmación antes de eliminar. Eliminar un juego **no elimina su historial**.

**Acciones / destinos:**

| Acción | Resultado |
| --- | --- |
| Crear juego | Abre el editor con valores iniciales |
| Editar | Abre el editor del juego elegido |
| Jugar | Abre “Preparar partida” |
| Duplicar | Genera copia independiente con nuevas IDs |
| Ver historial | Abre historial filtrado por juego |
| Eliminar | Confirmación y regreso a la biblioteca |

---

### B. Editor de juego

**Propósito:** configurar todo lo que diferencia a un juego de otro. Se presenta como una ventana amplia o una página de edición con pestañas. La acción `Guardar juego` debe ser persistente y visible en todo momento.

**Cabecera:**

- Título: `Nuevo juego` o `Configuración del juego`.
- Acción secundaria `Cancelar`.
- Acción primaria `Guardar juego`.
- Si hay cambios sin guardar, se recomienda advertir antes de cancelar/cerrar.

#### B1. Pestaña “Identidad visual”

**Campos obligatorios:**

- Nombre interno: identifica el juego en la biblioteca.
- Título visible: se proyecta durante la partida.

**Campos de estilo:**

- Color de fondo.
- Imagen de fondo opcional, elegida desde un archivo local.
- Color de acento.
- Color de texto.
- Color de las tarjetas/paneles.
- Tipografía instalada (campo de texto o selector, según plataforma).

**UX clave:**

- Vista previa en vivo de título, color y fondo.
- Selector visual para cada color, además de permitir un valor hexadecimal.
- Opción clara para quitar la imagen de fondo.
- Si la imagen no está disponible, el juego sigue funcionando con el color de fondo.

#### B2. Pestaña “Equipos”

**Propósito:** definir los equipos predeterminados del juego.

**Contenido:**

- Selector de cantidad de equipos: mínimo 2, máximo 8.
- Fila por equipo: ordinal, nombre y color.
- Selector de color por fila.
- Texto aclaratorio: antes de iniciar una partida se pueden ajustar nombres/cantidad solo para esa ocasión, sin modificar el juego base.

**Reglas:**

- Nombres vacíos se sustituyen por `Equipo N`.
- Colores no válidos se sustituyen por un color de respaldo.
- La configuración predeterminada se reutiliza en partidas futuras.

#### B3. Pestaña “Categorías y preguntas”

**Propósito:** organizar el banco de preguntas del tablero.

**Estructura recomendada:**

- Columna izquierda: lista de categorías, cantidad de preguntas y acciones `Añadir`, `Editar`, `Eliminar`.
- Área principal: tabla/lista de preguntas de la categoría seleccionada.
- Botón destacado `+ Nueva pregunta`.
- Acciones por pregunta: `Editar`, `Duplicar`, `Eliminar`.

**Categoría:**

- Nombre obligatorio.
- Color identificador.
- Lista de preguntas.

**Pregunta:**

- Valor de puntos: entero positivo.
- Enunciado obligatorio.
- Alternativas opcionales, una por línea.
- Respuesta correcta obligatoria.
- Imagen opcional de la pregunta.

**Estados y validaciones:**

- No permitir guardar una pregunta sin enunciado o respuesta.
- No permitir valores de puntos vacíos, no numéricos o menores/iguales a cero.
- Confirmar antes de eliminar categoría (la acción borra sus preguntas) o pregunta.
- La duplicación crea una nueva pregunta, con nueva ID, y sube inicialmente su valor en 10 puntos.
- Si no hay categorías, el estado vacío guía a crear una.
- Si no hay preguntas en la categoría, conservar el contexto y mostrar CTA `Nueva pregunta`.

---

### C. Diálogo “Preparar partida”

**Propósito:** última revisión antes de empezar; crea una instancia independiente de la partida.

**Contenido:**

- Título `Preparar partida` y título visible del juego.
- Selector de cantidad de equipos (2–8).
- Filas de equipos con nombre y color.
- Acciones `Cancelar` e `Iniciar partida`.

**Regla importante:** los cambios hechos aquí se aplican únicamente a la nueva partida. No cambian el juego guardado.

**Bloqueo:** no debe poder iniciarse un juego que no tenga al menos una pregunta en alguna categoría. Mostrar un mensaje que indique que se deben añadir preguntas primero.

---

### D. Partida activa: tablero

**Propósito:** pantalla principal para jugar y proyectar.

**Jerarquía visual:**

1. Barra superior oscura y estable con controles y marcador.
2. Título del juego y contador de cartas disponibles.
3. Tablero de categorías y cartas de puntos.

**Barra superior:**

- `Salir` (mantiene la partida como “en curso”).
- `Historial` (abre historial de ese juego sin cerrar la partida).
- `Finalizar` (cierra la partida y calcula ganador).
- Tarjeta por equipo: nombre, puntaje, color y controles rápidos `−10` / `+10`.

**Tablero:**

- Cada categoría tiene un nombre y un color propios.
- Las preguntas de una categoría se ordenan de mayor a menor valor.
- Cada carta disponible muestra su puntaje.
- Una carta usada cambia a estado bloqueado y muestra `✓`.
- Las cartas usadas no se pueden seleccionar nuevamente.
- El layout debe distribuir categorías en hasta cinco columnas y agregar filas al ser necesario. Debe reducir la densidad de manera legible cuando hay muchas categorías o preguntas. Si el rediseño lo requiere, se puede usar desplazamiento o paginación, pero no se deben ocultar cartas sin indicarlo.

**Estados:**

- Juego sin categorías: mensaje explicativo.
- Juego con categorías sin preguntas: categoría visible, sin cartas.
- Todas las cartas usadas: mantener tablero visible e invitar a finalizar.

---

### E. Partida activa: pregunta

**Propósito:** mostrar la carta elegida a participantes y anfitrión.

**Al seleccionar una carta:**

- La carta se marca usada de inmediato y la partida se guarda.
- Se conserva la barra superior con el marcador y accesos principales.
- Se muestra categoría, valor en puntos, imagen opcional, enunciado y alternativas opcionales.
- CTA único y claro: `Mostrar respuesta`.
- Acción secundaria: `Tablero`.

**Regla:** no debe revelarse la respuesta antes de que el anfitrión use el CTA.

---

### F. Partida activa: respuesta y puntos

**Propósito:** revelar solución y asignar puntos rápidamente.

**Contenido:**

- Se conserva en pantalla el enunciado y aparece la respuesta destacada.
- Área `Asignar puntos` con un botón por equipo: `+{valor} {nombre del equipo}`.
- Hasta cuatro botones por fila; los equipos adicionales ocupan una segunda fila.
- Botón `Volver al tablero`.

**Reglas:**

- Otorgar puntos actualiza inmediatamente el marcador y el historial persistente.
- Los controles `−10` / `+10` de la barra permiten correcciones manuales incluso fuera de una carta.
- Puede volver al tablero sin otorgar puntos.

---

### G. Historial global

**Propósito:** consultar todas las partidas realizadas.

**Contenido:**

- Misma barra lateral de administración.
- Encabezado `Historial de partidas`.
- Lista cronológica descendente.

**Cada registro muestra:**

- Estado: `FINALIZADA` o `EN CURSO`.
- Título visible del juego y su nombre interno.
- Equipos y puntajes.
- Ganador si terminó; fecha de inicio si continúa en curso.

**Estado vacío:** explicar que las partidas aparecerán al iniciar un juego y ofrecer volver a la biblioteca.

---

### H. Historial de un juego (modal)

**Propósito:** revisar las partidas de un juego puntual sin abandonar el contexto actual.

**Accesos:** menú de una tarjeta en biblioteca y botón `Historial` durante la partida.

**Comportamiento:**

- Filtra únicamente por el juego actual.
- Conserva el mismo formato de registros del historial global.
- Durante una partida debe ser un modal no bloqueante: se puede cerrar y continuar exactamente donde se estaba.

## 6. Flujos críticos

### Crear y jugar un juego

```text
Mis juegos
→ Crear juego
→ Identidad visual / Equipos / Categorías y preguntas
→ Guardar juego
→ Mis juegos
→ Jugar
→ Preparar partida
→ Tablero
→ Pregunta
→ Mostrar respuesta
→ Asignar puntos o volver al tablero
→ Finalizar
→ Historial
```

### Abandonar una partida sin perderla

```text
Partida activa → Salir → Confirmar
→ Biblioteca

Resultado: la partida permanece con estado “en curso” en el historial,
incluyendo equipos, puntajes y cartas usadas.
```

### Finalizar una partida

```text
Partida activa → Finalizar → Confirmar
→ estado “finalizado” + fecha de finalización + ganador(es)
→ Historial
```

Si hay empate, el ganador contiene los nombres de todos los equipos con el puntaje máximo.

## 7. Modelo de datos que el frontend debe respetar

### Juego

```json
{
  "id": "id-unico",
  "name": "Trivia de Navidad",
  "title": "¿Cuánto conoces de Navidad?",
  "background_color": "#111827",
  "background_image": "/ruta/local/fondo.jpg",
  "accent_color": "#5EEAD4",
  "text_color": "#F8FAFC",
  "card_color": "#243047",
  "font_family": "Arial",
  "teams": [
    { "name": "Renos", "color": "#22C7A9" },
    { "name": "Duendes", "color": "#F26B9A" }
  ],
  "categories": [
    {
      "id": "categoria-id",
      "name": "Películas",
      "color": "#3B82F6",
      "questions": [
        {
          "id": "pregunta-id",
          "value": 20,
          "question": "¿Pregunta?",
          "choices": ["Opción A", "Opción B"],
          "answer": "Respuesta correcta",
          "image_path": "/ruta/local/imagen.png"
        }
      ]
    }
  ],
  "created_at": "2026-10-10T10:00:00-05:00",
  "updated_at": "2026-10-10T11:00:00-05:00"
}
```

### Partida / historial

```json
{
  "id": "sesion-id",
  "game_id": "id-del-juego",
  "game_name": "Trivia de Navidad",
  "game_title": "¿Cuánto conoces de Navidad?",
  "status": "en curso",
  "started_at": "2026-10-10T10:30:00-05:00",
  "ended_at": "",
  "teams": [
    { "name": "Renos", "color": "#22C7A9", "score": 40 },
    { "name": "Duendes", "color": "#F26B9A", "score": 30 }
  ],
  "used_cards": ["categoria-id:pregunta-id"],
  "winner": ""
}
```

## 8. Estados, persistencia y reglas de negocio

| Elemento | Regla |
| --- | --- |
| Juegos | Se guardan de forma independiente y pueden coexistir sin límite práctico. |
| Partida | Es una instantánea del juego y de los equipos al momento de iniciarla. |
| Equipos de partida | Pueden diferir de los equipos predeterminados sin alterar el juego. |
| Pregunta usada | Se identifica como `category_id:question_id`; queda bloqueada en esa partida. |
| Historial | Las partidas se crean al iniciar, se actualizan con cada puntaje/carta y se finalizan explícitamente. |
| Eliminar juego | Conserva los registros anteriores del historial. |
| Imagen local | Se guarda la ruta; si el archivo se mueve o desaparece, se usa el color de fondo. |

En la implementación actual, los datos se guardan en:

- `storage/games.json`: catálogo de juegos.
- `storage/history.json`: partidas e historial.

En la primera ejecución se importa el banco existente de 25 preguntas como `Trivia inicial`. Los archivos `game_data.json` y `config.example.json` son solo la fuente de esa primera importación, no el almacenamiento principal.

## 9. Sistema visual de referencia

El frontend puede proponer un rediseño completo, pero debe conservar una estética de aplicación moderna, clara y apta para proyección.

**Dirección actual:**

- Administración: fondo gris azulado muy claro, tarjetas blancas, barra lateral azul marino.
- Partida: fondo oscuro configurable por juego, tarjetas de pregunta contrastadas y tipografía grande.
- Botón primario: azul vivo.
- Acento: turquesa por defecto, personalizable por juego.
- Estados: verde para finalizada, ámbar para en curso, rojo solo para acciones destructivas.

**Tokens iniciales:**

```text
sidebar:          #111A2E
surface:          #F5F7FB
text strong:      #16213A
text muted:       #64748B
primary:          #1778D4
default accent:   #5EEAD4
game background:  #111827
game card:        #243047
```

**Accesibilidad y legibilidad:**

- Mantener contrastes AA como mínimo, especialmente en texto sobre fondos configurables.
- No depender únicamente del color para estado de carta usada o estado de partida.
- Usar objetivos táctiles/clicables amplios.
- En la vista de juego, priorizar tamaños grandes y texto corto; es una pantalla compartida.
- Truncar textos largos en tarjetas/tablas, pero mostrar el contenido completo al editar o jugar.

## 10. Componentes reutilizables sugeridos

- `AppSidebar`
- `PrimaryButton`, `SecondaryButton`, `DestructiveButton`, `IconButton`
- `GameCard`
- `EmptyState`
- `GameEditorTabs`
- `ColorField` / selector de color
- `ImagePicker` con quitar y previsualización
- `TeamEditorRow`
- `CategoryList`
- `QuestionTable`
- `QuestionForm`
- `ConfirmDialog`
- `HistoryRow`
- `ScoreTile`
- `GameTopBar`
- `BoardCategory`
- `QuestionCard`
- `AwardPointsPanel`

## 11. Fuera de alcance

No implementar ni reintroducir como requisito del producto:

- navegación por diapositivas;
- animaciones o automatizaciones propias de PowerPoint;
- cuenta regresiva obligatoria;
- pantalla de “tiempo agotado”;
- flujos que dependan de macros de PowerPoint;
- dependencias de un número fijo de 5 categorías o 25 preguntas.

Un temporizador opcional podría considerarse una mejora futura, pero no debe condicionar la arquitectura ni el flujo actual.

## 12. Criterios de aceptación para el frontend

El frontend estará listo cuando una persona pueda:

1. Crear dos juegos visualmente distintos y encontrarlos en la biblioteca.
2. Configurar cantidad, nombres y colores de equipos.
3. Crear categorías, preguntas, alternativas, respuestas, valores e imágenes.
4. Iniciar una partida con equipos temporalmente distintos a los predeterminados.
5. Jugar una carta completa: abrir, revelar, otorgar puntos y ver que queda bloqueada.
6. Consultar el historial sin salir de una partida activa.
7. Finalizar una partida y ver ganador, puntajes y estado final en historial.
8. Salir de una partida antes de terminar y comprobar que sigue guardada como “en curso”.
9. Usar el juego sin una imagen de fondo o con una ruta de imagen rota sin que falle la interfaz.
10. Leer sin dificultad el contenido esencial desde una pantalla de proyección.

## 13. Archivos de referencia de la implementación actual

- `main.py`: interfaz actual en Tkinter, flujos y pantallas.
- `store.py`: persistencia, modelo de datos, importación inicial y reglas de historial.
- `game_data.json`: banco original que se importa como juego inicial.
- `config.example.json`: datos base usados durante la importación inicial.
- `README.md`: instrucciones para ejecutar la aplicación.
- `FRONTEND_SCREEN_CATALOG.md`: inventario cerrado de pantallas, modales y estados límite que la IA debe diseñar; es el complemento obligatorio de este brief.
- `../Quiz_Studio_26_pantallas_PNG/`: referencia visual de 26 mockups PNG y su guía. Sirve para el lenguaje visual (no para añadir lógica de PowerPoint).

El objetivo de la IA de frontend no es preservar Tkinter ni su layout actual; debe preservar los flujos, los datos y las reglas descritas en este documento, mejorando coherencia visual, interacción y adaptabilidad.
