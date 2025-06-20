#!/usr/bin/env python3
# presentation_gui.py – v3.1.0  (19 Jun 2025)
# ---------------------------------------------------------------------------
# Interfaz DearPyGui – ChapterSync Generator
# • Perfiles múltiples (combo, nuevo, editar, eliminar)
# • Placeholders
# • Panel de LOG (scroll) para avisos que el usuario puede solucionar
# ---------------------------------------------------------------------------

from __future__ import annotations

import json
import os
import re
import runpy
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import List

import dearpygui.dearpygui as dpg

import graphs

# ╔═════════════════════  CONFIG BÁSICA  ══════════════════════════════╗
ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "chapter_config.json"
SYNC_ROOT = (ROOT_DIR.parent / "ChapterSyncFiles" / "S00001").resolve()
if not SYNC_ROOT.exists():
    with suppress(Exception):
        SYNC_ROOT = Path(graphs.DATA_DIR).resolve().parents[1]

PRESENTATION_SCRIPT = ROOT_DIR / "generate_presentation.py"
DEFAULT_MONTH_DIR = Path(graphs.DATA_DIR).name

WINDOW_W, WINDOW_H = 560, 620  # +altura por log
FONT_SIZE, HEADER_FONT_SIZE = 17, 24

COLOR_BG = (30, 35, 45, 255)
COLOR_HEADER = (52, 152, 219, 255)
COLOR_BTN = (41, 128, 185, 255)
COLOR_BTN_HOV = (52, 152, 219, 255)
COLOR_ERR = (231, 76, 60, 255)
COLOR_WARN = (255, 215, 0, 255)
COLOR_INFO = (190, 190, 190, 255)

HINT_NAME = "Rene Ruben Plaz Cabrera"
HINT_EMAIL = "rplaz@bcp.com.pe"

# ───── Tags ──────────────────────────────────────────────────────────
(
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
    TAG_SPINNER,
    TAG_LOG_CHILD,
) = (
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
    "##spinner",
    "##log_child",
)


# ╔════════════════════  PERFILES (config)  ═══════════════════════════╗
def load_config() -> tuple[List[dict], str]:
    if not CONFIG_PATH.exists():
        return [], ""
    with suppress(Exception):
        data = json.loads(CONFIG_PATH.read_text("utf-8"))
        if "profiles" in data:
            return data["profiles"], data.get("active", "")
        if "chapter_leader" in data:  # migración formato viejo
            prof = {
                "name": data["chapter_leader"],
                "email": data.get("email", ""),
                "validated": data.get("validated", False),
            }
            save_config([prof], prof["email"])
            return [prof], prof["email"]
    return [], ""


def save_config(profiles: List[dict], active_email: str) -> None:
    CONFIG_PATH.write_text(
        json.dumps({"active": active_email, "profiles": profiles}, indent=2), "utf-8"
    )


PROFILES, ACTIVE_EMAIL = load_config()
EDIT_MODE: str | None = None  # None | "new" | "edit"


def get_profile_by_email(email: str) -> dict | None:
    return next((p for p in PROFILES if p["email"] == email), None)


# ╔════════════════════  LOG helpers  ═════════════════════════════════╗
def log_message(msg: str, level: str = "info"):
    color = {"error": COLOR_ERR, "warn": COLOR_WARN, "info": COLOR_INFO}.get(
        level, COLOR_INFO
    )
    dpg.add_text(msg, parent=TAG_LOG_CHILD, color=color)

    # Limitar a 1000 líneas de forma segura
    children_all = dpg.get_item_children(TAG_LOG_CHILD)
    slot1 = children_all[1] if children_all and len(children_all) > 1 else []
    if len(slot1) > 1000:
        dpg.delete_item(slot1[0])


def clear_log():
    children_all = dpg.get_item_children(TAG_LOG_CHILD)
    slot1 = children_all[1] if children_all and len(children_all) > 1 else []
    for cid in slot1:
        dpg.delete_item(cid)


# Parchar graphs._warn para redirigir a log
def _patch_graphs_warn():
    def _gui_warn(msg: str):
        log_message(msg, "warn")

    graphs._warn = _gui_warn  # type: ignore[attr-defined]


_patch_graphs_warn()


# ╔════════════════════  UTILIDADES GENERALES  ════════════════════════╗
def listar_meses() -> List[str]:
    if not SYNC_ROOT.exists():
        return []
    return sorted(
        p.name
        for p in SYNC_ROOT.iterdir()
        if p.is_dir() and re.match(r"^20\d{2} [01]\d$", p.name)
    )


def abrir_explorador(r: Path):
    if not r.exists():
        return
    if sys.platform.startswith("win"):
        os.startfile(str(r))  # type: ignore[attr-defined]
    elif sys.platform.startswith("darwin"):
        subprocess.Popen(["open", str(r)])
    else:
        subprocess.Popen(["xdg-open", str(r)])


def registrar_fuente():
    with dpg.font_registry():
        path = None
        if os.name == "nt":
            cand = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf"
            if cand.exists():
                path = str(cand)
        if path:
            normal = dpg.add_font(path, FONT_SIZE)
            header = dpg.add_font(path, HEADER_FONT_SIZE)
            dpg.bind_font(normal)
            return header
        try:
            normal = header = dpg.add_font_default()  # type: ignore[attr-defined]
            dpg.bind_font(normal)
            return header
        except AttributeError:
            return None


def theme_global():
    with dpg.theme() as t:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, COLOR_BG)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 12)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 5)
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, COLOR_BTN)
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, COLOR_BTN_HOV)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 6)
    dpg.bind_theme(t)


def set_status(msg: str, err=False):
    dpg.configure_item(
        TAG_LBL_STATUS, default_value=msg, color=COLOR_ERR if err else (255, 255, 255)
    )
    log_message(msg, "error" if err else "info")


def validate_email(email: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()))


# ╔════════════════════  UI HELPERS (perfil)  ═════════════════════════╗
def refresh_profile_combo():
    names = [p["name"] for p in PROFILES]
    dpg.configure_item(TAG_COMBO_PROFILE, items=names)
    if not names:
        return
    active_name = (
        get_profile_by_email(ACTIVE_EMAIL)["name"] if ACTIVE_EMAIL else names[0]
    )
    dpg.configure_item(TAG_COMBO_PROFILE, default_value=active_name)


def show_inputs(name="", email=""):
    dpg.set_value(TAG_INPUT_CL, name)
    dpg.set_value(TAG_INPUT_EMAIL, email)
    for it in (
        "lbl_nombre",
        TAG_INPUT_CL,
        "lbl_correo",
        TAG_INPUT_EMAIL,
        TAG_BTN_CANCEL,
        TAG_INFO,
    ):
        dpg.show_item(it)


def hide_inputs():
    for it in (
        "lbl_nombre",
        TAG_INPUT_CL,
        "lbl_correo",
        TAG_INPUT_EMAIL,
        TAG_BTN_CANCEL,
        TAG_INFO,
    ):
        dpg.hide_item(it)


def current_name_email() -> tuple[str, str]:
    p = get_profile_by_email(ACTIVE_EMAIL)
    return (p["name"], p["email"]) if p else ("", "")


# ╔════════════════════  CALLBACKS — perfiles  ════════════════════════╗
def on_profile_selected(s, a, u):
    global ACTIVE_EMAIL
    if not PROFILES:
        return
    ACTIVE_EMAIL = next(p["email"] for p in PROFILES if p["name"] == a)
    hide_inputs()
    set_status(f"Perfil activo: {a}")


def on_new_profile(s, a, u):
    global EDIT_MODE
    EDIT_MODE = "new"
    show_inputs()


def on_edit_profile(s, a, u):
    global EDIT_MODE
    if not ACTIVE_EMAIL:
        return
    EDIT_MODE = "edit"
    name, email = current_name_email()
    show_inputs(name, email)


def on_delete_profile(s, a, u):
    global PROFILES, ACTIVE_EMAIL
    if not ACTIVE_EMAIL:
        return
    PROFILES = [p for p in PROFILES if p["email"] != ACTIVE_EMAIL]
    ACTIVE_EMAIL = PROFILES[0]["email"] if PROFILES else ""
    save_config(PROFILES, ACTIVE_EMAIL)
    refresh_profile_combo()
    hide_inputs()
    set_status("Perfil eliminado.")


def on_cancel(s, a, u):
    global EDIT_MODE
    EDIT_MODE = None
    hide_inputs()


# ╔════════════════════  CALLBACKS — otros  ═══════════════════════════╗
def toggle_combo_cb(s, a, u):
    dpg.configure_item(TAG_COMBO_MONTH, show=not a)


def abrir_carpeta_cb(s, a, u):
    abrir_explorador(Path(u))


def abrir_pptx_cb(s, a, u):
    abrir_explorador(Path(u))


# ╔════════════════════  CALLBACK — Generar PPT  ══════════════════════╗
def generar_cb(*_):
    global PROFILES, ACTIVE_EMAIL, EDIT_MODE
    clear_log()  # limpiar log
    # Obtener nombre/correo
    if dpg.is_item_shown(TAG_INPUT_CL):
        cl = dpg.get_value(TAG_INPUT_CL).strip()
        email = dpg.get_value(TAG_INPUT_EMAIL).strip()
    else:
        cl, email = current_name_email()

    demo = dpg.get_value(TAG_CHK_DEFAULT)
    mes = DEFAULT_MONTH_DIR if demo else dpg.get_value(TAG_COMBO_MONTH)

    for t in (TAG_BTN_OPEN_FOLDER, TAG_BTN_OPEN_PPTX):
        dpg.configure_item(t, show=False)
    set_status("")
    dpg.configure_item(TAG_SPINNER, show=True)

    # Validaciones
    if not SYNC_ROOT.exists():
        set_status(f"Ruta raíz no encontrada: {SYNC_ROOT}", err=True)
        return end_spinner()
    if not cl:
        set_status("Nombre del Chapter Leader vacío", err=True)
        return end_spinner()
    if not validate_email(email):
        set_status("Correo electrónico inválido", err=True)
        return end_spinner()
    if not mes:
        set_status("Mes no seleccionado", err=True)
        return end_spinner()

    log_message(f"Generando presentación para {cl} ({mes})", "info")

    graphs.CHAPTER_LEADER = cl
    graphs.CHAPTER_LEADER_EMAIL = email
    graphs.CL_NORM = graphs.normalize_name(cl)
    graphs.DATA_DIR = str(SYNC_ROOT / mes)
    graphs.FILES_DIR = graphs.DATA_DIR
    graphs.CACHE_DIR = os.path.join(graphs.FILES_DIR, graphs.CACHE_SUBDIR)

    try:
        runpy.run_path(str(PRESENTATION_SCRIPT))
    except Exception as exc:
        set_status(f"Error al generar PPT: {exc}", err=True)
        return end_spinner()

    src, dst = ROOT_DIR / "outputs", SYNC_ROOT / mes / "outputs"
    dst.mkdir(exist_ok=True)
    pptxs = [shutil.copy2(p, dst / p.name) for p in src.glob("*.pptx")]
    if not pptxs:
        set_status("No se encontró ningún .pptx generado", err=True)
        return end_spinner()
    ultimo = max(pptxs, key=lambda p: p.stat().st_mtime)

    # Actualizar perfiles
    if EDIT_MODE == "new":
        PROFILES.append({"name": cl, "email": email, "validated": True})
        ACTIVE_EMAIL = email
    elif EDIT_MODE == "edit":
        for p in PROFILES:
            if p["email"] == ACTIVE_EMAIL:
                p.update({"name": cl, "email": email, "validated": True})
                ACTIVE_EMAIL = email
                break
    else:
        prof = get_profile_by_email(email)
        prof["validated"] = True if prof else None

    save_config(PROFILES, ACTIVE_EMAIL)
    refresh_profile_combo()
    hide_inputs()
    EDIT_MODE = None
    dpg.configure_item(TAG_SPINNER, show=False)
    dpg.configure_item(TAG_BTN_OPEN_FOLDER, user_data=str(dst), show=True)
    dpg.configure_item(TAG_BTN_OPEN_PPTX, user_data=str(ultimo), show=True)
    set_status("Presentación generada y perfil actualizado.")
    log_message(f"Archivo copiado a {dst}", "info")


def end_spinner():
    dpg.configure_item(TAG_SPINNER, show=False)


# ╔════════════════════  BUILD UI  ════════════════════════════════════╗
def build_ui():
    header = registrar_fuente()
    theme_global()
    with dpg.window(
        label="Generar Presentación",
        width=WINDOW_W,
        height=WINDOW_H,
        no_resize=True,
        no_collapse=True,
    ):
        dpg.add_spacer(height=6)
        t = dpg.add_text("ChapterSync", color=COLOR_HEADER)
        dpg.bind_item_font(t, header) if header else None
        dpg.add_text("Generación de PPT")
        dpg.add_separator()

        dpg.add_text("Perfil activo:")
        dpg.add_combo(
            [p["name"] for p in PROFILES],
            tag=TAG_COMBO_PROFILE,
            width=-1,
            callback=on_profile_selected,
        )
        refresh_profile_combo()
        with dpg.group(horizontal=True):
            dpg.add_button(label="Nuevo", tag=TAG_BTN_NEW, callback=on_new_profile)
            dpg.add_button(label="Editar", tag=TAG_BTN_EDIT, callback=on_edit_profile)
            dpg.add_button(
                label="Eliminar", tag=TAG_BTN_DEL, callback=on_delete_profile
            )

        # Inputs ocultos
        dpg.add_text("Nombre del Chapter Leader:", tag="lbl_nombre", show=False)
        dpg.add_input_text(tag=TAG_INPUT_CL, hint=HINT_NAME, width=-1, show=False)
        dpg.add_text("Correo del Chapter Leader:", tag="lbl_correo", show=False)
        dpg.add_input_text(tag=TAG_INPUT_EMAIL, hint=HINT_EMAIL, width=-1, show=False)
        dpg.add_text(
            "Los cambios se guardarán automáticamente\ncuando la presentación se genere correctamente.",
            tag=TAG_INFO,
            wrap=WINDOW_W - 40,
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
            callback=toggle_combo_cb,
        )
        meses = listar_meses()
        dpg.add_combo(
            meses,
            label="Selecciona mes",
            default_value=DEFAULT_MONTH_DIR if DEFAULT_MONTH_DIR in meses else "",
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
        )
        dpg.add_button(
            label="Abrir presentación",
            tag=TAG_BTN_OPEN_PPTX,
            show=False,
            callback=abrir_pptx_cb,
        )

        # Spinner
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=(WINDOW_W - 22) // 2)
            try:
                dpg.add_loading_indicator(radius=11, tag=TAG_SPINNER, show=False)
            except AttributeError:
                dpg.add_progress_bar(
                    width=22, default_value=0.5, overlay="", tag=TAG_SPINNER, show=False
                )

        dpg.add_text("", tag=TAG_LBL_STATUS)

        # ─── PANEL DE LOG ───
        dpg.add_separator()
        dpg.add_text("Registro de mensajes:")
        dpg.add_child_window(
            tag=TAG_LOG_CHILD, autosize_x=True, height=140, border=True
        )

    with dpg.handler_registry():
        dpg.add_key_press_handler(
            dpg.mvKey_Escape, callback=lambda *_: dpg.stop_dearpygui()
        )
        dpg.add_key_press_handler(dpg.mvKey_Return, callback=generar_cb)


# ╔════════════════════  MAIN  ════════════════════════════════════════╗
if __name__ == "__main__":
    dpg.create_context()
    build_ui()
    dpg.create_viewport(
        title="ChapterSync Generador de PPT", width=WINDOW_W, height=WINDOW_H
    )
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
