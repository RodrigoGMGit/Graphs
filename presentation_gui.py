"""
GUI para generar presentaciones de Chapter Leaders con DearPyGui.

Ejecuta:
    python presentation_gui.py

Requisitos (ya instalados en tu venv):
    pip install dearpygui python-pptx matplotlib numpy pandas seaborn openpyxl

Genera la presentación con `generate_presentation.py`, copia el archivo *.pptx* a la
carpeta correspondiente del mes seleccionado, por ejemplo:
    C:/.../ChapterSyncFiles/S00001/2025 04/outputs/
"""

from __future__ import annotations

import os
import re
import runpy
import shutil
from pathlib import Path
from typing import List

import dearpygui.dearpygui as dpg

import graphs

# ────────────────────────────────────────────────────────────────────────────────
# Ajustes de estilo
# ────────────────────────────────────────────────────────────────────────────────


def _register_default_font() -> None:
    """Asegura una fuente predeterminada legible en todas las versiones."""

    with dpg.font_registry():
        if hasattr(dpg, "add_font_default"):
            font = dpg.add_font_default()
        else:
            ttf = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"
            font = dpg.add_font(str(ttf), 17) if ttf.exists() else None

    if font is not None:
        dpg.bind_font(font)


# ────────────────────────────────────────────────────────────────────────────────
# Utilidades
# ────────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(graphs.DATA_DIR).parents[0]  # .../S00001
DEFAULT_MONTH_DIR = Path(graphs.DATA_DIR).name  # "2025 05"
PRESENTATION_SCRIPT = Path(__file__).with_name("generate_presentation.py")
OUTPUTS_SRC_DIR = Path(__file__).with_name("outputs")  # donde genera por defecto

re_month = re.compile(r"^\d{4} \d{2}$")  # ej. "2025 05"


def list_month_dirs() -> list[str]:
    """Devuelve subdirectorios con patrón "YYYY MM" ordenados desc."""
    return sorted(
        [p.name for p in ROOT_DIR.iterdir() if p.is_dir() and re_month.match(p.name)],
        reverse=True,
    )


def _copiar_presentaciones(origen: Path, destino: Path) -> List[Path]:
    """Copia todos los *.pptx* de *origen* a *destino* y devuelve las rutas nuevas."""
    if not origen.is_dir():
        return []

    destino.mkdir(parents=True, exist_ok=True)
    copiados: List[Path] = []
    for ppt in origen.glob("*.pptx"):
        dst = destino / ppt.name
        try:
            shutil.copy2(ppt, dst)
            copiados.append(dst)
        except Exception:
            # Si no se puede copiar un archivo concreto, continuamos con los demás
            continue
    return copiados


# ────────────────────────────────────────────────────────────────────────────────
# Callbacks
# ────────────────────────────────────────────────────────────────────────────────


def generate_presentation_callback(sender, app_data, user_data):  # noqa: D401
    """Recolecta entradas de la GUI y lanza el script de presentación."""

    chapter_leader = dpg.get_value("##input_cl").strip()
    if not chapter_leader:
        dpg.configure_item(
            "##lbl_status", default_value="❌ Ingresa el nombre del Chapter Leader."
        )
        return

    use_default = dpg.get_value("##chk_default")
    month_dir = DEFAULT_MONTH_DIR if use_default else dpg.get_value("##combo_month")

    # ─── Actualizar variables globales en graphs ───────────────────────
    graphs.CHAPTER_LEADER = chapter_leader
    graphs.CL_NORM = graphs.normalize_name(chapter_leader)

    graphs.DATA_DIR = str(ROOT_DIR / month_dir)
    graphs.FILES_DIR = graphs.DATA_DIR
    graphs.CACHE_DIR = os.path.join(graphs.FILES_DIR, graphs.CACHE_SUBDIR)

    # ─── Ejecutar generación ──────────────────────────────────────────
    try:
        runpy.run_path(str(PRESENTATION_SCRIPT))
    except Exception as exc:  # pragma: no cover – uso interactivo
        dpg.configure_item(
            "##lbl_status", default_value=f"❌ Error al generar presentación: {exc}"
        )
        return

    # ─── Copiar *.pptx* a la carpeta del mes ──────────────────────────
    destino_out = Path(graphs.DATA_DIR) / "outputs"
    copiados = _copiar_presentaciones(OUTPUTS_SRC_DIR, destino_out)

    if copiados:
        msg = f"✅ Presentación copiada a: {destino_out}"
    else:
        msg = "⚠️  No se encontró ningún .pptx para copiar. Verifica la generación."

    dpg.configure_item("##lbl_status", default_value=msg)


# ────────────────────────────────────────────────────────────────────────────────
# Construcción de la interfaz
# ────────────────────────────────────────────────────────────────────────────────


def build_gui() -> None:
    _register_default_font()

    with dpg.window(label="Generador de Presentaciones", width=520, height=280):
        dpg.add_text("Nombre del Chapter Leader:")
        dpg.add_input_text(tag="##input_cl", width=320)

        dpg.add_separator()

        dpg.add_checkbox(
            label=f"Usar carpeta por defecto ({DEFAULT_MONTH_DIR})",
            tag="##chk_default",
            default_value=True,
            callback=lambda s, a: dpg.configure_item(
                "##combo_month", show=not dpg.get_value("##chk_default")
            ),
        )

        dpg.add_combo(
            list_month_dirs(),
            tag="##combo_month",
            default_value=DEFAULT_MONTH_DIR,
            show=False,
            width=160,
            label="Selecciona el mes:",
        )

        dpg.add_spacing(count=2)
        dpg.add_button(
            label="Generar presentación",
            callback=generate_presentation_callback,
            width=220,
        )
        dpg.add_spacing(count=1)
        dpg.add_text(tag="##lbl_status", default_value="")


# ────────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport(title="Chapter Presentation Builder", width=540, height=320)
    build_gui()
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
