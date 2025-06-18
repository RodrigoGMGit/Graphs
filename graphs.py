#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graphs.py – Genera 4 gráficos (Calidad, Dedicación, Niveles de Madurez LEP,
TMD) filtrados por Chapter Leader.  Usa caché Parquet en «<DATA_DIR>/cached_files».

• DATA_DIR puede editarse a mano o indicarse por CLI con --root.
"""

from __future__ import annotations

import argparse
import os
import re
import unicodedata
from typing import cast

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import cm, colors

# ───────────── RUTAS BASE (editable) ─────────────
DATA_DIR = r"C:\Users\ROD\Documents\Projects\BCP\ChapterSyncFiles\S00001\2025 05"
CACHE_SUBDIR = "cached_files"

# Estas variables se recalculan si se pasa --root
FILES_DIR = DATA_DIR
CACHE_DIR = os.path.join(FILES_DIR, CACHE_SUBDIR)

# ───────────── CONFIG RESTO ─────────────
CHAPTER_LEADER = "ANTHONY JAESSON ROJAS MUNARES"
TMD_THRESHOLD = 13  # días

DEFAULT_CALIDAD = "Calidad__Pases a Producción y Reversiones – BCP TI 2025.xlsx"
DEFAULT_DEDICACION = "DR__Reporte_detallado_general.xlsx"
DEFAULT_MADUREZ = "NivelesMadurez__Reporte_NM_25_04_25.xlsx"
DEFAULT_TIEMPO = "TMD__BD Dashboard OKR T.Desarrollo-02.05.25.xlsx"

sns.set_theme(style="whitegrid", context="notebook")

MONTHS_ES = [
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
]
MONTH_CAT = pd.CategoricalDtype(categories=MONTHS_ES, ordered=True)


def _warn(msg: str) -> None:
    print(f"⚠️  {msg}")


# ─── Normalización de nombres ─────────────────────────────────────────
def normalize_name(txt: str | float) -> str:
    if not isinstance(txt, str):
        return ""
    txt = txt.split("(")[0]
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", txt).strip().upper()


CL_NORM = normalize_name(CHAPTER_LEADER)


def norm_series(s: pd.Series) -> pd.Series:
    return s.fillna("").map(normalize_name)


# ─── Caché Excel → Parquet ────────────────────────────────────────────
def _slugify(txt: str) -> str:
    norm = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w.\-]+", "_", norm)


def read_any(fp: str, **kw) -> pd.DataFrame:
    sheet = kw.get("sheet_name")
    base = os.path.splitext(os.path.basename(fp))[0]
    cache_name = f"{base}__{sheet}.parquet" if sheet else f"{base}.parquet"
    cache_path = os.path.join(CACHE_DIR, _slugify(cache_name))

    if os.path.isfile(cache_path):
        return pd.read_parquet(cache_path)

    if fp.lower().endswith(".parquet"):
        return pd.read_parquet(fp)

    df = pd.read_excel(fp, **kw)
    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].astype("string")
    os.makedirs(CACHE_DIR, exist_ok=True)  # asegura carpeta si ruta cambió por CLI
    df.reset_index(drop=True).to_parquet(cache_path, compression="snappy", index=False)
    return df


# ───────────── 1 · CALIDAD ─────────────
def plot_calidad_pases(file_name: str) -> None:
    fp = os.path.join(FILES_DIR, file_name)
    if fp.lower().endswith(".xlsx"):
        pases = read_any(fp, sheet_name="Consolidado Pases")
        revs = read_any(fp, sheet_name="Consolidado Reversiones")
    else:
        dfall = read_any(fp)
        pases = dfall[dfall["Tipo"] == "Pase a Producción"].copy()
        revs = dfall[dfall["Tipo"] == "Reversión"].copy()

    pases = pases[norm_series(pases["Chapter leader"]) == CL_NORM]
    revs = revs[norm_series(revs["Chapter leader"]) == CL_NORM]
    if pases.empty and revs.empty:
        return _warn("Sin datos de Calidad.")

    pases["Mes"] = pases["Mes"].astype(MONTH_CAT)
    revs["Mes"] = revs["Mes"].astype(MONTH_CAT)

    c_p = (
        pases.groupby(["Squad", "Mes"], observed=True).size().reset_index(name="passes")
    )
    c_r = revs.groupby(["Squad", "Mes"], observed=True).size().reset_index(name="revs")

    full = c_p.merge(c_r, on=["Squad", "Mes"], how="outer")
    full["passes"] = full["passes"].fillna(0).astype(int)
    full["revs"] = full["revs"].fillna(0).astype(int)
    full = full[(full["passes"] + full["revs"]) > 0]

    for sq in sorted(full["Squad"].unique()):
        d = full[full["Squad"] == sq].sort_values("Mes")
        plt.figure(figsize=(8, 4))
        plt.plot(d["Mes"].astype(str), d["passes"], marker="o", label="Pases")
        plt.plot(
            d["Mes"].astype(str), d["revs"], marker="x", ls="--", label="Reversiones"
        )
        plt.title(sq)
        plt.ylabel("Eventos")
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.show()


# ───────────── 2 · DEDICACIÓN ─────────────
def plot_dedicacion_tm(file_name: str) -> None:
    df = read_any(os.path.join(FILES_DIR, file_name))
    df = df[norm_series(df["Nombre CL"]) == CL_NORM]
    if df.empty:
        return _warn("Sin dedicación para CL.")

    avg = df.groupby("Nombres")["Dedicación"].mean().sort_values()
    plt.figure(figsize=(10, 6))
    plt.grid(axis="x", ls="--", alpha=0.4)
    bars = plt.barh(avg.index.tolist(), avg.values.tolist(), color="seagreen")
    for bar in bars:
        rect = cast(mpatches.Rectangle, bar)
        width = rect.get_width()  # type: ignore[attr-defined]
        plt.text(
            width + 0.03,
            rect.get_y() + rect.get_height() / 2,  # type: ignore[attr-defined]
            f"{width:.1f} h",
            va="center",
            fontsize=9,
        )
    plt.xlabel("Promedio de Dedicación (horas)")
    plt.title("Dedicación promedio por miembro de equipo")
    plt.tight_layout()
    plt.show()


# ───────────── 3 · NIVELES DE MADUREZ (LEP) ─────────────
def plot_niveles_madurez(file_name: str) -> None:
    df = read_any(os.path.join(FILES_DIR, file_name))
    df = df[norm_series(df["Chapter Leader"]) == CL_NORM]
    if df.empty:
        return _warn("Sin registros LEP para CL.")

    lep_cols = [c for c in df.columns if str(c).startswith("LEP_")]
    sq_candidates = [
        c
        for c in df.columns
        if c.upper() in {"SQ", "SQUAD", "SQUAD NAME", "NOMBRE SQUAD"}
    ]
    if not lep_cols or not sq_candidates:
        return _warn("Faltan columnas LEP_ o Squad.")
    SQ_COL = sq_candidates[0]

    group_sq = df.groupby(SQ_COL)[lep_cols].mean()
    group_sq["overall_avg"] = group_sq.mean(axis=1)
    group_sq = group_sq.sort_values("overall_avg", ascending=False).drop(
        columns="overall_avg"
    )

    melted_sq = group_sq.reset_index().melt(
        id_vars=SQ_COL,
        value_vars=lep_cols,
        var_name="Métrica LEP",
        value_name="Puntuación",
    )

    plt.figure(figsize=(14, 6))
    palette = sns.color_palette("Set2", len(lep_cols))
    ax = sns.barplot(
        data=melted_sq,
        y=SQ_COL,
        x="Puntuación",
        hue="Métrica LEP",
        palette=palette,
        dodge=True,
    )

    ax.set_title("Niveles de Madurez – Promedio LEP por Squad")
    ax.set_ylabel("Squad")
    ax.set_xlabel("Puntuación promedio")
    ax.grid(True, axis="x")

    for p in ax.patches:
        w = p.get_width()  # type: ignore[attr-defined]
        ax.annotate(
            f"{w:.2f}",
            (w, p.get_y() + p.get_height() / 2),  # type: ignore[attr-defined]
            ha="left",
            va="center",
            xytext=(3, 0),
            textcoords="offset points",
            fontsize=8,
        )

    plt.legend(title="Métrica LEP", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    plt.show()


# ───────────── 4 · TMD (estilo tmd.py) ─────────────
def _find_cl_column(df: pd.DataFrame) -> str | None:
    candidates = ["Nombre CL", "cl_dev", "Chapter leader", "Chapter Leader", "NombreCL"]
    for c in df.columns:
        if normalize_name(c) in map(normalize_name, candidates):
            return c
    return None


def _plot_tmd(series: pd.Series, title: str) -> None:
    vals: np.ndarray = series.astype(float).to_numpy()
    labels = series.index.tolist()
    max_val = np.nanmax(vals)

    cmap = cm.get_cmap("RdYlGn_r")
    norm = colors.Normalize(vmin=TMD_THRESHOLD, vmax=max_val)
    bar_colors = [cmap(norm(v)) for v in vals]

    plt.figure(figsize=(14, 6))
    ax = sns.barplot(y=labels, x=vals, palette=bar_colors)

    ax.set_title(title)
    ax.set_xlabel("Promedio de días")
    ax.set_ylabel("")

    ax.set_xticks(np.arange(0, int(np.ceil(max_val)) + 1, 1))
    ax.set_xlim(0, np.ceil(max_val) + 1)

    for p, v in zip(ax.patches, vals):
        ax.annotate(  # type: ignore[attr-defined]
            f"{v:.1f}",
            (v, p.get_y() + p.get_height() / 2),  # type: ignore[attr-defined]
            ha="left",
            va="center",
            xytext=(3, 0),
            textcoords="offset points",
            fontsize=9,
        )

    ax.axvline(TMD_THRESHOLD, color="black", linestyle="--", linewidth=1)

    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=ax, orientation="vertical", label="Días (rojo = peor)")
    plt.tight_layout()
    plt.show()


def plot_tiempo_desarrollo(file_name: str) -> None:
    df = read_any(os.path.join(FILES_DIR, file_name))

    cl_col = _find_cl_column(df)
    if cl_col is None:
        return _warn("No se encontró columna de Chapter Leader en TMD.")

    df = df[norm_series(df[cl_col]) == CL_NORM]
    if df.empty:
        return _warn("Sin datos de TMD para CL.")

    df["Tiempo Desarrollo"] = pd.to_numeric(df["Tiempo Desarrollo"], errors="coerce")

    squad_avg = (
        df.groupby("Descripción squad")["Tiempo Desarrollo"]
        .mean()
        .dropna()
        .sort_values(ascending=False)
    )

    tribe_avg = (
        df.groupby("Descripción tribu")["Tiempo Desarrollo"]
        .mean()
        .dropna()
        .sort_values(ascending=False)
    )

    _plot_tmd(
        tribe_avg,
        f"Tiempo de Desarrollo Promedio por Tribu (umbral {TMD_THRESHOLD} días)",
    )
    _plot_tmd(
        squad_avg,
        f"Tiempo de Desarrollo Promedio por Squad (umbral {TMD_THRESHOLD} días)",
    )


# ───────────── CLI ─────────────
def parse_args():
    p = argparse.ArgumentParser(description="Gráficos filtrados por Chapter Leader")
    p.add_argument("--root", help="Ruta base donde están los Excel", default=None)
    p.add_argument("--calidad", nargs="?", const=DEFAULT_CALIDAD)
    p.add_argument("--dedicacion", nargs="?", const=DEFAULT_DEDICACION)
    p.add_argument("--madurez", nargs="?", const=DEFAULT_MADUREZ)
    p.add_argument("--tiempo", nargs="?", const=DEFAULT_TIEMPO)
    return p.parse_args()


def main() -> None:
    global DATA_DIR, FILES_DIR, CACHE_DIR

    a = parse_args()
    if a.root:
        DATA_DIR = a.root
        FILES_DIR = DATA_DIR
        CACHE_DIR = os.path.join(FILES_DIR, CACHE_SUBDIR)
    os.makedirs(CACHE_DIR, exist_ok=True)  # crea caché (nuevo o default)

    tasks = [
        ("calidad", a.calidad, plot_calidad_pases),
        ("dedicacion", a.dedicacion, plot_dedicacion_tm),
        ("madurez", a.madurez, plot_niveles_madurez),
        ("tiempo", a.tiempo, plot_tiempo_desarrollo),
    ]

    if not any(fname for _, fname, _ in tasks):
        for k, _, fn in tasks:
            fn(globals()[f"DEFAULT_{k.upper()}"])
    else:
        for _, fname, fn in tasks:
            if fname:
                fn(fname)


if __name__ == "__main__":
    main()
