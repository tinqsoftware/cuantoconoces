# Catálogo exhaustivo de ventanas y casuísticas — Quiz Studio

> **Propósito de este documento:** entregar a una IA de diseño/frontend una lista cerrada de las vistas, ventanas, modales, mensajes y estados que necesita diseñar para Quiz Studio. Debe usarse junto con [FRONTEND_BRIEF.md](FRONTEND_BRIEF.md), que explica el producto, datos y reglas de negocio.

> **Convención:**
>
> - `P` = pantalla o vista de nivel principal.
> - `V` = ventana de trabajo o diálogo grande.
> - `M` = modal, menú contextual, confirmación o mensaje.
> - `E` = estado alternativo dentro de una pantalla.
> - **Implementado** indica que el caso ya está cubierto por la aplicación Tkinter. **Objetivo UX** identifica una mejora opcional que la IA de frontend puede elevar, sin cambiar las reglas ni omitir el caso.

---

## 0. Mapa total de navegación

```text
P-01 Biblioteca / Mis juegos
├── V-01 Editor de juego
│   ├── Tab Identidad visual
│   ├── Tab Equipos
│   └── Tab Categorías y preguntas
│       ├── V-02 Editor de categoría
│       └── V-03 Editor de pregunta
├── V-04 Preparar partida
│   └── P-03 Tablero de partida
│       ├── P-04 Pregunta abierta
│       ├── P-05 Respuesta y asignación de puntos
│       └── V-05 Historial del juego en curso
├── M-01 Menú contextual de juego
└── V-05 Historial filtrado por juego

P-02 Historial global
└── V-05 Historial filtrado por juego (cuando se abre desde una tarjeta)

Mensajes y confirmaciones transversales:
M-02 a M-12
```

No hay pantalla de bienvenida, login, cronómetro, “tiempo agotado”, presentación, diapositivas ni resultados con animación obligatoria.

---

### 0.1 Trazabilidad con los 26 mockups de referencia

Los PNG viven en `../Quiz_Studio_26_pantallas_PNG/Quiz_Studio_PNG/`. Esta matriz evita que la IA de frontend diseñe sólo el flujo ideal y omita alguno de los estados visuales proporcionados.

| PNG | Estado del catálogo | Qué debe representar |
| --- | --- | --- |
| `01_library.png` | P-01 / E-01 | Biblioteca con tarjetas de juego. |
| `02_menu.png` | M-01 | Menú contextual de un juego. |
| `03_empty.png` | P-01 / E-02 | Biblioteca sin juegos. |
| `04_identity.png` | V-01.A | Identidad visual y previsualización. |
| `05_teams.png` | V-01.B | Equipos predeterminados. |
| `06_questions.png` | V-01.C | Categoría elegida con sus preguntas. |
| `07_questionsNoCats.png` | V-01.C / E-03 | Editor sin categorías. |
| `08_questionsNoQs.png` | V-01.C / E-04 | Categoría elegida sin preguntas. |
| `09_categoryModal.png` | V-02 | Crear/editar categoría. |
| `10_questionModal.png` | V-03 | Crear/editar pregunta. |
| `11_unsavedDialog.png` | M-03 | Confirmar descarte de cambios. |
| `12_prepare.png` | V-04 | Preparar equipos de una partida. |
| `13_noQuestionsDialog.png` | M-14 | Intento de jugar sin preguntas. |
| `14_board.png` | P-03 / E-05 | Tablero normal. |
| `15_boardNoCats.png` | P-03 / E-06 | Juego sin categorías. |
| `16_allUsed.png` | P-03 / E-08 | Todas las cartas usadas. |
| `17_question.png` | P-04 | Pregunta con imagen. |
| `18_questionPlain.png` | P-04 | Pregunta sólo de texto. |
| `19_answer.png` | P-05 | Respuesta y asignación de puntos. |
| `20_history.png` | P-02 / E-11 | Historial global con resultados. |
| `21_historyEmpty.png` | P-02 / E-12 | Historial global vacío. |
| `22_historyModal.png` | V-05 / E-10 | Historial abierto durante una partida. |
| `23_exitDialog.png` | M-15 | Salir conservando partida en curso. |
| `24_finishDialog.png` | M-16 | Confirmación de finalización. |
| `25_saved.png` | M-17 | Resultado final guardado. |
| `26_deleteDialog.png` | M-02 | Confirmación de eliminar juego. |

---

## 1. Reglas globales de presentación

### 1.1 Dos modos visuales

| Modo | Dónde aplica | Prioridad visual |
| --- | --- | --- |
| **Administración** | Biblioteca, historial y editor | Densidad controlada, formularios claros, lectura de datos y edición segura. |
| **Juego en vivo** | Tablero, pregunta, respuesta | Legibilidad a distancia, interacción veloz y marcador siempre visible. |

### 1.2 Dimensiones y comportamiento

- Tamaño mínimo de la ventana: **1120 × 680 px**.
- Tamaño de referencia: **1360 × 820 px** y pantalla 16:9.
- Atajo `F11`: entrar/salir de pantalla completa.
- Atajo `Esc`: salir de pantalla completa; no debe descartar datos ni cerrar una partida.
- El editor se abre encima de la biblioteca; el juego ocupa el área principal completa.
- El historial de un juego abierto durante una partida no debe destruir, pausar ni reiniciar la partida.
- Las acciones destructivas deben pedir confirmación explícita.

### 1.3 Estados de controles (aplican a todos)

Cada diseño de botón, tarjeta seleccionable, input y carta de juego debe contemplar:

- normal;
- hover;
- foco por teclado;
- presionado;
- deshabilitado;
- error de validación (en inputs);
- carga/proceso, si el frontend realiza operaciones asíncronas.

### 1.4 Navegación persistente de administración

La barra lateral se muestra en P-01 y P-02.

| Elemento | Acción | Estado activo |
| --- | --- | --- |
| Logotipo `QUIZ STUDIO` | Identidad, sin acción obligatoria | — |
| `Mis juegos` | Ir a P-01 | Fondo destacado cuando está seleccionado |
| `Historial` | Ir a P-02 | Fondo destacado cuando está seleccionado |
| Ayuda corta | Explica que cada juego tiene banco, equipos y estilo propio | — |
| Ayuda de pantalla completa | Muestra `F11 Pantalla completa` | — |

---

## 2. P-01 — Biblioteca “Mis juegos”

**Tipo:** pantalla principal de administración.  
**Estado actual:** implementado.  
**Entrada:** al abrir la aplicación, al guardar/cancelar el editor, al salir de una partida o al tocar `Mis juegos`.  
**Salida:** editor, preparación de partida, menú contextual, historial filtrado.

### 2.1 Composición obligatoria

1. Barra lateral persistente.
2. Encabezado:
   - título `Mis juegos`;
   - texto: “Crea una trivia para cada ocasión y vuelve a jugarla cuando quieras.”;
   - CTA primario `+ Crear juego`.
3. Contenedor desplazable verticalmente.
4. Rejilla de tarjetas: tres columnas en escritorio amplio, dos o una si el ancho disponible lo exige.

### 2.2 Tarjeta de juego

Cada tarjeta representa un objeto `Game`.

| Área | Datos / comportamiento |
| --- | --- |
| Cabecera visual | Color de fondo del juego, franja de acento, título visible y nombre interno. Puede usar imagen de fondo si el rediseño la resuelve con suficiente contraste. |
| Resumen | `{n} categorías · {n} preguntas`. |
| Metadato | `Editado dd/mm/aaaa · hh:mm`. |
| Acción secundaria | `Editar`. |
| Acción primaria | `Jugar`. |
| Menú de opciones | Ícono `…`; abre M-01. |

**Estados de tarjeta:** normal, hover, foco, título largo (máximo dos/tres líneas con truncado o ajuste seguro), juego sin categorías, juego sin preguntas y colores personalizados de bajo contraste.

### 2.3 E-01 — Biblioteca con juegos

**Precondición:** existe al menos un juego guardado.

**Casos a representar:**

- 1 juego.
- 2–3 juegos (fila incompleta).
- muchas tarjetas y desplazamiento vertical.
- juego recién creado/actualizado aparece primero por `updated_at`.
- juego con título largo.
- juego cuya imagen local de fondo no está disponible: degradar a color de fondo, sin mostrar error técnico.

### 2.4 E-02 — Biblioteca vacía

**Precondición:** no hay juegos en `games.json`.

**Contenido:**

- ícono/ilustración sobria;
- titular `Aún no hay juegos`;
- ayuda: “Crea el primero para empezar a diseñar tus preguntas.”;
- CTA `+ Crear juego`.

No debe haber una rejilla vacía sin explicación.

### 2.5 M-01 — Menú contextual de un juego

**Disparador:** pulsar `…` en una tarjeta.

| Opción | Resultado |
| --- | --- |
| `Duplicar juego` | Crea una copia independiente y actualiza la biblioteca. |
| `Ver historial de este juego` | Abre V-05 con filtro por `game_id`. |
| `Eliminar juego` | Abre M-02. Debe estar visualmente separada/destructiva. |

**Estados:** menú anclado a tarjeta, menú en borde de pantalla (no debe cortarse), cierre por clic exterior o `Esc`.

### 2.6 M-02 — Confirmación “Eliminar juego”

**Disparador:** opción destructiva del menú contextual.

**Contenido exacto:**

- título: `Eliminar juego`;
- mensaje: `¿Eliminar “{nombre del juego}”? El historial se conservará.`;
- acción secundaria `Cancelar`;
- acción destructiva `Eliminar juego`.

**Resultado:** se elimina solo la definición del juego; no se eliminan sus sesiones históricas. Regresa a P-01, en E-01 o E-02 según corresponda.

---

## 3. V-01 — Editor de juego

**Tipo:** ventana grande/modal de administración con pestañas.  
**Estado actual:** implementado, incluida la advertencia por cambios sin guardar.  
**Entrada:** `+ Crear juego` o `Editar` desde una tarjeta.  
**Salida:** P-01 tras guardar/cancelar.

### 3.1 Cabecera global del editor

| Caso | Título | Acción primaria |
| --- | --- | --- |
| Nuevo juego | `Nuevo juego` | `Guardar juego` |
| Editar juego | `Configuración del juego` | `Guardar juego` |

Acciones constantes: `Cancelar` y `Guardar juego`.

**M-03 — Descartar cambios sin guardar**

- Disparador: cerrar/cancelar y hay diferencias respecto al último guardado.
- Mensaje: `Tienes cambios sin guardar. ¿Quieres descartarlos?`.
- Acciones: `Seguir editando`, `Descartar cambios`.
- No aparece si no hubo cambios.

### 3.2 Navegación interna

Tres pestañas:

1. `Identidad visual`.
2. `Equipos`.
3. `Categorías y preguntas`.

Al cambiar de pestaña no se deben perder cambios en campos ni selecciones. `Guardar juego` guarda los cambios de todas las pestañas en un solo objeto.

---

### 3.3 V-01.A — Pestaña “Identidad visual”

**Objetivo:** dar nombre e identidad al juego.

| Campo / elemento | Tipo | Obligatorio | Casos |
| --- | --- | --- | --- |
| Nombre para identificarlo en biblioteca | input de una línea | Sí | vacío = error M-04; largo = truncar solo en tarjetas, no aquí. |
| Título visible | input de una línea | Sí | vacío = error M-04; se proyecta durante el juego. |
| Vista previa | bloque visual | — | Debe reaccionar a nombre, título, colores, tipografía e imagen. |
| Fondo | hex + selector de color | No, tiene valor inicial | valor inválido = color seguro por defecto. |
| Color destacado | hex + selector de color | No | ver caso de contraste. |
| Texto | hex + selector de color | No | ver caso de contraste. |
| Cartas | hex + selector de color | No | — |
| Tipografía instalada | input o selector | No | valor vacío = `Arial`. |
| Imagen de fondo | input de ruta + `Examinar` + `Quitar` | No | no encontrada = mantener color de fondo; no bloquear guardado. |

**Vista previa, casos obligatorios:**

- sin imagen: usar color de fondo;
- imagen cargada: mostrar recorte tipo cover;
- imagen rota/no disponible: color de fondo y, opcionalmente, aviso no bloqueante;
- título vacío durante escritura: placeholder `Título del juego`;
- nombre vacío durante escritura: placeholder `Nombre interno`;
- combinación de colores poco contrastada: advertencia de accesibilidad recomendada, sin impedir guardar salvo que el producto defina lo contrario.

**M-04 — Error de identidad incompleta**

- Disparador: guardar sin nombre interno o título visible.
- Título: `Faltan datos`.
- Mensaje: `Escribe el nombre interno y el título visible del juego.`
- Acción: `Entendido`; devolver foco al primer campo vacío.

**M-05 — Selector de color del sistema o personalizado**

- Disparador: botón `Elegir` de cualquier color.
- Debe actualizar el valor hexadecimal y la vista previa inmediatamente.
- Cancelar no cambia el color.

**M-06 — Selector de archivo de imagen**

- Disparador: `Examinar` para fondo o imagen de pregunta.
- Filtros: PNG, JPG/JPEG, WEBP, GIF, BMP y todos los archivos.
- Cancelar no modifica el campo.
- Seleccionar archivo guarda una ruta local; no se copia el archivo.

---

### 3.4 V-01.B — Pestaña “Equipos”

**Objetivo:** definir el conjunto predeterminado que se propone al iniciar partidas.

**Elementos:**

- título `Equipos predeterminados`;
- explicación de que la preparación previa permite cambios temporales;
- control `Cantidad de equipos` (mínimo 2, máximo 8);
- botón `Aplicar` o actualización inmediata;
- tabla/lista de filas de equipo.

**Fila por equipo:**

| Columna | Contenido |
| --- | --- |
| Orden | `01`, `02`, etc. |
| Nombre visible | Input de texto. |
| Color | Hex + botón de selector de color. |

**Casos:**

- aumentar cantidad: conservar equipos existentes y crear nuevos como `Equipo N` con color de la paleta;
- reducir cantidad: pedir confirmación **objetivo UX** si se perderían valores que el usuario ya editó; la implementación actual reduce directamente;
- nombre vacío al guardar: usar `Equipo N`;
- color inválido: usar color de respaldo;
- 8 equipos: la lista debe seguir siendo legible con desplazamiento vertical si hace falta.

---

### 3.5 V-01.C — Pestaña “Categorías y preguntas”

**Objetivo:** editar contenido del tablero.

**Composición de escritorio:**

```text
┌─────────────────────┬───────────────────────────────────────────┐
│ Categorías          │ Preguntas · {Categoría seleccionada}       │
│ [+]                 │                         [+ Nueva pregunta]│
│                     ├────────┬─────────────────┬────────────────┤
│ Categoría · 5       │ Valor  │ Pregunta        │ Respuesta      │
│ Categoría · 0       ├────────┼─────────────────┼────────────────┤
│                     │ 50     │ Texto truncado  │ Texto truncado │
│ [Editar] [Eliminar] │ ...                                      │
│                     ├───────────────────────────────────────────┤
│                     │ [Editar] [Duplicar] [Eliminar]            │
└─────────────────────┴───────────────────────────────────────────┘
```

**Lista de categorías:**

- Muestra `{nombre} · {cantidad de preguntas}`.
- La categoría activa tiene estado seleccionado claro, además del color propio si se usa.
- Botón `+` abre V-02 en modo nueva.
- Botones `Editar` y `Eliminar` requieren una categoría seleccionada.

**Tabla de preguntas:**

- Columnas: `Valor`, `Pregunta`, `Respuesta`.
- Orden: mayor a menor valor.
- Textos largos se truncan en tabla y se ven completos al abrir el editor.
- Doble clic y botón `Editar` abren V-03 en modo editar.

**E-03 — Sin categorías**

- Panel izquierdo vacío con CTA `+`.
- Panel derecho no debe parecer roto: titular `Preguntas`, mensaje `Crea o selecciona una categoría primero.` y CTA opcional `Crear categoría`.
- `+ Nueva pregunta`, `Editar`, `Duplicar` y `Eliminar` de pregunta deben estar deshabilitados o explicar el requisito.

**E-04 — Categoría seleccionada sin preguntas**

- Mantener encabezado `Preguntas · {categoría}`.
- Tabla vacía con mensaje y CTA `+ Nueva pregunta`.

**M-07 — Información: falta seleccionar categoría**

- Disparador: editar/eliminar categoría sin selección, o crear pregunta sin categoría.
- Mensaje contextual: `Selecciona una categoría.` o `Crea o selecciona una categoría primero.`

**M-08 — Información: falta seleccionar pregunta**

- Disparador: editar, duplicar o eliminar pregunta sin selección.
- Mensaje: `Selecciona una pregunta.`

---

## 4. V-02 — Editor de categoría

**Tipo:** diálogo compacto.  
**Modos:** nueva categoría y editar categoría existente.

| Elemento | Nueva | Editar |
| --- | --- | --- |
| Título | `Nueva categoría` | `Editar categoría` |
| Nombre | Vacío | Valor existente |
| Color | Azul inicial | Color existente |
| Acción primaria | `Guardar` | `Guardar` |

**Campos:**

- `Nombre de la categoría` (obligatorio).
- `Color` (hexadecimal y selector visual).

**M-09 — Error de categoría sin nombre**

- Disparador: guardar con nombre vacío.
- Título: `Falta un nombre`.
- Mensaje: `Escribe el nombre de la categoría.`

**M-10 — Confirmación de eliminar categoría**

- Disparador: `Eliminar` dentro de V-01.C.
- Mensaje: `¿Eliminar “{nombre}” y sus preguntas?`.
- Acciones: `Cancelar`, `Eliminar categoría`.
- Resultado: eliminar categoría y todas sus preguntas; seleccionar la primera categoría restante o mostrar E-03.

---

## 5. V-03 — Editor de pregunta

**Tipo:** diálogo grande de formulario.  
**Modos:** nueva pregunta y editar pregunta.

### 5.1 Estructura del formulario

| Orden | Campo | Tipo | Regla |
| --- | --- | --- | --- |
| 1 | Valor de la carta | número entero | obligatorio, mayor que 0. |
| 2 | Pregunta | textarea | obligatoria. |
| 3 | Alternativas opcionales | textarea | una alternativa por línea; puede estar vacío. |
| 4 | Respuesta | textarea | obligatoria. |
| 5 | Imagen opcional | ruta + `Examinar` + `Quitar` | ruta local; puede estar vacía. |
| 6 | Acciones | `Cancelar` / `Guardar pregunta` | — |

### 5.2 Casuísticas

- nueva pregunta: campos vacíos, valor sugerido 10;
- editar pregunta: cargar todos los campos existentes;
- alternativas vacías: la partida no mostrará bloque de opciones;
- una alternativa por línea: se eliminan líneas vacías al guardar;
- imagen no existente: no bloquear guardado, mostrar fondo/espacio sin imagen al jugar;
- texto largo: textarea con scroll y contador opcional, sin truncar el dato;
- guardar exitosamente: regresar a V-01.C, conservar la categoría seleccionada y refrescar conteo/lista.

### 5.3 M-11 — Error de valor inválido

- Disparador: valor vacío, no numérico, decimal no permitido, cero o negativo.
- Título: `Valor inválido`.
- Mensaje: `El valor debe ser un número entero positivo.`
- Devolver foco al campo de valor.

### 5.4 M-12 — Error de pregunta/respuesta incompletas

- Disparador: falta pregunta o falta respuesta.
- Título: `Faltan datos`.
- Mensaje: `Completa la pregunta y la respuesta.`
- Resaltar el/los campos necesarios.

### 5.5 Duplicar y eliminar pregunta

| Acción | Resultado |
| --- | --- |
| `Duplicar` | Copia la pregunta, asigna una ID nueva y propone valor original + 10. Debe actualizar la tabla. |
| `Eliminar` | Abre M-13. |

**M-13 — Confirmación eliminar pregunta**

- Texto: `¿Eliminar esta pregunta del juego?`.
- Acciones: `Cancelar` y `Eliminar pregunta`.
- Resultado: tabla actualizada; si era la última, mostrar E-04.

---

## 6. V-04 — Preparar partida

**Tipo:** diálogo previo al juego.  
**Estado actual:** implementado.  
**Entrada:** `Jugar` desde una tarjeta válida.

### 6.1 Composición

- título `Preparar partida`;
- subtítulo con el título visible del juego;
- selector `Cantidad de equipos` (2–8) y acción de aplicar;
- una fila por equipo: etiqueta, nombre y color;
- `Cancelar`;
- CTA `Iniciar partida`.

### 6.2 Reglas y casos

- Inicia con los equipos predeterminados del juego.
- Ajustar aquí cantidad, nombres o colores no altera la configuración base del juego.
- Al agregar equipos: crear `Equipo N` y asignar color de paleta.
- Al reducir equipos: conservar solo los primeros N para esta partida.
- Nombres vacíos: `Equipo N`.
- Colores inválidos: color de respaldo.
- 8 equipos: mantener toda la lista accesible; agregar scroll si no cabe verticalmente.

### 6.3 M-14 — Juego sin preguntas

**Disparador:** pulsar `Jugar` y ninguna categoría tiene preguntas.

- Título: `Juego vacío`.
- Mensaje: `Añade al menos una pregunta antes de iniciar una partida.`
- Acción: `Entendido`.
- No abrir V-04.

---

## 7. P-03 — Tablero de partida

**Tipo:** pantalla de juego en vivo.  
**Estado actual:** implementado.  
**Entrada:** `Iniciar partida` en V-04, retorno desde P-04/P-05.  
**Salida:** P-04, V-05, confirmaciones de salida/finalización o P-01/P-02.

### 7.1 Barra superior de la partida

Siempre visible en P-03, P-04 y P-05.

| Zona | Elementos |
| --- | --- |
| Izquierda | `← Salir`; en P-04/P-05 también `Tablero`. |
| Centro/derecha | Marcadores de todos los equipos. Cada marcador: nombre, puntaje, color y controles `−10` / `+10`. |
| Derecha | `Historial`, `Finalizar`. |

**Casuísticas de marcador:**

- 2–4 equipos: tarjetas amplias en una fila.
- 5–8 equipos: compactar, permitir scroll horizontal o una disposición alternativa sin cortar ni ocultar equipos.
- nombre de equipo largo: truncar visualmente con tooltip/lectura completa accesible.
- puntajes negativos permitidos por ajuste manual.
- cada ajuste se persiste de inmediato.

### 7.2 Cuerpo del tablero

- Título visible del juego.
- Contador `{n} cartas disponibles`.
- Conjunto de categorías.

**Categoría en tablero:**

- nombre de categoría;
- color identificador;
- preguntas ordenadas por valor descendente;
- una carta por pregunta.

**Carta disponible:**

- muestra valor;
- es clicable;
- al clicarse, se persiste como usada inmediatamente y se abre P-04.

**Carta usada:**

- muestra `✓`;
- estilo inactivo/atenuado;
- no es clicable;
- no depender solo del color para comunicar que fue usada.

### 7.3 E-05 — Tablero normal

**Precondición:** existen categorías con preguntas y al menos una carta sin usar.

**Reglas de layout:**

- hasta cinco categorías por fila en escritorio amplio;
- si hay más, formar filas adicionales o emplear desplazamiento/paginación;
- no ocultar cartas sin un indicador claro;
- si hay muchas preguntas por categoría, evitar comprimir los botones hasta volverlos ilegibles: preferir scroll/paginación/agrupación del tablero.

### 7.4 E-06 — Juego sin categorías

**Precondición:** el juego se abrió o se modificó para no tener categorías.

- Mensaje centrado: `Este juego aún no tiene categorías.`
- Mantener barra superior operativa, incluyendo Salir e Historial.
- No mostrar un tablero vacío ambiguo.

### 7.5 E-07 — Categoría sin preguntas

- Mostrar encabezado de categoría.
- Mostrar estado vacío compacto, por ejemplo `Sin preguntas`.
- No mostrar botones/espacios que parezcan cartas rotas.

### 7.6 E-08 — Todas las cartas usadas

- Contador `0 cartas disponibles`.
- Todas las cartas aparecen usadas/bloqueadas.
- Mensaje visible: `No quedan cartas. Puedes finalizar la partida.` y CTA `Finalizar partida`.
- No reiniciar el tablero automáticamente.

---

## 8. P-04 — Pregunta abierta

**Tipo:** etapa de juego, no una ventana separada.  
**Entrada:** seleccionar carta disponible en P-03.  
**Salida:** P-05 o P-03.

### 8.1 Contenido fijo

- Barra superior de partida.
- Acción secundaria `Tablero`.
- Nombre de categoría, en mayúsculas o estilo de etiqueta.
- `{valor} puntos`.
- Panel/tarjeta central de pregunta.
- CTA primario `Mostrar respuesta`.

### 8.2 Casuísticas del panel

| Caso | Contenido |
| --- | --- |
| Pregunta sin imagen ni alternativas | Pregunta centrada, con espacio generoso. |
| Pregunta con alternativas | Enunciado + lista de alternativas, sin revelar respuesta. |
| Pregunta con imagen | Imagen con proporción contenida, enunciado reubicado, alternativas si existen. |
| Imagen rota/no disponible | Omitir zona de imagen y reacomodar texto. No mostrar una imagen rota. |
| Pregunta muy larga | Ajustar tipografía/scroll interno de manera que no se corte. |
| Alternativas largas | Mantener jerarquía legible, permitir scroll si la altura lo exige. |

### 8.3 Regla de persistencia

Al entrar en P-04 la carta ya está en `used_cards` y la partida ya fue guardada. Volver a P-03 no vuelve a habilitarla.

---

## 9. P-05 — Respuesta y asignación de puntos

**Tipo:** etapa posterior de P-04.  
**Entrada:** CTA `Mostrar respuesta`.  
**Salida:** P-03 o actualización de la misma P-05 tras puntuar.

### 9.1 Contenido

- Barra superior de partida y acción `Tablero`.
- Categoría, valor y enunciado de la pregunta.
- Respuesta correcta destacada con mayor jerarquía visual.
- Bloque `Asignar puntos:`.
- Botón de puntos por cada equipo: `+{valor} {nombre}`.
- Acción `Volver al tablero`.

### 9.2 Casuísticas

| Caso | Diseño esperado |
| --- | --- |
| 2–4 equipos | Botones de asignación en una fila. |
| 5–8 equipos | Máximo cuatro por fila; segunda fila o layout compacto. |
| Ningún equipo recibe punto | Volver al tablero sin pulsar un botón de asignación. |
| Un equipo recibe punto | Puntaje se actualiza, persiste y permanece en P-05. |
| Corrección manual | Usar `−10`/`+10` de la barra; el estado sigue en P-05. |
| Respuesta extensa | Mantener texto visible o habilitar scroll dentro del panel, sin tapar los botones. |

**Regla:** otorgar los puntos no debe habilitar la carta ni crear una segunda entrada de historial.

---

## 10. V-05 — Historial de partidas de un juego

**Tipo:** ventana/modal no bloqueante.  
**Entradas:** M-01 desde la biblioteca o botón `Historial` durante P-03/P-04/P-05.

### 10.1 Composición

- título `Historial de partidas`;
- subtítulo `Este juego`;
- área desplazable de registros;
- botón de cierre estándar.

### 10.2 Registro de historial

| Dato | Forma visual |
| --- | --- |
| Estado | Chip `FINALIZADA` (verde) o `EN CURSO` (ámbar); incluir ícono además de color si es posible. |
| Juego | Título visible en jerarquía principal. |
| Nombre interno | Texto secundario. |
| Equipos / puntajes | `Equipo: puntuación · Equipo: puntuación`. |
| Resultado | `Ganador: {nombre}` si finalizó; `Inició: fecha` si continúa. |
| Cartas usadas | Mostrar `n cartas usadas`; un detalle desplegable por carta es una mejora opcional. |

### 10.3 E-09 — Historial del juego vacío

- Mensaje: `Aún no hay partidas guardadas.`
- No mostrar filas vacías ni errores.

### 10.4 E-10 — Historial durante partida activa

- Debe incluir la sesión recién iniciada como `EN CURSO`.
- Se actualiza cada vez que se usa una carta o cambia puntaje.
- Cerrar vuelve exactamente al estado de juego visible antes de abrirlo.

---

## 11. P-02 — Historial global

**Tipo:** pantalla principal de administración.  
**Entrada:** barra lateral o finalización de una partida.  
**Salida:** P-01 o V-05 desde tarjeta, si se incorpora esa acción.

### 11.1 Composición

- Barra lateral persistente con `Historial` activo.
- Encabezado `Historial de partidas`.
- Texto: `Resultados guardados de todos tus juegos.`
- Lista desplazable de registros, orden descendente por fecha de inicio.

**Cada fila reutiliza el componente descrito en V-05**, pero debe incluir juego y nombre interno porque mezcla distintos juegos.

### 11.2 E-11 — Historial global con partidas

**Casos de mezcla:**

- partidas terminadas y en curso;
- diferentes juegos;
- empate con varios ganadores separados por comas;
- sin ganador todavía;
- equipos con puntajes negativos;
- juego eliminado: el registro sigue mostrándose porque conserva `game_name` y `game_title` como instantánea.

### 11.3 E-12 — Historial global vacío

- Ícono/ilustración simple.
- Título `Todavía no hay partidas`.
- Texto: `Al iniciar un juego, su progreso y resultado aparecerán aquí.`
- CTA: `Ir a Mis juegos`.

---

## 12. Confirmaciones de partida en vivo

### M-15 — Confirmar salida de partida

**Disparador:** `← Salir` en cualquier estado de P-03, P-04 o P-05.

- Título: `Salir de la partida`.
- Mensaje: `La partida en curso quedará guardada en el historial.`
- Acciones: `Continuar jugando` y `Salir`.
- Resultado de salir: persistir estado actual, ir a P-01. La sesión queda `EN CURSO`.

### M-16 — Confirmar finalización

**Disparador:** `Finalizar` en cualquier estado de juego.

- Título: `Finalizar partida`.
- Mensaje: `¿Guardar el resultado final en el historial?`.
- Acciones: `Cancelar`, `Finalizar partida`.
- Resultado: calcular mayor puntaje, cambiar estado a `FINALIZADA`, definir `ended_at`, definir uno o varios ganadores e ir a P-02.

### M-17 — Resultado guardado

**Disparador:** completar M-16.

- Título: `Partida guardada`.
- Mensaje: `Resultado guardado. Ganador: {nombre o “sin definir”}`.
- Acción: `Entendido`.
- Después, P-02 debe mostrar el registro finalizado.

### Casos de ganador

| Condición | Valor visual |
| --- | --- |
| Un puntaje máximo | `Ganador: Equipo A`. |
| Empate | `Ganador: Equipo A, Equipo B`. |
| Todos con 0 | Empate de todos; el frontend puede explicitarlo como `Empate`. |
| Sin equipos (no debe ocurrir por mínimo 2) | `sin definir`. |

---

## 13. Matriz de cobertura por objeto visual

Esta tabla permite comprobar que no falte ningún diseño.

| Objeto | P-01 | V-01 | V-04 | P-03 | P-04 | P-05 | V-05 | P-02 |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Barra lateral administración | Sí | Fondo | Fondo | No | No | No | No | Sí |
| Cabecera de administración | Sí | Propia | No | No | No | No | Propia | Sí |
| Editor de estilo | No | Sí | No | No | No | No | No | No |
| Editor de equipos | No | Sí | Sí, temporal | Marcador | Marcador | Marcador | Lectura | Lectura |
| Categorías / preguntas | Resumen | Sí | No | Sí | Una | Una | No | No |
| Marcador vivo | No | No | No | Sí | Sí | Sí | No | No |
| Historial | Atajo | No | No | Atajo | Atajo | Atajo | Sí | Sí |
| Confirmación destructiva | Eliminar juego | Eliminar categoría/pregunta | No | Salir/finalizar | Salir/finalizar | Salir/finalizar | No | No |

---

## 14. Datos disponibles para poblar cada diseño

### 14.1 Juego

```ts
type Game = {
  id: string;
  name: string;
  title: string;
  background_color: string;
  background_image: string;
  accent_color: string;
  text_color: string;
  card_color: string;
  font_family: string;
  teams: { name: string; color: string }[];
  categories: Category[];
  created_at: string;
  updated_at: string;
};

type Category = {
  id: string;
  name: string;
  color: string;
  questions: Question[];
};

type Question = {
  id: string;
  value: number;
  question: string;
  choices: string[];
  answer: string;
  image_path: string;
};
```

### 14.2 Sesión/historial

```ts
type GameSession = {
  id: string;
  game_id: string;
  game_name: string;
  game_title: string;
  status: "en curso" | "finalizado";
  started_at: string;
  ended_at: string;
  teams: { name: string; color: string; score: number }[];
  // Copia completa e inmutable para esta sesión: permite consultar el
  // historial aunque el juego se edite o elimine después.
  game_snapshot: Game;
  used_cards: string[]; // "{category_id}:{question_id}"
  winner: string;
};
```

---

## 15. Lista de entregables que debe producir la IA de frontend

1. Diseño de P-01 en E-01 y E-02.
2. Diseño de M-01 y M-02.
3. Diseño completo de V-01 con sus tres pestañas, E-03, E-04 y campos en error.
4. Diseño de V-02 y V-03, incluyendo M-09 a M-13.
5. Diseño de V-04 y M-14.
6. Diseño de P-03 en E-05, E-06, E-07 y E-08.
7. Diseño de P-04 con/sin imagen y con/sin alternativas.
8. Diseño de P-05 para 2–4 y 5–8 equipos.
9. Diseño de V-05 en E-09 y E-10.
10. Diseño de P-02 en E-11 y E-12.
11. Diseño de M-15, M-16 y M-17.
12. Especificación de estados hover, foco, deshabilitado, error y responsive para todos los controles reutilizables.

## 16. Lista de verificación final antes de aprobar el frontend

- [ ] Todas las pantallas y modales enumerados arriba tienen diseño, no solo happy path.
- [ ] Las pantallas de juego funcionan bien con 2, 4 y 8 equipos.
- [ ] Se han diseñado preguntas con y sin imagen, y con y sin alternativas.
- [ ] Se han diseñado biblioteca e historiales vacíos.
- [ ] Todos los confirm dialogs tienen salida segura y acción destructiva claramente distinta.
- [ ] Ningún texto esencial depende únicamente del color.
- [ ] El tablero no oculta preguntas cuando hay muchas; tiene una estrategia explícita de scroll o paginación.
- [ ] El historial muestra claramente diferencia entre partida en curso y finalizada.
- [ ] Cambios de configuración no se confunden con cambios temporales de una partida.
- [ ] El resultado se lee con comodidad desde una pantalla grande.
- [ ] El diseño no introduce PowerPoint, temporizadores obligatorios ni flujo de diapositivas.
