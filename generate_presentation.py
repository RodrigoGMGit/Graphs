#!/usr/bin/env python3
# generate_presentation.py  —  versión final con TMD apilado (sin estirar)

import datetime as dt
import io
import os
from copy import deepcopy
from typing import List, cast

import matplotlib.pyplot as plt
from pptx import Presentation as _Presentation
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.shapes.autoshape import Shape
from pptx.slide import Slide as PPTSlide
from pptx.util import Emu, Inches

import graphs

TEMPLATE_PATH = r".\inputs\Template.pptx"
OUTPUT_DIR = r".\outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PLACEHOLDER_TYPES = {
    PP_PLACEHOLDER.PICTURE,
    PP_PLACEHOLDER.BODY,
    PP_PLACEHOLDER.OBJECT,
}


# ───────── capturar cada plt.show() ─────────
def capture(fn):
    bufs: List[io.BytesIO] = []
    orig = plt.show

    def _cap(*a, **k):  # noqa: ANN001
        b = io.BytesIO()
        plt.savefig(b, format="png", dpi=150, bbox_inches="tight")
        b.seek(0)
        bufs.append(b)
        plt.close()

    plt.show = _cap
    fn()
    plt.show = orig
    return bufs


# ───────── helpers ─────────
def insert_best(slide: PPTSlide, img: io.BytesIO, sw: Emu, sh: Emu) -> None:
    for ph in slide.placeholders:
        if ph.placeholder_format.type in PLACEHOLDER_TYPES:
            cast(Shape, ph).insert_picture(img)  # type: ignore[attr-defined]
            return
    # fallback: centrado bajo título
    left, top = Inches(0.5), Inches(1.0)
    slide.shapes.add_picture(img, left, top, cast(Emu, sw - Inches(1.0)))  # type: ignore[arg-type]


def grid_insert(slide, rect, bufs, idx):
    l, t, w, h = rect
    gap = Inches(0.15)
    cw, ch = cast(Emu, (w - gap) // 2), cast(Emu, (h - gap) // 2)
    for r in range(2):
        for c in range(2):
            if idx >= len(bufs):
                return idx
            slide.shapes.add_picture(
                bufs[idx],
                cast(Emu, l + c * (cw + gap)),
                cast(Emu, t + r * (ch + gap)),
                cw,
                ch,
            )  # type: ignore[arg-type]
            idx += 1
    return idx


def clone_slide(prs, slide):
    ns = prs.slides.add_slide(slide.slide_layout)
    for shp in slide.shapes:
        if shp.is_placeholder and shp.placeholder_format.type == PP_PLACEHOLDER.TITLE:
            ns.shapes._spTree.insert_element_before(deepcopy(shp.element), "p:extLst")
            break
    return ns


# ───────── obtener imágenes ─────────
def _imgs(key, fn):
    p = graphs._resolve_path(None, key)
    return capture(lambda: fn(p)) if p else []


imgs_mad = _imgs("madurez", graphs.plot_niveles_madurez)
imgs_ded = _imgs("dedicacion", graphs.plot_dedicacion_tm)
imgs_tmd = _imgs("tiempo", graphs.plot_tiempo_desarrollo)  # 2
imgs_cal = _imgs("calidad", graphs.plot_calidad_pases)  # N

# ───────── plantilla ─────────
prs = _Presentation(TEMPLATE_PATH)
SW: Emu = cast(Emu, prs.slide_width)
SH: Emu = cast(Emu, prs.slide_height)

# ───────── Madurez & Dedicación ─────────
if imgs_mad:
    insert_best(prs.slides[2], imgs_mad[0], SW, SH)
if imgs_ded:
    insert_best(prs.slides[3], imgs_ded[0], SW, SH)

# ───────── TMD – apilado sin estirar ─────────
if len(imgs_tmd) >= 2:
    s5 = prs.slides[4]

    # anchura igual a la usada antes en el formato lado-a-lado
    margin_h = Inches(0.5)
    gap_v = Inches(0.25)
    pic_w = cast(Emu, (SW - 2 * margin_h - Inches(0.25)) // 2)  # misma mitad de slide
    left_c = cast(Emu, (SW - pic_w) // 2)  # centrado
    top_1 = Inches(1.0)

    # primer gráfico
    shape1 = s5.shapes.add_picture(imgs_tmd[0], left_c, top_1, pic_w)  # type: ignore[arg-type]
    # segundo gráfico debajo, respetando gap_v
    top_2 = cast(Emu, shape1.top + shape1.height + gap_v)
    s5.shapes.add_picture(imgs_tmd[1], left_c, top_2, pic_w)  # type: ignore[arg-type]

# ───────── Calidad (slide 6 y clones) ─────────
if imgs_cal:
    base = prs.slides[5]
    ph = next(
        (
            p
            for p in base.placeholders
            if p.placeholder_format.type in PLACEHOLDER_TYPES
        ),
        None,
    )
    rect = (
        (ph.left, ph.top, ph.width, ph.height)
        if ph
        else (
            Inches(0.5),
            Inches(1.3),
            cast(Emu, SW - Inches(1.0)),
            cast(Emu, SH - Inches(1.8)),
        )
    )
    idx, cur, cur_rect = 0, base, rect
    while idx < len(imgs_cal):
        idx = grid_insert(cur, cur_rect, imgs_cal, idx)
        if idx < len(imgs_cal):
            cur = clone_slide(prs, base)

# ───────── guardar ─────────
out = os.path.join(
    OUTPUT_DIR, dt.datetime.today().strftime("%Y-%m-%d_Presentation.pptx")
)
prs.save(out)
print(f"\n✅ Presentación generada en {out}\n")
