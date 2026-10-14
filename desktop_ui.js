/* Quiz Studio desktop UI
 *
 * Esta capa se ejecuta exclusivamente dentro de Qt WebEngine. Los datos viven
 * en Python y se intercambian mediante QWebChannel, sin navegador ni servidor.
 */
(() => {
  'use strict';

  const root = document.getElementById('root');
  const palette = ['#43DAB0', '#6F9CF9', '#E4AC62', '#BB8BEF', '#EF8F7B', '#F26B9A'];
  const teamPalette = ['#22C7A9', '#F26B9A', '#6AA7FF', '#F7C84B', '#B891FF', '#FF8C69', '#60D394', '#FFAFCC'];
  let bridge;
  let state = { games: [], sessions: [] };
  let page = 'library';
  let draft = null;
  let selectedCategoryId = '';
  let selectedQuestionId = '';
  let prepareGameId = '';
  let prepareTeams = [];
  let preparePhase = 'teams';
  let turnOrderReady = false;
  let diceValue = null;
  let session = null;
  let activeQuestion = null;
  let selectedAnswerIndex = null;
  let answeringTeamIndex = null;
  let attemptedTeamIndexes = [];
  let questionOutcome = 'selecting';
  let writtenAnswer = '';
  let orderAvailable = [];
  let orderSelection = [];
  let questionStartedAt = 0;
  let timerHandle = null;
  let audioContext = null;
  let menuGameId = '';
  let menuPosition = null;
  let modal = null;
  let backToGame = false;
  let historyGameId = '';
  let toast = '';
  let automaticFinishInFlight = false;

  const clone = value => JSON.parse(JSON.stringify(value));
  const uid = () => `local-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[c]);
  const stamp = value => {
    if (!value) return 'Sin actividad';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? esc(value) : date.toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' });
  };
  const imagePath = value => typeof value === 'string' ? value : '';
  const imageName = value => {
    const path = imagePath(value);
    return path ? path.replace(/\\/g, '/').split('/').pop() : '';
  };
  const localUrl = value => {
    // QFileDialog entrega rutas POSIX en macOS y rutas con "\\" en Windows.
    // El WebEngine necesita una URL file:///…; normalizar aquí hace que las
    // imágenes seleccionadas se puedan mostrar tanto durante el desarrollo
    // como desde el instalador Windows, aun con espacios, # o tildes.
    let path = imagePath(value).replace(/\\/g, '/');
    if (!path) return '';
    if (/^[A-Za-z]:\//.test(path)) path = `/${path}`;
    const encoded = encodeURI(path).replace(/#/g, '%23').replace(/\?/g, '%3F').replace(/'/g, '%27');
    return `file://${encoded}`;
  };
  const normalizedAnswer = value => String(value ?? '').trim().replace(/^[A-ZÁÉÍÓÚÜÑ]\)\s*/i, '').trim().toLocaleLowerCase();
  const normalizedWrittenAnswer = value => String(value ?? '')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
  const answerType = question => question?.answer_type || ((question?.choices || []).length ? 'choice' : 'text');
  const gameQuestions = game => (game?.categories || []).flatMap(category => category.questions || []);
  const currentTurnIndex = () => {
    const total = session?.teams?.length || 1;
    return Math.max(0, Number(session?.current_turn_index || 0) % total);
  };
  const currentTurnTeam = () => session?.teams?.[currentTurnIndex()] || null;
  const respondingTeam = () => session?.teams?.[answeringTeamIndex ?? currentTurnIndex()] || null;
  const shuffle = items => {
    const copy = [...items];
    for (let index = copy.length - 1; index > 0; index -= 1) {
      const next = Math.floor(Math.random() * (index + 1));
      [copy[index], copy[next]] = [copy[next], copy[index]];
    }
    return copy;
  };
  const q = selector => root.querySelector(selector);
  const all = selector => [...root.querySelectorAll(selector)];
  const currentCategory = () => (draft?.categories || []).find(category => category.id === selectedCategoryId) || draft?.categories?.[0] || null;
  const currentQuestion = () => (currentCategory()?.questions || []).find(question => question.id === selectedQuestionId) || currentCategory()?.questions?.[0] || null;
  const gameFromSession = () => session?.game_snapshot || state.games.find(game => game.id === session?.game_id) || null;

  function playSound(name, game = gameFromSession()) {
    if (!game || game.sound_enabled === false || game.sound_enabled === 'false') return;
    const AudioEngine = window.AudioContext || window.webkitAudioContext;
    if (!AudioEngine) return;
    try {
      audioContext = audioContext || new AudioEngine();
      if (audioContext.state === 'suspended') audioContext.resume();
      const ctx = audioContext;
      const at = ctx.currentTime + 0.015;
      const volume = Math.max(0, Math.min(1, Number(game.sound_volume ?? 55) / 100)) * 0.16;
      const tone = (frequency, start, duration, type = 'sine', gain = 1) => {
        const oscillator = ctx.createOscillator();
        const envelope = ctx.createGain();
        oscillator.type = type;
        oscillator.frequency.setValueAtTime(frequency, start);
        envelope.gain.setValueAtTime(0.0001, start);
        envelope.gain.exponentialRampToValueAtTime(Math.max(0.0001, volume * gain), start + 0.012);
        envelope.gain.exponentialRampToValueAtTime(0.0001, start + duration);
        oscillator.connect(envelope).connect(ctx.destination);
        oscillator.start(start); oscillator.stop(start + duration + 0.02);
      };
      if (name === 'card') { tone(460, at, .07, 'triangle', .8); tone(670, at + .075, .13, 'sine', .95); }
      else if (name === 'select') tone(540, at, .08, 'sine', .58);
      else if (name === 'correct') { tone(523, at, .11, 'sine'); tone(659, at + .10, .12, 'sine'); tone(784, at + .20, .22, 'triangle', 1.15); }
      else if (name === 'wrong') { tone(260, at, .13, 'sawtooth', .65); tone(185, at + .12, .22, 'sawtooth', .62); }
      else if (name === 'dice') { [340, 430, 520, 610].forEach((frequency, index) => tone(frequency, at + index * .07, .055, 'square', .4)); }
      else if (name === 'turn') { tone(392, at, .09, 'triangle', .55); tone(494, at + .1, .13, 'triangle', .65); }
      else if (name === 'pass') { tone(440, at, .09, 'sine', .55); tone(330, at + .09, .12, 'sine', .5); }
      else if (name === 'winner') { [523, 659, 784, 1047].forEach((frequency, index) => tone(frequency, at + index * .11, .22, 'triangle', 1)); }
    } catch (_error) { /* El sonido no debe interrumpir la partida. */ }
  }

  function api(method, ...args) {
    return new Promise(resolve => {
      bridge[method](...args, raw => {
        try { resolve(JSON.parse(raw)); } catch (_error) { resolve({ error: 'No se pudo leer la respuesta de la aplicación.' }); }
      });
    });
  }

  function blankGame() {
    return {
      id: '', name: 'Nuevo juego', title: 'Mi juego de preguntas', background_color: '#111827',
      background_image: '', winner_image: '', accent_color: '#5EEAD4', text_color: '#F8FAFC', card_color: '#243047',
      font_family: 'Arial', sound_enabled: true, sound_volume: 55, teams: [
        { name: 'Equipo 1', color: teamPalette[0] }, { name: 'Equipo 2', color: teamPalette[1] },
      ], categories: [],
    };
  }

  function shell(body, active = 'games', className = '') {
    return `<div class="screen ${className}"><div class="app">${nav(active)}<main class="workspace ${className}">${body}</main></div></div>`;
  }

  function nav(active) {
    return `<aside class="side"><div class="brand"><div class="brand-mark">Q</div><div><div class="brand-name">QUIZ STUDIO</div><div class="brand-small">GAME CREATOR</div></div></div>
      <button class="nav-item ${active === 'games' ? 'active' : ''}" data-action="library">${ic('game')} Mis juegos</button>
      <button class="nav-item ${active === 'history' ? 'active' : ''}" data-action="history">${ic('history')} Historial</button>
      <div class="side-bottom"><div class="helper"><strong>${ic('info', 'sm')} Tus trivias, a tu estilo</strong>Crea juegos, personaliza sus colores y conserva cada partida.</div><div class="kbd"><span>Pantalla completa</span><span class="key">F11</span></div></div></aside>`;
  }

  const heading = (kicker, title, subtitle, actions = '') => `<header class="page-header"><div><div class="page-kicker">${esc(kicker)}</div><h1 class="text-h">${esc(title)}</h1><div class="subtitle">${esc(subtitle)}</div></div><div>${actions}</div></header>`;
  const button = (label, action, classes = 'btn-quiet', icon = '', attributes = '') => `<button class="btn ${classes}" data-action="${action}" ${attributes}>${icon ? ic(icon) : ''}${esc(label)}</button>`;

  function gameArtwork(game) {
    const background = imagePath(game.background_image)
      ? `background-image:linear-gradient(120deg,${esc(game.background_color || '#16223a')}bb,${esc(game.accent_color || '#667aff')}99),url('${localUrl(game.background_image)}');background-size:cover;background-position:center;`
      : `background:linear-gradient(120deg,${esc(game.background_color || '#21365b')},${esc(game.accent_color || '#667aff')});`;
    return background;
  }

  function playArtwork(game) {
    const color = esc(game?.background_color || '#091526');
    const accent = esc(game?.accent_color || '#4359a1');
    const image = localUrl(game?.background_image);
    return image
      ? `background-color:${color};background-image:linear-gradient(120deg,${color}e8,${accent}9c),url('${image}');background-size:cover;background-position:center;background-attachment:fixed;`
      : `background:radial-gradient(ellipse at 50% 0,${accent}55,${color} 75%);`;
  }

  function gameCard(game) {
    const categoryCount = (game.categories || []).length;
    const questionCount = gameQuestions(game).length;
    return `<article class="game-card"><div class="game-art" style="${gameArtwork(game)}"><div class="art-tag">${categoryCount ? `${categoryCount} CATEGORÍAS` : 'SIN CATEGORÍAS'}</div><div class="art-orb">Q</div><div class="art-title">${esc(game.title || game.name)}</div></div>
      <div class="card-body"><div class="card-name">${esc(game.name)}</div><div class="card-meta"><span>${categoryCount} categorías · ${questionCount} preguntas</span><span>${ic('history', 'sm')} ${stamp(game.updated_at)}</span></div>
      <div class="card-actions"><a class="btn btn-quiet btn-grow edit-link" href="#editar" role="button" data-action="prepare" data-edit-id="${esc(game.id)}">${ic('pencil')}Editar</a>${button('Jugar', 'prepare', 'btn-primary btn-grow', 'play', `type="button" data-id="${esc(game.id)}"`)}${button('', 'game-menu', 'btn-quiet btn-icon', 'more', `type="button" data-id="${esc(game.id)}"`)}</div></div></article>`;
  }

  function library() {
    const games = state.games || [];
    const contents = games.length
      ? `<div class="cards">${games.map(gameCard).join('')}</div>`
      : `<div class="empty"><div class="empty-ico">${ic('game', 'xl')}</div><h2>Aún no hay juegos</h2><p>Crea el primero para diseñar preguntas, equipos y el estilo de cada partida.</p>${button('Crear mi primer juego', 'new-game', 'btn-primary btn-lg', 'plus')}</div>`;
    const menuStyle = menuPosition ? `left:${menuPosition.left}px;top:${menuPosition.top}px;` : '';
    const menu = menuGameId ? `<div class="menu desktop-menu" style="${menuStyle}"><div class="menu-row" data-action="duplicate-game" data-id="${esc(menuGameId)}">${ic('copy')} Duplicar juego</div><div class="menu-row" data-action="game-history" data-id="${esc(menuGameId)}">${ic('history')} Ver historial de este juego</div><div class="menu-row bad" data-action="ask-delete-game" data-id="${esc(menuGameId)}">${ic('trash')} Eliminar juego</div></div>` : '';
    return shell(`${heading('Biblioteca', 'Mis juegos', 'Crea una trivia para cada ocasión y vuelve a jugarla cuando quieras.', button('Crear juego', 'new-game', 'btn-primary btn-lg', 'plus'))}${contents}${menu}`);
  }

  function editorHead() {
    const title = draft?.name || 'Nuevo juego';
    return `<div class="editor-head"><div class="editor-back">${button('', 'editor-cancel', 'btn-quiet btn-icon', 'arrow')}<div><div class="editor-title">Configuración del juego</div><div class="editor-meta">${esc(title)} <span style="color:#657596"> · </span> se guarda cuando pulses Guardar</div></div></div><div class="vcenter gap12">${button('Cancelar', 'editor-cancel', 'btn-quiet', 'close')}${button('Guardar juego', 'save-game', 'btn-primary', 'save')}</div></div>`;
  }

  function editorTabs(active) {
    const tabs = [['editor-identity', 'Identidad visual', 'palette'], ['editor-teams', 'Equipos', 'users'], ['editor-questions', 'Categorías y preguntas', 'list']];
    return `<nav class="editor-tabs">${tabs.map(([name, label, icon]) => `<button class="tab ${active === name ? 'active' : ''}" data-action="${name}">${ic(icon)}${label}</button>`).join('')}</nav>`;
  }

  function textInput(label, value, field, type = 'text', note = '') {
    return `<label><span class="field-label">${esc(label)}</span><input class="inp" type="${type}" value="${esc(value)}" data-game-field="${field}">${note ? `<span class="mini-note">${esc(note)}</span>` : ''}</label>`;
  }

  function colorInput(label, value, field) {
    return `<label><span class="field-label">${esc(label)}</span><div class="color-field"><input class="swatch native-color" type="color" value="${esc(value || '#000000')}" data-game-color="${field}"><input class="inp" type="text" value="${esc(value)}" readonly></div></label>`;
  }

  function identityEditor() {
    const game = draft || blankGame();
    const previewStyle = imagePath(game.background_image)
      ? `background-image:linear-gradient(140deg,${esc(game.background_color)}dd,${esc(game.accent_color)}77),url('${localUrl(game.background_image)}');background-size:cover;`
      : `background:radial-gradient(ellipse at 50% 0,${esc(game.accent_color)}88,${esc(game.background_color)} 75%);`;
    const soundEnabled = game.sound_enabled !== false && game.sound_enabled !== 'false';
    const soundSettings = `<div class="sound-settings"><div><span class="field-label">Sonidos del juego</span><label class="sound-switch"><input type="checkbox" data-game-field="sound_enabled" ${soundEnabled ? 'checked' : ''}><span>Activar efectos de sonido</span></label></div><label><span class="field-label">Volumen</span><div class="sound-volume"><input type="range" min="0" max="100" value="${esc(game.sound_volume ?? 55)}" data-game-field="sound_volume"><b>${esc(game.sound_volume ?? 55)}%</b></div></label><div class="sound-preview">${button('Probar sonidos', 'preview-sounds', 'btn-quiet', 'play')}</div></div>`;
    return shell(`${editorHead()}${editorTabs('editor-identity')}<div class="style-grid"><section class="panel style-left"><h3 class="group-title">Información del juego</h3><div class="form2">${textInput('Nombre interno *', game.name, 'name')}${textInput('Título visible *', game.title, 'title')}</div><div class="line" style="margin:26px 0 23px"></div><h3 class="group-title">Personalización visual</h3><div class="form2">${colorInput('Color de fondo', game.background_color, 'background_color')}${colorInput('Color destacado', game.accent_color, 'accent_color')}${colorInput('Color del texto', game.text_color, 'text_color')}${colorInput('Color de tarjetas', game.card_color, 'card_color')}<label><span class="field-label">Tipografía</span><select class="inp" data-game-field="font_family">${['Arial', 'Inter', 'Verdana', 'Georgia'].map(font => `<option ${game.font_family === font ? 'selected' : ''}>${font}</option>`).join('')}</select></label><label><span class="field-label">Imagen de fondo (opcional)</span><div class="vcenter gap8"><div class="inp muted image-name">${esc(imageName(game.background_image) || 'Ninguna seleccionada')}</div>${button('Examinar', 'choose-background', 'btn-quiet', 'image')}</div></label><label><span class="field-label">Imagen de celebración (opcional)</span><div class="vcenter gap8"><div class="inp muted image-name">${esc(imageName(game.winner_image) || 'Se usará una celebración visual')}</div>${button('Examinar', 'choose-winner-image', 'btn-quiet', 'trophy')}</div></label></div><div class="line" style="margin:26px 0 21px"></div><h3 class="group-title">Audio</h3>${soundSettings}<p class="mini-note" style="margin-top:22px">Los sonidos están integrados en la app y funcionan sin internet. La imagen de celebración se muestra al finalizar la partida.</p></section><section class="panel style-right"><div class="between" style="margin-bottom:18px"><h3 class="group-title" style="margin:0">Vista previa del juego</h3><span class="chip">${ic('grid', 'sm')} En vivo</span></div><div class="mini-preview" style="${previewStyle};font-family:${esc(game.font_family || 'Arial')}"><div class="preview-score">${(game.teams || []).slice(0, 4).map(team => `<span>${esc(team.name)} <b>0</b></span>`).join('')}</div><div class="preview-title">${esc(game.title)}</div><div class="preview-board">${(game.categories || []).slice(0, 4).map(category => `<div class="preview-col"><b style="border-top-color:${esc(category.color || game.accent_color)}">${esc(category.name)}</b>${(category.questions || []).slice(0, 4).map(question => `<span>${esc(question.value)}</span>`).join('') || '<span>—</span>'}</div>`).join('') || '<div class="note" style="margin:90px auto">Añade categorías para ver el tablero.</div>'}</div></div><div class="between" style="margin-top:17px"><span class="note">Tus cambios se reflejarán al guardar.</span><span class="tiny muted">Vista orientativa</span></div></section></div>`, 'games', 'editor-work');
  }

  function teamRow(team, index) {
    return `<div class="team-line"><div class="team-order">${String(index + 1).padStart(2, '0')}</div><input class="inp" value="${esc(team.name)}" data-team-name="${index}"><input class="swatch native-color" type="color" value="${esc(team.color)}" data-team-color-picker="${index}"><input class="inp" value="${esc(team.color)}" readonly>${button('', 'remove-team', 'btn-quiet btn-icon', 'trash', `data-index="${index}"`)}</div>`;
  }

  function teamsEditor() {
    const teams = draft?.teams || [];
    return shell(`${editorHead()}${editorTabs('editor-teams')}<div class="team-top"><section class="panel team-lists"><div class="between"><div><h3 class="group-title" style="margin-bottom:5px">Equipos predeterminados</h3><div class="note">Se pueden modificar para cada partida, sin cambiar el juego guardado.</div></div><div class="vcenter gap12"><span class="muted small">Cantidad</span><strong style="font-size:22px">${teams.length}</strong></div></div><div class="between tiny muted" style="margin-top:25px"><span>Orden &nbsp; &nbsp; Nombre del equipo</span><span style="margin-right:118px">Color asignado</span></div>${teams.map(teamRow).join('')}<div class="vcenter gap12" style="margin-top:28px">${button('Agregar equipo', 'add-team', 'btn-quiet', 'plus')}<span class="note">Mínimo 2 · Máximo 8 equipos</span></div></section><section class="panel team-preview"><h3 class="group-title">Vista del marcador</h3><div class="note" style="margin-bottom:26px">Así aparecerá al jugar.</div>${teams.map(team => `<div class="team-mini" style="border-left:4px solid ${esc(team.color)}"><span class="dot" style="background:${esc(team.color)}"></span>${esc(team.name)}<b>0</b></div>`).join('')}<div class="line" style="margin:29px 0 22px"></div><div class="note">Los nombres y colores se guardarán al pulsar Guardar juego.</div></section></div>`, 'games', 'editor-work');
  }

  function categoryRow(category) {
    const selected = category.id === selectedCategoryId;
    return `<button class="category-row ${selected ? 'active' : ''}" data-action="select-category" data-id="${esc(category.id)}"><span class="dot" style="background:${esc(category.color || '#43DAB0')}"></span>${esc(category.name)}<span class="count-pill">${(category.questions || []).length}</span></button>`;
  }

  function questionChoice(question, index) {
    const selected = question.id === selectedQuestionId;
    const summary = String(question.question || 'Sin enunciado').trim();
    const label = summary.length > 92 ? `${summary.slice(0, 91)}…` : summary;
    return `<button class="question-card-choice ${selected ? 'active' : ''}" data-action="select-question" data-id="${esc(question.id)}"><div class="between"><span class="question-value">${esc(question.value)} pts</span><span class="tiny muted">Pregunta ${index + 1}</span></div><strong>${esc(label)}</strong><span class="question-card-answer">${esc(question.answer || 'Sin respuesta configurada')}</span></button>`;
  }

  function questionEditor() {
    const category = currentCategory();
    const question = currentQuestion();
    const categories = draft?.categories || [];
    let editPanel = '';
    if (!category) {
      editPanel = `<section class="panel question-edit-panel blank-state"><div class="empty-ico">${ic('list', 'xl')}</div><h2>Sin categorías</h2><p class="muted">Crea la primera categoría para añadir preguntas y construir el tablero.</p>${button('Añadir categoría', 'add-category', 'btn-primary', 'plus')}</section>`;
    } else if (!question) {
      editPanel = `<section class="panel question-edit-panel blank-state"><div class="empty-ico">${ic('file', 'xl')}</div><h2>Selecciona o crea una pregunta</h2><p class="muted">La pregunta elegida aparecerá aquí para editarla.</p>${button('Nueva pregunta', 'add-question', 'btn-primary', 'plus')}</section>`;
    } else {
      const choices = (question.choices || []).join('\n');
      const image = question.image_path ? `<img class="question-photo" src="${localUrl(question.image_path)}" alt="Imagen de la pregunta">` : `<div class="qillustration stars">${ic('image', 'xl')}</div>`;
      editPanel = `<section class="panel question-edit-panel"><div class="toolbar"><div><div class="page-kicker">Pregunta seleccionada</div><h3 class="group-title" style="margin:2px 0 5px">Editar pregunta</h3><div class="note">Los cambios quedarán en este juego al guardarlo.</div></div><div class="vcenter gap8">${button('Nueva', 'add-question', 'btn-quiet', 'plus')}${button('Eliminar', 'ask-delete-question', 'btn-danger', 'trash')}</div></div><div class="question-form"><div><label><span class="field-label">Valor de la carta *</span><input class="inp" style="width:170px" type="number" min="1" value="${esc(question.value)}" data-question-field="value"></label><label style="display:block;margin-top:18px"><span class="field-label">Pregunta *</span><textarea class="area" data-question-field="question">${esc(question.question)}</textarea></label><label style="display:block;margin-top:18px"><span class="field-label">Alternativas (una por línea)</span><textarea class="area" style="height:124px" data-question-field="choices">${esc(choices)}</textarea></label><label style="display:block;margin-top:18px"><span class="field-label">Respuesta correcta *</span><input class="inp" value="${esc(question.answer)}" data-question-field="answer"></label></div><div><label class="field-label">Imagen de la pregunta (opcional)</label>${image}<div class="vcenter gap8" style="margin-top:12px">${button('Examinar', 'choose-question-image', 'btn-quiet', 'image')}${question.image_path ? button('Quitar', 'remove-question-image', 'btn-quiet', 'trash') : ''}</div><p class="note" style="margin-top:22px">La imagen se mostrará junto con la pregunta. Si no la eliges, se usa solo texto.</p></div></div></section>`;
    }
    if (question) {
      const type = answerType(question);
      const formImage = question.image_path ? `<img class="question-photo" src="${localUrl(question.image_path)}" alt="Imagen de la pregunta">` : `<div class="qillustration stars">${ic('image', 'xl')}</div>`;
      const answerConfig = type === 'choice'
        ? `<label style="display:block;margin-top:18px"><span class="field-label">Alternativas (una por línea)</span><textarea class="area" style="height:124px" data-question-field="choices">${esc((question.choices || []).join('\n'))}</textarea></label><label style="display:block;margin-top:18px"><span class="field-label">Respuesta correcta *</span><input class="inp" value="${esc(question.answer)}" data-question-field="answer"></label>`
        : type === 'text'
        ? `<label style="display:block;margin-top:18px"><span class="field-label">Respuestas aceptadas (una por línea) *</span><textarea class="area" style="height:124px" data-question-field="accepted_answers">${esc((question.accepted_answers?.length ? question.accepted_answers : [question.answer]).join('\n'))}</textarea><span class="mini-note">Se ignoran mayúsculas, tildes, diéresis, puntuación y espacios repetidos.</span></label>`
          : type === 'manual'
            ? `<label style="display:block;margin-top:18px"><span class="field-label">Respuesta para mostrar al moderador *</span><textarea class="area" style="height:124px" data-question-field="answer">${esc(question.answer)}</textarea><span class="mini-note">Durante la partida solo se verá la pregunta. El moderador revelará esta respuesta y decidirá si el equipo acertó.</span></label>`
            : `<label style="display:block;margin-top:18px"><span class="field-label">Elementos a ordenar (una por línea, en el orden correcto) *</span><textarea class="area" style="height:148px" data-question-field="order_items">${esc((question.order_items || []).join('\n'))}</textarea><span class="mini-note">En el juego aparecerán mezclados. El equipo los ubicará del 1 al ${Math.max(2, (question.order_items || []).length || 5)}.</span></label>`;
      editPanel = `<section class="panel question-edit-panel"><div class="toolbar"><div><div class="page-kicker">Pregunta seleccionada</div><h3 class="group-title" style="margin:2px 0 5px">Editar pregunta</h3><div class="note">Los cambios quedarán en este juego al guardarlo.</div></div><div class="vcenter gap8">${button('Nueva', 'add-question', 'btn-quiet', 'plus')}${button('Eliminar', 'ask-delete-question', 'btn-danger', 'trash')}</div></div><div class="question-form"><div><label><span class="field-label">Tipo de respuesta *</span><select class="inp" data-question-field="answer_type"><option value="choice" ${type === 'choice' ? 'selected' : ''}>Alternativas · una correcta</option><option value="text" ${type === 'text' ? 'selected' : ''}>Respuesta escrita</option><option value="order" ${type === 'order' ? 'selected' : ''}>Ordenar elementos</option><option value="manual" ${type === 'manual' ? 'selected' : ''}>Respuesta oral · decide el moderador</option></select></label><label style="display:block;margin-top:18px"><span class="field-label">Valor de la carta *</span><input class="inp" style="width:170px" type="number" min="1" value="${esc(question.value)}" data-question-field="value"></label><label style="display:block;margin-top:18px"><span class="field-label">Pregunta *</span><textarea class="area" data-question-field="question">${esc(question.question)}</textarea></label>${answerConfig}</div><div><label class="field-label">Imagen de la pregunta (opcional)</label>${formImage}<div class="vcenter gap8" style="margin-top:12px">${button('Examinar', 'choose-question-image', 'btn-quiet', 'image')}${question.image_path ? button('Quitar', 'remove-question-image', 'btn-quiet', 'trash') : ''}</div><p class="note" style="margin-top:22px">La imagen se mostrará junto con la pregunta. Si no la eliges, se usa solo texto.</p></div></div></section>`;
    }
    const categoryControls = category ? `<section class="panel category-controls"><div><div class="page-kicker">Categoría seleccionada</div><h3 class="group-title" style="margin:2px 0 0">${esc(category.name)}</h3></div><label><span class="field-label">Nombre</span><input class="inp" value="${esc(category.name)}" data-category-field="name"></label><label><span class="field-label">Color</span><input class="swatch native-color category-color" type="color" value="${esc(category.color || '#43DAB0')}" data-category-field="color"></label>${button('Eliminar categoría', 'ask-delete-category', 'btn-danger', 'trash')}</section>` : '';
    const questionBrowser = category ? `<section class="panel questions-browser"><div class="toolbar"><div><div class="page-kicker">${esc(category.name)}</div><h3 class="group-title" style="margin:2px 0 5px">Preguntas de la categoría</h3><div class="note">Selecciona una tarjeta para editarla abajo.</div></div>${button('Nueva pregunta', 'add-question', 'btn-primary', 'plus')}</div><div class="questions-grid">${(category.questions || []).map(questionChoice).join('') || `<div class="questions-empty">Esta categoría aún no tiene preguntas.</div>`}</div></section>` : '';
    const left = `<section class="panel category-list"><div class="between"><h3 class="group-title" style="margin:0">Categorías</h3>${button('', 'add-category', 'btn-primary btn-icon', 'plus')}</div><div class="note" style="margin:12px 0 15px">Selecciona la categoría que quieres configurar.</div>${categories.map(categoryRow).join('')}</section>`;
    const right = category ? `<section class="question-editor-workspace">${categoryControls}${questionBrowser}${editPanel}</section>` : editPanel;
    return shell(`${editorHead()}${editorTabs('editor-questions')}<div class="question-layout">${left}${right}</div>`, 'games', 'editor-work');
  }

  function prepareScreen() {
    const game = state.games.find(item => item.id === prepareGameId);
    if (!game) { page = 'library'; return library(); }
    const teamsStep = `<div class="prepare-layout panel"><div class="between"><div><div class="page-kicker">Paso 1 de 2</div><h3 class="group-title" style="margin:3px 0 5px">Equipos de esta partida</h3><div class="note">Modifica nombres y colores sin afectar la plantilla del juego.</div></div><span class="chip">${prepareTeams.length} equipos</span></div><div class="prepare-teams">${prepareTeams.map((team, index) => `<div class="prepare-team"><span class="dot" style="width:21px;height:21px;background:${esc(team.color)}"></span><input class="inp" value="${esc(team.name)}" data-prepare-name="${index}"><input class="swatch native-color" type="color" value="${esc(team.color)}" data-prepare-color="${index}"><span class="small muted">Equipo ${index + 1}</span>${button('', 'remove-prepare-team', 'btn-quiet btn-icon', 'trash', `data-index="${index}"`)}</div>`).join('')}</div><div class="vcenter gap12" style="margin-top:22px">${button('Agregar equipo', 'add-prepare-team', 'btn-quiet', 'plus')}<span class="note">Mínimo 2 · Máximo 8 equipos</span></div><div class="modal-foot">${button('Cancelar', 'library', 'btn-quiet')}${button('Definir orden de turnos', 'prepare-turns', 'btn-primary btn-lg', 'arrow')}</div></div>`;
    const turnsStep = `<div class="prepare-layout panel"><div class="between"><div><div class="page-kicker">Paso 2 de 2</div><h3 class="group-title" style="margin:3px 0 5px">Sorteo de turnos</h3><div class="note">Lanza el dado para decidir el orden. El primer equipo tendrá la primera oportunidad.</div></div><div class="dice-value">${diceValue ?? '🎲'}</div></div><div class="turn-order-list">${turnOrderReady ? prepareTeams.map((team, index) => `<div class="turn-order-row"><span class="turn-position">${index + 1}</span><span class="dot" style="background:${esc(team.color)}"></span><strong>${esc(team.name)}</strong><span class="note">${index === 0 ? 'Comienza la partida' : `Turno ${index + 1}`}</span></div>`).join('') : '<div class="turn-order-empty">Lanza el dado para generar las posiciones de los equipos.</div>'}</div><div class="vcenter gap12" style="margin-top:22px">${button(turnOrderReady ? 'Lanzar nuevamente' : 'Lanzar dado', 'roll-turns', 'btn-quiet btn-lg', 'spark')}<span class="note">Puedes repetir el sorteo antes de iniciar.</span></div><div class="modal-foot">${button('Volver a equipos', 'prepare-teams', 'btn-quiet', 'arrow')}${button('Iniciar partida', 'start-session', `btn-primary btn-lg ${turnOrderReady ? '' : 'btn-disabled'}`, 'play', turnOrderReady ? '' : 'disabled')}</div></div>`;
    const content = preparePhase === 'turns' ? turnsStep : teamsStep;
    return shell(`${heading('Antes de comenzar', 'Preparar partida', `${game.title || game.name} · Estos cambios solo se aplican a esta ocasión.`, button('Volver', 'library', 'btn-quiet', 'arrow'))}${content}`, 'games');
  }

  function scoreCards() {
    return (session?.teams || []).map((team, index) => `<div class="score" style="--team:${esc(team.color)}"><div class="score-name"><span class="dot" style="background:${esc(team.color)}"></span>${esc(team.name)}</div><div class="score-value"><b>${Number(team.score || 0)}</b><div class="score-ticks"><button class="small-btn" data-action="score" data-index="${index}" data-delta="-10">−10</button><button class="small-btn" data-action="score" data-index="${index}" data-delta="10">+10</button></div></div></div>`).join('');
  }

  function gameBar(mode = 'play') {
    if (mode === 'board') return `<div class="gamebar board-gamebar"><div class="scoreboard">${scoreCards()}</div></div>`;
    if (mode === 'question') {
      const game = gameFromSession();
      return `<div class="gamebar question-gamebar"><div class="question-game-navigation">${button('Tablero', 'return-board', 'btn-quiet question-board-button', 'arrow')}<div class="question-game-title">${esc(game?.title || game?.name || 'Juego')}</div></div><div class="scoreboard">${scoreCards()}</div></div>`;
    }
    const controls = mode === 'winner' ? `<span class="turn-badge">Resultado final</span>` : button('Finalizar', 'ask-finish-session', 'btn-danger', 'power');
    return `<div class="gamebar"><div class="game-logo"><span class="mark">Q</span><div>QUIZ<br>STUDIO</div></div><div class="game-actions">${controls}</div><div class="scoreboard">${scoreCards()}</div></div>`;
  }

  function board() {
    const game = gameFromSession();
    if (!game) { page = 'library'; return library(); }
    const used = new Set(session.used_cards || []);
    const questions = gameQuestions(game);
    if (!questions.length) {
      return `<div class="screen play">${gameBar()}<main class="play-content"><div class="game-heading"><div class="page-kicker">Partida activa</div><h1>${esc(game.title)}</h1></div><div class="empty"><div class="empty-ico">${ic('book', 'xl')}</div><h2>Este juego aún no tiene preguntas</h2><p>Vuelve a la biblioteca, edita el juego y añade al menos una pregunta antes de jugar.</p>${button('Salir de la partida', 'ask-exit-session', 'btn-quiet btn-lg', 'arrow')}</div></main></div>`;
    }
    const remaining = questions.filter(question => !used.has(question.id)).length;
    const boardFooter = `<footer class="board-footer"><div class="board-remaining">${ic('grid', 'sm')} ${remaining} cartas disponibles</div><div class="board-turn" style="--turn:${esc(currentTurnTeam()?.color || game.accent_color)}"><span>Turno:</span><strong>${esc(currentTurnTeam()?.name || '—')}</strong></div>${button('', 'ask-finish-session', 'btn-danger btn-icon footer-finish', 'power', 'title="Finalizar partida" aria-label="Finalizar partida"')}</footer>`;
    return `<div class="screen play board-screen" style="${playArtwork(game)}">${gameBar('board')}<main class="play-content board-content"><div class="game-heading board-heading"><h1>${esc(game.title)}</h1></div><section class="board">${(game.categories || []).map(category => `<div class="board-cat" style="--cat:${esc(category.color || game.accent_color)};--catSoft:${esc(category.color || game.accent_color)}44;--catStroke:${esc(category.color || game.accent_color)}88"><div class="board-cat-head">${ic('spark')}<b>${esc(category.name)}</b></div>${(category.questions || []).sort((a, b) => Number(b.value) - Number(a.value)).map(question => { const isUsed = used.has(question.id); return `<button class="point-tile ${isUsed ? 'used' : ''}" ${isUsed ? 'disabled' : `data-action="open-question" data-category-id="${esc(category.id)}" data-question-id="${esc(question.id)}"`}>${isUsed ? `<span class="used-check">${ic('check')} USADA</span>` : esc(question.value)}</button>`; }).join('') || '<div class="note" style="padding:25px 8px;text-align:center">Sin preguntas</div>'}</div>`).join('')}</section>${boardFooter}</main></div>`;
  }

  function winnerScreen() {
    const game = gameFromSession();
    const teams = [...(session?.teams || [])].sort((left, right) => Number(right.score || 0) - Number(left.score || 0));
    const topScore = Number(teams[0]?.score || 0);
    const winners = teams.filter(team => Number(team.score || 0) === topScore);
    const winnerNames = winners.map(team => team.name).join(' y ');
    const heroImage = game?.winner_image ? `<img class="winner-photo" src="${localUrl(game.winner_image)}" alt="Celebración de la partida">` : `<div class="winner-art"><span>${ic('trophy', 'xl')}</span><i>✦</i><i>✦</i></div>`;
    return `<div class="screen play winner-screen" style="${playArtwork(game)}">${gameBar('winner')}<main class="winner-content"><section class="winner-card" style="--winner:${esc(winners[0]?.color || game?.accent_color || '#5EEAD4')}"><div class="winner-kicker">PARTIDA FINALIZADA</div>${heroImage}<div class="winner-copy"><div class="winner-label">${winners.length > 1 ? 'EMPATE' : 'GANADOR DE LA PARTIDA'}</div><h1>${esc(winnerNames || 'Sin ganador')}</h1><div class="winner-points">${topScore} <span>puntos</span></div><p>${winners.length > 1 ? 'Los equipos comparten el primer lugar.' : '¡Una gran partida! El resultado quedó guardado en el historial.'}</p></div><div class="winner-ranking">${teams.map((team, index) => `<div class="winner-team ${Number(team.score || 0) === topScore ? 'leader' : ''}" style="--team:${esc(team.color)}"><span class="winner-position">${index + 1}</span><span class="dot" style="background:${esc(team.color)}"></span><strong>${esc(team.name)}</strong><b>${Number(team.score || 0)} pts</b></div>`).join('')}</div><div class="winner-actions">${button('Ver historial', 'winner-history', 'btn-primary btn-lg', 'history')}${button('Volver a mis juegos', 'winner-library', 'btn-quiet btn-lg', 'game')}</div></section></main></div>`;
  }

  function questionScreen() {
    const game = gameFromSession();
    const category = (game?.categories || []).find(item => item.id === activeQuestion?.categoryId);
    const question = (category?.questions || []).find(item => item.id === activeQuestion?.questionId);
    if (!game || !category || !question) { page = 'board'; return board(); }
    const type = answerType(question);
    const choices = question.choices || [];
    const correctOrder = question.order_items || [];
    const image = question.image_path ? `<img class="question-photo large-photo" src="${localUrl(question.image_path)}" alt="Imagen de la pregunta">` : '';
    const isSelecting = questionOutcome === 'selecting';
    const responder = respondingTeam();
    const choiceAnswers = `<div class="answers">${choices.map((choice, index) => {
      const chosen = selectedAnswerIndex === index;
      const correct = questionOutcome === 'correct' && normalizedAnswer(choice) === normalizedAnswer(question.answer);
      const revealed = questionOutcome === 'revealed' && normalizedAnswer(choice) === normalizedAnswer(question.answer);
      const incorrect = questionOutcome === 'incorrect' && chosen;
      return `<button class="answer ${chosen && isSelecting ? 'selected' : ''} ${correct || revealed ? 'correct' : ''} ${incorrect ? 'incorrect' : ''}" ${isSelecting ? `data-action="select-answer" data-index="${index}"` : 'disabled'}><span class="answer-letter">${'ABCDEFGHIJKLMNOPQRSTUVWXYZ'[index]}</span>${esc(choice)}${correct || revealed ? `<span style="margin-left:auto">${ic('check')}</span>` : incorrect ? `<span style="margin-left:auto">${ic('close')}</span>` : ''}</button>`;
    }).join('')}</div>`;
    const textAnswer = `<div class="written-answer"><label class="field-label">Respuesta del equipo</label><input class="inp" value="${esc(writtenAnswer)}" ${isSelecting ? 'data-written-answer autofocus' : 'readonly'} placeholder="Escribe la respuesta aquí"><span class="note">Se aceptan las variantes configuradas para esta pregunta.</span></div>`;
    const orderAnswer = `<div class="order-game"><div class="order-source"><span class="field-label">Opciones disponibles</span><div class="order-options">${orderAvailable.map((item, index) => `<button class="order-option" ${isSelecting ? `data-action="order-add" data-index="${index}"` : 'disabled'}>${esc(item)}</button>`).join('') || '<span class="note">Todas las opciones ya están ubicadas.</span>'}</div></div><div class="order-target"><span class="field-label">Orden del equipo</span>${correctOrder.map((_item, index) => { const value = orderSelection[index]; return `<div class="order-slot ${value ? 'filled' : ''}"><span class="order-number">${index + 1}</span><strong>${value ? esc(value) : 'Selecciona una opción arriba'}</strong>${value && isSelecting ? `<span class="order-move">${button('↑', 'order-up', 'btn-quiet btn-icon', '', `data-index="${index}"`)}${button('↓', 'order-down', 'btn-quiet btn-icon', '', `data-index="${index}"`)}</span>` : ''}</div>`; }).join('')}</div></div>`;
    const responseArea = type === 'choice' ? choiceAnswers : type === 'text' ? textAnswer : type === 'order' ? orderAnswer : '';
    const turnInfo = `<div class="question-live-info"><div class="question-points">${esc(question.value)} <span>puntos</span></div><div class="question-timer" id="question-timer">00:00</div>${responder ? `<div class="answering-turn answering-turn-large" style="--team:${esc(responder.color)}"><span class="dot" style="background:${esc(responder.color)}"></span><span>Responde:</span><strong>${esc(responder.name)}</strong></div>` : ''}</div>`;
    const result = questionOutcome === 'manual-review'
      ? `<div class="reveal manual-reveal"><span style="color:#ffdc78">${ic('spark', 'xl')}</span><div><div class="reveal-title">RESPUESTA</div><div class="reveal-answer">${esc(question.answer)}</div></div></div>`
      : questionOutcome === 'manual-incorrect'
        ? `<div class="reveal reveal-wrong"><span style="color:#ff9dad">${ic('close', 'xl')}</span><div><div class="reveal-title">NO SE ASIGNARON PUNTOS</div><div class="reveal-answer">${esc(question.answer)}</div></div></div>`
      : questionOutcome === 'correct'
      ? `<div class="reveal"><span style="color:#80f4c8">${ic('check', 'xl')}</span><div><div class="reveal-title">RESPUESTA CORRECTA</div><div class="reveal-answer">${esc(responder?.name)} gana ${esc(question.value)} puntos.</div></div></div>`
      : questionOutcome === 'incorrect'
        ? `<div class="reveal reveal-wrong"><span style="color:#ff9dad">${ic('close', 'xl')}</span><div><div class="reveal-title">RESPUESTA INCORRECTA</div><div class="reveal-answer">La respuesta correcta sigue oculta.</div></div></div>`
        : questionOutcome === 'revealed'
          ? `<div class="reveal"><span style="color:#80f4c8">${ic('check', 'xl')}</span><div><div class="reveal-title">RESPUESTA CORRECTA</div><div class="reveal-answer">${esc(question.answer)}</div></div></div>` : '';
    const hasAnotherTeam = (session?.teams || []).some((_team, index) => index !== answeringTeamIndex && !attemptedTeamIndexes.includes(index));
    const canValidate = type === 'choice' ? selectedAnswerIndex !== null : type === 'text' ? normalizedWrittenAnswer(writtenAnswer).length > 0 : type === 'order' ? correctOrder.length > 0 && orderSelection.length === correctOrder.length : false;
    let actions = '';
    if (isSelecting) {
      actions = type === 'manual'
        ? `${hasAnotherTeam ? button('Otro equipo responde', 'choose-other-team', 'btn-quiet btn-lg', 'users') : ''}${button('Mostrar respuesta', 'reveal-answer', 'btn-primary btn-lg', 'check')}`
        : `${hasAnotherTeam ? button('Otro equipo responde', 'choose-other-team', 'btn-quiet btn-lg', 'users') : ''}${button(canValidate ? 'Validar resultado' : (type === 'text' ? 'Escribe una respuesta' : type === 'order' ? 'Completa el orden' : 'Selecciona una respuesta'), 'validate-answer', `btn-primary btn-lg ${canValidate ? '' : 'btn-disabled'}`, 'check', canValidate ? '' : 'disabled')}`;
    } else if (questionOutcome === 'manual-review') {
      actions = `${button('No acertó', 'manual-incorrect', 'btn-danger btn-lg', 'close')}${button('Acertó', 'manual-correct', 'btn-primary btn-lg', 'check')}`;
    } else if (questionOutcome === 'incorrect') {
      actions = `${button('Mostrar respuesta', 'reveal-answer', 'btn-quiet btn-lg', 'check')}${hasAnotherTeam ? button('Otro equipo responde', 'choose-other-team', 'btn-primary btn-lg', 'users') : ''}`;
    }
    const actionsMarkup = actions ? `<div class="question-foot">${actions}</div>` : '';
    const base = `<div class="screen play question-screen" style="${playArtwork(game)}">${gameBar('question')}<main class="play-content"><div class="question-stage">${turnInfo}<div class="qbox"><div class="question-category-badge">${ic('spark', 'sm')} ${esc(category.name)}</div><div class="qtop"><div class="qtext">${esc(question.question)}</div>${image}</div>${responseArea}</div>${result}${actionsMarkup}</div></main></div>`;
    return base;
  }

  function history() {
    const game = state.games.find(item => item.id === historyGameId);
    const sessions = (state.sessions || []).filter(item => !historyGameId || item.game_id === historyGameId);
    const title = historyGameId ? `Historial · ${game?.name || 'juego'}` : (backToGame ? 'Historial de partidas' : 'Historial');
    const actions = backToGame ? button('Volver a la partida', 'board', 'btn-primary', 'arrow') : '';
    const content = sessions.length ? `<div class="history-list">${sessions.map(historyRow).join('')}</div>` : `<div class="empty"><div class="empty-ico">${ic('history', 'xl')}</div><h2>Aún no hay partidas</h2><p>Cuando empieces una partida, su marcador y cartas usadas aparecerán aquí.</p>${button('Ir a mis juegos', 'library', 'btn-primary', 'game')}</div>`;
    return shell(`${heading('Partidas guardadas', title, 'Consulta resultados, partidas en curso y el juego con el que se realizaron.', actions)}${content}`, 'history');
  }

  function historyRow(item) {
    const teams = item.teams || [];
    const leaders = [...teams].sort((a, b) => Number(b.score) - Number(a.score));
    const leading = leaders[0];
    return `<article class="history-card"><div class="h-cover">Q</div><div><div class="page-kicker">${esc(item.status || 'en curso')}</div><div class="h-name">${esc(item.game_title || item.game_name || 'Juego')}</div><div class="note">${stamp(item.started_at)}</div></div><div class="h-stats">${teams.map(team => `<div class="h-team"><span style="color:${esc(team.color)}">●</span> ${esc(team.name)}<b>${Number(team.score || 0)}</b></div>`).join('')}</div><div class="h-winner"><span class="tiny">${item.status === 'finalizado' ? 'Ganador' : 'Lidera'}</span>${esc(item.winner || leading?.name || 'Sin equipos')}</div><div><span class="chip ${item.status === 'finalizado' ? 'chip-green' : 'chip-amber'}">${item.status === 'finalizado' ? 'Finalizada' : 'En curso'}</span></div></article>`;
  }

  function modalMarkup() {
    if (!modal) return '';
    const dialog = (title, description, confirmText, confirmAction, danger = false) => `<div class="dim"></div><div class="dialog confirmation-dialog"><div class="modal-icon">${ic(danger ? 'trash' : 'alert', 'xl')}</div><h2>${esc(title)}</h2><p class="note">${esc(description)}</p><div class="modal-foot">${button('Cancelar', 'close-modal', 'btn-quiet')}${button(confirmText, confirmAction, danger ? 'btn-danger' : 'btn-primary')}</div></div>`;
    if (modal.type === 'delete-game') return dialog('Eliminar juego', 'Se eliminará el juego de tu biblioteca. Sus partidas ya guardadas seguirán en el historial.', 'Eliminar juego', 'delete-game', true);
    if (modal.type === 'delete-category') return dialog('Eliminar categoría', 'También se eliminarán todas las preguntas de esta categoría.', 'Eliminar categoría', 'delete-category', true);
    if (modal.type === 'delete-question') return dialog('Eliminar pregunta', 'Esta carta dejará de aparecer en el tablero del juego.', 'Eliminar pregunta', 'delete-question', true);
    if (modal.type === 'finish') return `<div class="dim"></div><div class="dialog confirmation-dialog"><div class="modal-icon">${ic('alert', 'xl')}</div><h2>¿Finalizar la partida?</h2><p class="note">Puedes guardar el resultado y ver al ganador, o salir sin conservar esta partida.</p><div class="modal-foot finish-options">${button('Cancelar', 'close-modal', 'btn-quiet')}${button('Salir sin guardar', 'discard-session', 'btn-danger')}${button('Finalizar y ver ganador', 'finish-session', 'btn-primary')}</div></div>`;
    if (modal.type === 'exit') return dialog('Salir de la partida', 'La partida se conserva en el historial como “en curso” para que puedas consultarla después.', 'Salir', 'exit-session');
    if (modal.type === 'no-questions') return dialog('Juego sin preguntas', 'Añade al menos una pregunta antes de iniciar una partida.', 'Entendido', 'close-modal');
    if (modal.type === 'choose-other-team') {
      const alternatives = (session?.teams || []).map((team, index) => ({ team, index })).filter(item => item.index !== answeringTeamIndex && !attemptedTeamIndexes.includes(item.index));
      return `<div class="dim"></div><div class="dialog team-choice-dialog"><div class="modal-heading"><div><div class="page-kicker">Nueva oportunidad</div><h2>¿Qué equipo responderá?</h2><div class="note">La respuesta y los puntos se asignarán a este equipo. El orden general de turnos no cambia.</div></div>${button('', 'close-modal', 'btn-quiet btn-icon', 'close')}</div><div class="team-choice-list">${alternatives.map(({ team, index }) => `<button class="team-choice" style="--team:${esc(team.color)}" data-action="select-other-team" data-index="${index}"><span class="dot" style="background:${esc(team.color)}"></span><strong>${esc(team.name)}</strong><span>Responder por ${esc(questionValueForModal())} puntos</span></button>`).join('')}</div><div class="modal-foot">${button('Cancelar', 'close-modal', 'btn-quiet')}</div></div>`;
    }
    return '';
  }

  function questionValueForModal() {
    const game = gameFromSession();
    const category = (game?.categories || []).find(item => item.id === activeQuestion?.categoryId);
    const question = (category?.questions || []).find(item => item.id === activeQuestion?.questionId);
    return question?.value || 0;
  }

  function toastMarkup() { return toast ? `<div class="desktop-toast">${esc(toast)}</div>` : ''; }

  function render() {
    let contents;
    if (page === 'editor-identity') contents = identityEditor();
    else if (page === 'editor-teams') contents = teamsEditor();
    else if (page === 'editor-questions') contents = questionEditor();
    else if (page === 'prepare') contents = prepareScreen();
    else if (page === 'board') contents = board();
    else if (page === 'question') contents = questionScreen();
    else if (page === 'winner') contents = winnerScreen();
    else if (page === 'history') contents = history();
    else contents = library();
    root.innerHTML = contents + modalMarkup() + toastMarkup();
    wireRenderedControls();
    refreshQuestionTimer();
    if (page === 'board') window.setTimeout(finishCompletedBoard, 0);
    if (toast) window.setTimeout(() => { toast = ''; render(); }, 2600);
  }

  async function finishCompletedBoard() {
    if (automaticFinishInFlight || page !== 'board' || !session?.id) return;
    const game = gameFromSession();
    const questions = gameQuestions(game);
    if (!questions.length || !questions.every(question => (session.used_cards || []).includes(question.id))) return;
    automaticFinishInFlight = true;
    try {
      session = await api('finishSession', JSON.stringify(session));
      await refresh();
      page = 'winner';
      backToGame = false;
      playSound('winner', game);
      render();
    } finally {
      automaticFinishInFlight = false;
    }
  }

  // Qt WebEngine puede entregar el clic de algunos botones de una tarjeta al
  // contenedor antes que al listener delegado. Enlazamos Editar directamente
  // cada vez que se pinta la biblioteca: no depende de atributos inline ni de
  // la propagación del evento.
  function wireRenderedControls() {
    all('[data-edit-id]').forEach(control => {
      control.onclick = event => {
        event.preventDefault();
        event.stopPropagation();
        openGameEditor(control.dataset.editId);
      };
    });
  }

  function refreshQuestionTimer() {
    if (timerHandle) { window.clearInterval(timerHandle); timerHandle = null; }
    if (page !== 'question' || !questionStartedAt) return;
    const paint = () => {
      const target = document.getElementById('question-timer');
      if (!target) return;
      const elapsed = Math.max(0, Date.now() - questionStartedAt);
      const minutes = Math.floor(elapsed / 60000);
      const seconds = Math.floor((elapsed % 60000) / 1000);
      target.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    };
    paint();
    timerHandle = window.setInterval(paint, 250);
  }

  function refreshWrittenAnswerValidation() {
    const validateButton = root.querySelector('button[data-action="validate-answer"]');
    if (!validateButton || page !== 'question') return;
    const canValidate = normalizedWrittenAnswer(writtenAnswer).length > 0;
    validateButton.disabled = !canValidate;
    validateButton.classList.toggle('btn-disabled', !canValidate);
    validateButton.innerHTML = `${ic('check')} ${canValidate ? 'Validar resultado' : 'Escribe una respuesta'}`;
  }

  function syncDraft() {
    if (!draft) return;
    all('[data-game-field]').forEach(input => {
      draft[input.dataset.gameField] = input.type === 'checkbox' ? input.checked : input.value.trim();
    });
    all('[data-game-color]').forEach(input => { draft[input.dataset.gameColor] = input.value; });
    all('[data-team-name]').forEach(input => { if (draft.teams[Number(input.dataset.teamName)]) draft.teams[Number(input.dataset.teamName)].name = input.value.trim() || `Equipo ${Number(input.dataset.teamName) + 1}`; });
    all('[data-team-color-picker]').forEach(input => { if (draft.teams[Number(input.dataset.teamColorPicker)]) draft.teams[Number(input.dataset.teamColorPicker)].color = input.value; });
    const category = currentCategory();
    if (category) {
      all('[data-category-field]').forEach(input => { category[input.dataset.categoryField] = input.value.trim() || (input.dataset.categoryField === 'name' ? 'Nueva categoría' : '#43DAB0'); });
      const question = currentQuestion();
      if (question) all('[data-question-field]').forEach(input => {
        const field = input.dataset.questionField;
        if (field === 'choices' || field === 'accepted_answers' || field === 'order_items') {
          question[field] = input.value.split('\n').map(value => value.trim()).filter(Boolean);
        } else if (field === 'value') {
          question[field] = Math.max(1, Number(input.value) || 10);
        } else {
          question[field] = input.value.trim();
        }
      });
      question.answer_type = answerType(question);
      if (question.answer_type === 'text') question.answer = question.accepted_answers?.[0] || question.answer || '';
      if (question.answer_type === 'manual') question.accepted_answers = question.answer ? [question.answer] : [];
      if (question.answer_type === 'order') question.answer = (question.order_items || []).join(' → ');
    }
  }

  function syncPrepareTeams() {
    all('[data-prepare-name]').forEach(input => { prepareTeams[Number(input.dataset.prepareName)].name = input.value.trim() || `Equipo ${Number(input.dataset.prepareName) + 1}`; });
    all('[data-prepare-color]').forEach(input => { prepareTeams[Number(input.dataset.prepareColor)].color = input.value.trim() || teamPalette[Number(input.dataset.prepareColor) % teamPalette.length]; });
  }

  async function refresh() {
    state = await api('getState');
    if (state.error) { toast = state.error; state = { games: [], sessions: [] }; }
  }

  function openGameEditor(gameId) {
    try {
      const game = state.games.find(item => String(item.id) === String(gameId));
      if (!game) { toast = 'No se encontró el juego que deseas editar.'; render(); return; }
      draft = clone(game);
      selectedCategoryId = draft.categories?.[0]?.id || '';
      selectedQuestionId = draft.categories?.[0]?.questions?.[0]?.id || '';
      menuGameId = '';
      menuPosition = null;
      page = 'editor-identity';
      render();
    } catch (error) {
      console.error('No se pudo abrir el editor', error);
      page = 'library';
      toast = `No se pudo abrir el editor: ${error?.message || 'error inesperado'}`;
      render();
    }
  }

  async function handle(action, element) {
    if (action === 'library') { page = 'library'; menuGameId = ''; menuPosition = null; backToGame = false; historyGameId = ''; render(); return; }
    if (action === 'history') { page = 'history'; menuGameId = ''; menuPosition = null; backToGame = false; historyGameId = ''; render(); return; }
    if (action === 'history-game') { page = 'history'; backToGame = true; historyGameId = session?.game_id || ''; render(); return; }
    if (action === 'game-history') { page = 'history'; menuGameId = ''; menuPosition = null; backToGame = false; historyGameId = element.dataset.id; render(); return; }
    if (action === 'new-game') {
      if (element.dataset.editId) { openGameEditor(element.dataset.editId); return; }
      draft = blankGame(); selectedCategoryId = ''; selectedQuestionId = ''; page = 'editor-identity'; render(); return;
    }
    if (action === 'edit-game') { openGameEditor(element.dataset.id); return; }
    if (action === 'editor-identity' || action === 'editor-teams' || action === 'editor-questions') { syncDraft(); page = action; render(); return; }
    if (action === 'editor-cancel') { draft = null; page = 'library'; render(); return; }
    if (action === 'save-game') { syncDraft(); const saved = await api('saveGame', JSON.stringify(draft)); if (saved.error) { toast = saved.error; render(); return; } await refresh(); draft = null; page = 'library'; toast = 'Juego guardado correctamente.'; render(); return; }
    if (action === 'choose-background') { syncDraft(); const path = await api('chooseImage'); if (path) { draft.background_image = path; } render(); return; }
    if (action === 'choose-winner-image') { syncDraft(); const path = await api('chooseImage'); if (path) { draft.winner_image = path; } render(); return; }
    if (action === 'preview-sounds') { syncDraft(); playSound('card', draft); window.setTimeout(() => playSound('correct', draft), 250); window.setTimeout(() => playSound('wrong', draft), 720); return; }
    if (action === 'add-team') { syncDraft(); if (draft.teams.length < 8) draft.teams.push({ name: `Equipo ${draft.teams.length + 1}`, color: teamPalette[draft.teams.length % teamPalette.length] }); render(); return; }
    if (action === 'remove-team') { syncDraft(); if (draft.teams.length > 2) draft.teams.splice(Number(element.dataset.index), 1); else toast = 'El juego necesita al menos dos equipos.'; render(); return; }
    if (action === 'add-category') { syncDraft(); const category = { id: uid(), name: `Categoría ${draft.categories.length + 1}`, color: palette[draft.categories.length % palette.length], questions: [] }; draft.categories.push(category); selectedCategoryId = category.id; selectedQuestionId = ''; page = 'editor-questions'; render(); return; }
    if (action === 'select-category') { syncDraft(); selectedCategoryId = element.dataset.id; selectedQuestionId = currentCategory()?.questions?.[0]?.id || ''; render(); return; }
    if (action === 'select-question') { syncDraft(); selectedQuestionId = element.dataset.id; render(); return; }
    if (action === 'ask-delete-category') { syncDraft(); modal = { type: 'delete-category' }; render(); return; }
    if (action === 'delete-category') { const index = draft.categories.findIndex(category => category.id === selectedCategoryId); if (index >= 0) draft.categories.splice(index, 1); selectedCategoryId = draft.categories[0]?.id || ''; selectedQuestionId = draft.categories[0]?.questions?.[0]?.id || ''; modal = null; render(); return; }
    if (action === 'add-question') { syncDraft(); const category = currentCategory(); if (!category) return; const question = { id: uid(), value: 10, question: 'Escribe aquí la pregunta.', choices: [], answer: 'Escribe aquí la respuesta.', answer_type: 'choice', accepted_answers: [], order_items: [], image_path: '' }; category.questions.push(question); selectedQuestionId = question.id; render(); return; }
    if (action === 'ask-delete-question') { syncDraft(); modal = { type: 'delete-question' }; render(); return; }
    if (action === 'delete-question') { const category = currentCategory(); const index = category.questions.findIndex(question => question.id === selectedQuestionId); if (index >= 0) category.questions.splice(index, 1); selectedQuestionId = category.questions[0]?.id || ''; modal = null; render(); return; }
    if (action === 'choose-question-image') { syncDraft(); const path = await api('chooseImage'); if (path && currentQuestion()) currentQuestion().image_path = path; render(); return; }
    if (action === 'remove-question-image') { syncDraft(); if (currentQuestion()) currentQuestion().image_path = ''; render(); return; }
    if (action === 'game-menu') {
      if (menuGameId === element.dataset.id) { menuGameId = ''; menuPosition = null; render(); return; }
      const rect = element.getBoundingClientRect();
      const menuWidth = 248;
      menuGameId = element.dataset.id;
      menuPosition = {
        left: Math.max(260, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 18)),
        top: Math.min(rect.bottom + 8, window.innerHeight - 184),
      };
      render();
      return;
    }
    if (action === 'duplicate-game') { await api('duplicateGame', element.dataset.id); await refresh(); menuGameId = ''; menuPosition = null; toast = 'Se creó una copia del juego.'; render(); return; }
    if (action === 'ask-delete-game') { modal = { type: 'delete-game', id: element.dataset.id }; menuGameId = ''; menuPosition = null; render(); return; }
    if (action === 'delete-game') { await api('deleteGame', modal.id); await refresh(); modal = null; toast = 'Juego eliminado de la biblioteca.'; render(); return; }
    if (action === 'prepare') {
      if (element.dataset.editId) { openGameEditor(element.dataset.editId); return; }
      const game = state.games.find(item => item.id === element.dataset.id);
      if (game) { prepareGameId = game.id; prepareTeams = clone(game.teams || []); preparePhase = 'teams'; turnOrderReady = false; diceValue = null; page = 'prepare'; render(); }
      return;
    }
    if (action === 'add-prepare-team') { syncPrepareTeams(); if (prepareTeams.length < 8) prepareTeams.push({ name: `Equipo ${prepareTeams.length + 1}`, color: teamPalette[prepareTeams.length % teamPalette.length] }); render(); return; }
    if (action === 'remove-prepare-team') { syncPrepareTeams(); if (prepareTeams.length > 2) prepareTeams.splice(Number(element.dataset.index), 1); else toast = 'Una partida necesita al menos dos equipos.'; render(); return; }
    if (action === 'prepare-turns') { syncPrepareTeams(); preparePhase = 'turns'; turnOrderReady = false; diceValue = null; render(); return; }
    if (action === 'prepare-teams') { preparePhase = 'teams'; render(); return; }
    if (action === 'roll-turns') { prepareTeams = shuffle(prepareTeams); diceValue = Math.floor(Math.random() * 6) + 1; turnOrderReady = true; playSound('dice', state.games.find(game => game.id === prepareGameId)); render(); return; }
    if (action === 'start-session') { syncPrepareTeams(); const game = state.games.find(item => item.id === prepareGameId); if (!gameQuestions(game).length) { modal = { type: 'no-questions' }; render(); return; } if (!turnOrderReady) { toast = 'Primero lanza el dado para definir el orden de turnos.'; render(); return; } const started = await api('startSession', prepareGameId, JSON.stringify(prepareTeams)); if (started.error) { toast = started.error; render(); return; } session = started; session.current_turn_index = 0; await api('updateSession', JSON.stringify(session)); page = 'board'; activeQuestion = null; selectedAnswerIndex = null; answeringTeamIndex = null; questionOutcome = 'selecting'; await refresh(); render(); return; }
    if (action === 'open-question') { const game = gameFromSession(); const category = (game.categories || []).find(item => item.id === element.dataset.categoryId); const question = (category?.questions || []).find(item => item.id === element.dataset.questionId); if (!question) return; if (!(session.used_cards || []).includes(question.id)) session.used_cards.push(question.id); await api('updateSession', JSON.stringify(session)); activeQuestion = { categoryId: category.id, questionId: question.id }; selectedAnswerIndex = null; writtenAnswer = ''; orderAvailable = shuffle(question.order_items || []); orderSelection = []; answeringTeamIndex = currentTurnIndex(); attemptedTeamIndexes = []; questionOutcome = 'selecting'; questionStartedAt = Date.now(); playSound('card', game); page = 'question'; render(); return; }
    if (action === 'select-answer') { selectedAnswerIndex = Number(element.dataset.index); playSound('select'); render(); return; }
    if (action === 'order-add') { const index = Number(element.dataset.index); const item = orderAvailable[index]; if (item) { orderSelection.push(item); orderAvailable.splice(index, 1); render(); } return; }
    if (action === 'order-up') { const index = Number(element.dataset.index); if (index > 0) { [orderSelection[index - 1], orderSelection[index]] = [orderSelection[index], orderSelection[index - 1]]; render(); } return; }
    if (action === 'order-down') { const index = Number(element.dataset.index); if (index < orderSelection.length - 1) { [orderSelection[index + 1], orderSelection[index]] = [orderSelection[index], orderSelection[index + 1]]; render(); } return; }
    if (action === 'validate-answer') {
      const game = gameFromSession(); const category = (game.categories || []).find(item => item.id === activeQuestion?.categoryId); const question = (category?.questions || []).find(item => item.id === activeQuestion?.questionId);
      if (!question) return;
      const type = answerType(question);
      const correct = type === 'choice'
        ? selectedAnswerIndex !== null && normalizedAnswer((question.choices || [])[selectedAnswerIndex]) === normalizedAnswer(question.answer)
        : type === 'text'
          ? (question.accepted_answers?.length ? question.accepted_answers : [question.answer]).some(answer => normalizedWrittenAnswer(answer) === normalizedWrittenAnswer(writtenAnswer))
          : type === 'order'
            ? (question.order_items || []).length === orderSelection.length && (question.order_items || []).every((item, index) => normalizedWrittenAnswer(item) === normalizedWrittenAnswer(orderSelection[index]))
            : false;
      if (correct) { const team = respondingTeam(); if (team) team.score = Number(team.score || 0) + Number(question.value || 0); questionOutcome = 'correct'; playSound('correct'); await api('updateSession', JSON.stringify(session)); }
      else { if (!attemptedTeamIndexes.includes(answeringTeamIndex)) attemptedTeamIndexes.push(answeringTeamIndex); questionOutcome = 'incorrect'; playSound('wrong'); }
      render(); return;
    }
    if (action === 'choose-other-team') { modal = { type: 'choose-other-team' }; render(); return; }
    if (action === 'select-other-team') { answeringTeamIndex = Number(element.dataset.index); selectedAnswerIndex = null; writtenAnswer = ''; const game = gameFromSession(); const category = (game?.categories || []).find(item => item.id === activeQuestion?.categoryId); const question = (category?.questions || []).find(item => item.id === activeQuestion?.questionId); orderAvailable = shuffle(question?.order_items || []); orderSelection = []; questionOutcome = 'selecting'; modal = null; playSound('pass'); render(); return; }
    if (action === 'reveal-answer') {
      const game = gameFromSession();
      const category = (game?.categories || []).find(item => item.id === activeQuestion?.categoryId);
      const question = (category?.questions || []).find(item => item.id === activeQuestion?.questionId);
      questionOutcome = answerType(question) === 'manual' ? 'manual-review' : 'revealed';
      render(); return;
    }
    if (action === 'manual-correct') {
      const game = gameFromSession();
      const category = (game?.categories || []).find(item => item.id === activeQuestion?.categoryId);
      const question = (category?.questions || []).find(item => item.id === activeQuestion?.questionId);
      const team = respondingTeam();
      if (!question || !team) return;
      team.score = Number(team.score || 0) + Number(question.value || 0);
      questionOutcome = 'correct';
      playSound('correct', game);
      await api('updateSession', JSON.stringify(session));
      render(); return;
    }
    if (action === 'manual-incorrect') {
      if (!attemptedTeamIndexes.includes(answeringTeamIndex)) attemptedTeamIndexes.push(answeringTeamIndex);
      questionOutcome = 'manual-incorrect';
      playSound('wrong');
      render(); return;
    }
    if (action === 'return-board') {
      if (questionOutcome !== 'selecting') {
        session.current_turn_index = (currentTurnIndex() + 1) % (session.teams?.length || 1);
        const game = gameFromSession();
        const allCardsUsed = gameQuestions(game).length > 0 && gameQuestions(game).every(question => (session.used_cards || []).includes(question.id));
        if (allCardsUsed) {
          session = await api('finishSession', JSON.stringify(session));
          await refresh();
          page = 'winner';
          backToGame = false;
          playSound('winner', game);
          render();
          return;
        }
        await api('updateSession', JSON.stringify(session));
        playSound('turn');
      }
      page = 'board'; backToGame = false; render(); return;
    }
    if (action === 'board') { page = 'board'; backToGame = false; render(); return; }
    if (action === 'score') { const team = session.teams[Number(element.dataset.index)]; if (team) { team.score = Number(team.score || 0) + Number(element.dataset.delta || 0); await api('updateSession', JSON.stringify(session)); render(); } return; }
    if (action === 'ask-finish-session') { modal = { type: 'finish' }; render(); return; }
    if (action === 'finish-session') { session = await api('finishSession', JSON.stringify(session)); await refresh(); modal = null; page = 'winner'; backToGame = false; playSound('winner'); render(); return; }
    if (action === 'discard-session') { if (session?.id) await api('discardSession', session.id); await refresh(); session = null; activeQuestion = null; modal = null; page = 'library'; toast = 'La partida se descartó y no fue guardada en el historial.'; render(); return; }
    if (action === 'winner-history') { page = 'history'; historyGameId = session?.game_id || ''; session = null; toast = 'Partida finalizada y guardada en el historial.'; render(); return; }
    if (action === 'winner-library') { session = null; page = 'library'; toast = 'Partida finalizada y guardada en el historial.'; render(); return; }
    if (action === 'ask-exit-session') { modal = { type: 'exit' }; render(); return; }
    if (action === 'exit-session') { await api('updateSession', JSON.stringify(session)); await refresh(); session = null; activeQuestion = null; modal = null; page = 'library'; toast = 'La partida sigue disponible en el historial.'; render(); return; }
    if (action === 'close-modal') { modal = null; render(); return; }
  }

  root.addEventListener('click', event => {
    const control = event.target.closest('[data-action]');
    if (control) { event.preventDefault(); handle(control.dataset.action, control); }
  });
  root.addEventListener('change', event => {
    if (event.target.matches('[data-question-field="answer_type"]')) { syncDraft(); render(); }
  });
  root.addEventListener('input', event => {
    if (event.target.matches('[data-written-answer]')) {
      writtenAnswer = event.target.value;
      refreshWrittenAnswerValidation();
    }
  });
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && modal) { modal = null; render(); } });

  function installStyle() {
    document.head.insertAdjacentHTML('beforeend', `<style>
      button.nav-item{background:transparent;border:0;width:100%;cursor:pointer;text-align:left}button.tab{background:transparent;cursor:pointer}input.inp,select.inp,textarea.area{font:inherit;outline:none}select.inp{appearance:auto}.native-color{padding:2px;cursor:pointer}.native-color::-webkit-color-swatch-wrapper{padding:0}.native-color::-webkit-color-swatch{border:0;border-radius:8px}.image-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.desktop-menu{position:fixed;z-index:20}.edit-link{text-decoration:none}.category-list{overflow:auto}.category-row{width:100%;text-align:left;cursor:pointer;background:transparent}.category-edit{border-top:1px solid #2b3b51;margin-top:20px;padding-top:18px;display:grid;grid-template-columns:1fr 42px 42px;gap:9px;align-items:end}.category-edit .field-label{margin-bottom:5px}.question-picker{border-top:1px solid #2b3b51;margin-top:18px;padding-top:18px}.question-choice{width:100%;border:1px solid transparent;background:#101a2a;color:#c7d6eb;border-radius:10px;padding:9px;display:flex;align-items:center;gap:9px;text-align:left;margin:7px 0;cursor:pointer}.question-choice:hover{background:#192a43}.question-choice.active{background:#27365a;border-color:#5369ad;color:#fff}.question-choice small{display:block;color:#8ea2bd;font-size:11px;margin-top:3px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:165px}.question-value{background:#263957;border:1px solid #4b6389;border-radius:7px;padding:5px 7px;font-weight:800;font-size:12px;min-width:37px;text-align:center}.question-picker-empty{padding:13px 0}.blank-state{display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center}.blank-state .empty-ico{margin-bottom:18px}.question-form{display:grid;grid-template-columns:1.25fr .82fr;gap:27px}.question-photo{width:100%;height:265px;object-fit:cover;border:1px solid #344c6a;border-radius:18px;background:#0e1a2d}.large-photo{width:305px;height:260px;flex:none}.answer{width:100%;text-align:left;cursor:pointer}.answer.selected{border-color:#8497ff;background:#2b3b69;box-shadow:0 0 0 2px #7589ff55}.answer.incorrect{background:#4a2632;border-color:#f26b83}.answer.incorrect .answer-letter{background:#a94a60;border-color:#ff9aaa}.answer:disabled{cursor:default}.reveal-wrong{background:linear-gradient(90deg,#4a222d,#40212a);border-color:#cc5269}.reveal-wrong .reveal-title{color:#ffb1be}.award-confirmed{display:flex;margin:18px auto 0;width:max-content}.btn:disabled{cursor:not-allowed}.prepare-layout{max-width:820px;margin:25px auto;padding:28px}.prepare-teams{margin-top:23px}.prepare-team{display:flex;align-items:center;gap:14px;margin:9px 0;background:#111d31;padding:12px 14px;border:1px solid #32465f;border-radius:11px}.prepare-team .inp{flex:1}.confirmation-dialog{text-align:center;width:510px}.confirmation-dialog .note{margin:0 auto 8px;max-width:390px}.desktop-toast{position:fixed;right:30px;bottom:28px;z-index:30;background:#173b35;border:1px solid #38b991;color:#d7fff0;padding:14px 18px;border-radius:12px;box-shadow:0 14px 42px #0009;font-weight:650;max-width:390px}.point-tile{cursor:pointer}.point-tile:disabled{cursor:default}.award-btn{color:#e7effd;cursor:pointer}.score-ticks button{cursor:pointer}.score-ticks{display:flex;gap:5px}@media(max-width:1250px){.workspace{padding:26px 30px}.cards{grid-template-columns:repeat(2,minmax(0,1fr))}.question-form{grid-template-columns:1fr}.large-photo{display:none}.board{gap:10px}.point-tile{font-size:23px}}
    </style>`);
    document.head.insertAdjacentHTML('beforeend', `<style>
      .turn-badge{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--turn);background:#14243b;border-radius:9px;padding:9px 12px;color:#eaf2ff;font-size:12px;font-weight:750}.turn-badge .dot{width:9px;height:9px}.answering-turn{display:flex;align-items:center;justify-content:center;gap:9px;width:max-content;margin:0 auto 14px;border:1px solid var(--team);background:#14243b;border-radius:11px;padding:10px 16px;color:#bac9df}.answering-turn strong{color:#fff}.dice-value{display:grid;place-items:center;width:62px;height:62px;border-radius:17px;background:#25385b;border:1px solid #5d78b2;color:#fff;font-weight:850;font-size:25px}.turn-order-list{margin-top:23px}.turn-order-row{display:flex;align-items:center;gap:13px;background:#111d31;border:1px solid #32465f;border-radius:11px;padding:13px 15px;margin:9px 0}.turn-position{display:grid;place-items:center;width:31px;height:31px;border-radius:9px;background:#2a3d61;border:1px solid #536f9f;font-weight:800}.turn-order-row strong{min-width:150px}.turn-order-row .note{margin-left:auto}.turn-order-empty{border:1px dashed #445674;border-radius:12px;padding:38px;text-align:center;color:#8fa3bd}.team-choice-dialog{width:610px}.team-choice-list{display:grid;gap:10px}.team-choice{display:flex;align-items:center;gap:12px;width:100%;border:1px solid #3b516e;border-left:4px solid var(--team);border-radius:11px;background:#14243a;color:#e8efff;padding:14px;text-align:left;cursor:pointer}.team-choice:hover{background:#20334f}.team-choice strong{font-size:16px}.team-choice span:last-child{margin-left:auto;color:#9eafc8;font-size:12px}@media(max-width:1250px){.turn-badge{display:none}.turn-order-row strong{min-width:0}.team-choice-dialog{width:560px}}
    </style>`);
    document.head.insertAdjacentHTML('beforeend', `<style>
      /* El formulario de una pregunta puede ser más alto que la lista de categorías.
         El scroll es de toda la vista de configuración, no de una caja de 650px. */
      .editor-work{min-height:0;overflow-y:auto;overflow-x:hidden;padding-bottom:42px}.question-layout{display:grid;grid-template-columns:285px minmax(0,1fr);gap:20px;height:auto;min-height:650px;align-items:start}.question-layout>.category-list{height:fit-content;max-height:calc(100vh - 245px);padding:21px;position:sticky;top:0}.question-editor-workspace{height:auto;overflow:visible;padding-right:3px;padding-bottom:32px;display:flex;flex-direction:column;gap:16px}.category-controls{display:grid;grid-template-columns:minmax(190px,1fr) minmax(270px,1.6fr) 72px 170px;align-items:end;gap:14px;padding:18px 20px}.category-controls .field-label{margin-bottom:6px}.category-color{width:46px;height:45px}.questions-browser{padding:20px}.questions-browser .toolbar{margin-bottom:16px}.questions-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.question-card-choice{min-height:132px;border:1px solid #344963;background:#111d30;color:#dce7f8;border-radius:13px;padding:13px;text-align:left;cursor:pointer;display:flex;flex-direction:column;gap:10px}.question-card-choice:hover{background:#1a2a43;border-color:#526b94}.question-card-choice.active{background:#26365a;border-color:#7489e6;box-shadow:0 0 0 1px #7187e888}.question-card-choice strong{font-size:13px;line-height:1.38}.question-card-answer{display:block;margin-top:auto;color:#91a6c2;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.questions-empty{grid-column:1/-1;border:1px dashed #3b506e;border-radius:12px;padding:28px;color:#91a4bf;text-align:center}.question-edit-panel{padding:22px 25px}.question-edit-panel.blank-state{min-height:290px}@media(max-width:1250px){.question-layout{grid-template-columns:245px minmax(0,1fr)}.category-controls{grid-template-columns:1fr 1.4fr 60px 150px}.questions-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:1050px){.question-layout{grid-template-columns:1fr}.question-layout>.category-list{position:static;height:auto;max-height:280px}.question-editor-workspace{height:auto;max-height:none}.category-controls{grid-template-columns:1fr 1fr 60px 150px}.questions-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>`);
    document.head.insertAdjacentHTML('beforeend', `<style>
      .question-live-info{display:flex;justify-content:center;align-items:stretch;gap:14px;margin:0 auto 18px}.question-timer{display:grid;place-items:center;min-width:210px;border:1px solid #576f98;background:#14243b;border-radius:13px;padding:12px 18px;color:#f5f8ff;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:29px;font-weight:800;letter-spacing:1px;font-variant-numeric:tabular-nums}.answering-turn-large{margin:0;font-size:16px;padding:13px 20px;min-width:245px}.written-answer{max-width:760px;margin:12px auto 0}.written-answer .inp{font-size:21px;min-height:64px}.written-answer .note{display:block;margin-top:10px}.order-game{margin-top:16px;display:grid;gap:18px}.order-options{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.order-option{min-height:62px;border:1px solid #4b6389;background:#243852;color:#eff6ff;border-radius:10px;padding:9px;font-size:15px;font-weight:700;cursor:pointer}.order-option:hover{background:#304a6d;border-color:#7b96c1}.order-target{display:grid;gap:9px}.order-slot{display:flex;align-items:center;gap:12px;min-height:54px;border:1px dashed #526783;background:#101b2b;border-radius:10px;padding:8px 12px;color:#8194ae}.order-slot.filled{border-style:solid;background:#1d304a;color:#edf5ff}.order-number{display:grid;place-items:center;width:29px;height:29px;border-radius:8px;background:#2b405e;border:1px solid #587398;font-size:13px;font-weight:800}.order-move{margin-left:auto;display:flex;gap:7px}.order-move .btn{min-width:35px;height:34px;min-height:34px;padding:6px;font-size:16px}.order-option:disabled{cursor:default;opacity:.7}@media(max-width:900px){.question-live-info{flex-direction:column;align-items:center}.order-options{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>`);
    document.head.insertAdjacentHTML('beforeend', `<style>
      /* Tablero: prioriza lectura a distancia y aprovecha el ancho disponible. */
      .gamebar{height:132px;padding:18px 52px;gap:28px}.game-logo{width:205px;font-size:19px;line-height:1.02}.game-logo .mark{width:48px;height:48px;border-radius:14px;font-size:23px}.game-actions{gap:12px}.game-actions .btn{height:50px;min-height:50px;padding:10px 16px;font-size:15px;border-radius:12px}.turn-badge{padding:12px 16px;font-size:15px;border-radius:12px}.scoreboard{gap:14px}.score{min-width:205px;height:94px;padding:11px 14px;border-radius:13px;border-top-width:4px}.score-name{font-size:16px;font-weight:760}.score-name .dot{width:11px;height:11px}.score-value b{font-size:32px}.small-btn{font-size:12px;padding:6px 9px;border-radius:7px}.play-content{padding:24px 46px 38px}.game-heading{margin-bottom:20px}.game-heading h1{font-size:38px;margin:1px 0 9px}.game-stamp{font-size:15px;padding:11px 16px}.board{max-width:1840px;width:100%;gap:20px}.board-cat{border-radius:20px;padding:12px 12px 14px}.board-cat-head{height:116px;border-radius:14px;margin-bottom:14px;gap:12px}.board-cat-head b{font-size:22px;text-align:center;line-height:1.1}.board-cat-head .ico{width:28px;height:28px}.point-tile{height:82px;margin-bottom:12px;border-radius:12px;font-size:38px}.used-check{font-size:17px}.winner-content{position:relative;z-index:1;display:grid;place-items:center;padding:34px 34px 48px}.winner-card{position:relative;overflow:hidden;width:min(1060px,100%);padding:32px 44px 34px;border:1px solid #526987;border-top:5px solid var(--winner);border-radius:28px;background:linear-gradient(145deg,#172840,#0d1829);box-shadow:0 28px 80px #0008;text-align:center}.winner-card:before{content:'';position:absolute;inset:-120px 20% auto;height:250px;background:radial-gradient(circle,var(--winner),transparent 67%);opacity:.2;pointer-events:none}.winner-kicker,.winner-label{position:relative;color:#96abc7;letter-spacing:2px;font-size:13px;font-weight:850}.winner-photo{position:relative;width:158px;height:158px;border-radius:50%;object-fit:cover;border:5px solid var(--winner);box-shadow:0 0 0 10px color-mix(in srgb,var(--winner) 20%,transparent),0 12px 32px #0008;margin:19px auto 16px}.winner-art{position:relative;display:grid;place-items:center;width:142px;height:142px;margin:19px auto 16px;border:3px solid var(--winner);border-radius:50%;background:radial-gradient(circle at 40% 30%,#365173,#16263b 68%);color:#ffd66b;box-shadow:0 0 0 10px #ffffff08,0 12px 32px #0008}.winner-art .ico{width:66px;height:66px}.winner-art i{position:absolute;font-style:normal;color:#fff;font-size:24px}.winner-art i:first-of-type{left:15px;top:19px}.winner-art i:last-of-type{right:16px;bottom:20px;color:var(--winner)}.winner-copy{position:relative}.winner-copy h1{font-size:48px;letter-spacing:-1.8px;margin:8px 0;color:#fff}.winner-points{font-size:54px;font-weight:900;line-height:1;color:var(--winner);letter-spacing:-2px}.winner-points span{font-size:20px;letter-spacing:0;color:#c4d3e8}.winner-copy p{color:#9fb0c8;font-size:16px;margin:14px auto 23px}.winner-ranking{position:relative;display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;text-align:left}.winner-team{display:flex;align-items:center;gap:9px;border:1px solid #3e5471;border-left:4px solid var(--team);padding:12px 14px;border-radius:12px;background:#101d30;color:#dbe7f8}.winner-team.leader{background:#193a39;border-color:var(--team);box-shadow:0 0 0 1px color-mix(in srgb,var(--team) 35%,transparent)}.winner-position{display:grid;place-items:center;width:24px;height:24px;border-radius:7px;background:#314761;color:#fff;font-size:12px;font-weight:850}.winner-team strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.winner-team b{margin-left:auto;color:#fff;white-space:nowrap}.winner-actions{position:relative;display:flex;justify-content:center;gap:12px;margin-top:26px}.winner-actions .btn{min-width:210px}@media(max-width:1450px){.gamebar{padding:16px 30px;gap:18px}.game-logo{width:172px}.score{min-width:170px}.score-name{font-size:14px}.game-actions .btn{font-size:13px;padding:9px 12px}.board-cat-head b{font-size:18px}.point-tile{font-size:32px;height:72px}}@media(max-width:1100px){.gamebar{height:auto;flex-wrap:wrap}.scoreboard{width:100%;order:3;justify-content:flex-start}.score{flex:1}.board{grid-template-columns:repeat(3,minmax(0,1fr))}.winner-copy h1{font-size:38px}}@media(max-width:720px){.play-content{padding:18px}.game-logo{width:auto}.game-actions{flex-wrap:wrap}.scoreboard{overflow:auto}.score{min-width:170px}.board{grid-template-columns:repeat(2,minmax(0,1fr))}.board-cat-head b{font-size:17px}.point-tile{font-size:29px}.winner-card{padding:26px 18px}.winner-copy h1{font-size:32px}.winner-points{font-size:44px}.winner-actions{flex-direction:column}.winner-actions .btn{width:100%}}
    </style>`);
    document.head.insertAdjacentHTML('beforeend', `<style>
      /* Tablero limpio: el marcador vive arriba y las acciones viven en el footer. */
      .board-screen .board-gamebar{height:auto;min-height:130px;justify-content:center;padding:18px 44px}.board-gamebar .scoreboard{width:auto;max-width:100%;margin:0;justify-content:center;flex-wrap:wrap}.board-gamebar .score{min-width:220px;text-align:center}.board-gamebar .score-name{justify-content:center;font-size:17px}.board-gamebar .score-value{justify-content:center;gap:17px}.board-screen .board-content{padding-top:22px;padding-bottom:22px}.board-heading{margin-bottom:18px}.board-heading h1{font-size:46px;line-height:1.08;margin:0}.board-screen .board{max-width:1840px}.board-screen .board-cat-head{height:122px}.board-screen .board-cat-head b{font-size:25px}.board-footer{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;max-width:1840px;margin:17px auto 0;min-height:54px}.board-remaining{justify-self:start;display:inline-flex;align-items:center;gap:7px;color:#91a7c2;font-size:13px;font-weight:650}.board-remaining .ico{width:17px;height:17px}.board-turn{position:relative;justify-self:center;display:flex;flex-direction:column;align-items:center;gap:2px;color:#9aacc4;font-size:14px;line-height:1.15}.board-turn strong{font-size:18px;color:#eef5ff;font-weight:800}.board-turn:before{content:'';width:8px;height:8px;border-radius:50%;background:var(--turn);box-shadow:0 0 0 4px color-mix(in srgb,var(--turn) 16%,transparent);position:absolute;left:-17px;top:4px}.footer-finish{justify-self:end;width:46px;height:46px;min-height:46px;padding:0;border-radius:13px}.footer-finish .ico{width:21px;height:21px}.board-finished{max-width:1840px;margin:8px auto 0;text-align:center;color:#8df8ca;font-size:13px}.finish-options{display:flex;justify-content:center;gap:9px;flex-wrap:wrap}.finish-options .btn{font-size:13px;padding-left:12px;padding-right:12px}.sound-settings{display:grid;grid-template-columns:1.25fr 1fr auto;align-items:end;gap:14px;margin-top:15px;padding:15px;border:1px solid #334863;border-radius:12px;background:#101b2b}.sound-switch{display:flex;align-items:center;gap:9px;color:#dce7f8;font-size:13px;font-weight:650}.sound-switch input{width:17px;height:17px;accent-color:#6478ff}.sound-volume{display:flex;align-items:center;gap:9px}.sound-volume input{width:100%;accent-color:#6d82ff}.sound-volume b{font-size:12px;color:#b9c9df;min-width:32px}.sound-preview .btn{white-space:nowrap}@media(max-width:1100px){.board-screen .board-gamebar{padding:14px 22px}.board-gamebar .score{min-width:185px}.board-screen .board-cat-head b{font-size:21px}.board-footer{padding:0 4px}.sound-settings{grid-template-columns:1fr 1fr}}@media(max-width:720px){.board-gamebar .score{min-width:150px}.board-gamebar .score-name{font-size:14px}.board-heading h1{font-size:34px}.board-screen .board-cat-head b{font-size:18px}.board-footer{grid-template-columns:1fr auto 1fr}.board-remaining{font-size:11px}.board-turn{font-size:12px}.board-turn strong{font-size:15px}.board-turn:before{display:none}.sound-settings{grid-template-columns:1fr}.sound-preview .btn{width:100%}}
    </style>`);
    document.head.insertAdjacentHTML('beforeend', `<style>
      /* Pregunta: navegación mínima y lectura prioritaria. */
      .question-gamebar{min-height:112px;height:auto;padding:18px 52px}.question-game-navigation{display:flex;align-items:center;gap:17px;min-width:0}.question-board-button{height:50px;min-height:50px;padding:10px 16px;font-size:15px;border-radius:12px}.question-game-title{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#f3f7ff;font-size:25px;font-weight:820;letter-spacing:-.5px}.question-screen .play-content{padding-top:20px}.question-screen .question-stage{max-width:1360px;margin-top:12px}.question-screen .question-live-info{margin-bottom:16px}.question-points{display:grid;place-items:center;min-width:148px;border:1px solid #9a7540;background:#282133;border-radius:13px;padding:12px 16px;color:#ffcf6a;text-transform:uppercase;font-size:22px;font-weight:900;letter-spacing:.2px}.question-points span{font-size:13px;letter-spacing:.6px}.question-screen .question-timer{min-width:170px;font-size:31px}.question-screen .answering-turn-large{min-width:230px}.question-category-badge{display:inline-flex;align-items:center;gap:7px;border:1px solid #405977;background:#14243b;border-radius:9px;padding:8px 12px;color:#cbd9ed;font-size:13px;font-weight:760;margin-bottom:18px}.question-category-badge .ico{width:17px;height:17px}.question-screen .qtext{margin-top:0}.question-screen .question-foot{margin-top:20px}.question-screen .question-foot .btn{min-width:250px}@media(max-width:1100px){.question-gamebar{padding:14px 24px}.question-gamebar .scoreboard{margin-left:auto;width:auto;order:initial}.question-gamebar .score{min-width:170px}.question-game-title{font-size:20px}.question-points{min-width:128px;font-size:19px}}@media(max-width:720px){.question-gamebar{gap:12px}.question-gamebar .scoreboard{display:none}.question-game-title{font-size:17px}.question-live-info{gap:9px}.question-points{min-width:108px;padding:9px 10px;font-size:17px}.question-points span{font-size:10px}.question-screen .question-timer{min-width:136px;font-size:25px}.question-screen .answering-turn-large{min-width:0;padding:10px 13px;font-size:14px}.question-screen .question-foot .btn{min-width:0}}
    </style>`);
    document.head.insertAdjacentHTML('beforeend', `<style>
      /* Celebración de cierre automático al agotar el tablero. */
      .winner-screen:after{content:'';position:absolute;inset:0;pointer-events:none;z-index:0;background:radial-gradient(circle at 12% 16%,#ffcf6a66 0 3px,transparent 4px),radial-gradient(circle at 83% 19%,#8cf4d866 0 4px,transparent 5px),radial-gradient(circle at 76% 76%,#8799ff66 0 3px,transparent 4px),radial-gradient(circle at 22% 74%,#ff75ad66 0 3px,transparent 4px);background-size:160px 145px,200px 175px,185px 165px,225px 190px;animation:confettiDrift 7s linear infinite}.winner-card{animation:winnerEnter .68s cubic-bezier(.19,1,.22,1) both}.winner-card:before{animation:winnerGlow 2.8s ease-in-out infinite}.winner-art,.winner-photo{animation:winnerFloat 2.7s ease-in-out infinite}.winner-copy h1{animation:winnerTitle .7s .18s both}.winner-points{animation:winnerTitle .7s .3s both}.winner-team{animation:winnerRow .5s both}.winner-team:nth-child(1){animation-delay:.38s}.winner-team:nth-child(2){animation-delay:.48s}.winner-team:nth-child(3){animation-delay:.58s}.winner-team:nth-child(4){animation-delay:.68s}.winner-team:nth-child(5){animation-delay:.78s}.winner-team:nth-child(6){animation-delay:.88s}@keyframes winnerEnter{from{opacity:0;transform:translateY(32px) scale(.96)}to{opacity:1;transform:translateY(0) scale(1)}}@keyframes winnerGlow{0%,100%{opacity:.16;transform:scale(.94)}50%{opacity:.36;transform:scale(1.08)}}@keyframes winnerFloat{0%,100%{transform:translateY(0) rotate(-2deg)}50%{transform:translateY(-10px) rotate(2deg)}}@keyframes winnerTitle{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}@keyframes winnerRow{from{opacity:0;transform:translateX(-16px)}to{opacity:1;transform:translateX(0)}}@keyframes confettiDrift{from{background-position:0 0,0 0,0 0,0 0}to{background-position:70px 150px,-90px 180px,110px 170px,-65px 195px}}@media(prefers-reduced-motion:reduce){.winner-screen:after,.winner-card,.winner-card:before,.winner-art,.winner-photo,.winner-copy h1,.winner-points,.winner-team{animation:none}}
    </style>`);
  }

  function connect() {
    if (!window.qt || !window.QWebChannel) return;
    new QWebChannel(qt.webChannelTransport, async channel => {
      bridge = channel.objects.quizBridge;
      installStyle();
      await refresh();
      render();
    });
  }

  connect();
})();
