#!/usr/bin/env python3
# presentation_gui.py – v3.6.0  (19 Jun 2025)
# ---------------------------------------------------------------------------
# GUI ChapterSync  –  Dear PyGUI
#  • Hilo de fondo con spinner activo
#  • Perfiles persistentes (@dataclass → JSON)
#  • Márgenes interno izquierdo y derecho independientes
# ---------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import re
import runpy
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Tuple

import dearpygui.dearpygui as dpg

import graphs

# ╔══════════════════ CONFIG VISUAL  ═════════════════════════════════╗
LEFT_PAD = 20  # margen interno izquierdo
RIGHT_PAD = 20  # margen interno derecho
BASE_PAD = 12  # padding simétrico mínimo (Dear PyGUI sólo acepta 1 valor)

VERT_PAD = 16  # padding vertical para todas las ventanas
BTN_SPACING = 8  # separación horizontal entre botones

WIN_INIT_W, WIN_INIT_H = 560, 620
SPINNER_R = 8
SPINNER_D = SPINNER_R * 2 + 2
SPINNER_MG = 14  # separación extra del spinner al borde

FONT_SIZE, HEADER_FONT_SIZE = 17, 24

# Colores
COLOR_BG = (30, 35, 45, 255)
COLOR_HEADER = (52, 152, 219, 255)
COLOR_BTN = (41, 128, 185, 255)
COLOR_HOVER = (52, 152, 219, 255)
COLOR_ERR = (231, 76, 60, 255)
COLOR_WARN = (255, 215, 0, 255)
COLOR_INFO = (190, 190, 190, 255)

HINT_NAME = "Rene Ruben Plaz Cabrera"
HINT_EMAIL = "rplaz@bcp.com.pe"

EXECUTOR = ThreadPoolExecutor(max_workers=1)

# ╔══════════════════ RUTAS  ═════════════════════════════════════════╗
ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "chapter_config.json"
SYNC_ROOT = (ROOT_DIR.parent / "ChapterSyncFiles" / "S00001").resolve()
with suppress(Exception):
    if not SYNC_ROOT.exists():
        SYNC_ROOT = Path(graphs.DATA_DIR).resolve().parents[1]

PRESENTATION_SCRIPT = ROOT_DIR / "generate_presentation.py"
DEFAULT_MONTH_DIR = Path(graphs.DATA_DIR).name

# ╔══════════════════ TAGS  ══════════════════════════════════════════╗
(
    TAG_ROOT,
    TAG_SPINNER,
    TAG_COMBO_PROFILE,
    TAG_BTN_NEW,
    TAG_BTN_EDIT,
    TAG_BTN_DEL,
    TAG_INPUT_CL,
    TAG_INPUT_EMAIL,
    TAG_BTN_CANCEL,
    TAG_INFO,
    TAG_CHK_DEFAULT,
    TAG_COMBO_MONTH,
    TAG_BTN_GENERAR,
    TAG_BTN_OPEN_FOLDER,
    TAG_BTN_OPEN_PPTX,
    TAG_LBL_STATUS,
    TAG_LOG_CHILD,
) = (
    "##root",
    "##spinner",
    "##combo_profile",
    "##btn_new",
    "##btn_edit",
    "##btn_del",
    "##input_cl",
    "##input_email",
    "##btn_cancel",
    "##lbl_info",
    "##chk_default",
    "##combo_month",
    "##btn_generar",
    "##btn_open_folder",
    "##btn_open_pptx",
    "##lbl_status",
    "##log_child",
)

RESPONSIVE_TAGS = [
    TAG_ROOT,
    TAG_COMBO_PROFILE,
    TAG_INPUT_CL,
    TAG_INPUT_EMAIL,
    TAG_BTN_CANCEL,
    TAG_COMBO_MONTH,
    TAG_BTN_GENERAR,
    TAG_BTN_OPEN_FOLDER,
    TAG_BTN_OPEN_PPTX,
    TAG_LOG_CHILD,
]

# ╔══════════════════ PERFILES  ══════════════════════════════════════╗
EMAIL_RE = re.compile(r"^[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}$")


@dataclass
class Profile:
    name: str
    email: str
    validated: bool = False


def load_config() -> Tuple[List[Profile], str]:
    if not CONFIG_PATH.exists():
        return [], ""
    try:
        d = json.loads(CONFIG_PATH.read_text("utf-8"))
        return [Profile(**p) for p in d.get("profiles", [])], d.get("active", "")
    except Exception:
        return [], ""


PROFILES, ACTIVE_EMAIL = load_config()
EDIT_MODE: str | None = None  # "new"|"edit"|None


def save_config(active_email: str):
    CONFIG_PATH.write_text(
        json.dumps(
            {"active": active_email, "profiles": [asdict(p) for p in PROFILES]},
            indent=2,
        ),
        "utf-8",
    )


def prof_by_email(e: str) -> Profile | None:
    return next((p for p in PROFILES if p.email == e), None)


# ╔══════════════════ LOG helpers  ═══════════════════════════════════╗
def log_message(msg: str, level="info"):
    col = {"error": COLOR_ERR, "warn": COLOR_WARN}.get(level, COLOR_INFO)
    dpg.add_text(msg, parent=TAG_LOG_CHILD, color=col)
    if (children := dpg.get_item_children(TAG_LOG_CHILD, 1)) and len(children) > 500:
        dpg.delete_item(children[0])


graphs._warn = lambda m: log_message(m, "warn")  # type: ignore[attr-defined]


def set_status(msg: str, err=False):
    dpg.configure_item(
        TAG_LBL_STATUS, default_value=msg, color=COLOR_ERR if err else (255, 255, 255)
    )
    log_message(msg, "error" if err else "info")


# ╔══════════════════ UTILIDADES  ════════════════════════════════════╗
def listar_meses() -> List[str]:
    if not SYNC_ROOT.exists():
        return []
    pat = re.compile(r"^20\d{2} [01]\d$")
    return sorted(
        p.name for p in SYNC_ROOT.iterdir() if p.is_dir() and pat.match(p.name)
    )


def abrir_explorador(p: Path):
    if not p.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(p))  # type: ignore[attr-defined]
    elif sys.platform.startswith("darwin"):
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


def registrar_fuente():
    with dpg.font_registry():
        if os.name == "nt":
            arial = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts/arial.ttf"
            if arial.exists():
                normal = dpg.add_font(str(arial), FONT_SIZE)
                header = dpg.add_font(str(arial), HEADER_FONT_SIZE)
                dpg.bind_font(normal)
                return header
        header = dpg.add_font_default()  # type: ignore[attr-defined]
        dpg.bind_font(header)
        return header


# ╔══════════════════ CALLBACKS básicos  ═════════════════════════════╗
def refresh_combo():
    items = [p.name for p in PROFILES]
    dpg.configure_item(TAG_COMBO_PROFILE, items=items)
    if items:
        active = prof_by_email(ACTIVE_EMAIL)
        dpg.set_value(TAG_COMBO_PROFILE, active.name if active else items[0])


def on_profile_selected(_, sel, __):
    global ACTIVE_EMAIL
    if p := next((x for x in PROFILES if x.name == sel), None):
        ACTIVE_EMAIL = p.email
        hide_inputs()
        set_status(f"Perfil activo: {sel}")


def show_inputs(name="", email=""):
    dpg.set_value(TAG_INPUT_CL, name)
    dpg.set_value(TAG_INPUT_EMAIL, email)
    for t in (
        "lbl_nombre",
        TAG_INPUT_CL,
        "lbl_correo",
        TAG_INPUT_EMAIL,
        TAG_BTN_CANCEL,
        TAG_INFO,
    ):
        dpg.show_item(t)


def hide_inputs():
    for t in (
        "lbl_nombre",
        TAG_INPUT_CL,
        "lbl_correo",
        TAG_INPUT_EMAIL,
        TAG_BTN_CANCEL,
        TAG_INFO,
    ):
        dpg.hide_item(t)


def current_name_email() -> Tuple[str, str]:
    p = prof_by_email(ACTIVE_EMAIL)
    return (p.name, p.email) if p else ("", "")


# ── CRUD botones perfil ─────────────────────────────────────────────
def on_new(*_):
    global EDIT_MODE
    EDIT_MODE = "new"
    show_inputs()


def on_edit(*_):
    global EDIT_MODE
    if not ACTIVE_EMAIL:
        return
    EDIT_MODE = "edit"
    show_inputs(*current_name_email())


def on_del(*_):
    global PROFILES, ACTIVE_EMAIL
    if not ACTIVE_EMAIL:
        return
    PROFILES = [p for p in PROFILES if p.email != ACTIVE_EMAIL]
    ACTIVE_EMAIL = PROFILES[0].email if PROFILES else ""
    save_config(ACTIVE_EMAIL)
    refresh_combo()
    hide_inputs()
    set_status("Perfil eliminado.")


def on_cancel(*_):
    global EDIT_MODE
    EDIT_MODE = None
    hide_inputs()


# ╔══════════════════ GENERACIÓN PPT  (hilo)  ════════════════════════╗
def _gen_ppt(cl, email, mes):
    try:
        graphs.CHAPTER_LEADER, graphs.CHAPTER_LEADER_EMAIL = cl, email
        graphs.CL_NORM = graphs.normalize_name(cl)
        graphs.DATA_DIR = str(SYNC_ROOT / mes)
        graphs.FILES_DIR = graphs.DATA_DIR
        graphs.CACHE_DIR = os.path.join(graphs.FILES_DIR, graphs.CACHE_SUBDIR)

        runpy.run_path(str(PRESENTATION_SCRIPT))
        dst = SYNC_ROOT / mes / "outputs"
        dst.mkdir(exist_ok=True)
        src = ROOT_DIR / "outputs"
        pptxs = [Path(shutil.copy2(p, dst / p.name)) for p in src.glob("*.pptx")]
        if not pptxs:
            return False, "No se generó .pptx", None, None
        ultimo = max(pptxs, key=lambda p: p.stat().st_mtime)
        return True, "Presentación generada.", str(dst), str(ultimo)
    except Exception as exc:
        return False, f"Error: {exc}", None, None


# ─── util cross-thread → hilo GUI ────────────────────────────────────
def _invoke(func, *args):
    """
    Ejecuta `func(*args)` en el hilo principal cualquiera que sea la
    versión de Dear PyGUI.

    Orden de prueba:
      1. invoke_callback   (≥ 1.4)
      2. invoke_deferred   (≥ 1.3)
      3. add_render_callback (≥ 0.8, < 1.3)
      4. set_render_callback  (≤ 0.8  y también en 2.0.0)
      5. llamada directa    (fallback extremo)
    """

    # 1-2  (no existen en 2.0.0, pero por si actualizas)
    if hasattr(dpg, "invoke_callback"):
        dpg.invoke_callback(func, *args)  # type: ignore[attr-defined]
        return
    if hasattr(dpg, "invoke_deferred"):
        dpg.invoke_deferred(func, *args)  # type: ignore[attr-defined]
        return

    # 3  (series 0.8–1.2)
    if hasattr(dpg, "add_render_callback"):
        token = []

        def _once():
            func(*args)
            dpg.delete_item(token[0])  # type: ignore[attr-defined]

        token.append(dpg.add_render_callback(_once))  # type: ignore[attr-defined]
        return

    # 4  (≤0.8  y  2.0.x alpha/beta)
    if hasattr(dpg, "set_render_callback"):

        def _once(sender, data):
            func(*args)
            dpg.set_render_callback(None)  # type: ignore[attr-defined]

        dpg.set_render_callback(_once)  # type: ignore[attr-defined]
        return

    # 5  – último recurso (no recomendable, pero evita crash)
    func(*args)


def generar_cb(*_):
    global EDIT_MODE, ACTIVE_EMAIL
    dpg.configure_item(TAG_BTN_OPEN_FOLDER, show=False)
    dpg.configure_item(TAG_BTN_OPEN_PPTX, show=False)
    set_status("")
    dpg.configure_item(TAG_SPINNER, show=True)

    cl, email = (
        (dpg.get_value(TAG_INPUT_CL).strip(), dpg.get_value(TAG_INPUT_EMAIL).strip())
        if dpg.is_item_shown(TAG_INPUT_CL)
        else current_name_email()
    )
    mes = (
        DEFAULT_MONTH_DIR
        if dpg.get_value(TAG_CHK_DEFAULT)
        else dpg.get_value(TAG_COMBO_MONTH)
    )

    if not SYNC_ROOT.exists():
        return _err(f"Ruta no encontrada: {SYNC_ROOT}")
    if not cl:
        return _err("Nombre vacío")
    if not EMAIL_RE.fullmatch(email):
        return _err("Email inválido")
    if not mes:
        return _err("Mes no seleccionado")

    future = EXECUTOR.submit(_gen_ppt, cl, email, mes)
    future.add_done_callback(lambda fut: _invoke(on_done, fut, cl, email))


def on_done(fut, cl, email):
    ok, msg, dst, ppt = fut.result()
    dpg.configure_item(TAG_SPINNER, show=False)
    if not ok:
        return _err(msg)

    global EDIT_MODE, ACTIVE_EMAIL
    if EDIT_MODE == "new":
        PROFILES.append(Profile(cl, email, True))
        ACTIVE_EMAIL = email
    elif EDIT_MODE == "edit":
        if p := prof_by_email(ACTIVE_EMAIL):
            p.name, p.email, p.validated = cl, email, True
            ACTIVE_EMAIL = email
    else:
        if p := prof_by_email(email):
            p.validated = True

    EDIT_MODE = None
    save_config(ACTIVE_EMAIL)
    refresh_combo()
    hide_inputs()
    if dst and ppt:
        dpg.configure_item(TAG_BTN_OPEN_FOLDER, user_data=dst, show=True)
        dpg.configure_item(TAG_BTN_OPEN_PPTX, user_data=ppt, show=True)
        log_message(f"Archivo copiado a {dst}")
    set_status(msg)


def _err(m):
    set_status(m, True)
    dpg.configure_item(TAG_SPINNER, show=False)


# ╔══════════════════ RESIZE  ════════════════════════════════════════╗
def resize_cb(_, data):
    if isinstance(data, (list, tuple)):
        w, h = data[:2]
    elif isinstance(data, dict):
        w = data.get("viewport_width") or dpg.get_viewport_client_width()
        h = data.get("viewport_height") or dpg.get_viewport_client_height()
    else:
        w, h = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()

    usable_w = max(320, w - LEFT_PAD - RIGHT_PAD)
    usable_h = max(300, h - 2 * VERT_PAD)

    dpg.configure_item(TAG_ROOT, width=w, height=h)  # la ventana ocupa todo el viewport

    for t in RESPONSIVE_TAGS:
        if dpg.does_item_exist(t):
            dpg.configure_item(t, width=usable_w)

    each = max(int((usable_w - 2 * BTN_SPACING) / 3), 80)
    for t in (TAG_BTN_NEW, TAG_BTN_EDIT, TAG_BTN_DEL):
        dpg.configure_item(t, width=each)

    dpg.configure_item(TAG_INFO, wrap=usable_w)

    dpg.set_item_pos(  # type: ignore[arg-type]
        TAG_SPINNER,
        [
            LEFT_PAD + usable_w - SPINNER_D - SPINNER_MG,
            VERT_PAD + usable_h - SPINNER_D - SPINNER_MG,
        ],
    )


# ╔══════════════════ BUILD UI  ══════════════════════════════════════╗
def build_ui():
    # --- tema global ---
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLOR_BG)
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, BASE_PAD, VERT_PAD)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, BTN_SPACING, 6)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLOR_BTN)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLOR_HOVER)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 6)
    dpg.bind_theme(theme)

    header_font = registrar_fuente()

    with dpg.window(
        tag=TAG_ROOT,
        label="Generar Presentación",
        width=WIN_INIT_W,
        height=WIN_INIT_H,
        no_collapse=True,
        no_resize=False,
    ):
        dpg.add_loading_indicator(radius=SPINNER_R, tag=TAG_SPINNER, show=False)

        dpg.add_spacer(height=4)
        title = dpg.add_text("ChapterSync", color=COLOR_HEADER)
        if header_font:
            dpg.bind_item_font(title, header_font)
        dpg.add_text("Generación de PPT")
        dpg.add_separator()

        dpg.add_text("Perfil activo:")
        dpg.add_combo([], tag=TAG_COMBO_PROFILE, callback=on_profile_selected)
        refresh_combo()

        with dpg.group(horizontal=True):
            dpg.add_button(label="Nuevo", tag=TAG_BTN_NEW, callback=on_new)
            dpg.add_button(label="Editar", tag=TAG_BTN_EDIT, callback=on_edit)
            dpg.add_button(label="Eliminar", tag=TAG_BTN_DEL, callback=on_del)

        dpg.add_text("Nombre del Chapter Leader:", tag="lbl_nombre", show=False)
        dpg.add_input_text(tag=TAG_INPUT_CL, hint=HINT_NAME, show=False)
        dpg.add_text("Correo del Chapter Leader:", tag="lbl_correo", show=False)
        dpg.add_input_text(tag=TAG_INPUT_EMAIL, hint=HINT_EMAIL, show=False)

        dpg.add_text(
            "Los cambios se guardarán automáticamente\ncuando la presentación se genere correctamente.",
            tag=TAG_INFO,
            wrap=WIN_INIT_W,
            color=(200, 200, 200),
            show=False,
        )
        dpg.add_button(
            label="Cancelar", tag=TAG_BTN_CANCEL, callback=on_cancel, show=False
        )

        dpg.add_checkbox(
            label="Usar carpeta para demo",
            default_value=True,
            tag=TAG_CHK_DEFAULT,
            callback=lambda s, c, u: dpg.configure_item(TAG_COMBO_MONTH, show=not c),
        )
        dpg.add_combo(
            listar_meses(),
            label="Selecciona mes",
            default_value=DEFAULT_MONTH_DIR
            if DEFAULT_MONTH_DIR in listar_meses()
            else "",
            tag=TAG_COMBO_MONTH,
            show=False,
        )

        dpg.add_spacer(height=6)
        dpg.add_button(
            label="Generar presentación", tag=TAG_BTN_GENERAR, callback=generar_cb
        )
        dpg.add_button(
            label="Abrir carpeta",
            tag=TAG_BTN_OPEN_FOLDER,
            callback=lambda s, a, p: abrir_explorador(Path(str(p))),
            show=False,
        )
        dpg.add_button(
            label="Abrir presentación",
            tag=TAG_BTN_OPEN_PPTX,
            callback=lambda s, a, p: abrir_explorador(Path(str(p))),
            show=False,
        )

        dpg.add_text("", tag=TAG_LBL_STATUS)
        dpg.add_separator()

        dpg.add_text("Registro de mensajes:")
        dpg.add_child_window(tag=TAG_LOG_CHILD, height=140, border=True)

    (
        dpg.add_viewport_resize_callback  # type: ignore[attr-defined]
        if hasattr(dpg, "add_viewport_resize_callback")
        else dpg.set_viewport_resize_callback
    )(resize_cb)

    with dpg.handler_registry():
        dpg.add_key_press_handler(
            dpg.mvKey_Escape, callback=lambda *_: dpg.stop_dearpygui()
        )
        dpg.add_key_press_handler(dpg.mvKey_Return, callback=generar_cb)


# ╔══════════════════ MAIN  ══════════════════════════════════════════╗
if __name__ == "__main__":
    dpg.create_context()
    build_ui()
    dpg.create_viewport(
        title="ChapterSync Generador de PPT",
        width=WIN_INIT_W,
        height=WIN_INIT_H,
        resizable=True,
    )
    dpg.set_primary_window(TAG_ROOT, True)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
