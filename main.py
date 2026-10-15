"""Quiz Studio: aplicación de escritorio para crear y jugar trivias configurables."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import textwrap
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from store import GameStore, TEAM_COLORS, new_id

# El Tk integrado en macOS muestra una advertencia deprecada al crear la
# ventana. La aplicación no usa APIs eliminadas; esta variable sólo evita que
# esa advertencia ensucie la terminal del usuario.
os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")

import tkinter as tk
from tkinter import colorchooser, filedialog, font as tkfont

try:
    from PIL import Image, ImageOps, ImageTk

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# Sistema visual inspirado en los 26 mockups de Quiz Studio.
BG = "#080D18"
BG_PLAY = "#0A1323"
SIDEBAR = "#0C1422"
SURFACE = "#111B2D"
PANEL = "#131E30"
PANEL_2 = "#19263B"
INPUT = "#0D1524"
STROKE = "#2A3B55"
STROKE_LIGHT = "#405473"
TEXT = "#F4F7FF"
MUTED = "#91A0B9"
PRIMARY = "#687DFF"
PRIMARY_ACTIVE = "#5269F4"
MINT = "#42DFB5"
AMBER = "#F6C56B"
FONT = "Arial"
IMAGE_TYPES = [("Imágenes", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("Todos los archivos", "*.*")]

def bundled_path(filename: str) -> Path:
    """Devuelve una ruta de recursos tanto en desarrollo como empaquetada.

    PyInstaller extrae los recursos de un ejecutable en una carpeta temporal
    (``_MEIPASS``). No debemos depender de la ubicación del .exe para leer la
    interfaz, pues en una instalación de Windows estará dentro de Program
    Files.
    """
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return bundle_dir / filename


WEB_UI_PATH = bundled_path("web_ui.html")


# Formato del archivo portable para Windows.
#
# El .exe final empieza como un lanzador nativo pequeño y termina con un ZIP
# (runtime + datos) y este pie. El lanzador sólo lee el ZIP; el proceso Python
# lo vuelve a escribir al cerrar, por lo que el mismo archivo puede viajar con
# sus juegos, imágenes e historial, como una presentación de PowerPoint.
PORTABLE_MAGIC = b"QUIZSTUDIO_PORTABLE_V1"
PORTABLE_MAGIC_SIZE = 32
PORTABLE_FOOTER_SIZE = PORTABLE_MAGIC_SIZE + 8 + 32


def _portable_context() -> Optional[tuple[Path, Path]]:
    """Devuelve (carpeta temporal del paquete, .exe portable) si aplica."""
    raw_root = os.environ.get("QUIZ_STUDIO_PORTABLE_BUNDLE", "").strip()
    raw_container = os.environ.get("QUIZ_STUDIO_PORTABLE_CONTAINER", "").strip()
    if not raw_root or not raw_container or not sys.platform.startswith("win"):
        return None
    root, container = Path(raw_root), Path(raw_container)
    if not root.is_dir() or not container.is_file() or not (root / "runtime").is_dir():
        return None
    return root, container


def _portable_payload_start(container: Path) -> int:
    """Lee y valida el pie del contenedor portable sin cargarlo en memoria."""
    size = container.stat().st_size
    if size < PORTABLE_FOOTER_SIZE:
        raise OSError("El archivo portable no tiene un paquete válido.")
    with container.open("rb") as source:
        source.seek(size - PORTABLE_FOOTER_SIZE)
        footer = source.read(PORTABLE_FOOTER_SIZE)
    magic = footer[:PORTABLE_MAGIC_SIZE]
    expected_magic = PORTABLE_MAGIC.ljust(PORTABLE_MAGIC_SIZE, b"\0")
    if magic != expected_magic:
        raise OSError("No se reconoce el formato del archivo portable.")
    payload_size = struct.unpack("<Q", footer[PORTABLE_MAGIC_SIZE : PORTABLE_MAGIC_SIZE + 8])[0]
    start = size - PORTABLE_FOOTER_SIZE - payload_size
    if payload_size <= 0 or start <= 0:
        raise OSError("El paquete portable está incompleto.")
    return start


def _sha256(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def _create_portable_payload(root: Path, destination: Path) -> None:
    """Empaqueta sólo runtime y data, excluyendo cualquier temporal externo."""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for directory_name in ("runtime", "data"):
            directory = root / directory_name
            if not directory.is_dir():
                continue
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(root).as_posix())


def _save_portable_copy(root: Path, container: Path) -> None:
    """Actualiza atómicamente el .exe que abrió la persona.

    El lanzador termina antes de abrir la aplicación interior, de modo que el
    archivo no está bloqueado. Si algo falla, se conserva el archivo previo.
    """
    payload_path = container.parent / f".{container.name}.{uuid.uuid4().hex}.zip"
    replacement_path = container.parent / f".{container.name}.{uuid.uuid4().hex}.tmp"
    try:
        _create_portable_payload(root, payload_path)
        payload_start = _portable_payload_start(container)
        footer = (
            PORTABLE_MAGIC.ljust(PORTABLE_MAGIC_SIZE, b"\0")
            + struct.pack("<Q", payload_path.stat().st_size)
            + _sha256(payload_path)
        )
        with container.open("rb") as source, replacement_path.open("wb") as destination:
            remaining = payload_start
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise OSError("No se pudo leer el lanzador portable.")
                destination.write(chunk)
                remaining -= len(chunk)
            with payload_path.open("rb") as payload:
                shutil.copyfileobj(payload, destination, 1024 * 1024)
            destination.write(footer)
            destination.flush()
            os.fsync(destination.fileno())
        # El lanzador ya pidió terminar, pero Windows puede conservar su handle
        # durante unas milésimas. Reintentamos antes de informar un error.
        last_error: Optional[OSError] = None
        for _attempt in range(12):
            try:
                os.replace(replacement_path, container)
                last_error = None
                break
            except OSError as exc:
                last_error = exc
                time.sleep(0.18)
        if last_error is not None:
            raise last_error
    finally:
        for temporary in (payload_path, replacement_path):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _schedule_portable_cleanup(root: Path) -> None:
    """El runtime ya cerró: elimina su copia temporal después de unos segundos."""
    if not sys.platform.startswith("win") or not root.name.startswith("QuizStudioPortable-"):
        return
    command = f'ping 127.0.0.1 -n 3 > nul & rmdir /s /q "{root}"'
    try:
        subprocess.Popen(["cmd.exe", "/c", command], creationflags=0x08000000)
    except OSError:
        pass


def format_date(value: str) -> str:
    if not value:
        return "Sin finalizar"
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y · %H:%M")
    except ValueError:
        return value


def short_text(value: str, limit: int) -> str:
    return textwrap.shorten(value or "", width=limit, placeholder="…")


class ScrollableFrame(tk.Frame):
    """Lienzo desplazable con la misma superficie oscura que el resto de la app."""

    def __init__(self, parent: tk.Widget, background: str = BG) -> None:
        super().__init__(parent, bg=background)
        self.canvas = tk.Canvas(self, bg=background, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview, bg=PANEL, activebackground=STROKE_LIGHT, troughcolor=background, highlightthickness=0, bd=0)
        self.body = tk.Frame(self.canvas, bg=background)
        self.window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.body.bind("<Configure>", self._refresh)
        self.canvas.bind("<Configure>", self._fit_width)
        self.canvas.bind_all("<MouseWheel>", self._wheel, add="+")

    def _refresh(self, _event: tk.Event) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def _fit_width(self, event: tk.Event) -> None:
        try:
            self.canvas.itemconfigure(self.window, width=event.width)
        except tk.TclError:
            pass

    def _wheel(self, event: tk.Event) -> None:
        try:
            if self.winfo_ismapped():
                self.canvas.yview_scroll(int(-event.delta / 90), "units")
        except tk.TclError:
            pass


class PaintedLabel(tk.Canvas):
    """Texto pintado en Canvas para evitar el renderer nativo defectuoso de Tk 8.5 en macOS.

    El Tk que acompaña a Python 3.9 en macOS ignora colores de ``Label`` en
    modo oscuro. Canvas sí respeta los colores; este widget conserva la API
    práctica de Label que usa el resto de la interfaz.
    """

    def __init__(self, parent: tk.Widget, text: str, *, font: tuple[Any, ...], fg: str, bg: str, **kwargs: Any) -> None:
        self._text = text
        self._font_spec = font
        self._fg = fg
        self._anchor = kwargs.pop("anchor", "center")
        self._justify = kwargs.pop("justify", "center")
        self._wraplength = int(kwargs.pop("wraplength", 0) or 0)
        self._padx = int(kwargs.pop("padx", 0) or 0)
        self._pady = int(kwargs.pop("pady", 0) or 0)
        self._char_width = kwargs.pop("width", None)
        self._line_count = kwargs.pop("height", None)
        self._background = bg
        self._font = tkfont.Font(parent, font=font)
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, takefocus=0, **kwargs)
        self._item = self.create_text(0, 0, text=text, font=self._font, fill=fg)
        self.bind("<Configure>", lambda _event: self._draw())
        self._resize()

    def _resize(self) -> None:
        line_height = self._font.metrics("linespace")
        content_width = max((self._font.measure(line) for line in self._text.splitlines() or [""]), default=0)
        if self._wraplength:
            content_width = min(max(content_width, 1), self._wraplength)
        if self._char_width is not None:
            content_width = max(content_width, self._font.measure("0") * int(self._char_width))
        if self._line_count is not None:
            content_height = line_height * int(self._line_count)
        elif self._wraplength:
            estimated_lines = max(1, (max(content_width, self._font.measure(self._text or " ")) + self._wraplength - 1) // self._wraplength)
            content_height = line_height * estimated_lines
        else:
            content_height = line_height * max(1, len(self._text.splitlines()))
        super().configure(width=content_width + self._padx * 2, height=content_height + self._pady * 2)
        self._draw()

    def _draw(self) -> None:
        width = max(self.winfo_width(), self.winfo_reqwidth())
        height = max(self.winfo_height(), self.winfo_reqheight())
        horizontal = self._anchor.lower()
        if horizontal in {"w", "sw", "nw"}:
            x, anchor = self._padx, "w"
        elif horizontal in {"e", "se", "ne"}:
            x, anchor = width - self._padx, "e"
        else:
            x, anchor = width / 2, "center"
        self.coords(self._item, x, height / 2)
        self.itemconfigure(self._item, text=self._text, font=self._font, fill=self._fg, anchor=anchor, justify=self._justify, width=max(0, self._wraplength))

    def configure(self, cnf: Any = None, **kwargs: Any) -> Any:  # type: ignore[override]
        options = dict(cnf or {})
        options.update(kwargs)
        if "text" in options:
            self._text = str(options.pop("text"))
        if "fg" in options:
            self._fg = str(options.pop("fg"))
        if "foreground" in options:
            self._fg = str(options.pop("foreground"))
        if "font" in options:
            self._font_spec = options.pop("font")
            self._font.configure(font=self._font_spec)
        if "bg" in options:
            self._background = str(options.pop("bg"))
            options["bg"] = self._background
        if "background" in options:
            self._background = str(options.pop("background"))
            options["bg"] = self._background
        if "anchor" in options:
            self._anchor = str(options.pop("anchor"))
        if "justify" in options:
            self._justify = str(options.pop("justify"))
        if "wraplength" in options:
            self._wraplength = int(options.pop("wraplength") or 0)
        if "padx" in options:
            self._padx = int(options.pop("padx") or 0)
        if "pady" in options:
            self._pady = int(options.pop("pady") or 0)
        if "width" in options:
            self._char_width = options.pop("width")
        if "height" in options:
            self._line_count = options.pop("height")
        result = super().configure(**options) if options else None
        if hasattr(self, "_item"):
            self._resize()
        return result

    config = configure


class PaintedButton(tk.Canvas):
    """Botón pintado, estable y visualmente consistente en macOS y Windows."""

    def __init__(self, parent: tk.Widget, *, text: str, command: Callable[[], None], bg: str, fg: str, activebackground: str, activeforeground: str, disabledforeground: str, highlightbackground: str, highlightthickness: int, font: tuple[Any, ...], padx: int, pady: int, state: str = "normal", width: int | None = None, cursor: str = "", anchor: str = "center", **kwargs: Any) -> None:
        self._text, self._command = text, command
        self._fill, self._fg = bg, fg
        self._active_fill, self._active_fg = activebackground, activeforeground
        self._disabled_fg = disabledforeground
        self._border, self._border_width = highlightbackground, highlightthickness
        self._font = tkfont.Font(parent, font=font)
        self._padx, self._pady, self._state = padx, pady, state
        self._char_width = width
        self._anchor = anchor
        self._hover = False
        super().__init__(parent, bg=parent.cget("bg"), highlightthickness=0, bd=0, takefocus=0, cursor=cursor or "arrow", **kwargs)
        self._shape = self.create_rectangle(0, 0, 0, 0, outline=self._border, width=self._border_width)
        self._label = self.create_text(0, 0, text=text, font=self._font, fill=fg, anchor="center")
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self._resize()

    def _resize(self) -> None:
        content_width = self._font.measure(self._text or " ")
        if self._char_width is not None:
            content_width = max(content_width, self._font.measure("0") * int(self._char_width))
        super().configure(width=content_width + self._padx * 2 + self._border_width * 2, height=self._font.metrics("linespace") + self._pady * 2 + self._border_width * 2)
        self._draw()

    def _draw(self) -> None:
        width, height = max(self.winfo_width(), self.winfo_reqwidth()), max(self.winfo_height(), self.winfo_reqheight())
        enabled = self._state == "normal"
        fill = self._active_fill if enabled and self._hover else self._fill
        foreground = self._active_fg if enabled and self._hover else self._fg if enabled else self._disabled_fg
        self.coords(self._shape, 0.5, 0.5, width - 0.5, height - 0.5)
        self.itemconfigure(self._shape, fill=fill, outline=self._border, width=self._border_width)
        if self._anchor in {"w", "sw", "nw"}:
            x, anchor = self._padx + self._border_width, "w"
        elif self._anchor in {"e", "se", "ne"}:
            x, anchor = width - self._padx - self._border_width, "e"
        else:
            x, anchor = width / 2, "center"
        self.coords(self._label, x, height / 2)
        self.itemconfigure(self._label, text=self._text, font=self._font, fill=foreground, anchor=anchor)

    def _enter(self, _event: tk.Event) -> None:
        if self._state == "normal":
            self._hover = True
            self._draw()

    def _leave(self, _event: tk.Event) -> None:
        self._hover = False
        self._draw()

    def _click(self, _event: tk.Event) -> None:
        if self._state == "normal":
            self._command()

    def configure(self, cnf: Any = None, **kwargs: Any) -> Any:  # type: ignore[override]
        options = dict(cnf or {})
        options.update(kwargs)
        for key, attribute in (("text", "_text"), ("bg", "_fill"), ("fg", "_fg"), ("activebackground", "_active_fill"), ("activeforeground", "_active_fg"), ("disabledforeground", "_disabled_fg"), ("highlightbackground", "_border"), ("highlightthickness", "_border_width"), ("state", "_state"), ("padx", "_padx"), ("pady", "_pady")):
            if key in options:
                setattr(self, attribute, options.pop(key))
        if "font" in options:
            self._font.configure(font=options.pop("font"))
        if "width" in options:
            self._char_width = options.pop("width")
        if "anchor" in options:
            self._anchor = str(options.pop("anchor"))
        options.pop("relief", None)
        options.pop("bd", None)
        options.pop("cursor", None)
        result = super().configure(**options) if options else None
        if hasattr(self, "_shape"):
            self._resize()
        return result

    config = configure


class UI:
    """Fábrica de widgets oscuros reutilizables."""

    # Se restablece para administración y se personaliza durante una partida.
    # Tk aplica una alternativa del sistema si la familia elegida no existe.
    font_family = FONT

    @staticmethod
    def frame(parent: tk.Widget, background: str = PANEL, border: str = STROKE, padding: int = 0) -> tk.Frame:
        return tk.Frame(parent, bg=background, highlightbackground=border, highlightthickness=1, bd=0, padx=padding, pady=padding)

    @staticmethod
    def label(parent: tk.Widget, text: str, *, size: int = 12, weight: str = "normal", fg: str = TEXT, bg: str | None = None, **kwargs: Any) -> PaintedLabel:
        widget_font = kwargs.pop("font", (UI.font_family, size, weight))
        return PaintedLabel(parent, text=text, bg=bg or parent.cget("bg"), fg=fg, font=widget_font, **kwargs)

    @staticmethod
    def button(parent: tk.Widget, text: str, command: Callable[[], None], *, variant: str = "quiet", size: str = "normal", width: int | None = None, state: str = "normal") -> PaintedButton:
        colors = {
            "primary": (PRIMARY, "#FFFFFF", PRIMARY_ACTIVE, "#FFFFFF", PRIMARY_ACTIVE),
            "quiet": ("#111C2C", "#E8EFFF", "#1D2B40", "#FFFFFF", STROKE_LIGHT),
            "danger": ("#42232C", "#FFC7CF", "#5B2935", "#FFFFFF", "#A2485D"),
            "mint": ("#164C47", "#C9FFEF", "#1B6A62", "#FFFFFF", "#2BBFA2"),
            "bare": (parent.cget("bg"), MUTED, parent.cget("bg"), TEXT, parent.cget("bg")),
        }
        bg, fg, active_bg, active_fg, border = colors[variant]
        padding = (18, 10) if size == "normal" else (23, 14)
        if size == "small":
            padding = (11, 7)
        elif size == "tiny":
            padding = (5, 3)
        options = {
            "text": text,
            "command": command,
            "state": state,
            "bg": bg,
            "fg": fg,
            "activebackground": active_bg,
            "activeforeground": active_fg,
            "disabledforeground": "#65758D",
            "highlightbackground": border,
            "highlightthickness": 1 if variant != "bare" else 0,
            "relief": "flat",
            "bd": 0,
            "font": (UI.font_family, 13 if size == "large" else 10 if size == "small" else 8 if size == "tiny" else 11, "bold"),
            "padx": padding[0],
            "pady": padding[1],
            "cursor": "hand2" if state == "normal" else "",
        }
        if width is not None:
            options["width"] = width
        return PaintedButton(parent, **options)

    @staticmethod
    def entry(parent: tk.Widget, variable: tk.StringVar, *, width: int | None = None, font_size: int = 11) -> tk.Entry:
        return tk.Entry(parent, textvariable=variable, width=width, bg=INPUT, fg=TEXT, insertbackground=TEXT, selectbackground="#324A78", selectforeground=TEXT, relief="flat", highlightbackground=STROKE_LIGHT, highlightcolor=PRIMARY, highlightthickness=1, font=(UI.font_family, font_size))

    @staticmethod
    def text(parent: tk.Widget, *, height: int, font_size: int = 11) -> tk.Text:
        return tk.Text(parent, height=height, bg=INPUT, fg=TEXT, insertbackground=TEXT, selectbackground="#324A78", selectforeground=TEXT, relief="flat", highlightbackground=STROKE_LIGHT, highlightcolor=PRIMARY, highlightthickness=1, font=(UI.font_family, font_size), wrap="word", padx=12, pady=10)


class BaseDialog(tk.Toplevel):
    """Diálogo de superficie oscura que evita los messageboxes nativos."""

    def __init__(self, parent: tk.Widget, title: str, geometry: str, *, modal: bool = True) -> None:
        super().__init__(parent)
        self.title(title)
        self.geometry(geometry)
        self.configure(bg=BG)
        self.transient(parent)
        self.resizable(False, False)
        if modal:
            self.grab_set()

    def close_button(self, parent: tk.Widget, command: Callable[[], None] | None = None) -> tk.Button:
        return UI.button(parent, "×", command or self.destroy, variant="quiet", size="small", width=2)


class ConfirmDialog(BaseDialog):
    def __init__(self, parent: tk.Widget, *, title: str, message: str, confirm_label: str, on_confirm: Callable[[], None], variant: str = "primary", icon: str = "✓", cancel_label: str | None = "Cancelar") -> None:
        super().__init__(parent, title, "540x330")
        card = UI.frame(self, PANEL, STROKE_LIGHT)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        UI.label(card, icon, size=28, weight="bold", fg=AMBER, bg="#263854", width=3, height=2).pack(pady=(25, 14))
        UI.label(card, title, size=23, weight="bold", anchor="center").pack(fill="x", padx=24)
        UI.label(card, message, size=12, fg="#B4C2D7", anchor="center", justify="center", wraplength=410).pack(fill="x", padx=38, pady=(12, 22))
        actions = tk.Frame(card, bg=PANEL)
        actions.pack()
        if cancel_label:
            UI.button(actions, cancel_label, self.destroy, variant="quiet", size="normal").pack(side="left", padx=5)

        def confirm() -> None:
            self.destroy()
            on_confirm()

        UI.button(actions, confirm_label, confirm, variant=variant, size="normal").pack(side="left", padx=5)


class QuizApp(tk.Tk):
    """Biblioteca, editor y experiencia de juego de Quiz Studio."""

    def __init__(self) -> None:
        super().__init__()
        UI.font_family = FONT
        self.store = GameStore()
        self._photos: list[Any] = []
        self.title("Quiz Studio")
        self.geometry("1360x820")
        self.minsize(1120, 680)
        self.configure(bg=BG)
        self.bind("<F11>", lambda _event: self.toggle_fullscreen())
        self.bind("<Escape>", lambda _event: self.attributes("-fullscreen", False))
        self.show_library()

    def safe_color(self, candidate: str, fallback: str) -> str:
        try:
            self.winfo_rgb(candidate)
            return candidate
        except tk.TclError:
            return fallback

    def toggle_fullscreen(self) -> None:
        self.attributes("-fullscreen", not bool(self.attributes("-fullscreen")))

    def clear_window(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        self._photos.clear()

    def admin_shell(self, selected: str) -> tk.Frame:
        UI.font_family = FONT
        self.clear_window()
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True)
        sidebar = tk.Frame(root, bg=SIDEBAR, width=245, highlightbackground="#273448", highlightthickness=1)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=SIDEBAR)
        brand.pack(fill="x", padx=27, pady=(34, 42))
        UI.label(brand, "Q", size=18, weight="bold", bg=PRIMARY, fg="white", width=2, height=1).pack(side="left")
        brand_words = tk.Frame(brand, bg=SIDEBAR)
        brand_words.pack(side="left", padx=12)
        UI.label(brand_words, "QUIZ STUDIO", size=16, weight="bold", bg=SIDEBAR).pack(anchor="w")
        UI.label(brand_words, "GAME CREATOR", size=8, fg="#9CAAC7", bg=SIDEBAR).pack(anchor="w", pady=(3, 0))
        self._nav_button(sidebar, "▣  Mis juegos", selected == "games", self.show_library).pack(fill="x", padx=20, pady=4)
        self._nav_button(sidebar, "◷  Historial", selected == "history", self.show_history).pack(fill="x", padx=20, pady=4)
        helper = UI.frame(sidebar, "#111C2F", "#2A3850")
        helper.pack(side="bottom", fill="x", padx=20, pady=(0, 14))
        UI.label(helper, "ⓘ  Tus trivias, a tu estilo", size=11, weight="bold", bg="#111C2F").pack(anchor="w", padx=15, pady=(14, 4))
        UI.label(helper, "Crea juegos, personaliza sus\ncolores y conserva cada partida.", size=10, fg="#9EACC3", bg="#111C2F", justify="left").pack(anchor="w", padx=15, pady=(0, 14))
        footer = tk.Frame(sidebar, bg=SIDEBAR)
        footer.pack(side="bottom", fill="x", padx=28, pady=(0, 24))
        UI.label(footer, "Pantalla completa", size=9, fg="#7589A8", bg=SIDEBAR).pack(side="left")
        UI.label(footer, "F11", size=9, fg="#B5C6E3", bg="#1B293C", padx=6, pady=2).pack(side="right")
        workspace = tk.Frame(root, bg=BG)
        workspace.pack(side="left", fill="both", expand=True)
        return workspace

    def _nav_button(self, parent: tk.Widget, label: str, active: bool, command: Callable[[], None]) -> tk.Button:
        button = UI.button(parent, label, command, variant="quiet", size="normal")
        button.configure(anchor="w", bg="#29345C" if active else SIDEBAR, fg="white" if active else "#9BADC6", activebackground="#29345C", activeforeground="white", highlightbackground="#384678" if active else SIDEBAR, highlightthickness=1 if active else 0, font=(FONT, 11, "bold"), padx=16, pady=14)
        return button

    def page_header(self, parent: tk.Widget, kicker: str, title: str, detail: str, action: tk.Widget | None = None) -> tk.Frame:
        header = tk.Frame(parent, bg=BG)
        header.pack(fill="x", padx=46, pady=(36, 27))
        labels = tk.Frame(header, bg=BG)
        labels.pack(side="left")
        UI.label(labels, kicker.upper(), size=9, weight="bold", fg="#7188AB", bg=BG).pack(anchor="w")
        UI.label(labels, title, size=31, weight="bold", bg=BG).pack(anchor="w", pady=(7, 2))
        UI.label(labels, detail, size=12, fg="#9BABBE", bg=BG).pack(anchor="w")
        if action:
            action.pack(side="right", pady=13)
        return header

    def show_library(self) -> None:
        content = self.admin_shell("games")
        action = UI.button(content, "+  Crear juego", self.create_game, variant="primary", size="large")
        self.page_header(content, "Biblioteca", "Mis juegos", "Crea una trivia para cada ocasión y vuelve a jugarla cuando quieras.", action)
        games = self.store.list_games()
        scroll = ScrollableFrame(content, BG)
        scroll.pack(fill="both", expand=True, padx=(38, 29), pady=(0, 26))
        body = scroll.body
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform="games")
        if not games:
            self._empty_games(body)
            return
        for index, game in enumerate(games):
            self._game_card(body, game).grid(row=index // 3, column=index % 3, sticky="nsew", padx=10, pady=10)

    def _empty_games(self, parent: tk.Widget) -> None:
        empty = UI.frame(parent, "#0D1727", "#2C4262")
        empty.pack(fill="x", padx=190, pady=85, ipady=65)
        UI.label(empty, "▣", size=34, fg="#94A4FF", bg="#23375C", width=3, height=2).pack(pady=(5, 14))
        UI.label(empty, "Aún no hay juegos", size=25, weight="bold", bg="#0D1727").pack()
        UI.label(empty, "Crea el primero para empezar a diseñar tus preguntas, equipos y\nestilo de juego.", size=12, fg="#9FB2D1", bg="#0D1727", justify="center").pack(pady=(11, 22))
        UI.button(empty, "+  Crear mi primer juego", self.create_game, variant="primary", size="large").pack()

    def _game_card(self, parent: tk.Widget, game: dict[str, Any]) -> tk.Frame:
        color = self.safe_color(game.get("background_color", "#304EA6"), "#304EA6")
        card = UI.frame(parent, "#111C2E", "#2C3D55")
        card.configure(height=315)
        card.grid_propagate(False)
        art = tk.Frame(card, bg=color, height=142)
        art.pack(fill="x")
        art.pack_propagate(False)
        category_name = next((category.get("name") for category in game.get("categories", []) if category.get("name")), "TRIVIA")
        UI.label(art, category_name.upper(), size=8, weight="bold", bg="#0A111F", fg="#E4EBFF", padx=10, pady=6).place(x=20, y=18)
        UI.label(art, short_text(game.get("title", "Juego de preguntas"), 34), size=20, weight="bold", bg=color, fg="white", justify="left", wraplength=255).place(x=20, y=67)
        UI.label(art, "✦", size=44, weight="bold", bg=color, fg="#FFFFFF", anchor="center").place(relx=0.74, y=24, width=82, height=82)
        body = tk.Frame(card, bg="#111C2E")
        body.pack(fill="both", expand=True, padx=18, pady=14)
        UI.label(body, game.get("name", "Juego"), size=10, weight="bold", fg="#AAB8D0", bg="#111C2E").pack(anchor="w")
        count = sum(len(category.get("questions", [])) for category in game.get("categories", []))
        meta = tk.Frame(body, bg="#111C2E")
        meta.pack(fill="x", pady=(10, 12))
        UI.label(meta, f"{len(game.get('categories', []))} categorías · {count} preguntas", size=9, fg="#8497B5", bg="#111C2E").pack(side="left")
        UI.label(meta, f"◷ {format_date(game.get('updated_at', ''))}", size=9, fg="#8497B5", bg="#111C2E").pack(side="right")
        actions = tk.Frame(body, bg="#111C2E")
        actions.pack(fill="x")
        UI.button(actions, "✎  Editar", lambda item=game: self.edit_game(item), variant="quiet", size="small").pack(side="left")
        UI.button(actions, "▶  Jugar", lambda item=game: self.prepare_session(item), variant="primary", size="small").pack(side="left", padx=8, fill="x", expand=True)
        UI.button(actions, "⋯", lambda item=game: self.open_game_menu(item), variant="quiet", size="small", width=2).pack(side="right")
        return card

    def open_game_menu(self, game: dict[str, Any]) -> None:
        menu = BaseDialog(self, game.get("name", "Juego"), "300x220")
        box = UI.frame(menu, PANEL_2, "#56688E")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        UI.button(box, "▣  Duplicar juego", lambda: (self.store.duplicate_game(game["id"]), menu.destroy(), self.show_library()), variant="bare", size="small").pack(fill="x", padx=5, pady=3)
        UI.button(box, "◷  Ver historial de este juego", lambda: (menu.destroy(), HistoryDialog(self, game["id"])), variant="bare", size="small").pack(fill="x", padx=5, pady=3)
        tk.Frame(box, bg=STROKE, height=1).pack(fill="x", padx=10, pady=4)
        delete = UI.button(box, "⌫  Eliminar juego", lambda: (menu.destroy(), self.confirm_delete_game(game)), variant="bare", size="small")
        delete.configure(fg="#FF9CAC", activeforeground="#FFC7CF")
        delete.pack(fill="x", padx=5, pady=3)

    def confirm_delete_game(self, game: dict[str, Any]) -> None:
        ConfirmDialog(self, title="Eliminar juego", message=f"¿Eliminar “{game.get('name', 'este juego')}”? El historial se conservará.", confirm_label="Eliminar juego", on_confirm=lambda: (self.store.delete_game(game["id"]), self.show_library()), variant="danger", icon="⌫")

    def create_game(self) -> None:
        GameEditor(self, self.store.blank_game(), is_new=True)

    def edit_game(self, game: dict[str, Any]) -> None:
        GameEditor(self, self.store.get_game(game["id"]) or game, is_new=False)

    def show_history(self) -> None:
        content = self.admin_shell("history")
        filter_chip = UI.label(content, "⌄  Todos los juegos", size=10, weight="bold", fg="#C8D7EB", bg="#1B2940", padx=13, pady=8)
        self.page_header(content, "Partidas guardadas", "Historial de partidas", "Resultados guardados de todos tus juegos.", filter_chip)
        scroll = ScrollableFrame(content, BG)
        scroll.pack(fill="both", expand=True, padx=(38, 29), pady=(0, 26))
        sessions = self.store.list_sessions()
        if not sessions:
            self._empty_history(scroll.body)
            return
        for session in sessions:
            self._history_card(scroll.body, session, modal=False).pack(fill="x", padx=8, pady=8)

    def _empty_history(self, parent: tk.Widget) -> None:
        empty = UI.frame(parent, "#0D1727", "#2C4262")
        empty.pack(fill="x", padx=190, pady=70, ipady=65)
        UI.label(empty, "◷", size=34, fg="#94A4FF", bg="#23375C", width=3, height=2).pack(pady=(5, 14))
        UI.label(empty, "Todavía no hay partidas", size=25, weight="bold", bg="#0D1727").pack()
        UI.label(empty, "Al iniciar un juego, su progreso y resultado aparecerán aquí.", size=12, fg="#9FB2D1", bg="#0D1727").pack(pady=(11, 22))
        UI.button(empty, "←  Ir a Mis juegos", self.show_library, variant="primary", size="large").pack()

    def _history_card(self, parent: tk.Widget, session: dict[str, Any], *, modal: bool) -> tk.Frame:
        snapshot = session.get("game_snapshot", {})
        cover = self.safe_color(snapshot.get("background_color", "#273F78"), "#273F78")
        row = UI.frame(parent, "#111D31", "#2C405C")
        pad = 11 if modal else 17
        row.configure(padx=pad, pady=pad)
        art = tk.Frame(row, bg=cover, width=74 if modal else 92, height=74 if modal else 88)
        art.pack(side="left", padx=(0, 16), fill="y")
        art.pack_propagate(False)
        UI.label(art, "▣", size=20, weight="bold", bg=cover, fg="#DDE6FF").place(relx=0.5, rely=0.5, anchor="center")
        details = tk.Frame(row, bg="#111D31")
        details.pack(side="left", fill="x", expand=True)
        active = session.get("status") == "en curso"
        chip_bg, chip_fg = ("#3E3322", "#FFD27F") if active else ("#123B34", "#66EFB9")
        UI.label(details, "◷  EN CURSO" if active else "✓  FINALIZADA", size=9, weight="bold", fg=chip_fg, bg=chip_bg, padx=9, pady=5).pack(anchor="w")
        UI.label(details, session.get("game_title", "Juego de preguntas"), size=15 if not modal else 12, weight="bold", bg="#111D31").pack(anchor="w", pady=(7, 1))
        UI.label(details, format_date(session.get("started_at", "")), size=9, fg="#90A3C0", bg="#111D31").pack(anchor="w")
        if modal:
            UI.label(details, f"{len(session.get('used_cards', []))} cartas usadas", size=9, fg="#90A3C0", bg="#111D31").pack(anchor="w", pady=(4, 0))
        scores = tk.Frame(row, bg="#111D31")
        scores.pack(side="left", padx=15)
        teams = session.get("teams", [])
        score_text = "   ".join(f"{short_text(team.get('name', 'Equipo'), 12)}  {team.get('score', 0)}" for team in teams)
        UI.label(scores, score_text, size=12 if modal else 15, weight="bold", bg="#111D31", justify="left", wraplength=320).pack()
        if not modal:
            outcome = f"Empate: {session.get('winner')}" if "," in session.get("winner", "") else f"Ganador: {session.get('winner')}"
            if active:
                outcome = "Partida en progreso"
            result = UI.frame(row, "#3A3025" if active else "#123B34", "#6A5434" if active else "#2D6C5A")
            result.pack(side="right", padx=(12, 0))
            UI.label(result, "Estado" if active else "Resultado", size=8, fg="#A9D7C7" if not active else "#D9C795", bg=result.cget("bg")).pack(padx=18, pady=(10, 2))
            UI.label(result, outcome, size=10, weight="bold", fg="#FFD27F" if active else "#9AF2D2", bg=result.cget("bg")).pack(padx=18, pady=(0, 10))
        return row

    def prepare_session(self, game: dict[str, Any]) -> None:
        if not any(category.get("questions") for category in game.get("categories", [])):
            ConfirmDialog(self, title="Juego vacío", message="Añade al menos una pregunta antes de iniciar una partida.", confirm_label="Entendido", on_confirm=lambda: None, icon="⚠", cancel_label=None)
            return
        TeamSetupDialog(self, game)

    def launch_session(self, game: dict[str, Any], teams: list[dict[str, Any]]) -> None:
        GameSession(self, game, self.store.start_session(game, teams)).show_board()


class GameEditor(BaseDialog):
    """Editor de identidad, equipos y contenido con la navegación de los mockups."""

    def __init__(self, app: QuizApp, game: dict[str, Any], is_new: bool) -> None:
        super().__init__(app, "Nuevo juego" if is_new else "Configuración del juego", "1280x800")
        UI.font_family = FONT
        self.app, self.store = app, app.store
        self.game = copy.deepcopy(game)
        self.is_new = is_new
        self.current_tab = "identity"
        self.selected_category_id: str | None = None
        self.dirty = False
        self._preview_photo: Any | None = None
        self._team_data = copy.deepcopy(self.game.get("teams", []))
        self.name_var = tk.StringVar(value=self.game.get("name", ""))
        self.title_var = tk.StringVar(value=self.game.get("title", ""))
        self.background_var = tk.StringVar(value=self.game.get("background_color", "#0F1829"))
        self.background_image_var = tk.StringVar(value=self.game.get("background_image", ""))
        self.accent_var = tk.StringVar(value=self.game.get("accent_color", PRIMARY))
        self.text_var = tk.StringVar(value=self.game.get("text_color", "#F4F7FF"))
        self.card_var = tk.StringVar(value=self.game.get("card_color", "#25354F"))
        self.font_var = tk.StringVar(value=self.game.get("font_family", "Arial"))
        for variable in (self.name_var, self.title_var, self.background_var, self.background_image_var, self.accent_var, self.text_var, self.card_var, self.font_var):
            variable.trace_add("write", self._on_value_change)
        self.protocol("WM_DELETE_WINDOW", self.request_close)
        self._build()

    def _on_value_change(self, *_args: Any) -> None:
        self.dirty = True
        if self.current_tab == "identity":
            self.after_idle(self._refresh_preview)

    def _build(self) -> None:
        self.header = tk.Frame(self, bg=BG)
        self.header.pack(fill="x", padx=28, pady=(22, 13))
        UI.button(self.header, "←", self.request_close, variant="quiet", size="small", width=2).pack(side="left")
        title_box = tk.Frame(self.header, bg=BG)
        title_box.pack(side="left", padx=16)
        UI.label(title_box, "Nuevo juego" if self.is_new else "Configuración del juego", size=25, weight="bold", bg=BG).pack(anchor="w")
        UI.label(title_box, "Cambios sin guardar" if self.dirty else (self.game.get("name", "") if not self.is_new else "Define la identidad de tu trivia"), size=9, fg="#8296B5", bg=BG).pack(anchor="w", pady=(3, 0))
        UI.button(self.header, "✕  Cancelar", self.request_close, variant="quiet", size="small").pack(side="right")
        UI.button(self.header, "▣  Guardar juego", self.save, variant="primary", size="small").pack(side="right", padx=10)
        self.tab_bar = tk.Frame(self, bg=BG)
        self.tab_bar.pack(fill="x", padx=28)
        self._tab_button("identity", "◉  Identidad visual").pack(side="left", padx=(0, 8))
        self._tab_button("teams", "♧  Equipos").pack(side="left", padx=4)
        self._tab_button("questions", "☷  Categorías y preguntas").pack(side="left", padx=4)
        tk.Frame(self, bg="#28364D", height=1).pack(fill="x", padx=28, pady=(14, 0))
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True, padx=28, pady=(23, 22))
        self.render_tab()

    def _tab_button(self, name: str, label: str) -> tk.Button:
        active = name == self.current_tab
        button = UI.button(self.tab_bar, label, lambda: self.set_tab(name), variant="quiet", size="normal")
        button.configure(bg="#2A3256" if active else BG, fg="white" if active else "#98ABC7", activebackground="#2A3256", activeforeground="white", highlightbackground="#485A9C" if active else BG, highlightthickness=1 if active else 0, font=(FONT, 11, "bold"), padx=18, pady=12)
        return button

    def set_tab(self, name: str) -> None:
        self.current_tab = name
        for child in self.tab_bar.winfo_children():
            child.destroy()
        self._tab_button("identity", "◉  Identidad visual").pack(side="left", padx=(0, 8))
        self._tab_button("teams", "♧  Equipos").pack(side="left", padx=4)
        self._tab_button("questions", "☷  Categorías y preguntas").pack(side="left", padx=4)
        self.render_tab()

    def render_tab(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        if self.current_tab == "identity":
            self._identity_tab()
        elif self.current_tab == "teams":
            self._teams_tab()
        else:
            self._questions_tab()

    def _identity_tab(self) -> None:
        self.content.grid_columnconfigure(0, weight=11)
        self.content.grid_columnconfigure(1, weight=9)
        self.content.grid_rowconfigure(0, weight=1)
        left = UI.frame(self.content, PANEL, STROKE)
        right = UI.frame(self.content, PANEL, STROKE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 11))
        right.grid(row=0, column=1, sticky="nsew", padx=(11, 0))
        UI.label(left, "Información del juego", size=15, weight="bold", bg=PANEL).grid(row=0, column=0, columnspan=2, sticky="w", padx=25, pady=(25, 17))
        left.grid_columnconfigure((0, 1), weight=1)
        self._form_entry(left, "Nombre interno *", self.name_var, 1, 0)
        self._form_entry(left, "Título visible *", self.title_var, 1, 1)
        tk.Frame(left, bg=STROKE, height=1).grid(row=3, column=0, columnspan=2, sticky="ew", padx=25, pady=25)
        UI.label(left, "Personalización visual", size=15, weight="bold", bg=PANEL).grid(row=4, column=0, columnspan=2, sticky="w", padx=25, pady=(0, 8))
        self._color_field(left, "Color de fondo", self.background_var, 5, 0)
        self._color_field(left, "Color destacado", self.accent_var, 5, 1)
        self._color_field(left, "Color del texto", self.text_var, 7, 0)
        self._color_field(left, "Color de tarjetas", self.card_var, 7, 1)
        UI.label(left, "Tipografía", size=10, weight="bold", fg="#B7C4DA", bg=PANEL).grid(row=9, column=0, sticky="w", padx=25, pady=(20, 8))
        font_entry = UI.entry(left, self.font_var, width=22)
        font_entry.grid(row=10, column=0, sticky="ew", padx=25)
        font_entry.bind("<KeyRelease>", lambda _event: self._on_value_change())
        UI.label(left, "Imagen de fondo (opcional)", size=10, weight="bold", fg="#B7C4DA", bg=PANEL).grid(row=9, column=1, sticky="w", padx=25, pady=(20, 8))
        image_line = tk.Frame(left, bg=PANEL)
        image_line.grid(row=10, column=1, sticky="ew", padx=25)
        image_line.grid_columnconfigure(0, weight=1)
        image_entry = UI.entry(image_line, self.background_image_var)
        image_entry.grid(row=0, column=0, sticky="ew")
        UI.button(image_line, "Examinar", self.pick_background, variant="quiet", size="small").grid(row=0, column=1, padx=(7, 0))
        UI.button(image_line, "Quitar", lambda: self.background_image_var.set(""), variant="bare", size="small").grid(row=0, column=2, padx=(4, 0))
        UI.label(left, "Si no hay imagen, se utilizará el color de fondo del juego.", size=9, fg="#798EAB", bg=PANEL).grid(row=11, column=1, sticky="w", padx=25, pady=(8, 0))
        UI.label(right, "Vista previa del juego", size=15, weight="bold", bg=PANEL).pack(anchor="w", padx=25, pady=(25, 14))
        self.preview = tk.Frame(right, bg="#17263B", highlightbackground=STROKE_LIGHT, highlightthickness=1)
        self.preview.pack(fill="both", expand=True, padx=25, pady=(0, 14))
        UI.label(right, "Los cambios se reflejan mientras editas.", size=9, fg="#8498B7", bg=PANEL).pack(anchor="w", padx=25, pady=(0, 22))
        self._refresh_preview()

    def _form_entry(self, parent: tk.Widget, label: str, variable: tk.StringVar, row: int, column: int) -> None:
        UI.label(parent, label, size=10, weight="bold", fg="#B7C4DA", bg=PANEL).grid(row=row, column=column, sticky="w", padx=25, pady=(0, 8))
        entry = UI.entry(parent, variable)
        entry.grid(row=row + 1, column=column, sticky="ew", padx=25, pady=(0, 5))
        entry.bind("<KeyRelease>", lambda _event: self._on_value_change())

    def _color_field(self, parent: tk.Widget, label: str, variable: tk.StringVar, row: int, column: int) -> None:
        UI.label(parent, label, size=10, weight="bold", fg="#B7C4DA", bg=PANEL).grid(row=row, column=column, sticky="w", padx=25, pady=(13, 8))
        line = tk.Frame(parent, bg=PANEL)
        line.grid(row=row + 1, column=column, sticky="ew", padx=25)
        swatch = UI.label(line, "", bg=self.app.safe_color(variable.get(), PRIMARY), width=4, height=2)
        swatch.pack(side="left")
        entry = UI.entry(line, variable, width=13)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        UI.button(line, "◉", lambda: self.pick_color(variable), variant="quiet", size="small", width=2).pack(side="right")
        variable.trace_add("write", lambda *_args: swatch.configure(bg=self.app.safe_color(variable.get(), PRIMARY)))

    def _refresh_preview(self) -> None:
        if not hasattr(self, "preview") or not self.preview.winfo_exists():
            return
        for child in self.preview.winfo_children():
            child.destroy()
        bg = self.app.safe_color(self.background_var.get(), "#17263B")
        text = self.app.safe_color(self.text_var.get(), TEXT)
        accent = self.app.safe_color(self.accent_var.get(), PRIMARY)
        self.preview.configure(bg=bg)
        self._preview_photo = None
        image_path = self.background_image_var.get().strip()
        if image_path and PIL_AVAILABLE and Path(image_path).is_file():
            try:
                image = Image.open(image_path).convert("RGB")
                image = ImageOps.fit(image, (500, 420), method=Image.Resampling.LANCZOS)
                self._preview_photo = ImageTk.PhotoImage(image)
                image_label = tk.Label(self.preview, image=self._preview_photo, bd=0)
                image_label.place(x=0, y=0, relwidth=1, relheight=1)
                image_label.lower()
            except (OSError, ValueError):
                pass
        top = tk.Frame(self.preview, bg=bg)
        top.pack(fill="x", padx=17, pady=16)
        for team in self._team_data[:4]:
            UI.label(top, f"{short_text(team.get('name', 'Equipo'), 10)} 90", size=8, bg="#14243B", fg="#E5EEFF", padx=8, pady=6).pack(side="right", padx=3)
        preview_font = self.font_var.get().strip() or FONT
        UI.label(self.preview, self.title_var.get().upper() or "TÍTULO DEL JUEGO", size=18, weight="bold", fg=text, bg=bg, wraplength=380, font=(preview_font, 18, "bold")).pack(pady=(20, 14))
        board = tk.Frame(self.preview, bg=bg)
        board.pack(fill="x", padx=22)
        cats = self.game.get("categories", [])[:4] or [{"name": "Categoría"} for _ in range(4)]
        for category in cats:
            col = tk.Frame(board, bg=bg)
            col.pack(side="left", fill="both", expand=True, padx=4)
            UI.label(col, short_text(category.get("name", "Categoría"), 13), size=8, weight="bold", bg="#243650", fg=text, pady=10).pack(fill="x")
            for value in (50, 40, 30, 20):
                UI.label(col, str(value), size=10, weight="bold", bg=self.app.safe_color(self.card_var.get(), "#25354F"), fg=text, pady=8).pack(fill="x", pady=3)
        UI.label(self.preview, "Vista orientativa", size=8, fg=accent, bg=bg).pack(side="bottom", pady=13)

    def pick_color(self, variable: tk.StringVar) -> None:
        color = colorchooser.askcolor(color=variable.get(), parent=self)[1]
        if color:
            variable.set(color.upper())

    def pick_background(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Selecciona una imagen de fondo", filetypes=IMAGE_TYPES)
        if path:
            self.background_image_var.set(path)

    def _teams_tab(self) -> None:
        self.content.grid_columnconfigure(0, weight=8)
        self.content.grid_columnconfigure(1, weight=2)
        self.content.grid_rowconfigure(0, weight=1)
        left = UI.frame(self.content, PANEL, STROKE)
        right = UI.frame(self.content, PANEL, STROKE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        header = tk.Frame(left, bg=PANEL)
        header.pack(fill="x", padx=25, pady=(25, 10))
        labels = tk.Frame(header, bg=PANEL)
        labels.pack(side="left")
        UI.label(labels, "Equipos predeterminados", size=15, weight="bold", bg=PANEL).pack(anchor="w")
        UI.label(labels, "Puedes ajustar estos datos para cada nueva partida.", size=10, fg="#93A6C3", bg=PANEL).pack(anchor="w", pady=(4, 0))
        count = tk.Frame(header, bg=PANEL)
        count.pack(side="right")
        UI.label(count, "Cantidad", size=10, fg="#AABAD1", bg=PANEL).pack(side="left", padx=(0, 9))
        UI.button(count, "−", self.remove_team, variant="quiet", size="small", width=2).pack(side="left")
        UI.label(count, str(len(self._team_data)), size=15, weight="bold", bg=PANEL, padx=11).pack(side="left")
        UI.button(count, "+", self.add_team, variant="quiet", size="small", width=2).pack(side="left")
        table = tk.Frame(left, bg=PANEL)
        table.pack(fill="both", expand=True, padx=25, pady=(15, 14))
        UI.label(table, "Orden", size=9, fg="#8FA2BE", bg=PANEL).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 8))
        UI.label(table, "Nombre del equipo", size=9, fg="#8FA2BE", bg=PANEL).grid(row=0, column=1, sticky="w", padx=10, pady=(0, 8))
        UI.label(table, "Color asignado", size=9, fg="#8FA2BE", bg=PANEL).grid(row=0, column=2, columnspan=2, sticky="w", padx=10, pady=(0, 8))
        table.grid_columnconfigure(1, weight=1)
        for index, team in enumerate(self._team_data):
            UI.label(table, f"{index + 1:02}", size=10, bg="#15243A", fg="#9FB2D0", padx=8, pady=7).grid(row=index + 1, column=0, sticky="w", padx=4, pady=7)
            name_var = tk.StringVar(value=team.get("name", ""))
            entry = UI.entry(table, name_var)
            entry.grid(row=index + 1, column=1, sticky="ew", padx=10, pady=7)
            entry.bind("<KeyRelease>", lambda _event, i=index, var=name_var: self._set_team_name(i, var.get()))
            color = self.app.safe_color(team.get("color", TEAM_COLORS[index % len(TEAM_COLORS)]), TEAM_COLORS[index % len(TEAM_COLORS)])
            UI.label(table, "", bg=color, width=4, height=2).grid(row=index + 1, column=2, padx=(0, 8), pady=7)
            color_var = tk.StringVar(value=color)
            color_entry = UI.entry(table, color_var, width=12)
            color_entry.grid(row=index + 1, column=3, sticky="w", pady=7)
            color_entry.bind("<KeyRelease>", lambda _event, i=index, var=color_var: self._set_team_color(i, var.get()))
            UI.button(table, "◉", lambda i=index: self.pick_team_color(i), variant="quiet", size="small", width=2).grid(row=index + 1, column=4, padx=(8, 0), pady=7)
        add_line = tk.Frame(left, bg=PANEL)
        add_line.pack(fill="x", padx=25, pady=(0, 23))
        UI.button(add_line, "+  Agregar equipo", self.add_team, variant="quiet", size="small").pack(side="left")
        UI.label(add_line, "Mínimo 2 · Máximo 8 equipos", size=9, fg="#8195B3", bg=PANEL).pack(side="left", padx=13)
        UI.label(right, "Vista del marcador", size=14, weight="bold", bg=PANEL).pack(anchor="w", padx=22, pady=(25, 5))
        UI.label(right, "Ejemplo en una partida en vivo", size=9, fg="#91A3C0", bg=PANEL).pack(anchor="w", padx=22, pady=(0, 17))
        for index, team in enumerate(self._team_data):
            tile = UI.frame(right, "#17263B", self.app.safe_color(team.get("color", PRIMARY), PRIMARY))
            tile.pack(fill="x", padx=22, pady=6)
            UI.label(tile, f"●  {short_text(team.get('name', f'Equipo {index + 1}'), 15)}", size=10, bg="#17263B", fg="#DDE7FA").pack(side="left", padx=11, pady=13)
            UI.label(tile, str((index + 1) * 30), size=20, weight="bold", bg="#17263B").pack(side="right", padx=12)
        UI.label(right, "Los nombres y colores definidos aquí se usarán como base. No modifican los resultados anteriores.", size=9, fg="#91A3C0", bg=PANEL, wraplength=175, justify="left").pack(anchor="w", padx=22, pady=20)

    def _set_team_name(self, index: int, value: str) -> None:
        self._team_data[index]["name"] = value
        self.dirty = True

    def _set_team_color(self, index: int, value: str) -> None:
        self._team_data[index]["color"] = self.app.safe_color(value, TEAM_COLORS[index % len(TEAM_COLORS)])
        self.dirty = True

    def add_team(self) -> None:
        if len(self._team_data) >= 8:
            return
        index = len(self._team_data)
        self._team_data.append({"name": f"Equipo {index + 1}", "color": TEAM_COLORS[index % len(TEAM_COLORS)]})
        self.dirty = True
        self.render_tab()

    def remove_team(self) -> None:
        if len(self._team_data) <= 2:
            return
        self._team_data.pop()
        self.dirty = True
        self.render_tab()

    def pick_team_color(self, index: int) -> None:
        color = colorchooser.askcolor(color=self._team_data[index].get("color"), parent=self)[1]
        if color:
            self._team_data[index]["color"] = color.upper()
            self.dirty = True
            self.render_tab()

    def _questions_tab(self) -> None:
        self.content.grid_columnconfigure(0, minsize=285)
        self.content.grid_columnconfigure(1, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        left = UI.frame(self.content, PANEL, STROKE)
        right = UI.frame(self.content, PANEL, STROKE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        cat_head = tk.Frame(left, bg=PANEL)
        cat_head.pack(fill="x", padx=20, pady=(20, 9))
        UI.label(cat_head, "Categorías", size=15, weight="bold", bg=PANEL).pack(side="left")
        UI.button(cat_head, "+", self.add_category, variant="primary", size="small", width=2).pack(side="right")
        categories = self.game.get("categories", [])
        if not categories:
            self._category_empty(left)
            self._questions_empty(right, no_categories=True)
            return
        if not self.selected_category_id or not any(c.get("id") == self.selected_category_id for c in categories):
            self.selected_category_id = categories[0].get("id")
        UI.label(left, "Organiza el tablero por temas.", size=9, fg="#91A3C0", bg=PANEL).pack(anchor="w", padx=20, pady=(0, 9))
        list_box = tk.Frame(left, bg=PANEL)
        list_box.pack(fill="both", expand=True, padx=12)
        current = self.current_category()
        for category in categories:
            active = category.get("id") == self.selected_category_id
            row = UI.button(list_box, f"●   {short_text(category.get('name', 'Categoría'), 22)}                         {len(category.get('questions', []))}", lambda item=category: self.select_category(item), variant="quiet", size="normal")
            row.configure(anchor="w", bg="#29385F" if active else PANEL, fg="white" if active else "#BBCCE3", activebackground="#29385F", activeforeground="white", highlightbackground="#4E62A1" if active else PANEL, highlightthickness=1 if active else 0, font=(FONT, 10, "bold" if active else "normal"), padx=12, pady=13)
            row.pack(fill="x", pady=4)
        cat_actions = tk.Frame(left, bg=PANEL)
        cat_actions.pack(fill="x", padx=20, pady=20)
        UI.button(cat_actions, "✎  Editar", self.edit_category, variant="quiet", size="small").pack(side="left")
        delete_button = UI.button(cat_actions, "⌫  Eliminar", self.delete_category, variant="quiet", size="small")
        delete_button.configure(fg="#FFC7CF")
        delete_button.pack(side="right")
        if current and current.get("questions"):
            self._question_table(right, current)
        else:
            self._questions_empty(right, no_categories=False)

    def _category_empty(self, parent: tk.Widget) -> None:
        empty = UI.frame(parent, "#101B2C", "#2C4262")
        empty.pack(fill="x", padx=20, pady=42, ipady=22)
        UI.label(empty, "☷", size=23, fg="#94A4FF", bg="#23375C", width=3, height=2).pack(pady=(3, 8))
        UI.label(empty, "Sin categorías", size=16, weight="bold", bg="#101B2C").pack()
        UI.label(empty, "Crea la primera categoría.", size=9, fg="#92A5C2", bg="#101B2C").pack(pady=(6, 13))
        UI.button(empty, "+  Añadir", self.add_category, variant="primary", size="small").pack()

    def _questions_empty(self, parent: tk.Widget, *, no_categories: bool) -> None:
        empty = tk.Frame(parent, bg=PANEL)
        empty.pack(fill="both", expand=True)
        UI.label(empty, "▤" if no_categories else "▧", size=32, fg="#94A4FF", bg="#23375C", width=3, height=2).place(relx=0.5, rely=0.38, anchor="center")
        UI.label(empty, "Preguntas" if no_categories else "Sin preguntas", size=21, weight="bold", bg=PANEL).place(relx=0.5, rely=0.52, anchor="center")
        message = "Crea o selecciona una categoría primero." if no_categories else "Añade una pregunta para que esta categoría aparezca en el tablero."
        UI.label(empty, message, size=11, fg="#93A7C4", bg=PANEL, wraplength=410, justify="center").place(relx=0.5, rely=0.58, anchor="center")
        UI.button(empty, "+  Nueva pregunta", self.add_question, variant="primary" if not no_categories else "quiet", size="small", state="normal" if not no_categories else "disabled").place(relx=0.5, rely=0.68, anchor="center")

    def _question_table(self, parent: tk.Widget, category: dict[str, Any]) -> None:
        head = tk.Frame(parent, bg=PANEL)
        head.pack(fill="x", padx=24, pady=(21, 8))
        labels = tk.Frame(head, bg=PANEL)
        labels.pack(side="left")
        UI.label(labels, f"Preguntas · {category.get('name', 'Categoría')}", size=16, weight="bold", bg=PANEL).pack(anchor="w")
        UI.label(labels, f"{len(category.get('questions', []))} cartas ordenadas de mayor a menor puntaje", size=9, fg="#91A3C0", bg=PANEL).pack(anchor="w", pady=(4, 0))
        UI.button(head, "+  Nueva pregunta", self.add_question, variant="primary", size="small").pack(side="right", pady=3)
        table = tk.Frame(parent, bg=PANEL)
        table.pack(fill="both", expand=True, padx=24, pady=(8, 18))
        headers = ("VALOR", "PREGUNTA", "RESPUESTA", "ACCIONES")
        table.grid_columnconfigure(1, weight=6)
        table.grid_columnconfigure(2, weight=3)
        for index, header in enumerate(headers):
            UI.label(table, header, size=9, fg="#8DA1BE", bg=PANEL).grid(row=0, column=index, sticky="w", padx=10, pady=(2, 11))
        questions = sorted(category.get("questions", []), key=lambda item: item.get("value", 0), reverse=True)
        for index, question in enumerate(questions):
            row_bg = "#263650" if index == 0 else PANEL
            UI.label(table, str(question.get("value", "")), size=10, weight="bold", bg="#2B4164", fg="#E2EAFF", padx=11, pady=8).grid(row=index + 1, column=0, sticky="w", padx=10, pady=5)
            UI.label(table, short_text(question.get("question", ""), 65), size=10, bg=row_bg, anchor="w").grid(row=index + 1, column=1, sticky="ew", padx=10, pady=14)
            UI.label(table, short_text(question.get("answer", ""), 35), size=10, fg="#A2B2C9", bg=row_bg, anchor="w").grid(row=index + 1, column=2, sticky="ew", padx=10, pady=14)
            actions = tk.Frame(table, bg=row_bg)
            actions.grid(row=index + 1, column=3, padx=6)
            UI.button(actions, "✎", lambda q=question: self.edit_question(q), variant="bare", size="small", width=2).pack(side="left")
            UI.button(actions, "⧉", lambda q=question: self.duplicate_question(q), variant="bare", size="small", width=2).pack(side="left")
            UI.button(actions, "⌫", lambda q=question: self.delete_question(q), variant="bare", size="small", width=2).pack(side="left")

    def current_category(self) -> dict[str, Any] | None:
        return next((category for category in self.game.get("categories", []) if category.get("id") == self.selected_category_id), None)

    def select_category(self, category: dict[str, Any]) -> None:
        self.selected_category_id = category.get("id")
        self.render_tab()

    def add_category(self) -> None:
        CategoryDialog(self, None)

    def edit_category(self) -> None:
        category = self.current_category()
        if category is None:
            self.info("Categorías", "Selecciona una categoría.")
            return
        CategoryDialog(self, category)

    def delete_category(self) -> None:
        category = self.current_category()
        if category is None:
            self.info("Categorías", "Selecciona una categoría.")
            return
        ConfirmDialog(self, title="Eliminar categoría", message=f"¿Eliminar “{category.get('name')}” y sus preguntas?", confirm_label="Eliminar categoría", on_confirm=lambda: self._delete_category(category), variant="danger", icon="⌫")

    def _delete_category(self, category: dict[str, Any]) -> None:
        self.game["categories"].remove(category)
        self.selected_category_id = None
        self.dirty = True
        self.render_tab()

    def add_question(self) -> None:
        category = self.current_category()
        if category is None:
            self.info("Preguntas", "Crea o selecciona una categoría primero.")
            return
        QuestionDialog(self, category, None)

    def edit_question(self, question: dict[str, Any]) -> None:
        category = self.current_category()
        if category is None:
            self.info("Preguntas", "Selecciona una categoría.")
            return
        QuestionDialog(self, category, question)

    def duplicate_question(self, question: dict[str, Any]) -> None:
        category = self.current_category()
        if category is None:
            return
        duplicate = copy.deepcopy(question)
        duplicate["id"] = new_id()
        duplicate["value"] = int(duplicate.get("value", 0)) + 10
        category.setdefault("questions", []).append(duplicate)
        self.dirty = True
        self.render_tab()

    def delete_question(self, question: dict[str, Any]) -> None:
        ConfirmDialog(self, title="Eliminar pregunta", message="¿Eliminar esta pregunta del juego?", confirm_label="Eliminar pregunta", on_confirm=lambda: self._delete_question(question), variant="danger", icon="⌫")

    def _delete_question(self, question: dict[str, Any]) -> None:
        category = self.current_category()
        if category and question in category.get("questions", []):
            category["questions"].remove(question)
            self.dirty = True
            self.render_tab()

    def info(self, title: str, message: str) -> None:
        ConfirmDialog(self, title=title, message=message, confirm_label="Entendido", on_confirm=lambda: None, icon="ⓘ", cancel_label=None)

    def request_close(self) -> None:
        if self.dirty:
            ConfirmDialog(self, title="Cambios sin guardar", message="Tienes cambios sin guardar. ¿Quieres descartarlos?", confirm_label="Descartar cambios", on_confirm=self.destroy, variant="quiet", icon="⚠", cancel_label="Seguir editando")
        else:
            self.destroy()

    def save(self) -> None:
        name, title = self.name_var.get().strip(), self.title_var.get().strip()
        if not name or not title:
            self.info("Faltan datos", "Escribe el nombre interno y el título visible del juego.")
            return
        self.game.update({
            "name": name,
            "title": title,
            "background_color": self.app.safe_color(self.background_var.get(), "#0F1829"),
            "background_image": self.background_image_var.get().strip(),
            "accent_color": self.app.safe_color(self.accent_var.get(), PRIMARY),
            "text_color": self.app.safe_color(self.text_var.get(), TEXT),
            "card_color": self.app.safe_color(self.card_var.get(), "#25354F"),
            "font_family": self.font_var.get().strip() or FONT,
            "teams": [{"name": team.get("name", "").strip() or f"Equipo {index + 1}", "color": self.app.safe_color(team.get("color", ""), TEAM_COLORS[index % len(TEAM_COLORS)])} for index, team in enumerate(self._team_data)],
        })
        self.store.save_game(self.game)
        self.dirty = False
        self.destroy()
        self.app.show_library()


class CategoryDialog(BaseDialog):
    def __init__(self, editor: GameEditor, category: dict[str, Any] | None) -> None:
        super().__init__(editor, "Nueva categoría" if category is None else "Editar categoría", "570x390")
        self.editor, self.category = editor, category
        self.name_var = tk.StringVar(value=category.get("name", "") if category else "")
        self.color_var = tk.StringVar(value=category.get("color", "#43DAB0") if category else "#43DAB0")
        card = UI.frame(self, PANEL_2, STROKE_LIGHT)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        head = tk.Frame(card, bg=PANEL_2)
        head.pack(fill="x", padx=25, pady=(22, 15))
        UI.label(head, "Nueva categoría" if category is None else "Editar categoría", size=22, weight="bold", bg=PANEL_2).pack(side="left")
        self.close_button(head).pack(side="right")
        UI.label(card, "Define cómo aparecerá en el tablero.", size=10, fg="#9CB0CC", bg=PANEL_2).pack(anchor="w", padx=25)
        UI.label(card, "Nombre de la categoría *", size=10, weight="bold", fg="#C1CEE2", bg=PANEL_2).pack(anchor="w", padx=25, pady=(21, 8))
        UI.entry(card, self.name_var).pack(fill="x", padx=25)
        UI.label(card, "Color identificador", size=10, weight="bold", fg="#C1CEE2", bg=PANEL_2).pack(anchor="w", padx=25, pady=(18, 8))
        line = tk.Frame(card, bg=PANEL_2)
        line.pack(fill="x", padx=25)
        swatch = UI.label(line, "", bg=self.color_var.get(), width=4, height=2)
        swatch.pack(side="left")
        UI.entry(line, self.color_var).pack(side="left", fill="x", expand=True, padx=8)
        UI.button(line, "◉", self.pick_color, variant="quiet", size="small", width=2).pack(side="right")
        self.color_var.trace_add("write", lambda *_args: swatch.configure(bg=editor.app.safe_color(self.color_var.get(), "#43DAB0")))
        tk.Frame(card, bg=STROKE, height=1).pack(fill="x", padx=25, pady=(21, 14))
        actions = tk.Frame(card, bg=PANEL_2)
        actions.pack(fill="x", padx=25)
        UI.button(actions, "Cancelar", self.destroy, variant="quiet", size="small").pack(side="right")
        UI.button(actions, "✓  Guardar categoría", self.save, variant="primary", size="small").pack(side="right", padx=(0, 8))

    def pick_color(self) -> None:
        color = colorchooser.askcolor(color=self.color_var.get(), parent=self)[1]
        if color:
            self.color_var.set(color.upper())

    def save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            self.editor.info("Falta un nombre", "Escribe el nombre de la categoría.")
            return
        if self.category is None:
            self.category = {"id": new_id(), "name": name, "color": self.editor.app.safe_color(self.color_var.get(), "#43DAB0"), "questions": []}
            self.editor.game.setdefault("categories", []).append(self.category)
        else:
            self.category.update({"name": name, "color": self.editor.app.safe_color(self.color_var.get(), "#43DAB0")})
        self.editor.selected_category_id = self.category["id"]
        self.editor.dirty = True
        self.destroy()
        self.editor.render_tab()


class QuestionDialog(BaseDialog):
    def __init__(self, editor: GameEditor, category: dict[str, Any], question: dict[str, Any] | None) -> None:
        super().__init__(editor, "Nueva pregunta" if question is None else "Editar pregunta", "1000x680")
        self.editor, self.category, self.question = editor, category, question
        self.value_var = tk.StringVar(value=str(question.get("value", 10) if question else 10))
        self.image_var = tk.StringVar(value=question.get("image_path", "") if question else "")
        card = UI.frame(self, PANEL_2, STROKE_LIGHT)
        card.pack(fill="both", expand=True, padx=17, pady=17)
        head = tk.Frame(card, bg=PANEL_2)
        head.pack(fill="x", padx=25, pady=(20, 4))
        texts = tk.Frame(head, bg=PANEL_2)
        texts.pack(side="left")
        UI.label(texts, "Nueva pregunta" if question is None else "Editar pregunta", size=22, weight="bold", bg=PANEL_2).pack(anchor="w")
        UI.label(texts, f"Categoría: {category.get('name', '')}", size=10, fg="#9CB0CC", bg=PANEL_2).pack(anchor="w", pady=(5, 0))
        self.close_button(head).pack(side="right")
        body = tk.Frame(card, bg=PANEL_2)
        body.pack(fill="both", expand=True, padx=25, pady=(18, 10))
        body.grid_columnconfigure(0, weight=6)
        body.grid_columnconfigure(1, weight=4)
        left = tk.Frame(body, bg=PANEL_2)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = tk.Frame(body, bg=PANEL_2)
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        UI.label(left, "Valor de la carta *", size=10, weight="bold", fg="#C1CEE2", bg=PANEL_2).pack(anchor="w", pady=(0, 7))
        UI.entry(left, self.value_var, width=14).pack(anchor="w")
        UI.label(left, "Pregunta *", size=10, weight="bold", fg="#C1CEE2", bg=PANEL_2).pack(anchor="w", pady=(17, 7))
        self.question_text = UI.text(left, height=4)
        self.question_text.pack(fill="x")
        self.question_text.insert("1.0", question.get("question", "") if question else "")
        UI.label(left, "Alternativas (una por línea)", size=10, weight="bold", fg="#C1CEE2", bg=PANEL_2).pack(anchor="w", pady=(17, 7))
        self.choices_text = UI.text(left, height=6)
        self.choices_text.pack(fill="x")
        self.choices_text.insert("1.0", "\n".join(question.get("choices", []) if question else []))
        UI.label(left, "Respuesta correcta *", size=10, weight="bold", fg="#C1CEE2", bg=PANEL_2).pack(anchor="w", pady=(17, 7))
        self.answer_text = UI.text(left, height=2)
        self.answer_text.pack(fill="x")
        self.answer_text.insert("1.0", question.get("answer", "") if question else "")
        UI.label(right, "Imagen de la pregunta (opcional)", size=10, weight="bold", fg="#C1CEE2", bg=PANEL_2).pack(anchor="w", pady=(0, 7))
        self.image_preview = tk.Frame(right, bg="#101B2D", highlightbackground=STROKE_LIGHT, highlightthickness=1, height=260)
        self.image_preview.pack(fill="x")
        self.image_preview.pack_propagate(False)
        self._image_photo: Any | None = None
        self._refresh_image()
        self.image_var.trace_add("write", lambda *_args: self._refresh_image())
        actions_image = tk.Frame(right, bg=PANEL_2)
        actions_image.pack(fill="x", pady=11)
        UI.button(actions_image, "▧  Examinar", self.pick_image, variant="quiet", size="small").pack(side="left")
        UI.button(actions_image, "⌫  Quitar", lambda: self.image_var.set(""), variant="quiet", size="small").pack(side="left", padx=7)
        UI.label(right, "Se admite una ruta local. Si la imagen no se encuentra, la pregunta se mostrará solo con texto.", size=9, fg="#91A3C0", bg=PANEL_2, wraplength=270, justify="left").pack(anchor="w", pady=(6, 0))
        tk.Frame(card, bg=STROKE, height=1).pack(fill="x", padx=25, pady=(3, 13))
        foot = tk.Frame(card, bg=PANEL_2)
        foot.pack(fill="x", padx=25, pady=(0, 8))
        UI.button(foot, "Cancelar", self.destroy, variant="quiet", size="small").pack(side="right")
        UI.button(foot, "✓  Guardar pregunta", self.save, variant="primary", size="small").pack(side="right", padx=(0, 8))

    def _refresh_image(self) -> None:
        if not hasattr(self, "image_preview") or not self.image_preview.winfo_exists():
            return
        for child in self.image_preview.winfo_children():
            child.destroy()
        self._image_photo = None
        path = self.image_var.get().strip()
        if path and PIL_AVAILABLE and Path(path).is_file():
            try:
                image = Image.open(path).convert("RGB")
                image = ImageOps.contain(image, (310, 245), method=Image.Resampling.LANCZOS)
                self._image_photo = ImageTk.PhotoImage(image)
                tk.Label(self.image_preview, image=self._image_photo, bg="#101B2D").place(relx=0.5, rely=0.5, anchor="center")
                return
            except (OSError, ValueError):
                pass
        UI.label(self.image_preview, "▧", size=42, fg="#5B7196", bg="#101B2D").place(relx=0.5, rely=0.45, anchor="center")
        UI.label(self.image_preview, "Sin imagen", size=10, fg="#7F92AF", bg="#101B2D").place(relx=0.5, rely=0.67, anchor="center")

    def pick_image(self) -> None:
        path = filedialog.askopenfilename(parent=self, title="Selecciona una imagen", filetypes=IMAGE_TYPES)
        if path:
            self.image_var.set(path)

    def save(self) -> None:
        try:
            value = int(self.value_var.get())
            if value <= 0:
                raise ValueError
        except ValueError:
            self.editor.info("Valor inválido", "El valor debe ser un número entero positivo.")
            return
        question_text = self.question_text.get("1.0", "end").strip()
        answer = self.answer_text.get("1.0", "end").strip()
        if not question_text or not answer:
            self.editor.info("Faltan datos", "Completa la pregunta y la respuesta.")
            return
        question = self.question or {"id": new_id()}
        question.update({"value": value, "question": question_text, "choices": [line.strip() for line in self.choices_text.get("1.0", "end").splitlines() if line.strip()], "answer": answer, "image_path": self.image_var.get().strip()})
        if self.question is None:
            self.category.setdefault("questions", []).append(question)
        self.editor.dirty = True
        self.destroy()
        self.editor.render_tab()


class TeamSetupDialog(BaseDialog):
    """Edición temporal de equipos justo antes de crear una partida."""

    def __init__(self, app: QuizApp, game: dict[str, Any]) -> None:
        super().__init__(app, "Preparar partida", "740x720")
        self.app, self.game = app, copy.deepcopy(game)
        self.teams = copy.deepcopy(self.game.get("teams", []))
        if len(self.teams) < 2:
            self.teams = [{"name": f"Equipo {index + 1}", "color": TEAM_COLORS[index]} for index in range(2)]
        self._render()

    def _render(self) -> None:
        for child in self.winfo_children():
            child.destroy()
        card = UI.frame(self, PANEL_2, STROKE_LIGHT)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        head = tk.Frame(card, bg=PANEL_2)
        head.pack(fill="x", padx=25, pady=(20, 13))
        labels = tk.Frame(head, bg=PANEL_2)
        labels.pack(side="left")
        UI.label(labels, "ANTES DE COMENZAR", size=9, weight="bold", fg="#7188AB", bg=PANEL_2).pack(anchor="w")
        UI.label(labels, "Preparar partida", size=25, weight="bold", bg=PANEL_2).pack(anchor="w", pady=(7, 2))
        UI.label(labels, f"{self.game.get('title', 'Juego')} · Los cambios solo se aplican a esta partida.", size=9, fg="#98ABC7", bg=PANEL_2).pack(anchor="w")
        self.close_button(head).pack(side="right")
        count = UI.frame(card, "#111D31", STROKE)
        count.pack(fill="x", padx=25, pady=(4, 14))
        UI.label(count, "♧  Cantidad de equipos", size=12, weight="bold", bg="#111D31").pack(side="left", padx=18, pady=14)
        UI.button(count, "−", self.remove_team, variant="quiet", size="small", width=2).pack(side="right", padx=(0, 18), pady=9)
        UI.label(count, str(len(self.teams)), size=18, weight="bold", bg="#111D31", padx=12).pack(side="right")
        UI.button(count, "+", self.add_team, variant="quiet", size="small", width=2).pack(side="right", padx=(0, 7), pady=9)
        UI.label(card, "Personaliza los nombres y colores para esta ocasión:", size=10, fg="#92A5C2", bg=PANEL_2).pack(anchor="w", padx=25, pady=(0, 8))
        rows = tk.Frame(card, bg=PANEL_2)
        rows.pack(fill="both", expand=True, padx=25)
        for index, team in enumerate(self.teams):
            line = UI.frame(rows, "#111D31", STROKE)
            line.pack(fill="x", pady=4)
            color = self.app.safe_color(team.get("color", ""), TEAM_COLORS[index % len(TEAM_COLORS)])
            UI.label(line, "", bg=color, width=2, height=1).pack(side="left", padx=14, pady=11)
            name_var = tk.StringVar(value=team.get("name", ""))
            entry = UI.entry(line, name_var)
            entry.pack(side="left", fill="x", expand=True, pady=9)
            entry.bind("<KeyRelease>", lambda _event, i=index, var=name_var: self._set_name(i, var.get()))
            UI.label(line, f"Equipo {index + 1}", size=9, fg="#97A9C5", bg="#111D31", padx=13).pack(side="left")
            UI.button(line, "◉", lambda i=index: self.pick_color(i), variant="bare", size="small", width=2).pack(side="right", padx=10)
        tk.Frame(card, bg=STROKE, height=1).pack(fill="x", padx=25, pady=(10, 13))
        actions = tk.Frame(card, bg=PANEL_2)
        actions.pack(fill="x", padx=25, pady=(0, 5))
        UI.button(actions, "Cancelar", self.destroy, variant="quiet", size="small").pack(side="right")
        UI.button(actions, "▶  Iniciar partida", self.start, variant="primary", size="normal").pack(side="right", padx=(0, 8))

    def _set_name(self, index: int, value: str) -> None:
        self.teams[index]["name"] = value

    def add_team(self) -> None:
        if len(self.teams) < 8:
            index = len(self.teams)
            self.teams.append({"name": f"Equipo {index + 1}", "color": TEAM_COLORS[index % len(TEAM_COLORS)]})
            self._render()

    def remove_team(self) -> None:
        if len(self.teams) > 2:
            self.teams.pop()
            self._render()

    def pick_color(self, index: int) -> None:
        color = colorchooser.askcolor(color=self.teams[index].get("color"), parent=self)[1]
        if color:
            self.teams[index]["color"] = color.upper()
            self._render()

    def start(self) -> None:
        teams = [{"name": team.get("name", "").strip() or f"Equipo {index + 1}", "color": self.app.safe_color(team.get("color", ""), TEAM_COLORS[index % len(TEAM_COLORS)])} for index, team in enumerate(self.teams)]
        self.destroy()
        self.app.launch_session(self.game, teams)


class GameSession:
    """Estado de una partida activa, siempre persistido después de cada cambio."""

    def __init__(self, app: QuizApp, game: dict[str, Any], session: dict[str, Any]) -> None:
        # La interfaz de una partida usa su copia congelada, no la definición
        # viva de biblioteca. Esto mantiene el tablero consistente aun si ese
        # juego se edita o elimina en otra sesión de la aplicación.
        snapshot = session.get("game_snapshot") or game
        self.app, self.store, self.game, self.session = app, app.store, copy.deepcopy(snapshot), session
        configured_font = self.game.get("font_family", FONT)
        UI.font_family = configured_font.strip() if isinstance(configured_font, str) and configured_font.strip() else FONT
        self.current: tuple[dict[str, Any], dict[str, Any]] | None = None
        self.root: tk.Frame | None = None
        self._photos: list[Any] = []

    @property
    def background(self) -> str:
        return self.app.safe_color(self.game.get("background_color", BG_PLAY), BG_PLAY)

    @property
    def accent(self) -> str:
        return self.app.safe_color(self.game.get("accent_color", PRIMARY), PRIMARY)

    @property
    def text_color(self) -> str:
        return self.app.safe_color(self.game.get("text_color", TEXT), TEXT)

    @property
    def card_color(self) -> str:
        return self.app.safe_color(self.game.get("card_color", "#25354F"), "#25354F")

    def _new_page(self) -> tk.Frame:
        self.app.clear_window()
        self._photos.clear()
        self.root = tk.Frame(self.app, bg=self.background)
        self.root.pack(fill="both", expand=True)
        image_path = self.game.get("background_image", "")
        if image_path and PIL_AVAILABLE and Path(image_path).is_file():
            try:
                self.app.update_idletasks()
                image = Image.open(image_path).convert("RGB")
                image = ImageOps.fit(image, (max(self.app.winfo_width(), 1120), max(self.app.winfo_height(), 680)), method=Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                self._photos.append(photo)
                label = tk.Label(self.root, image=photo, bd=0)
                label.place(x=0, y=0, relwidth=1, relheight=1)
                label.lower()
            except (OSError, ValueError):
                pass
        return self.root

    def used(self, category: dict[str, Any], question: dict[str, Any]) -> bool:
        return f"{category.get('id')}:{question.get('id')}" in self.session.get("used_cards", [])

    def mark_used(self, category: dict[str, Any], question: dict[str, Any]) -> None:
        token = f"{category.get('id')}:{question.get('id')}"
        if token not in self.session["used_cards"]:
            self.session["used_cards"].append(token)
            self.store.update_session(self.session)

    def _topbar(self, parent: tk.Widget) -> None:
        teams = self.session.get("teams", [])
        dense_scores = len(teams) > 5
        bar = tk.Frame(parent, bg="#0A1323", height=112, highlightbackground="#31415C", highlightthickness=1)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        logo = tk.Frame(bar, bg="#0A1323", width=135 if dense_scores else 175)
        logo.pack(side="left", padx=16 if dense_scores else 28, pady=20)
        logo.pack_propagate(False)
        UI.label(logo, "Q", size=15, weight="bold", fg="white", bg=PRIMARY, width=2, height=1).pack(side="left")
        UI.label(logo, "QUIZ\nSTUDIO", size=11, weight="bold", bg="#0A1323", justify="left").pack(side="left", padx=9)
        actions = tk.Frame(bar, bg="#0A1323")
        actions.pack(side="left", pady=31)
        UI.button(actions, "←  Salir", self.exit_game, variant="quiet", size="small").pack(side="left", padx=4)
        UI.button(actions, "◷  Historial", lambda: HistoryDialog(self.app, self.game["id"]), variant="quiet", size="small").pack(side="left", padx=4)
        UI.button(actions, "◉  Finalizar", self.finish_game, variant="danger", size="small").pack(side="left", padx=4)
        scores = tk.Frame(bar, bg="#0A1323")
        scores.pack(side="right", padx=10 if dense_scores else 20, pady=17)
        tile_width = 72 if dense_scores else 125
        for index, team in enumerate(teams):
            color = self.app.safe_color(team.get("color", ""), TEAM_COLORS[index % len(TEAM_COLORS)])
            score = UI.frame(scores, "#15243A", color)
            score.configure(width=tile_width, height=76)
            score.pack(side="left", padx=4)
            score.pack_propagate(False)
            UI.label(score, f"● {short_text(team.get('name', f'Equipo {index + 1}'), 6 if dense_scores else 12)}", size=7 if dense_scores else 8, weight="bold", fg="#D5E0F3", bg="#15243A").pack(anchor="w", padx=7 if dense_scores else 10, pady=(7, 0))
            bottom = tk.Frame(score, bg="#15243A")
            bottom.pack(fill="x", padx=5 if dense_scores else 8, pady=(2, 0))
            UI.label(bottom, str(team.get("score", 0)), size=15 if dense_scores else 18, weight="bold", bg="#15243A").pack(side="left")
            ticks = tk.Frame(bottom, bg="#15243A")
            ticks.pack(side="right")
            decrement_label, increment_label = ("−", "+") if dense_scores else ("−10", "+10")
            tick_size = "tiny" if dense_scores else "small"
            UI.button(ticks, decrement_label, lambda i=index: self.change_score(i, -10), variant="quiet", size=tick_size, width=1 if dense_scores else None).pack(side="left", padx=1)
            UI.button(ticks, increment_label, lambda i=index: self.change_score(i, 10), variant="quiet", size=tick_size, width=1 if dense_scores else None).pack(side="left", padx=1)

    def show_board(self) -> None:
        self.current = None
        root = self._new_page()
        self._topbar(root)
        content = tk.Frame(root, bg=self.background)
        content.pack(fill="both", expand=True)
        heading = tk.Frame(content, bg=self.background)
        heading.pack(fill="x", pady=(28, 15))
        UI.label(heading, "PARTIDA ACTIVA", size=9, weight="bold", fg="#7188AB", bg=self.background).pack()
        UI.label(heading, self.game.get("title", "Juego de preguntas").upper(), size=27, weight="bold", fg=self.text_color, bg=self.background, wraplength=980).pack(pady=(8, 9))
        remaining = sum(1 for category in self.game.get("categories", []) for question in category.get("questions", []) if not self.used(category, question))
        UI.label(heading, f"⊞  {remaining} cartas disponibles", size=11, weight="bold", fg="#BBCDF0", bg="#1B2740", padx=13, pady=8).pack()
        categories = self.game.get("categories", [])
        if not categories:
            self._play_empty(content, "▧", "Este juego aún no tiene categorías", "Vuelve a la biblioteca y añade categorías con preguntas para continuar.")
            return
        scroll = ScrollableFrame(content, self.background)
        scroll.pack(fill="both", expand=True, padx=70, pady=(0, 25))
        board = scroll.body
        columns = min(5, max(1, len(categories)))
        for col in range(columns):
            board.grid_columnconfigure(col, weight=1, uniform="board")
        for index, category in enumerate(categories):
            self._board_category(board, category).grid(row=index // columns, column=index % columns, sticky="nsew", padx=8, pady=8)
        if remaining == 0:
            banner = tk.Frame(content, bg=self.background)
            banner.place(relx=0.5, rely=0.94, anchor="center")
            UI.label(banner, "✓  No quedan cartas. Puedes finalizar la partida.", size=10, weight="bold", fg="#80F4C8", bg="#123B34", padx=12, pady=8).pack(side="left", padx=5)
            UI.button(banner, "♜  Finalizar partida", self.finish_game, variant="primary", size="small").pack(side="left", padx=5)

    def _board_category(self, parent: tk.Widget, category: dict[str, Any]) -> tk.Frame:
        color = self.app.safe_color(category.get("color", PRIMARY), PRIMARY)
        box = UI.frame(parent, "#121C2B", "#32445C")
        head = tk.Frame(box, bg="#192840", highlightbackground=color, highlightthickness=1, height=84)
        head.pack(fill="x", padx=10, pady=10)
        head.pack_propagate(False)
        UI.label(head, "✦", size=19, weight="bold", fg=color, bg="#192840").pack(pady=(10, 1))
        UI.label(head, short_text(category.get("name", "Categoría"), 18), size=12, weight="bold", bg="#192840").pack()
        questions = sorted(category.get("questions", []), key=lambda item: item.get("value", 0), reverse=True)
        if not questions:
            UI.label(box, "Sin preguntas", size=10, fg="#8091A9", bg="#121C2B", pady=26).pack(fill="x")
        for question in questions:
            is_used = self.used(category, question)
            button = UI.button(box, "✓  USADA" if is_used else str(question.get("value", "")), lambda c=category, q=question: self.open_question(c, q), variant="quiet", size="normal", state="disabled" if is_used else "normal")
            button.configure(font=(UI.font_family, 18 if not is_used else 11, "bold"), bg="#151E2D" if is_used else self.card_color, fg="#8293AA" if is_used else self.text_color, activebackground=self.card_color, pady=12)
            button.pack(fill="x", padx=10, pady=(0, 10))
        return box

    def _play_empty(self, parent: tk.Widget, icon: str, title: str, detail: str) -> None:
        empty = UI.frame(parent, "#101B2C", "#2C4262")
        empty.pack(padx=245, pady=65, fill="x", ipady=48)
        UI.label(empty, icon, size=32, fg="#94A4FF", bg="#23375C", width=3, height=2).pack(pady=(3, 11))
        UI.label(empty, title, size=22, weight="bold", bg="#101B2C").pack()
        UI.label(empty, detail, size=11, fg="#9AAECD", bg="#101B2C", justify="center", wraplength=470).pack(pady=(10, 20))
        UI.button(empty, "←  Salir", self.exit_game, variant="quiet", size="normal").pack()

    def open_question(self, category: dict[str, Any], question: dict[str, Any]) -> None:
        self.current = (category, question)
        self.mark_used(category, question)
        self.show_question(reveal=False)

    def show_question(self, reveal: bool) -> None:
        if self.current is None:
            self.show_board()
            return
        category, question = self.current
        if reveal:
            self._show_answer(category, question)
            return
        root = self._new_page()
        self._topbar(root)
        content = tk.Frame(root, bg=self.background)
        content.pack(fill="both", expand=True)
        tags = tk.Frame(content, bg=self.background)
        tags.pack(pady=(38, 19))
        color = self.app.safe_color(category.get("color", PRIMARY), PRIMARY)
        UI.label(tags, f"✦  {category.get('name', 'Categoría').upper()}", size=10, weight="bold", bg="#1B2740", fg="#D6E3F8", padx=12, pady=7).pack(side="left", padx=6)
        UI.label(tags, f"{question.get('value', 0)} PUNTOS", size=10, weight="bold", bg="#1B2740", fg=AMBER, padx=12, pady=7).pack(side="left", padx=6)
        panel = UI.frame(content, "#16243A", "#49617F")
        panel.pack(fill="x", padx=170, pady=4)
        panel_body = tk.Frame(panel, bg="#16243A")
        panel_body.pack(fill="both", expand=True, padx=45, pady=36)
        has_image = self._question_image(panel_body, question)
        question_label = UI.label(panel_body, question.get("question", ""), size=30 if not has_image else 25, weight="bold", bg="#16243A", fg=self.text_color, justify="left" if has_image else "center", wraplength=730)
        if has_image:
            question_label.pack(side="left", fill="both", expand=True, padx=(0, 35))
        else:
            question_label.pack(fill="x", pady=(8, 20))
        choices = question.get("choices", [])
        if choices:
            choices_frame = tk.Frame(panel, bg="#16243A")
            choices_frame.pack(fill="x", padx=45, pady=(0, 30))
            for index, choice in enumerate(choices):
                choice_box = UI.frame(choices_frame, "#1C2E47", "#3E5572")
                choice_box.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)
                choices_frame.grid_columnconfigure(index % 2, weight=1)
                UI.label(choice_box, chr(65 + index), size=11, weight="bold", bg="#2C415E", fg="#E7EFFF", padx=10, pady=8).pack(side="left", padx=10, pady=8)
                UI.label(choice_box, choice, size=15, bg="#1C2E47", fg="#E7EFFF", anchor="w", wraplength=270).pack(side="left", fill="x", expand=True, padx=(0, 10))
        foot = tk.Frame(content, bg=self.background)
        foot.pack(pady=26)
        UI.button(foot, "⊞  Volver al tablero", self.show_board, variant="quiet", size="large").pack(side="left", padx=6)
        UI.button(foot, "✓  Mostrar respuesta", lambda: self.show_question(reveal=True), variant="primary", size="large").pack(side="left", padx=6)
        UI.label(content, "La respuesta aún no está visible para los participantes.", size=10, fg="#8FA3C2", bg=self.background).pack()

    def _question_image(self, parent: tk.Widget, question: dict[str, Any]) -> bool:
        path = question.get("image_path", "")
        if not path or not PIL_AVAILABLE or not Path(path).is_file():
            return False
        try:
            image = Image.open(path).convert("RGB")
            image = ImageOps.contain(image, (290, 230), method=Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._photos.append(photo)
            image_box = UI.frame(parent, "#101B2D", STROKE_LIGHT)
            image_box.pack(side="right")
            tk.Label(image_box, image=photo, bg="#101B2D").pack(padx=7, pady=7)
            return True
        except (OSError, ValueError):
            return False

    def _show_answer(self, category: dict[str, Any], question: dict[str, Any]) -> None:
        root = self._new_page()
        self._topbar(root)
        content = tk.Frame(root, bg=self.background)
        content.pack(fill="both", expand=True)
        tags = tk.Frame(content, bg=self.background)
        tags.pack(pady=(30, 13))
        UI.label(tags, f"✦  {category.get('name', 'Categoría').upper()}", size=10, weight="bold", bg="#1B2740", fg="#D6E3F8", padx=12, pady=7).pack(side="left", padx=6)
        UI.label(tags, f"{question.get('value', 0)} PUNTOS", size=10, weight="bold", bg="#1B2740", fg=AMBER, padx=12, pady=7).pack(side="left", padx=6)
        panel = UI.frame(content, "#16243A", "#49617F")
        panel.pack(fill="x", padx=170, pady=4)
        UI.label(panel, question.get("question", ""), size=22, weight="bold", bg="#16243A", fg=self.text_color, justify="center", wraplength=980).pack(fill="x", padx=34, pady=(22, 13))
        choices = question.get("choices", [])
        if choices:
            choices_frame = tk.Frame(panel, bg="#16243A")
            choices_frame.pack(fill="x", padx=28)
            answer_lower = question.get("answer", "").strip().casefold()
            for index, choice in enumerate(choices):
                correct = choice.strip().casefold() == answer_lower
                box_bg = "#135647" if correct else "#1C2E47"
                border = MINT if correct else "#3E5572"
                choice_box = UI.frame(choices_frame, box_bg, border)
                choice_box.grid(row=index // 2, column=index % 2, sticky="nsew", padx=6, pady=6)
                choices_frame.grid_columnconfigure(index % 2, weight=1)
                UI.label(choice_box, chr(65 + index), size=10, weight="bold", bg="#2C796D" if correct else "#2C415E", padx=9, pady=6).pack(side="left", padx=10, pady=7)
                UI.label(choice_box, choice, size=13, weight="bold" if correct else "normal", bg=box_bg, fg="white", anchor="w").pack(side="left", fill="x", expand=True)
                if correct:
                    UI.label(choice_box, "✓", size=15, weight="bold", bg=box_bg, fg="#B4FFE7").pack(side="right", padx=12)
        reveal = UI.frame(panel, "#104B40", MINT)
        reveal.pack(fill="x", padx=28, pady=18)
        UI.label(reveal, "✓", size=25, weight="bold", fg="#8DFFD9", bg="#104B40").pack(side="left", padx=17, pady=10)
        r_text = tk.Frame(reveal, bg="#104B40")
        r_text.pack(side="left", fill="x", expand=True, pady=10)
        UI.label(r_text, "RESPUESTA CORRECTA", size=9, weight="bold", fg="#8DFFD9", bg="#104B40").pack(anchor="w")
        UI.label(r_text, question.get("answer", ""), size=20, weight="bold", bg="#104B40").pack(anchor="w", pady=(3, 0))
        award = UI.frame(content, "#111D31", STROKE)
        award.pack(fill="x", padx=170, pady=(18, 7))
        UI.label(award, "Asignar puntos", size=17, weight="bold", bg="#111D31").pack(pady=(18, 2))
        UI.label(award, f"Selecciona el equipo que acertó para sumar {question.get('value', 0)} puntos.", size=10, fg="#9CB0CC", bg="#111D31").pack()
        buttons = tk.Frame(award, bg="#111D31")
        buttons.pack(fill="x", padx=18, pady=(14, 18))
        teams = self.session.get("teams", [])
        for index, team in enumerate(teams):
            color = self.app.safe_color(team.get("color", ""), TEAM_COLORS[index % len(TEAM_COLORS)])
            button = UI.button(buttons, f"●  +{question.get('value', 0)}  {short_text(team.get('name', 'Equipo'), 16)}", lambda i=index, points=int(question.get("value", 0)): self.change_score(i, points), variant="quiet", size="normal")
            button.configure(highlightbackground=color, highlightthickness=1, fg="#EAF2FF")
            button.grid(row=index // 4, column=index % 4, sticky="ew", padx=6, pady=5)
            buttons.grid_columnconfigure(index % 4, weight=1)
        UI.button(content, "⊞  Volver al tablero", self.show_board, variant="quiet", size="large").pack(pady=13)

    def change_score(self, index: int, delta: int) -> None:
        self.session["teams"][index]["score"] += delta
        self.store.update_session(self.session)
        if self.current:
            category, question = self.current
            self._show_answer(category, question)
        else:
            self.show_board()

    def exit_game(self) -> None:
        ConfirmDialog(self.app, title="Salir de la partida", message="La partida en curso quedará guardada en el historial.", confirm_label="Salir", on_confirm=lambda: (self.store.update_session(self.session), self.app.show_library()), variant="primary", icon="◉", cancel_label="Continuar jugando")

    def finish_game(self) -> None:
        ConfirmDialog(self.app, title="Finalizar partida", message="¿Guardar el resultado final en el historial?", confirm_label="Finalizar partida", on_confirm=self._finish_confirmed, variant="primary", icon="♜")

    def _finish_confirmed(self) -> None:
        self.session = self.store.finish_session(self.session)
        plural = "es" if "," in self.session.get("winner", "") else ""
        ConfirmDialog(self.app, title="Partida guardada", message=f"Resultado guardado. Ganador{plural}: {self.session.get('winner') or 'sin definir'}.", confirm_label="Entendido", on_confirm=self.app.show_history, variant="primary", icon="✓", cancel_label=None)


class HistoryDialog(BaseDialog):
    """Historial filtrado y consultable sin abandonar el tablero activo."""

    def __init__(self, app: QuizApp, game_id: str | None = None) -> None:
        super().__init__(app, "Historial de partidas", "900x650", modal=False)
        card = UI.frame(self, PANEL_2, STROKE_LIGHT)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        head = tk.Frame(card, bg=PANEL_2)
        head.pack(fill="x", padx=25, pady=(20, 8))
        labels = tk.Frame(head, bg=PANEL_2)
        labels.pack(side="left")
        UI.label(labels, "HISTORIAL DEL JUEGO" if game_id else "PARTIDAS GUARDADAS", size=9, weight="bold", fg="#7188AB", bg=PANEL_2).pack(anchor="w")
        UI.label(labels, "Historial de partidas", size=23, weight="bold", bg=PANEL_2).pack(anchor="w", pady=(5, 2))
        UI.label(labels, "Consulta las partidas de este juego sin salir de la actual." if game_id else "Resultados guardados de todos tus juegos.", size=10, fg="#9CB0CC", bg=PANEL_2).pack(anchor="w")
        self.close_button(head).pack(side="right")
        scroll = ScrollableFrame(card, PANEL_2)
        scroll.pack(fill="both", expand=True, padx=25, pady=(14, 16))
        sessions = app.store.list_sessions(game_id)
        if not sessions:
            UI.label(scroll.body, "Aún no hay partidas guardadas.", size=14, fg="#9CB0CC", bg=PANEL_2).pack(pady=120)
        for session in sessions:
            app._history_card(scroll.body, session, modal=True).pack(fill="x", pady=6)
        UI.button(card, "Cerrar y continuar", self.destroy, variant="primary", size="small").pack(anchor="e", padx=25, pady=(0, 15))


def run_desktop_app() -> None:
    """Muestra el diseño de Quiz Studio dentro de una ventana nativa de macOS.

    La capa visual sigue siendo HTML/CSS/JS porque reproduce fielmente el
    sistema de diseño, pero se ejecuta dentro de Qt WebEngine. No se inicia un
    navegador externo, no se abre un puerto y no hace falta Internet.
    """
    if not WEB_UI_PATH.is_file():
        raise RuntimeError(f"No se encontró la interfaz visual: {WEB_UI_PATH}")

    try:
        from PyQt5.QtCore import QObject, Qt, QUrl, pyqtSlot
        from PyQt5.QtWebChannel import QWebChannel
        from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QProgressDialog
        from PyQt5.QtWebEngineWidgets import QWebEngineView
    except ImportError as exc:
        raise RuntimeError(
            "Falta el motor visual de escritorio. Ejecuta: "
            "python3 -m pip install -r requirements.txt"
        ) from exc

    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName("Quiz Studio")
    qt_app.setOrganizationName("Quiz Studio")

    class DesktopBridge(QObject):
        """Puente privado entre la interfaz y la persistencia local de Python.

        Qt WebChannel no expone un servidor HTTP: ambos lados viven dentro del
        mismo proceso de la aplicación. Cada método devuelve JSON para que la
        interfaz pueda actualizarse sin recargar la ventana.
        """

        def __init__(self, game_store: GameStore) -> None:
            super().__init__()
            self.store = game_store
            self.view: Optional[QWebEngineView] = None

        @staticmethod
        def _payload(value: Any) -> str:
            return json.dumps(value, ensure_ascii=False)

        @staticmethod
        def _decode(raw: str, fallback: Any) -> Any:
            try:
                parsed = json.loads(raw)
                return parsed
            except (TypeError, json.JSONDecodeError):
                return copy.deepcopy(fallback)

        @pyqtSlot(result=str)
        def getState(self) -> str:
            return self._payload({"games": self.store.list_games(), "sessions": self.store.list_sessions()})

        @pyqtSlot(float, result=str)
        def setZoom(self, zoom: float) -> str:
            """Zoom nativo de Qt WebEngine, igual en Windows y macOS."""
            factor = max(0.45, min(1.30, float(zoom)))
            if self.view is not None:
                self.view.setZoomFactor(factor)
            return self._payload({"zoom": factor})

        @pyqtSlot(str, result=str)
        def saveGame(self, raw_game: str) -> str:
            game = self._decode(raw_game, {})
            if not isinstance(game, dict):
                return self._payload({"error": "La configuración del juego no es válida."})
            return self._payload(self.store.save_game(game))

        @pyqtSlot(str, result=str)
        def duplicateGame(self, game_id: str) -> str:
            game = self.store.duplicate_game(game_id)
            return self._payload(game or {"error": "No se encontró el juego."})

        @pyqtSlot(str, result=str)
        def deleteGame(self, game_id: str) -> str:
            self.store.delete_game(game_id)
            return self._payload({"ok": True})

        @pyqtSlot(str, str, result=str)
        def startSession(self, game_id: str, raw_teams: str) -> str:
            game = self.store.get_game(game_id)
            teams = self._decode(raw_teams, [])
            if game is None:
                return self._payload({"error": "No se encontró el juego."})
            if not isinstance(teams, list):
                teams = game.get("teams", [])
            return self._payload(self.store.start_session(game, teams))

        @pyqtSlot(str, result=str)
        def updateSession(self, raw_session: str) -> str:
            session = self._decode(raw_session, {})
            if not isinstance(session, dict):
                return self._payload({"error": "La partida no es válida."})
            self.store.update_session(session)
            return self._payload(session)

        @pyqtSlot(str, result=str)
        def finishSession(self, raw_session: str) -> str:
            session = self._decode(raw_session, {})
            if not isinstance(session, dict):
                return self._payload({"error": "La partida no es válida."})
            return self._payload(self.store.finish_session(session))

        @pyqtSlot(str, result=str)
        def discardSession(self, session_id: str) -> str:
            self.store.discard_session(session_id)
            return self._payload({"ok": True})

        @pyqtSlot(result=str)
        def chooseImage(self) -> str:
            path, _selected_filter = QFileDialog.getOpenFileName(
                window,
                "Elegir imagen",
                "",
                "Imágenes (*.png *.jpg *.jpeg *.webp *.gif *.bmp)",
            )
            # Todas las llamadas del puente se consumen con JSON en la capa
            # visual. Mantener este contrato evita guardar objetos de error
            # como si fueran rutas de imágenes.
            return self._payload(self.store.import_image(path) if path else "")

    portable = _portable_context()

    class QuizWindow(QMainWindow):
        """Ventana principal con guardado especial para el .exe portable."""

        def __init__(self) -> None:
            super().__init__()
            self._portable_saved = False

        def closeEvent(self, event: Any) -> None:  # noqa: N802 - API Qt
            if portable is None or self._portable_saved:
                event.accept()
                return
            root, container = portable
            progress = QProgressDialog("Guardando los cambios dentro de este archivo…", None, 0, 0, self)
            progress.setWindowTitle("Quiz Studio")
            progress.setWindowModality(Qt.ApplicationModal)
            progress.setCancelButton(None)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            progress.show()
            qt_app.processEvents()
            try:
                _save_portable_copy(root, container)
            except OSError as exc:
                progress.close()
                QMessageBox.critical(
                    self,
                    "No se pudo guardar",
                    "Quiz Studio no pudo actualizar este archivo portable. "
                    "Muévelo a una carpeta donde tengas permiso para escribir, como Documentos, "
                    "y vuelve a cerrarlo.\n\nDetalle: " + str(exc),
                )
                event.ignore()
                return
            progress.close()
            self._portable_saved = True
            _schedule_portable_cleanup(root)
            if os.environ.get("QUIZ_STUDIO_PORTABLE_SHOW_FILE") == "1":
                try:
                    subprocess.Popen(["explorer.exe", "/select," + str(container)])
                except OSError:
                    pass
            event.accept()

    window = QuizWindow()
    window.setWindowTitle("Quiz Studio")
    window.setMinimumSize(1120, 680)
    window.resize(1600, 900)

    view = QWebEngineView(window)
    settings = view.settings()
    # Es contenido empaquetado por la app, no contenido remoto. JavaScript se
    # usa únicamente para cambiar entre las pantallas del prototipo visual.
    settings.setAttribute(settings.JavascriptEnabled, True)
    settings.setAttribute(settings.LocalContentCanAccessFileUrls, True)
    window.setCentralWidget(view)
    bridge = DesktopBridge(GameStore())
    bridge.view = view
    channel = QWebChannel(view.page())
    channel.registerObject("quizBridge", bridge)
    view.page().setWebChannel(channel)
    # QWebChannel y el puente deben vivir tanto como la ventana.
    window._desktop_bridge = bridge  # type: ignore[attr-defined]
    window._web_channel = channel  # type: ignore[attr-defined]
    # Cache-buster para desarrollo y para actualizaciones locales: WebEngine
    # no reutiliza una versión anterior de la interfaz tras reiniciar la app.
    interface_url = QUrl.fromLocalFile(str(WEB_UI_PATH))
    interface_url.setQuery(f"build={WEB_UI_PATH.stat().st_mtime_ns}")
    view.load(interface_url)
    window.show()
    sys.exit(qt_app.exec_())


if __name__ == "__main__":
    if "--legacy-tk" in sys.argv:
        QuizApp().mainloop()
    else:
        run_desktop_app()
