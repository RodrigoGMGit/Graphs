#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graphs.py – Genera 4 gráficos (Calidad, Dedicación, Madurez-LEP, TMD)
Filtra por nombre completo del Chapter Leader, ignorando acentos y el correo
entre paréntesis que aparece en `cl_dev`.

• Sin warnings de Pylance / Ruff  • Sin TypeError en Categorical.fillna
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

# ───────────── CONFIG ─────────────
CHAPTER_LEADER = "ANTHONY JAESSON ROJAS MUNARES"
FILES_DIR = os.path.join(os.path.dirname(__file__), "files")
TMD_THRESHOLD = 13

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


def _warn(message: str) -> None:
    """Imprime mensajes informativos estandarizados."""
    print(f"[INFO] {message}")


# ───────────── HELPERS ─────────────
def normalize_name(txt: str | float) -> str:
    """Quita acentos, texto entre paréntesis y espacios duplicados; devuelve MAYÚSCULAS."""
    if not isinstance(txt, str):
        return ""
    txt = txt.split("(")[0]
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", txt).strip().upper()


CL_NORM = normalize_name(CHAPTER_LEADER)


def norm_series(s: pd.Series) -> pd.Series:
    """Normaliza cada celda de la serie para comparación exacta."""
    return s.fillna("").map(normalize_name)


def read_any(fp: str, **kw) -> pd.DataFrame:
    return (
        pd.read_excel(fp, **kw) if fp.lower().endswith(".xlsx") else pd.read_parquet(fp)
    )


# ───────────── 1 · CALIDAD ─────────────
def plot_calidad_pases(file_name: str) -> None:
    fp = os.path.join(FILES_DIR, file_name)
    if fp.lower().endswith(".xlsx"):
        pases = read_any(fp, sheet_name="Consolidado Pases")
        revs = read_any(fp, sheet_name="Consolidado Reversiones")
    else:
        df = read_any(fp)
        pases = df[df["Tipo"] == "Pase a Producción"].copy()
        revs = df[df["Tipo"] == "Reversión"].copy()

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
    if full.empty:
        return _warn("Conteos vacíos tras filtrado.")

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
            f"{width:.2f}",
            va="center",
        )
    plt.xlabel("Promedio de dedicación")
    plt.title("Dedicación promedio por TM")
    plt.tight_layout()
    plt.show()


# ───────────── 3 · MADUREZ (versión original) ─────────────
def plot_niveles_madurez(file_name: str) -> None:
    df = read_any(os.path.join(FILES_DIR, file_name))
    # ➜ El original usaba contains() (mayúsculas); mantenemos coincidencia exacta
    df = df[norm_series(df["Chapter Leader"]) == CL_NORM]
    if df.empty:
        return _warn("Sin registros LEP para CL.")

    lep_cols = [c for c in df.columns if str(c).startswith("LEP")]
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

    ax.set_title("Niveles de Madurez – Promedio LEP por Squad (Horizontal)")
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
def plot_tiempo_desarrollo(file_name: str) -> None:
    fp = os.path.join(FILES_DIR, file_name)
    df = (
        read_any(fp, sheet_name="Reporte Tiempo Desarrollo")
        if fp.lower().endswith(".xlsx")
        else read_any(fp)
    )

    df = df[norm_series(df["cl_dev"]) == CL_NORM]
    if df.empty:
        return _warn("Sin TMD para CL.")
    df["Tiempo Desarrollo"] = pd.to_numeric(df["Tiempo Desarrollo"], errors="coerce")

    tribu_avg = (
        df.groupby("Descripción tribu")["Tiempo Desarrollo"]
        .mean()
        .dropna()
        .sort_values(ascending=False)
    )
    squad_avg = (
        df.groupby("Descripción squad")["Tiempo Desarrollo"]
        .mean()
        .dropna()
        .sort_values(ascending=False)
    )

    sns.set_theme(style="whitegrid", context="talk")

    def _plot(series: pd.Series, lvl: str) -> None:
        if series.empty:
            return
        vals, labs, vmax = series.values, series.index.tolist(), series.max()
        norm = colors.Normalize(vmin=TMD_THRESHOLD, vmax=vmax)
        palette = [cm.get_cmap("RdYlGn_r")(norm(v)) for v in vals]

        plt.figure(figsize=(14, 6))
        ax = sns.barplot(y=labs, x=vals, palette=palette, edgecolor="black")
        ax.set_title(f"Tiempo de Desarrollo promedio por {lvl}")
        ax.set_xlabel("Promedio de días")
        ax.set_ylabel("")
        ax.set_xlim(0, np.ceil(vmax) + 1)
        ax.set_xticks(range(0, int(np.ceil(vmax)) + 1))

        for p, v in zip(ax.patches, vals):
            rect = cast(mpatches.Rectangle, p)
            ax.text(
                v + 0.3,
                rect.get_y() + rect.get_height() / 2,  # type: ignore[attr-defined]
                f"{v:.1f}",
                va="center",
                fontsize=8,
            )

        ax.axvline(
            TMD_THRESHOLD,
            color="black",
            ls="--",
            linewidth=1,
            label=f"Umbral {TMD_THRESHOLD} días",
        )
        sm = cm.ScalarMappable(norm=norm, cmap="RdYlGn_r")
        sm.set_array([])
        plt.colorbar(sm, ax=ax, label="Días")
        ax.legend(loc="lower right")
        plt.tight_layout()
        plt.show()

    _plot(tribu_avg, "Tribu")
    _plot(squad_avg, "Squad")


# ───────────── CLI ─────────────
def parse_args():
    p = argparse.ArgumentParser(
        description="Gráficos filtrados por nombre completo del CL."
    )
    p.add_argument("--calidad", nargs="?", const=DEFAULT_CALIDAD)
    p.add_argument("--dedicacion", nargs="?", const=DEFAULT_DEDICACION)
    p.add_argument("--madurez", nargs="?", const=DEFAULT_MADUREZ)
    p.add_argument("--tiempo", nargs="?", const=DEFAULT_TIEMPO)
    return p.parse_args()


def main() -> None:
    a = parse_args()
    tasks = [
        ("calidad", a.calidad, plot_calidad_pases),
        ("dedicacion", a.dedicacion, plot_dedicacion_tm),
        ("madurez", a.madurez, plot_niveles_madurez),
        ("tiempo", a.tiempo, plot_tiempo_desarrollo),
    ]

    if not any(fname for _, fname, _ in tasks):  # sin flags → todo default
        for k, _, fn in tasks:
            fn(globals()[f"DEFAULT_{k.upper()}"])
    else:
        for _, fname, fn in tasks:
            if fname:
                fn(fname)


if __name__ == "__main__":
    main()
