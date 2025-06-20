#!/usr/bin/env python3
# presentation_gui.py – v2.4.6  (19 Jun 2025)
# ---------------------------------------------------------------------------
# Interfaz DearPyGui para generar presentaciones de Chapter Leaders (ChapterSync)
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
import re
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

import dearpygui.dearpygui as dpg

import graphs

# ────────── Configuración ──────────
ROOT_DIR = Path(__file__).resolve().parent
SYNC_ROOT = (ROOT_DIR.parent / "ChapterSyncFiles" / "S00001").resolve()
if not SYNC_ROOT.exists():
    try:
        SYNC_ROOT = Path(graphs.DATA_DIR).resolve().parents[1]
    except Exception:
        pass

PRESENTATION_SCRIPT = ROOT_DIR / "generate_presentation.py"
DEFAULT_MONTH_DIR = Path(graphs.DATA_DIR).name  # ‘2025 05’

WINDOW_W, WINDOW_H = 560, 500  # Aumentar altura para acomodar nuevo campo
FONT_SIZE, HEADER_FONT_SIZE = 17, 24

COLOR_BG = (30, 35, 45, 255)
COLOR_HEADER = (52, 152, 219, 255)
COLOR_BTN = (41, 128, 185, 255)
COLOR_BTN_HOV = (52, 152, 219, 255)
COLOR_ERR = (231, 76, 60, 255)

# Tags
TAG_INPUT_CL, TAG_INPUT_EMAIL, TAG_CHK_DEFAULT, TAG_COMBO_MONTH = (
    "##input_cl",
    "##input_email",  # Nuevo tag para el correo
    "##chk_default",
    "##combo_month",
)
TAG_BTN_GENERAR, TAG_BTN_OPEN_FOLDER, TAG_BTN_OPEN_PPTX = (
    "##btn_generar",
    "##btn_open_folder",
    "##btn_open_pptx",
)
TAG_LBL_STATUS, TAG_SPINNER = "##lbl_status", "##spinner"


# ────────── Utilidades ──────────
def listar_meses() -> List[str]:
    if not SYNC_ROOT.exists():
        return []
    pat = re.compile(r"^20\d{2} [01]\d$")
    return sorted(
        p.name for p in SYNC_ROOT.iterdir() if p.is_dir() and pat.match(p.name)
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


def set_error(msg: str):
    dpg.configure_item(TAG_LBL_STATUS, default_value=msg, color=COLOR_ERR)


# ────────── Validación de correo ──────────
def validate_email(email: str) -> bool:
    """Valida que el correo tenga un formato básico (contiene @ y dominio)."""
    email = email.strip()
    if not email:
        return False
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))


# ────────── Callbacks ──────────
def abrir_carpeta_cb(s, a, u):
    abrir_explorador(Path(u))


def abrir_pptx_cb(s, a, u):
    abrir_explorador(Path(u))


def toggle_combo_cb(s, a, u):
    dpg.configure_item(TAG_COMBO_MONTH, show=not a)


def generar_cb(s=None, a=None, u=None):
    cl = dpg.get_value(TAG_INPUT_CL).strip()
    email = dpg.get_value(TAG_INPUT_EMAIL).strip()
    useD = dpg.get_value(TAG_CHK_DEFAULT)
    mes = DEFAULT_MONTH_DIR if useD else dpg.get_value(TAG_COMBO_MONTH)

    # Reset UI
    dpg.configure_item(TAG_BTN_OPEN_FOLDER, show=False)
    dpg.configure_item(TAG_BTN_OPEN_PPTX, show=False)
    dpg.configure_item(TAG_LBL_STATUS, default_value="")
    dpg.configure_item(TAG_SPINNER, show=True)

    # Validaciones
    if not SYNC_ROOT.exists():
        set_error(f"⚠ Carpeta raíz {SYNC_ROOT} no encontrada")
        dpg.configure_item(TAG_SPINNER, show=False)
        return
    if not cl:
        set_error("⚠ Ingresa el nombre del Chapter Leader")
        dpg.configure_item(TAG_SPINNER, show=False)
        return
    if not validate_email(email):
        set_error("⚠ Ingresa un correo electrónico válido")
        dpg.configure_item(TAG_SPINNER, show=False)
        return
    if not mes:
        set_error("⚠ Selecciona un mes válido")
        dpg.configure_item(TAG_SPINNER, show=False)
        return

    graphs.CHAPTER_LEADER = cl
    graphs.CHAPTER_LEADER_EMAIL = email  # Pasar el correo a graphs.py
    graphs.CL_NORM = graphs.normalize_name(cl)
    graphs.DATA_DIR = str(SYNC_ROOT / mes)
    graphs.FILES_DIR = graphs.DATA_DIR
    graphs.CACHE_DIR = os.path.join(graphs.FILES_DIR, graphs.CACHE_SUBDIR)

    try:
        runpy.run_path(str(PRESENTATION_SCRIPT))
    except Exception as exc:
        set_error(f"❌ Error: {exc}")
        dpg.configure_item(TAG_SPINNER, show=False)
        return

    src, dst = ROOT_DIR / "outputs", SYNC_ROOT / mes / "outputs"
    dst.mkdir(exist_ok=True)
    pptxs = []
    for p in src.glob("*.pptx"):
        dest = dst / p.name
        shutil.copy2(p, dest)
        pptxs.append(dest)
    if not pptxs:
        set_error("⚠ No se encontró ningún .pptx para copiar")
        dpg.configure_item(TAG_SPINNER, show=False)
        return
    pptxs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    ultimo = pptxs[0]

    # Éxito
    dpg.configure_item(TAG_SPINNER, show=False)
    dpg.configure_item(TAG_BTN_OPEN_FOLDER, user_data=str(dst), show=True)
    dpg.configure_item(TAG_BTN_OPEN_PPTX, user_data=str(ultimo), show=True)


# ────────── UI principal ──────────
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
        h = dpg.add_text("ChapterSync", color=COLOR_HEADER)
        if header:
            dpg.bind_item_font(h, header)
        dpg.add_text("Generación de PPT")
        dpg.add_separator()

        dpg.add_text("Nombre del Chapter Leader:")
        dpg.add_input_text(
            tag=TAG_INPUT_CL,
            default_value=graphs.CHAPTER_LEADER,
            on_enter=True,
            width=-1,
        )

        dpg.add_text("Correo del Chapter Leader:")  # Nuevo campo
        dpg.add_input_text(
            tag=TAG_INPUT_EMAIL,
            default_value=graphs.CHAPTER_LEADER_EMAIL,
            on_enter=True,
            width=-1,
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

        # Botones abrir (hidden)
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

        # Spinner centrado
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=(WINDOW_W - 22) // 2)  # 22 ≈ diámetro del spinner
            try:
                dpg.add_loading_indicator(radius=11, tag=TAG_SPINNER, show=False)
            except AttributeError:
                dpg.add_progress_bar(
                    width=22, default_value=0.5, overlay="", tag=TAG_SPINNER, show=False
                )

        dpg.add_text("", tag=TAG_LBL_STATUS)

    with dpg.handler_registry():
        dpg.add_key_press_handler(
            dpg.mvKey_Escape, callback=lambda *_: dpg.stop_dearpygui()
        )
        dpg.add_key_press_handler(dpg.mvKey_Return, callback=generar_cb)


# ────────── main ──────────
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
