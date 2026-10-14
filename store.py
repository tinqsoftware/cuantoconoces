"""Persistencia local para juegos configurables e historial de partidas."""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


# Los recursos incluidos en el instalador son de solo lectura. Los juegos e
# historiales de una instalación Windows se guardan en LOCALAPPDATA para no
# intentar escribir dentro de Program Files y para sobrevivir actualizaciones.
SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
if getattr(sys, "frozen", False) and sys.platform.startswith("win"):
    APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Quiz Studio"
else:
    APP_DIR = SOURCE_DIR

STORAGE_DIR = APP_DIR / "storage"
GAMES_PATH = STORAGE_DIR / "games.json"
HISTORY_PATH = STORAGE_DIR / "history.json"
LEGACY_DATA_PATH = RESOURCE_DIR / "game_data.json"
LEGACY_CONFIG_PATH = RESOURCE_DIR / "config.example.json"

TEAM_COLORS = ["#22C7A9", "#F26B9A", "#6AA7FF", "#F7C84B", "#B891FF", "#FF8C69", "#60D394", "#FFAFCC"]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path, fallback: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(fallback)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as destination:
        json.dump(data, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    temporary.replace(path)


class GameStore:
    """Almacena definiciones de juegos y sesiones sin depender de PowerPoint."""

    def __init__(self) -> None:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_seed_game()
        self._migrate_image_paths()
        self._migrate_history_snapshots()

    def import_image(self, raw_path: str) -> str:
        """Copia una imagen elegida a los datos de Quiz Studio.

        Guardar la ruta original haría que un juego pierda sus fotos al mover
        el archivo, actualizar la aplicación o instalarla en otra computadora.
        Cada carga se conserva por ello junto con el historial local.
        """
        source = Path(raw_path).expanduser()
        if not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
            return ""
        destination_dir = STORAGE_DIR / "images"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{new_id()}{source.suffix.lower()}"
        try:
            shutil.copy2(source, destination)
            return str(destination)
        except OSError:
            return ""

    def _is_managed_image(self, raw_path: str) -> bool:
        try:
            Path(raw_path).resolve().relative_to((STORAGE_DIR / "images").resolve())
            return True
        except (OSError, ValueError):
            return False

    def _migrate_image_paths(self) -> None:
        """Vuelve portables las imágenes que se eligieron en versiones previas."""
        games = self._read_games()
        changed = False
        for game in games:
            if not isinstance(game, dict):
                continue
            image_holders: list[tuple[dict[str, Any], str]] = [(game, "background_image"), (game, "winner_image")]
            for category in game.get("categories", []):
                if not isinstance(category, dict):
                    continue
                for question in category.get("questions", []):
                    if isinstance(question, dict):
                        image_holders.append((question, "image_path"))
            for holder, field in image_holders:
                path = holder.get(field, "")
                if not isinstance(path, str) or not path or self._is_managed_image(path):
                    continue
                imported = self.import_image(path)
                if imported:
                    holder[field] = imported
                    changed = True
        if changed:
            self._write_games(games)

    def _migrate_history_snapshots(self) -> None:
        """Añade instantáneas a historiales creados antes de esta versión.

        La migración es conservadora: sólo completa sesiones que aún no tenían
        copia y cuyo juego original sigue disponible. Nunca borra ni reescribe
        datos de resultados.
        """
        games_by_id = {game.get("id"): game for game in self._read_games() if game.get("id")}
        sessions = self._read_history()
        changed = False
        for session in sessions:
            if isinstance(session.get("game_snapshot"), dict):
                continue
            original = games_by_id.get(session.get("game_id"))
            if original is not None:
                session["game_snapshot"] = copy.deepcopy(original)
                changed = True
        if changed:
            self._write_history(sessions)

    def _ensure_seed_game(self) -> None:
        games = self._read_games()
        if games:
            return
        self._write_games([self._legacy_game()])

    def _legacy_game(self) -> dict[str, Any]:
        legacy_data = read_json(LEGACY_DATA_PATH, {"categories": []})
        legacy_config = read_json(LEGACY_CONFIG_PATH, {})
        legacy_game = legacy_config.get("game", {})
        title = legacy_game.get("title", "Cuánto conoces?")
        categories = copy.deepcopy(legacy_data.get("categories", []))
        for category_index, category in enumerate(categories):
            category.setdefault("id", new_id())
            category.setdefault("name", f"Categoría {category_index + 1}")
            category.setdefault("color", "#3B82F6")
            category.pop("screen_name", None)
            for question_index, question in enumerate(category.get("questions", [])):
                question.setdefault("id", new_id())
                question.setdefault("value", (question_index + 1) * 10)
                question.setdefault("question", question.pop("prompt", ""))
                question.setdefault("answer", "")
                question.setdefault("choices", [])
                question.setdefault("answer_type", "choice" if question.get("choices") else "text")
                question.setdefault("accepted_answers", [question["answer"]] if question.get("answer_type") == "text" and question.get("answer") else [])
                question.setdefault("order_items", [])

        default_teams = copy.deepcopy(legacy_game.get("teams", []))
        if not default_teams:
            default_teams = [{"name": f"Equipo {index + 1}", "color": TEAM_COLORS[index]} for index in range(4)]
        for index, team in enumerate(default_teams):
            team.setdefault("name", f"Equipo {index + 1}")
            team.setdefault("color", TEAM_COLORS[index % len(TEAM_COLORS)])

        now = timestamp()
        return {
            "id": new_id(),
            "name": "Trivia inicial",
            "title": title,
            "background_color": "#111827",
            "background_image": "",
            "winner_image": "",
            "accent_color": "#45DCC2",
            "text_color": "#F8FAFC",
            "card_color": "#1F2937",
            "font_family": "Arial",
            "sound_enabled": True,
            "sound_volume": 55,
            "teams": default_teams,
            "categories": categories,
            "created_at": now,
            "updated_at": now,
        }

    def blank_game(self) -> dict[str, Any]:
        now = timestamp()
        return {
            "id": new_id(),
            "name": "Nuevo juego",
            "title": "Mi juego de preguntas",
            "background_color": "#111827",
            "background_image": "",
            "winner_image": "",
            "accent_color": "#5EEAD4",
            "text_color": "#F8FAFC",
            "card_color": "#243047",
            "font_family": "Arial",
            "sound_enabled": True,
            "sound_volume": 55,
            "teams": [
                {"name": "Equipo 1", "color": TEAM_COLORS[0]},
                {"name": "Equipo 2", "color": TEAM_COLORS[1]},
            ],
            "categories": [
                {
                    "id": new_id(),
                    "name": "Nueva categoría",
                    "color": "#3B82F6",
                    "questions": [
                        {
                            "id": new_id(),
                            "value": 10,
                            "question": "Escribe aquí la primera pregunta.",
                            "choices": [],
                            "answer": "Escribe aquí la respuesta.",
                            "answer_type": "choice",
                            "accepted_answers": [],
                            "order_items": [],
                            "image_path": "",
                        }
                    ],
                }
            ],
            "created_at": now,
            "updated_at": now,
        }

    def _read_games(self) -> list[dict[str, Any]]:
        payload = read_json(GAMES_PATH, {"games": []})
        games = payload.get("games", []) if isinstance(payload, dict) else []
        if not isinstance(games, list):
            return []
        # Versiones previas del puente podían persistir un objeto de error
        # cuando se cancelaba/seleccionaba una imagen. Una ruta siempre es
        # texto; los valores incompatibles se degradan con seguridad a vacío.
        for game in games:
            if not isinstance(game, dict):
                continue
            for field in ("background_image", "winner_image"):
                if not isinstance(game.get(field, ""), str):
                    game[field] = ""
        return games

    def _write_games(self, games: list[dict[str, Any]]) -> None:
        write_json(GAMES_PATH, {"games": games})

    def list_games(self) -> list[dict[str, Any]]:
        return sorted(self._read_games(), key=lambda game: game.get("updated_at", ""), reverse=True)

    def get_game(self, game_id: str) -> dict[str, Any] | None:
        for game in self._read_games():
            if game.get("id") == game_id:
                return copy.deepcopy(game)
        return None

    def save_game(self, game: dict[str, Any]) -> dict[str, Any]:
        games = self._read_games()
        game = copy.deepcopy(game)
        for field in ("background_image", "winner_image"):
            if not isinstance(game.get(field, ""), str):
                game[field] = ""
        game["id"] = game.get("id") or new_id()
        game["created_at"] = game.get("created_at") or timestamp()
        game["updated_at"] = timestamp()
        replaced = False
        for index, existing in enumerate(games):
            if existing.get("id") == game["id"]:
                games[index] = game
                replaced = True
                break
        if not replaced:
            games.append(game)
        self._write_games(games)
        return copy.deepcopy(game)

    def duplicate_game(self, game_id: str) -> dict[str, Any] | None:
        game = self.get_game(game_id)
        if game is None:
            return None
        game["id"] = new_id()
        game["name"] = f"{game.get('name', 'Juego')} (copia)"
        game.pop("created_at", None)
        game.pop("updated_at", None)
        self._refresh_nested_ids(game)
        return self.save_game(game)

    def _refresh_nested_ids(self, game: dict[str, Any]) -> None:
        for category in game.get("categories", []):
            category["id"] = new_id()
            for question in category.get("questions", []):
                question["id"] = new_id()

    def delete_game(self, game_id: str) -> None:
        games = [game for game in self._read_games() if game.get("id") != game_id]
        self._write_games(games)

    def _read_history(self) -> list[dict[str, Any]]:
        payload = read_json(HISTORY_PATH, {"sessions": []})
        return payload.get("sessions", []) if isinstance(payload, dict) else []

    def _write_history(self, sessions: list[dict[str, Any]]) -> None:
        write_json(HISTORY_PATH, {"sessions": sessions})

    def list_sessions(self, game_id: str | None = None) -> list[dict[str, Any]]:
        sessions = self._read_history()
        if game_id:
            sessions = [session for session in sessions if session.get("game_id") == game_id]
        return sorted(sessions, key=lambda session: session.get("started_at", ""), reverse=True)

    def start_session(self, game: dict[str, Any], teams: list[dict[str, Any]]) -> dict[str, Any]:
        session = {
            "id": new_id(),
            "game_id": game["id"],
            "game_name": game.get("name", "Juego"),
            "game_title": game.get("title", "Juego de preguntas"),
            "status": "en curso",
            "started_at": timestamp(),
            "ended_at": "",
            "teams": [{"name": team["name"], "color": team["color"], "score": 0} for team in teams],
            # La partida es una instantánea. Así, editar o incluso eliminar el
            # juego original no altera lo que se mostró durante la sesión.
            "game_snapshot": copy.deepcopy(game),
            "used_cards": [],
            "winner": "",
        }
        sessions = self._read_history()
        sessions.append(session)
        self._write_history(sessions)
        return copy.deepcopy(session)

    def update_session(self, session: dict[str, Any]) -> None:
        sessions = self._read_history()
        for index, existing in enumerate(sessions):
            if existing.get("id") == session.get("id"):
                sessions[index] = copy.deepcopy(session)
                break
        else:
            sessions.append(copy.deepcopy(session))
        self._write_history(sessions)

    def discard_session(self, session_id: str) -> None:
        """Elimina una partida abandonada para que nunca llegue al historial."""
        sessions = self._read_history()
        self._write_history([session for session in sessions if session.get("id") != session_id])

    def finish_session(self, session: dict[str, Any]) -> dict[str, Any]:
        session = copy.deepcopy(session)
        session["status"] = "finalizado"
        session["ended_at"] = timestamp()
        teams = session.get("teams", [])
        if teams:
            highest = max(team.get("score", 0) for team in teams)
            winners = [team.get("name", "Equipo") for team in teams if team.get("score", 0) == highest]
            session["winner"] = ", ".join(winners)
        self.update_session(session)
        return session
