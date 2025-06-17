#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graphs.py  –  Versión 100 % fiel a los scripts individuales:
  • Calidad de Pases / Reversiones
  • Dedicación promedio por TM
  • Niveles de Madurez (LEP)
  • Tiempo de Desarrollo (TMD)

Ejemplos:
    python graphs.py                 # todos
    python graphs.py --madurez       # solo LEP
    python graphs.py --calidad --tiempo
"""

import argparse
import os
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import cm, colors

# ------------------- CONFIG -------------------
CHAPTER_LEADER = "ANTHONY JAESSON ROJAS MUNARES"
FILES_DIR = os.path.join(os.path.dirname(__file__), "files")
TMD_THRESHOLD = 13
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
_warn = lambda m: print(f"[INFO] {m}")
# ----------------------------------------------


# ---------- 1 · CALIDAD DE PASES ---------------
def plot_calidad_pases():
    path = os.path.join(
        FILES_DIR, "Calidad__Pases a Producción y Reversiones – BCP TI 2025.xlsx"
    )
    pases = pd.read_excel(path, sheet_name="Consolidado Pases")
    revs = pd.read_excel(path, sheet_name="Consolidado Reversiones")

    m_p = pases["Chapter leader"].str.contains(
        CHAPTER_LEADER.split()[0], case=False, na=False
    )
    m_r = revs["Chapter leader"].str.contains(
        CHAPTER_LEADER.split()[0], case=False, na=False
    )
    pases, revs = pases[m_p].copy(), revs[m_r].copy()

    pases["Mes"] = pases["Mes"].astype(MONTH_CAT)
    revs["Mes"] = revs["Mes"].astype(MONTH_CAT)

    pass_cnt = pases.groupby(["Squad", "Mes"]).size().reset_index(name="passes")
    rev_cnt = revs.groupby(["Squad", "Mes"]).size().reset_index(name="revs")
    full = pass_cnt.merge(rev_cnt, on=["Squad", "Mes"], how="outer")
    full[["passes", "revs"]] = full[["passes", "revs"]].fillna(0).astype(int)
    full = full[(full["passes"] + full["revs"]) > 0].copy()
    full["Mes"] = full["Mes"].cat.remove_unused_categories()

    if full.empty:
        return _warn("Sin datos de Calidad.")
    for sq in sorted(full["Squad"].unique()):
        df_s = full[full["Squad"] == sq].sort_values("Mes")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(df_s["Mes"].astype(str), df_s["passes"], marker="o", label="Pases")
        ax.plot(
            df_s["Mes"].astype(str),
            df_s["revs"],
            marker="x",
            ls="--",
            label="Reversiones",
        )
        ax.set_title(sq, fontsize=11)
        ax.set_ylabel("Número de Pases / Reversiones")
        ax.set_xticklabels(df_s["Mes"].astype(str), rotation=45, ha="right")
        ax.legend(fontsize=8)
        plt.tight_layout()
        plt.show()


# ---------- 2 · DEDICACIÓN TM -----------------
def plot_dedicacion_tm():
    path = os.path.join(FILES_DIR, "DR__Reporte_detallado_general.xlsx")
    df = pd.read_excel(path)
    df = df[df["Nombre CL"].str.upper() == CHAPTER_LEADER.upper()]
    if df.empty:
        return _warn("Sin dedicación para CL.")

    mean_ded = df.groupby("Nombres")["Dedicación"].mean().sort_values()
    plt.figure(figsize=(10, 6))
    plt.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)
    bars = plt.barh(mean_ded.index, mean_ded.values, color="seagreen", zorder=3)
    for bar in bars:
        w = bar.get_width()
        plt.annotate(
            f"{w:.2f}",
            (w, bar.get_y() + bar.get_height() / 2),
            xytext=(3, 0),
            textcoords="offset points",
            ha="left",
            va="center",
        )
    plt.xlabel("Promedio de dedicación")
    plt.title("Team Members vs Promedio de dedicación (Horizontal)")
    plt.tight_layout()
    plt.show()


# ---------- 3 · NIVELES DE MADUREZ ------------
def plot_niveles_madurez():
    path = os.path.join(FILES_DIR, "NivelesMadurez__Reporte_NM_25_04_25.xlsx")
    df = pd.read_excel(path)
    df = df[
        df["Chapter Leader"].fillna("").str.upper().str.contains(CHAPTER_LEADER.upper())
    ]
    if df.empty:
        return _warn("Sin registros LEP para CL.")

    lep_cols = [c for c in df.columns if str(c).startswith("LEP")]
    if not lep_cols:
        return _warn("No hay columnas LEP_.")
    sq_candidates = [
        c
        for c in df.columns
        if c.upper() in {"SQ", "SQUAD", "SQUAD NAME", "NOMBRE SQUAD"}
    ]
    if not sq_candidates:
        return _warn("No hallé columna Squad.")
    SQ = sq_candidates[0]

    group_sq = df.groupby(SQ)[lep_cols].mean()
    group_sq["overall_avg"] = group_sq.mean(axis=1)
    group_sq = group_sq.sort_values("overall_avg", ascending=False).drop(
        columns="overall_avg"
    )

    melted = group_sq.reset_index().melt(
        id_vars=SQ, value_vars=lep_cols, var_name="Métrica LEP", value_name="Puntuación"
    )

    plt.figure(figsize=(14, 6))
    palette = sns.color_palette("Set2", len(lep_cols))
    ax = sns.barplot(
        data=melted,
        y=SQ,
        x="Puntuación",
        hue="Métrica LEP",
        palette=palette,
        dodge=True,
    )
    ax.set_title("Niveles de Madurez – Promedio LEP por Squad (Horizontal)")
    ax.set_ylabel("Squad")
    ax.set_xlabel("Puntuación promedio")
    for p in ax.patches:
        w = p.get_width()
        ax.annotate(
            f"{w:.2f}",
            (w, p.get_y() + p.get_height() / 2),
            xytext=(3, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=8,
        )
    plt.legend(title="Métrica LEP", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.tight_layout()
    plt.show()


# ---------- 4 · TIEMPO DE DESARROLLO ---------
def plot_tiempo_desarrollo():
    path = os.path.join(FILES_DIR, "TMD__BD Dashboard OKR T.Desarrollo-02.05.25.xlsx")
    df = pd.read_excel(path, sheet_name="Reporte Tiempo Desarrollo")
    df = df[df["cl_dev"].fillna("").str.upper().str.contains("ANTHONY JAESSON")]
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

    def _plot(series, title):
        vals = series.values
        labels = series.index.tolist()
        max_v = np.nanmax(vals)
        cmap = cm.get_cmap("RdYlGn_r")
        norm = colors.Normalize(vmin=TMD_THRESHOLD, vmax=max_v)
        bar_c = [cmap(norm(v)) for v in vals]

        plt.figure(figsize=(14, 6))
        ax = sns.barplot(y=labels, x=vals, palette=bar_c)
        ax.set_title(title)
        ax.set_xlabel("Promedio de días")
        ax.set_ylabel("")
        ax.set_xticks(np.arange(0, int(np.ceil(max_v)) + 1, 1))
        ax.set_xlim(0, np.ceil(max_v) + 1)

        for p, v in zip(ax.patches, vals):
            ax.annotate(
                f"{v:.1f}",
                (v, p.get_y() + p.get_height() / 2),
                xytext=(3, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=9,
            )

        ax.axvline(TMD_THRESHOLD, color="black", ls="--", lw=1)
        sm = cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        plt.colorbar(sm, ax=ax, orientation="vertical", label="Días (rojo = peor)")
        plt.tight_layout()
        plt.show()

    _plot(
        tribu_avg,
        f"Tiempo de Desarrollo Promedio por Tribu (umbral {TMD_THRESHOLD} días)",
    )
    _plot(
        squad_avg,
        f"Tiempo de Desarrollo Promedio por Squad (umbral {TMD_THRESHOLD} días)",
    )


# ---------------- CLI ------------------------
def _parse() -> List[str]:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calidad", action="store_true")
    ap.add_argument("--dedicacion", action="store_true")
    ap.add_argument("--madurez", action="store_true")
    ap.add_argument("--tiempo", action="store_true")
    fl = vars(ap.parse_args())
    return [k for k, v in fl.items() if v] or [
        "calidad",
        "dedicacion",
        "madurez",
        "tiempo",
    ]


def main():
    funcs = {
        "calidad": plot_calidad_pases,
        "dedicacion": plot_dedicacion_tm,
        "madurez": plot_niveles_madurez,
        "tiempo": plot_tiempo_desarrollo,
    }
    for k in _parse():
        funcs[k]()


if __name__ == "__main__":
    main()
