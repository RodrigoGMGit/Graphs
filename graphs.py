#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graphs.py – Genera gráficas de:
• Calidad  (0-N gráficos)
• Dedicación
• Niveles de Madurez LEP
• TMD (2 gráficos)

Además:
• Busca automáticamente los .xlsx en DATA_DIR por palabra-clave.
• Usa caché Parquet en <DATA_DIR>/cached_files.
• Exporte _resolve_path() para que otros scripts (p.ej. generate_presentation.py)
  obtengan la ruta del archivo adecuado sin correr parse_args.
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

FILES_DIR = DATA_DIR
CACHE_DIR = os.path.join(FILES_DIR, CACHE_SUBDIR)

# Palabras-clave -> método
FILE_KEYWORDS = {
    "calidad": "CALIDAD",
    "dedicacion": "DR",
    "madurez": "NIVELESMADUREZ",
    "tiempo": "TMD",
}

# ───────────── CONFIG RESTO ─────────────
CHAPTER_LEADER = "ANTHONY JAESSON ROJAS MUNARES"
CHAPTER_LEADER_EMAIL = ""  # Nueva variable para el correo electrónico
TMD_THRESHOLD = 13  # días

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


# ─── Normalización genérica ───────────────────────────────────────────
def _normalize(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return re.sub(r"\s+", "", txt).upper()


def normalize_name(txt: str | float) -> str:
    if not isinstance(txt, str):
        return ""
    txt = txt.split("(")[0]
    return _normalize(txt)


CL_NORM = normalize_name(CHAPTER_LEADER)


def norm_series(s: pd.Series) -> pd.Series:
    return s.fillna("").map(normalize_name)


# ─── Búsqueda automática de archivos ──────────────────────────────────
def _find_file_by_keyword(keyword: str) -> str | None:
    """Busca en FILES_DIR un único .xlsx cuyo nombre contenga keyword (normalizado)."""
    files = [f for f in os.listdir(FILES_DIR) if f.lower().endswith(".xlsx")]
    matches = [f for f in files if keyword in _normalize(f)]
    if len(matches) == 1:
        return os.path.join(FILES_DIR, matches[0])
    if len(matches) == 0:
        _warn(f"No se encontró archivo con «{keyword}» en {FILES_DIR}")
    else:
        _warn(f"Hay múltiples archivos con «{keyword}»; corrige antes de continuar")
    return None


def _resolve_path(cli_arg: str | None, task_key: str) -> str | None:
    """Devuelve ruta absoluta al .xlsx para el método indicado."""
    if cli_arg:
        return cli_arg if os.path.isabs(cli_arg) else os.path.join(FILES_DIR, cli_arg)
    return _find_file_by_keyword(FILE_KEYWORDS[task_key])


# ─── Caché Excel → Parquet ────────────────────────────────────────────
def _slugify(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w.\-]+", "_", txt)


def read_any(fp: str, **kw) -> pd.DataFrame:
    sheet = kw.get("sheet_name")
    base = os.path.splitext(os.path.basename(fp))[0]
    cache_name = f"{base}__{sheet}.parquet" if sheet else f"{base}.parquet"
    cache_path = os.path.join(CACHE_DIR, _slugify(cache_name))

    if os.path.isfile(cache_path):
        return pd.read_parquet(cache_path)

    df = pd.read_excel(fp, **kw)
    obj_cols = df.select_dtypes(include="object").columns
    df[obj_cols] = df[obj_cols].astype("string")
    os.makedirs(CACHE_DIR, exist_ok=True)
    df.reset_index(drop=True).to_parquet(cache_path, compression="snappy", index=False)
    return df


# ───────────── 1 · CALIDAD ─────────────
def plot_calidad_pases(file_path: str) -> None:
    fp = file_path
    if fp.lower().endswith(".xlsx"):
        pases = read_any(fp, sheet_name="Consolidado Pases")
        revs = read_any(fp, sheet_name="Consolidado Reversiones")
    else:  # parquet unificado
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

        # Añadir etiquetas con el porcentaje de reversiones entre pases
        for i, row in d.iterrows():
            if row["passes"] > 0:  # Evitar división por cero
                percent = (row["revs"] / row["passes"]) * 100
                # Usar rojo si el porcentaje es mayor a 3%
                text_color = "red" if percent > 3 else "black"
                plt.text(
                    row["Mes"],
                    row["passes"],
                    f"{percent:.1f}%",
                    fontsize=8,
                    ha="center",
                    va="bottom",
                    color=text_color,
                    bbox=dict(
                        facecolor="white",
                        alpha=0.7,
                        edgecolor="none",
                        boxstyle="round,pad=0.3",
                    ),
                )

        # Añadir nota explicativa en la esquina inferior derecha
        plt.text(
            0.95,
            0.05,
            "% Reversiones > 3% en rojo",
            fontsize=8,
            ha="right",
            va="top",
            transform=plt.gca().transAxes,
            bbox=dict(
                facecolor="white",
                alpha=0.8,
                edgecolor="black",
                boxstyle="round,pad=0.3",
            ),
        )

        plt.title(sq)
        plt.ylabel("Pases a PRD vs Reversiones")
        plt.grid(True)
        plt.legend()
        # Forzar pasos de 1 en el eje Y
        max_y = int(max(d["passes"].max(), d["revs"].max())) + 1
        plt.yticks(range(0, max_y, 1))
        plt.tight_layout()
        plt.show()


# ───────────── 2 · DEDICACIÓN ─────────────
def plot_dedicacion_tm(file_path: str) -> None:
    df = read_any(file_path)
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
def plot_niveles_madurez(file_path: str) -> None:
    df = read_any(file_path)
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


# ───────────── 4 · TMD ─────────────
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


def plot_tiempo_desarrollo(file_path: str) -> None:
    df = read_any(file_path)

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


# ───────────── CLI (opcional) ─────────────
def parse_args():
    p = argparse.ArgumentParser(description="Gráficos filtrados por Chapter Leader")
    p.add_argument("--root", help="Ruta base donde están los Excel", default=None)
    p.add_argument(
        "--rev",
        nargs="?",
        const=True,
        default=None,
        help="Generar gráfico de calidad. Si no se especifica archivo, se busca automáticamente.",
    )
    p.add_argument(
        "--dr",
        nargs="?",
        const=True,
        default=None,
        help="Generar gráfico de dedicación. Si no se especifica archivo, se busca automáticamente.",
    )
    p.add_argument(
        "--m",
        nargs="?",
        const=True,
        default=None,
        help="Generar gráfico de madurez. Si no se especifica archivo, se busca automáticamente.",
    )
    p.add_argument(
        "--tmd",
        nargs="?",
        const=True,
        default=None,
        help="Generar gráfico de tiempo. Si no se especifica archivo, se busca automáticamente.",
    )
    return p.parse_args()


def main() -> None:
    global DATA_DIR, FILES_DIR, CACHE_DIR

    a = parse_args()
    if a.root:
        DATA_DIR = a.root
        FILES_DIR = DATA_DIR
        CACHE_DIR = os.path.join(FILES_DIR, CACHE_SUBDIR)
    os.makedirs(CACHE_DIR, exist_ok=True)

    tasks = [
        ("calidad", a.rev, plot_calidad_pases),
        ("dedicacion", a.dr, plot_dedicacion_tm),
        ("madurez", a.m, plot_niveles_madurez),
        ("tiempo", a.tmd, plot_tiempo_desarrollo),
    ]

    any_run = False

    for task_key, arg, fn in tasks:
        if arg is not None:
            if arg is True:
                # Buscar automáticamente el archivo
                path = _find_file_by_keyword(FILE_KEYWORDS[task_key])
                if path:
                    fn(path)
                    any_run = True
                else:
                    _warn(f"No se encontró archivo para {task_key}")
            else:
                # Usar el archivo proporcionado
                path = arg if os.path.isabs(arg) else os.path.join(FILES_DIR, arg)
                if os.path.isfile(path):
                    fn(path)
                    any_run = True
                else:
                    _warn(f"Archivo no encontrado: {path}")

    if not any_run:
        # Si no se especificó ningún gráfico, intentar generar todos automáticamente
        for task_key, _, fn in tasks:
            path = _find_file_by_keyword(FILE_KEYWORDS[task_key])
            if path:
                fn(path)
                any_run = True

    if not any_run:
        _warn("Ningún gráfico se ejecutó: revisa los archivos o los parámetros CLI.")


if __name__ == "__main__":
    main()
