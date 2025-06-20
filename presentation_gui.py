#!/usr/bin/env python3
# presentation_gui.py – v3.5.2  (19 Jun 2025)
# ---------------------------------------------------------------------------
# GUI ChapterSync – presentaciones PPT con Dear PyGUI
#  • Hilo de fondo (spinner activo) – ThreadPoolExecutor
#  • Perfiles persistentes (@dataclass → JSON)
#  • Padding interno ampliado (16 px) para evitar corte de botones/spinner
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

# ╔═══════════════════════  CONSTANTES & RUTAS  ═══════════════════════╗
ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "chapter_config.json"
SYNC_ROOT = (ROOT_DIR.parent / "ChapterSyncFiles" / "S00001").resolve()
if not SYNC_ROOT.exists():
    with suppress(Exception):
        SYNC_ROOT = Path(graphs.DATA_DIR).resolve().parents[1]

PRESENTATION_SCRIPT = ROOT_DIR / "generate_presentation.py"
DEFAULT_MONTH_DIR = Path(graphs.DATA_DIR).name

WIN_INIT_W, WIN_INIT_H = 560, 620

# ─── Padding interno mayor (16 px) ────────────────────────────────────
INNER_MARGIN = 25  # ← antes 10 px
SPINNER_R = 8
SPINNER_D = SPINNER_R * 2 + 2
SPINNER_MG = 12  # margen extra para spinner

FONT_SIZE, HEADER_FONT_SIZE = 17, 24

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

# ╔═══════════════════════  TAGS  ════════════════════════════════════╗
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
    "##root_window",
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

# ╔═══════════════════════  PERFILES  ════════════════════════════════╗
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
        data = json.loads(CONFIG_PATH.read_text("utf-8"))
        profiles = [Profile(**p) for p in data.get("profiles", [])]
        return profiles, data.get("active", "")
    except Exception as exc:
        print("Config corrupta:", exc)
        return [], ""


def save_config(profiles: List[Profile], active_email: str) -> None:
    CONFIG_PATH.write_text(
        json.dumps(
            {"active": active_email, "profiles": [asdict(p) for p in profiles]},
            indent=2,
        ),
        "utf-8",
    )


PROFILES, ACTIVE_EMAIL = load_config()
EDIT_MODE: str | None = None  # "new" | "edit" | None


def get_profile_by_email(email: str) -> Profile | None:
    return next((p for p in PROFILES if p.email == email), None)


# ╔═══════════════════════  LOG helpers  ══════════════════════════════╗
def log_message(msg: str, level="info"):
    color = {"error": COLOR_ERR, "warn": COLOR_WARN}.get(level, COLOR_INFO)
    dpg.add_text(msg, parent=TAG_LOG_CHILD, color=color)
    children = dpg.get_item_children(TAG_LOG_CHILD, 1) or []
    if len(children) > 500:
        dpg.delete_item(children[0])


def clear_log():
    for cid in dpg.get_item_children(TAG_LOG_CHILD, 1) or []:
        dpg.delete_item(cid)


graphs._warn = lambda m: log_message(m, "warn")  # type: ignore[attr-defined]


# ╔═══════════════════════  UTILIDADES  ══════════════════════════════╗
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
        header = dpg.add_font_default()
        dpg.bind_font(header)
        return header


def set_status(msg: str, err: bool = False):
    dpg.configure_item(
        TAG_LBL_STATUS,
        default_value=msg,
        color=COLOR_ERR if err else (255, 255, 255),
    )
    log_message(msg, "error" if err else "info")


# ╔═══════════════════════  UI helpers  ══════════════════════════════╗
def refresh_profile_combo():
    names = [p.name for p in PROFILES]
    dpg.configure_item(TAG_COMBO_PROFILE, items=names)
    if names:
        active = get_profile_by_email(ACTIVE_EMAIL)
        dpg.set_value(TAG_COMBO_PROFILE, active.name if active else names[0])


def show_inputs(name: str = "", email: str = ""):
    dpg.set_value(TAG_INPUT_CL, name)
    dpg.set_value(TAG_INPUT_EMAIL, email)
    for tag in (
        "lbl_nombre",
        TAG_INPUT_CL,
        "lbl_correo",
        TAG_INPUT_EMAIL,
        TAG_BTN_CANCEL,
        TAG_INFO,
    ):
        dpg.show_item(tag)


def hide_inputs():
    for tag in (
        "lbl_nombre",
        TAG_INPUT_CL,
        "lbl_correo",
        TAG_INPUT_EMAIL,
        TAG_BTN_CANCEL,
        TAG_INFO,
    ):
        dpg.hide_item(tag)


def current_name_email() -> Tuple[str, str]:
    prof = get_profile_by_email(ACTIVE_EMAIL)
    return (prof.name, prof.email) if prof else ("", "")


# ╔══════════════  CALLBACKS – perfiles  ═════════════════════════════╗
def on_profile_selected(_, selected, __):
    global ACTIVE_EMAIL
    prof = next((p for p in PROFILES if p.name == selected), None)
    if prof:
        ACTIVE_EMAIL = prof.email
        hide_inputs()
        set_status(f"Perfil activo: {selected}")


def on_new_profile(*_):
    global EDIT_MODE
    EDIT_MODE = "new"
    show_inputs()


def on_edit_profile(*_):
    global EDIT_MODE
    if not ACTIVE_EMAIL:
        return
    EDIT_MODE = "edit"
    n, e = current_name_email()
    show_inputs(n, e)


def on_delete_profile(*_):
    global PROFILES, ACTIVE_EMAIL
    if not ACTIVE_EMAIL:
        return
    PROFILES = [p for p in PROFILES if p.email != ACTIVE_EMAIL]
    ACTIVE_EMAIL = PROFILES[0].email if PROFILES else ""
    save_config(PROFILES, ACTIVE_EMAIL)
    refresh_profile_combo()
    hide_inputs()
    set_status("Perfil eliminado.")


def on_cancel(*_):
    global EDIT_MODE
    EDIT_MODE = None
    hide_inputs()


# ╔══════════════  CALLBACKS varios  ═════════════════════════════════╗
toggle_combo_cb = lambda _, checked, __: dpg.configure_item(
    TAG_COMBO_MONTH, show=not checked
)
abrir_carpeta_cb = lambda _, __, path: abrir_explorador(Path(str(path)))
abrir_pptx_cb = lambda _, __, path: abrir_explorador(Path(str(path)))


# ╔══════════════  BACKGROUND TASK  ══════════════════════════════════╗
def _generate_presentation(cl: str, email: str, mes: str):
    try:
        graphs.CHAPTER_LEADER = cl
        graphs.CHAPTER_LEADER_EMAIL = email
        graphs.CL_NORM = graphs.normalize_name(cl)
        graphs.DATA_DIR = str(SYNC_ROOT / mes)
        graphs.FILES_DIR = graphs.DATA_DIR
        graphs.CACHE_DIR = os.path.join(graphs.FILES_DIR, graphs.CACHE_SUBDIR)

        runpy.run_path(str(PRESENTATION_SCRIPT))
        src = ROOT_DIR / "outputs"
        dst = SYNC_ROOT / mes / "outputs"
        dst.mkdir(exist_ok=True)
        pptxs = [Path(shutil.copy2(p, dst / p.name)) for p in src.glob("*.pptx")]
        if not pptxs:
            return False, "No se encontró ningún .pptx generado", None, None
        ultimo = max(pptxs, key=lambda p: p.stat().st_mtime)
        return True, "Presentación generada.", str(dst), str(ultimo)
    except Exception as exc:
        return False, f"Error al generar PPT: {exc}", None, None


def _invoke(func, *args):
    """
    Llama `func(*args)` desde el hilo GUI principal.  Usa la API disponible
    según la versión de Dear PyGUI; si no existe ni `invoke_callback` ni
    `invoke_deferred`, hace un _fallback_ seguro: programa el wrapper con
    `add_render_callback` (>=0.8) y, si tampoco está, lo ejecuta directamente
    (último recurso).
    """
    if hasattr(dpg, "invoke_callback"):
        dpg.invoke_callback(func, *args)
    elif hasattr(dpg, "invoke_deferred"):
        dpg.invoke_deferred(func, *args)
    elif hasattr(dpg, "add_render_callback"):
        wrapper_id = []

        def wrapper():
            func(*args)
            # autodestruir el callback para que sólo corra una vez
            dpg.delete_item(wrapper_id[0])

        wrapper_id.append(dpg.add_render_callback(wrapper))
    else:  # Fallback extremo (puede no ser 100 % thread-safe en versiones muy antiguas)
        func(*args)


# ╔══════════════  CALLBACK – Generar PPT  ═══════════════════════════╗
def generar_cb(*_):
    global EDIT_MODE, ACTIVE_EMAIL, PROFILES
    clear_log()

    if dpg.is_item_shown(TAG_INPUT_CL):
        cl = dpg.get_value(TAG_INPUT_CL).strip()
        email = dpg.get_value(TAG_INPUT_EMAIL).strip()
    else:
        cl, email = current_name_email()

    mes = (
        DEFAULT_MONTH_DIR
        if dpg.get_value(TAG_CHK_DEFAULT)
        else dpg.get_value(TAG_COMBO_MONTH)
    )

    for t in (TAG_BTN_OPEN_FOLDER, TAG_BTN_OPEN_PPTX):
        dpg.configure_item(t, show=False)
    set_status("")
    dpg.configure_item(TAG_SPINNER, show=True)

    if not SYNC_ROOT.exists():
        return _err(f"Ruta raíz no encontrada: {SYNC_ROOT}")
    if not cl:
        return _err("Nombre del Chapter Leader vacío")
    if not EMAIL_RE.fullmatch(email):
        return _err("Correo electrónico inválido")
    if not mes:
        return _err("Mes no seleccionado")

    log_message(f"Generando presentación para {cl} ({mes})", "info")
    future = EXECUTOR.submit(_generate_presentation, cl, email, mes)
    future.add_done_callback(lambda fut: _invoke(on_done_generation, fut, cl, email))


def on_done_generation(fut, cl: str, email: str):
    success, msg, dst, ultimo = fut.result()
    dpg.configure_item(TAG_SPINNER, show=False)
    if not success:
        return _err(msg)

    global EDIT_MODE, ACTIVE_EMAIL
    if EDIT_MODE == "new":
        PROFILES.append(Profile(name=cl, email=email, validated=True))
        ACTIVE_EMAIL = email
    elif EDIT_MODE == "edit":
        pr = get_profile_by_email(ACTIVE_EMAIL)
        if pr:
            pr.name, pr.email, pr.validated = cl, email, True
            ACTIVE_EMAIL = email
    else:
        pr = get_profile_by_email(email)
        if pr:
            pr.validated = True

    save_config(PROFILES, ACTIVE_EMAIL)
    refresh_profile_combo()
    hide_inputs()
    EDIT_MODE = None

    if dst and ultimo:
        dpg.configure_item(TAG_BTN_OPEN_FOLDER, user_data=dst, show=True)
        dpg.configure_item(TAG_BTN_OPEN_PPTX, user_data=ultimo, show=True)
        log_message(f"Archivo copiado a {dst}", "info")
    set_status(msg)


def _err(msg: str):
    set_status(msg, True)
    dpg.configure_item(TAG_SPINNER, show=False)


# ╔══════════════  CALLBACK – resize  ════════════════════════════════╗
def resize_cb(sender, app_data):
    if isinstance(app_data, (list, tuple)):
        w, h = app_data[:2]
    elif isinstance(app_data, dict):
        w = (
            app_data.get("viewport_width")
            or app_data.get("width")
            or dpg.get_viewport_client_width()
        )
        h = (
            app_data.get("viewport_height")
            or app_data.get("height")
            or dpg.get_viewport_client_height()
        )
    else:
        w = dpg.get_viewport_client_width()
        h = dpg.get_viewport_client_height()

    usable_w = max(320, w - 2 * INNER_MARGIN)
    usable_h = max(300, h - 2 * INNER_MARGIN)

    dpg.configure_item(
        TAG_ROOT,
        width=usable_w + 2 * INNER_MARGIN,
        height=usable_h + 2 * INNER_MARGIN,
    )

    for tag in RESPONSIVE_TAGS:
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, width=usable_w)

    each = max(int((usable_w - 2 * 8) / 3), 80)
    for tag in (TAG_BTN_NEW, TAG_BTN_EDIT, TAG_BTN_DEL):
        dpg.configure_item(tag, width=each)

    dpg.configure_item(TAG_INFO, wrap=usable_w)

    dpg.set_item_pos(
        TAG_SPINNER,
        (
            INNER_MARGIN + usable_w - SPINNER_D - SPINNER_MG,
            INNER_MARGIN + usable_h - SPINNER_D - SPINNER_MG,
        ),
    )


# ╔══════════════  BUILD UI  ═════════════════════════════════════════╗
def build_ui():
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLOR_BG)
            dpg.add_theme_style(
                dpg.mvStyleVar_WindowPadding, INNER_MARGIN, INNER_MARGIN
            )
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)
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
        width=WIN_INIT_W + 2 * INNER_MARGIN,
        height=WIN_INIT_H + 2 * INNER_MARGIN,
        no_collapse=True,
        no_resize=False,
    ):
        dpg.add_loading_indicator(
            radius=SPINNER_R,
            tag=TAG_SPINNER,
            show=False,
            pos=(
                INNER_MARGIN + WIN_INIT_W - SPINNER_D - SPINNER_MG,
                INNER_MARGIN + WIN_INIT_H - SPINNER_D - SPINNER_MG,
            ),
        )

        dpg.add_spacer(height=6)
        title = dpg.add_text("ChapterSync", color=COLOR_HEADER)
        if header_font:
            dpg.bind_item_font(title, header_font)
        dpg.add_text("Generación de PPT")
        dpg.add_separator()

        dpg.add_text("Perfil activo:")
        dpg.add_combo([], tag=TAG_COMBO_PROFILE, width=-1, callback=on_profile_selected)
        refresh_profile_combo()

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Nuevo", tag=TAG_BTN_NEW, callback=on_new_profile, width=-1
            )
            dpg.add_button(
                label="Editar", tag=TAG_BTN_EDIT, callback=on_edit_profile, width=-1
            )
            dpg.add_button(
                label="Eliminar", tag=TAG_BTN_DEL, callback=on_delete_profile, width=-1
            )

        dpg.add_text("Nombre del Chapter Leader:", tag="lbl_nombre", show=False)
        dpg.add_input_text(tag=TAG_INPUT_CL, hint=HINT_NAME, width=-1, show=False)
        dpg.add_text("Correo del Chapter Leader:", tag="lbl_correo", show=False)
        dpg.add_input_text(tag=TAG_INPUT_EMAIL, hint=HINT_EMAIL, width=-1, show=False)

        dpg.add_text(
            "Los cambios se guardarán automáticamente\n"
            "cuando la presentación se genere correctamente.",
            tag=TAG_INFO,
            wrap=WIN_INIT_W,
            color=(200, 200, 200),
            show=False,
        )
        dpg.add_button(
            label="Cancelar",
            tag=TAG_BTN_CANCEL,
            callback=on_cancel,
            show=False,
            width=-1,
        )

        dpg.add_checkbox(
            label="Usar carpeta para demo",
            default_value=True,
            tag=TAG_CHK_DEFAULT,
            callback=toggle_combo_cb,
        )
        dpg.add_combo(
            listar_meses(),
            label="Selecciona mes",
            default_value=DEFAULT_MONTH_DIR
            if DEFAULT_MONTH_DIR in listar_meses()
            else "",
            tag=TAG_COMBO_MONTH,
            width=-1,
            show=False,
        )

        dpg.add_spacer(height=8)
        dpg.add_button(
            label="Generar presentación",
            tag=TAG_BTN_GENERAR,
            callback=generar_cb,
            width=-1,
        )
        dpg.add_button(
            label="Abrir carpeta",
            tag=TAG_BTN_OPEN_FOLDER,
            show=False,
            callback=abrir_carpeta_cb,
            width=-1,
        )
        dpg.add_button(
            label="Abrir presentación",
            tag=TAG_BTN_OPEN_PPTX,
            show=False,
            callback=abrir_pptx_cb,
            width=-1,
        )

        dpg.add_text("", tag=TAG_LBL_STATUS)
        dpg.add_separator()

        dpg.add_text("Registro de mensajes:")
        dpg.add_child_window(tag=TAG_LOG_CHILD, width=-1, height=140, border=True)

    (
        dpg.add_viewport_resize_callback
        if hasattr(dpg, "add_viewport_resize_callback")
        else dpg.set_viewport_resize_callback
    )(resize_cb)

    with dpg.handler_registry():
        dpg.add_key_press_handler(
            dpg.mvKey_Escape, callback=lambda *_: dpg.stop_dearpygui()
        )
        dpg.add_key_press_handler(dpg.mvKey_Return, callback=generar_cb)


# ╔══════════════  MAIN  ═════════════════════════════════════════════╗
if __name__ == "__main__":
    dpg.create_context()
    build_ui()
    dpg.create_viewport(
        title="ChapterSync Generador de PPT",
        resizable=True,
        width=WIN_INIT_W + 2 * INNER_MARGIN,
        height=WIN_INIT_H + 2 * INNER_MARGIN,
    )
    dpg.set_primary_window(TAG_ROOT, True)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
