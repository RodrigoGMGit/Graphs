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
import logging
import os
import re
import unicodedata
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import cm, colors

from chapter_sync.config import config
from pathlib import Path

logger = logging.getLogger(__name__)

# ───────────── RUTAS BASE ─────────────
DATA_DIR = config.data_dir
CACHE_SUBDIR = config.cache_subdir
FILES_DIR = config.files_dir
CACHE_DIR = config.cache_dir

# Palabras-clave -> método
FILE_KEYWORDS = {
    "calidad": "CALIDAD",
    "dedicacion": "DR",
    "madurez": "NIVELESMADUREZ",
    "tiempo": "TMD",
}

# ───────────── CONFIG RESTO ─────────────
CHAPTER_LEADER = config.chapter_leader
CHAPTER_LEADER_EMAIL = config.chapter_leader_email
TMD_THRESHOLD = config.tmd_threshold

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
    logger.warning(msg)


def _maybe_show() -> None:
    """Show the current figure unless running on a non-interactive backend.

    When the backend is "Agg" (used during tests), calling ``plt.show()``
    triggers a warning. This helper closes the figure instead. If ``plt.show``
    has been patched (e.g. by ``presentation.capture``), the patched function
    is executed so that image capture works as expected.
    """
    if plt.show.__module__ != "matplotlib.pyplot":
        plt.show()
    elif matplotlib.get_backend().lower() == "agg":
        plt.close()
    else:
        plt.show()


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


def _norm_col(s: str) -> str:
    # normalize column names: strip accents, remove spaces/underscores, uppercase
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[\s_]+", "", s)
    return s.upper()


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lookup = {_norm_col(c): c for c in df.columns}
    for cand in candidates:
        key = _norm_col(cand)
        if key in lookup:
            return lookup[key]
    return None


# ─── Filtro unificado por Chapter Leader ──────────────────────────────
def _filter_by_chapter_leader(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """Primero filtra por nombre; si no hay filas y hay correo, prueba por correo."""
    if col_name not in df.columns:
        return df.iloc[0:0]

    by_name = df[norm_series(df[col_name]) == CL_NORM]
    if not by_name.empty or not CHAPTER_LEADER_EMAIL:
        return by_name

    email = CHAPTER_LEADER_EMAIL.strip()
    if not email:
        return by_name

    email_mask = df[col_name].fillna("").str.contains(email, case=False, na=False)
    return df[email_mask]


# ─── Búsqueda automática de archivos ──────────────────────────────────
def _find_file_by_keyword(keyword: str) -> str | None:
    """Busca en FILES_DIR un único .xlsx cuyo nombre contenga keyword.

    Busca recursivamente en subdirectorios de FILES_DIR.
    Si hay múltiples coincidencias, retorna la más reciente según fecha
    en el nombre.
    """
    matches = []
    # Recursively search for Excel files in FILES_DIR and subdirectories
    for root, dirs, files in os.walk(FILES_DIR):
        for file in files:
            if file.lower().endswith(".xlsx"):
                if keyword in _normalize(file):
                    # Get relative path from FILES_DIR
                    rel_path = os.path.relpath(
                        os.path.join(root, file), FILES_DIR
                    )
                    matches.append(rel_path)

    if len(matches) == 0:
        _warn(
            f"No se encontró archivo con «{keyword}» en {FILES_DIR}"
        )
        return None

    if len(matches) == 1:
        return os.path.join(FILES_DIR, matches[0])

    # Multiple matches: sort by date in filename (latest first)
    # Import here to avoid circular dependency
    from chapter_sync.file_processor import (
        extract_date_from_standardized_filename,
    )

    def get_sort_key(rel_path: str) -> tuple[datetime, float]:
        """Return (date_from_filename, mtime) for sorting."""
        full_path = os.path.join(FILES_DIR, rel_path)
        filename = os.path.basename(rel_path)
        date_obj = extract_date_from_standardized_filename(filename)
        mtime = os.path.getmtime(full_path)
        # Use date from filename if available, otherwise use old date
        sort_date = date_obj if date_obj else datetime(1970, 1, 1)
        return (sort_date, mtime)

    matches.sort(key=get_sort_key, reverse=True)
    latest = matches[0]
    latest_filename = os.path.basename(latest)
    _warn(
        f"Procesando el archivo: {latest_filename}"
    )
    return os.path.join(FILES_DIR, latest)


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
    """
    Calidad – Pases a Producción vs Reversiones.

    ► Formatos soportados
      1. Excel antiguo (2 hojas): 'Consolidado Pases' + 'Consolidado Reversiones'
      2. Excel nuevo (1 hoja) con columna 'Tipo' ('Pase' | 'Reversion')
      3. Archivo unificado (Parquet) con columna 'Tipo'

    Mantiene:
      • Filtro por Chapter Leader
      • % Reversiones en rojo si > 3 %
      • Una figura por Squad
    """

    # ── helpers ───────────────────────────────────────────────────────────────

    def _ensure_month_col(df_: pd.DataFrame, date_col: str) -> pd.Series:
        """Deriva el mes (‘Ene’…‘Dic’) de una columna fecha en formato dd/mm/yyyy."""
        dt = pd.to_datetime(df_[date_col], format="%d/%m/%Y", errors="coerce")
        if dt.isna().mean() > 0.05:
            dt = pd.to_datetime(df_[date_col], dayfirst=True, errors="coerce")
        months = dt.dt.month
        labels = months.map(
            lambda x: MONTHS_ES[int(x) - 1]
            if pd.notna(x) and 1 <= int(x) <= 12
            else pd.NA
        )
        return labels.astype(MONTH_CAT)

    def _plot_squad(d: pd.DataFrame, squad: str) -> None:
        plt.figure(figsize=(8, 4))
        plt.plot(d["Mes"].astype(str), d["passes"], marker="o", label="Pases")
        plt.plot(
            d["Mes"].astype(str), d["revs"], marker="x", ls="--", label="Reversiones"
        )

        for _, row in d.iterrows():
            if row["passes"] > 0:
                pct = 100 * row["revs"] / row["passes"]
                color = "red" if pct > 3 else "black"
                plt.text(
                    row["Mes"],
                    row["passes"],
                    f"{pct:.1f}%",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=color,
                    bbox=dict(
                        facecolor="white",
                        alpha=0.7,
                        edgecolor="none",
                        boxstyle="round,pad=0.3",
                    ),
                )

        plt.text(
            0.95,
            0.05,
            "% Reversiones > 3% en rojo",
            ha="right",
            va="top",
            transform=plt.gca().transAxes,
            fontsize=8,
            bbox=dict(
                facecolor="white",
                alpha=0.8,
                edgecolor="black",
                boxstyle="round,pad=0.3",
            ),
        )

        plt.title(squad)
        plt.ylabel("Pases a PRD vs Reversiones")
        plt.grid(True)
        plt.legend()
        max_y = int(max(d["passes"].max(), d["revs"].max())) + 1
        plt.yticks(range(0, max_y, 1))
        plt.tight_layout()
        _maybe_show()

    # ── 1) Excel antiguo con 2 hojas ─────────────────────────────────────────
    if file_path.lower().endswith(".xlsx"):
        try:
            xl = pd.ExcelFile(file_path)
        except Exception as exc:
            return _warn(f"No se pudo leer Excel Calidad: {exc}")

        if {"Consolidado Pases", "Consolidado Reversiones"}.issubset(xl.sheet_names):
            pases = read_any(file_path, sheet_name="Consolidado Pases")
            revs = read_any(file_path, sheet_name="Consolidado Reversiones")

            cl_col = _find_col(pases, ["Chapter leader", "CL", "Nombre CL"])
            if cl_col is None:
                return _warn(
                    "Falta columna Chapter Leader en hojas antiguas de Calidad."
                )
            pases = _filter_by_chapter_leader(pases, cl_col)
            revs = _filter_by_chapter_leader(revs, cl_col)
            if pases.empty and revs.empty:
                return _warn("Sin datos de Calidad para CL.")

            pases["Mes"] = pases["Mes"].astype(MONTH_CAT)
            revs["Mes"] = revs["Mes"].astype(MONTH_CAT)

            c_p = (
                pases.groupby(["Squad", "Mes"], observed=True)
                .size()
                .reset_index(name="passes")
            )
            c_r = (
                revs.groupby(["Squad", "Mes"], observed=True)
                .size()
                .reset_index(name="revs")
            )
            full = c_p.merge(c_r, on=["Squad", "Mes"], how="outer")
            for col in ("passes", "revs"):
                if col in full.columns:
                    full[col] = full[col].fillna(0).astype(int)
                else:
                    full[col] = 0
            full = full[(full["passes"] + full["revs"]) > 0]

            for sq in sorted(full["Squad"].astype(str).unique()):
                _plot_squad(full[full["Squad"] == sq].sort_values("Mes"), sq)
            return  # ← fin formato antiguo

        # ── 2) Excel NUEVO con 1 hoja ‘Tipo’ ──────────────────────────────────
        df = read_any(file_path, sheet_name=xl.sheet_names[0])

        cl_col = _find_col(df, ["Chapter leader", "CL", "Nombre CL"])
        squad_col = _find_col(df, ["Squad", "SQ", "Nombre Squad"])
        tipo_col = _find_col(df, ["Tipo"])
        mes_col = _find_col(df, ["Mes"])
        fecha_col = _find_col(df, ["Fecha implementado", "Fecha Implementado", "Fecha"])

        if not all([cl_col, squad_col, tipo_col]):
            return _warn(
                "Faltan columnas básicas ('Tipo', 'Squad', 'CL') en Calidad nuevo."
            )

        df = _filter_by_chapter_leader(df, cl_col)  # type: ignore[arg-type]
        if df.empty:
            return _warn("Sin datos de Calidad para CL.")

        # Normalizar Tipo → {'Pase','Reversion'}
        tipo_norm = (
            df[tipo_col]
            .astype("string")
            .str.normalize("NFKD")
            .str.encode("ascii", "ignore")
            .str.decode("ascii")
            .str.strip()
            .str.upper()
        )
        df = df.assign(
            _TIPO=tipo_norm.map(
                lambda x: "Pase"
                if x.startswith("PASE")
                else ("Reversion" if x.startswith("REVER") else pd.NA)
            )
        )
        df = df[df["_TIPO"].notna()].copy()
        if df.empty:
            return _warn("No hay filas con Tipo válido ('Pase'|'Reversion').")

        # Mes
        if mes_col is None:
            if fecha_col is None:
                return _warn("Faltan 'Mes' y 'Fecha implementado' para derivar mes.")
            df["_Mes"] = _ensure_month_col(df, fecha_col)
        else:
            df["_Mes"] = df[mes_col].astype(MONTH_CAT)
        df["_Mes"] = df["_Mes"].astype(MONTH_CAT)

        # Conteos
        cnt = (
            df.groupby([squad_col, "_Mes", "_TIPO"], observed=True)
            .size()
            .unstack("_TIPO", fill_value=0)
            .reset_index()
        )

        # Garantizar columnas de tipo antes del rename (por si un tipo no aparece)
        if "Pase" not in cnt.columns:
            cnt["Pase"] = 0
        if "Reversion" not in cnt.columns:
            cnt["Reversion"] = 0

        # Renombrar a esquema estándar
        cnt = cnt.rename(
            columns={
                "Pase": "passes",
                "Reversion": "revs",
                "_Mes": "Mes",
                squad_col: "Squad",
            }
        )

        # ⬅️ Guardas FINALES: si tras el rename faltara alguno, créalo en cero
        if "passes" not in cnt.columns:
            cnt["passes"] = 0
        if "revs" not in cnt.columns:
            cnt["revs"] = 0

        full = cnt[(cnt["passes"] + cnt["revs"]) > 0]
        if full.empty:
            return _warn("Sin conteos de Pases/Reversiones para el CL.")

        for sq in sorted(full["Squad"].astype(str).unique()):
            _plot_squad(full[full["Squad"] == sq].sort_values("Mes"), sq)
        return

    # ── 3) Archivo unificado (Parquet) ────────────────────────────────────────
    df = read_any(file_path)
    cl_col = _find_col(df, ["Chapter leader", "CL", "Nombre CL"])
    squad_col = _find_col(df, ["Squad", "SQ"])
    tipo_col = _find_col(df, ["Tipo"])
    mes_col = _find_col(df, ["Mes"])
    if not all([cl_col, squad_col, tipo_col, mes_col]):
        return _warn("El archivo unificado carece de columnas 'Tipo', 'Squad' o 'Mes'.")

    df = _filter_by_chapter_leader(df, cl_col)  # type: ignore[arg-type]
    if df.empty:
        return _warn("Sin datos de Calidad para CL.")

    df["Mes"] = df[mes_col].astype(MONTH_CAT)

    cnt = (
        df.groupby([squad_col, "Mes", tipo_col], observed=True)
        .size()
        .unstack(tipo_col, fill_value=0)
        .reset_index()
    )

    # Estandarizar nombres de columnas de tipo por prefijo normalizado
    def _col_pref(c: str) -> str:
        cc = _norm_col(c)
        if cc.startswith("PASE"):
            return "Pase"
        if cc.startswith("REVER"):
            return "Reversion"
        return c

    new_cols = {}
    for c in list(cnt.columns):
        if isinstance(c, str):
            pref = _col_pref(c)
            if pref in {"Pase", "Reversion"} and c != pref:
                new_cols[c] = pref
    if new_cols:
        cnt = cnt.rename(columns=new_cols)

    if "Pase" not in cnt.columns:
        cnt["Pase"] = 0
    if "Reversion" not in cnt.columns:
        cnt["Reversion"] = 0

    cnt = cnt.rename(
        columns={squad_col: "Squad", "Pase": "passes", "Reversion": "revs"}
    )

    # ⬅️ Guardas FINALES también aquí
    if "passes" not in cnt.columns:
        cnt["passes"] = 0
    if "revs" not in cnt.columns:
        cnt["revs"] = 0

    full = cnt[(cnt["passes"] + cnt["revs"]) > 0]
    if full.empty:
        return _warn("Sin conteos de Pases/Reversiones para el CL.")

    for sq in sorted(full["Squad"].astype(str).unique()):
        _plot_squad(full[full["Squad"] == sq].sort_values("Mes"), sq)


# ───────────── 2 · DEDICACIÓN  +  DURACIÓN SUBTAREAS ─────────────
def plot_dedicacion_tm(file_path: str) -> None:
    """
    Genera hasta DOS gráficos (mostrados uno tras otro):

      1) Promedio de **Dedicación** (horas) por miembro de equipo.
      2) Promedio de **Duración de subtareas** (días) por miembro de equipo, si existe.

    • Busca columnas por sinónimos (acentos/case/underscores tolerados).
    • Filtra por CL por hoja.
    • Si falta una métrica o no hay columna de persona, se omite solo ese gráfico.
    • Compatible con pandas 2.x (sin mean(level=...)).
    """


    # ── helpers ────────────────────────────────────────────────────────────────

    def _has_cols(df_: pd.DataFrame, cols: list[str]) -> bool:
        return all(c in df_.columns for c in cols)

    def _plot_barh(series: pd.Series, title: str, unidad: str) -> None:
        plt.figure(figsize=(10, 6))
        plt.grid(axis="x", ls="--", alpha=0.4)
        bars = plt.barh(series.index.tolist(), series.values.tolist(), color="seagreen")
        for bar in bars:
            width = float(bar.get_width())
            plt.text(
                width + 0.03,
                bar.get_y() + bar.get_height() / 2,
                f"{width:.1f} {unidad}",
                va="center",
                fontsize=9,
            )
        plt.xlabel(f"Promedio ({unidad})")
        plt.title(title)
        plt.tight_layout()

    # ── hojas ─────────────────────────────────────────────────────────────────
    try:
        xls = pd.ExcelFile(file_path)
        sheet_names = xls.sheet_names
    except Exception:
        sheet_names = [None]  # type: ignore[list-item]

    # Sinónimos
    CL_CANDS = ["CL", "Nombre CL", "Chapter Leader", "Chapter leader", "NombreCL"]
    PERSON_CANDS = [
        "Nombres",
        "Nombre",
        "Colaborador",
        "Recurso",
        "Nombre Recurso",
        "Nombre Empleado",
    ]
    DEDIC_CANDS = [
        "Dedicación",
        "Dedicacion",
        "Dedicación (h)",
        "Horas dedicación",
        "Horas dedicacion",
        "DR",
    ]
    # DUR_CANDS = [
    #     "Duración subtareas Registradas (días)",
    #     "Duración subtareas (días)",
    #     "Duracion subtareas (dias)",
    #     "Duración",
    #     "Duracion",
    #     "Subtask Duration (days)",
    # ]

    dedic_series: pd.Series | None = None
    # dur_series: pd.Series | None = None  # Temporalmente deshabilitado

    # ── detectar métricas hoja por hoja ───────────────────────────────────────
    for sh in sheet_names:
        try:
            df = read_any(file_path, sheet_name=sh) if sh else read_any(file_path)
        except Exception as exc:
            logger.debug(f"No se pudo leer hoja {sh!r}: {exc}")
            continue

        cl_col = _find_col(df, CL_CANDS)
        person_col = _find_col(df, PERSON_CANDS)
        dedic_col = _find_col(df, DEDIC_CANDS)
        # dur_col = _find_col(df, DUR_CANDS)  # Temporalmente deshabilitado

        # Filtrar por CL (y hacer COPIA para evitar SettingWithCopyWarning)
        df_f = (df if cl_col is None else _filter_by_chapter_leader(df, cl_col)).copy()

        # DEDICACIÓN: requiere person_col + dedic_col
        if (
            dedic_series is None
            and person_col
            and dedic_col
            and _has_cols(df_f, [person_col, dedic_col])
        ):
            df_f.loc[:, dedic_col] = pd.to_numeric(df_f[dedic_col], errors="coerce")
            s = df_f.groupby(person_col, dropna=False)[dedic_col].mean()
            s = s.dropna().sort_values()
            if not s.empty:
                dedic_series = s

        # DURACIÓN: requiere person_col + dur_col
        # Temporalmente deshabilitado - no hay columna de persona en Actividades
        # if (
        #     dur_series is None
        #     and person_col
        #     and dur_col
        #     and _has_cols(df_f, [person_col, dur_col])
        # ):
        #     df_f.loc[:, dur_col] = pd.to_numeric(df_f[dur_col], errors="coerce")
        #     s = df_f.groupby(person_col, dropna=False)[dur_col].mean()
        #     s = s.dropna().sort_values()
        #     if not s.empty:
        #         dur_series = s

        # if dedic_series is not None and dur_series is not None:
        #     break
        if dedic_series is not None:
            break  # Solo necesitamos dedicación por ahora

    # ── graficar según disponibilidad ─────────────────────────────────────────
    any_chart = False

    if dedic_series is not None and not dedic_series.empty:
        _plot_barh(dedic_series, "Dedicación promedio por miembro de equipo", "h")
        _maybe_show()
        any_chart = True
    else:
        _warn(
            "No se encontró métrica de Dedicación con columna de persona ('Nombres'); se omitirá ese gráfico."
        )

    # Temporalmente deshabilitado - no hay columna de persona en Actividades
    # if dur_series is not None and not dur_series.empty:
    #     _plot_barh(
    #         dur_series, "Duración subtareas promedio por miembro de equipo", "días"
    #     )
    #     _maybe_show()
    #     any_chart = True
    # else:
    #     _warn(
    #         "No se encontró métrica de Duración de subtareas con columna de persona ('Nombres'); se omitirá ese gráfico."
    #     )

    if not any_chart:
        _warn("Sin datos de Dedicación ni Duración para el CL activo.")


# ───────────── 3 · NIVELES DE MADUREZ (LEP) ─────────────
def plot_niveles_madurez(file_path: str) -> None:
    df = read_any(file_path)
    # 1) locate key columns
    cl_col = _find_col(df, ["Chapter Leader", "Chapter leader", "Nombre CL", "CL"])
    sq_col = _find_col(df, ["SQ", "SQUAD", "SQUAD NAME", "NOMBRE SQUAD", "Squad"])

    if not cl_col:
        return _warn("Falta columna de Chapter Leader en Madurez.")
    if not sq_col:
        return _warn("Falta columna de Squad en Madurez.")

    # 2) filter by Chapter Leader (same unified logic as TMD)
    df = _filter_by_chapter_leader(df, cl_col)
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
        if not w:
            continue
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
    _maybe_show()


# ───────────── 4 · TMD ─────────────
def _find_cl_column(df: pd.DataFrame) -> str | None:
    candidates = [
        "Nombre CL",
        "cl_dev",
        "Chapter leader",
        "Chapter Leader",
        "NombreCL",
        "CL",
    ]
    for c in df.columns:
        if normalize_name(c) in map(normalize_name, candidates):
            return c
    return None


def _plot_tmd(series: pd.Series, title: str) -> None:
    """
    Gráfico de barras horizontales con escala 'RdYlGn_r'.

    • Colorea cada barra individualmente según los días (> rojo, < verde).
    • Mantiene visible la línea‐umbral TMD_THRESHOLD.
    • Compatible con seaborn ≥ 0.14: se pasa hue= para evitar FutureWarning.
    """
    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    # ── limpiar datos ──────────────────────────────────────────────────
    series = series.dropna()
    if series.empty:
        logger.warning("Sin datos válidos para TMD.")
        return

    vals = series.astype(float).to_numpy()
    labels = series.index.tolist()
    max_val = np.nanmax(vals)

    # Normalización segura para la rampa de color
    vmin = min(TMD_THRESHOLD, max_val)
    vmax = max(TMD_THRESHOLD, max_val)

    cmap = matplotlib.colormaps.get_cmap("RdYlGn_r")
    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    bar_colors = [cmap(norm(v)) for v in vals]

    # DataFrame requerido para hue=
    df_plot = pd.DataFrame({"Etiqueta": labels, "Valor": vals})

    # ── plot ───────────────────────────────────────────────────────────
    plt.figure(figsize=(14, 6))
    ax = sns.barplot(
        data=df_plot,
        y="Etiqueta",
        x="Valor",
        hue="Etiqueta",  # ← ahora hay hue
        palette=dict(zip(labels, bar_colors)),  # colores por etiqueta
        legend=False,
        dodge=False,
    )

    ax.set_title(title)
    ax.set_xlabel("Promedio de días")
    ax.set_ylabel("")

    # ── eje X llega siempre al umbral ─────────────────────────────────
    x_max_limit = max(max_val, TMD_THRESHOLD) + 1
    ax.set_xticks(np.arange(0, int(np.ceil(x_max_limit)) + 1, 1))
    ax.set_xlim(0, x_max_limit)

    # valores sobre cada barra
    for p, v in zip(ax.patches, vals):
        ax.annotate(
            f"{v:.1f}",
            (v, p.get_y() + p.get_height() / 2),  # type: ignore
            ha="left",
            va="center",
            xytext=(3, 0),
            textcoords="offset points",
            fontsize=9,
        )

    # línea de umbral
    ax.axvline(TMD_THRESHOLD, color="black", linestyle="--", linewidth=1)

    # barra de colores
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=ax, orientation="vertical", label="Días (rojo = peor)")

    plt.tight_layout()
    _maybe_show()


def plot_tiempo_desarrollo(file_path: str) -> None:
    df = read_any(file_path)

    # find columns by synonyms (accent/case/underscore-insensitive)
    tribu_col = _find_col(
        df, ["Descripción tribu", "Descripcion tribu", "descripcion_tribu"]
    )
    squad_col = _find_col(
        df, ["Descripción squad", "Descripcion squad", "descripcion_squad"]
    )
    metric_col = _find_col(
        df, ["Tiempo Desarrollo", "Tiempo_Desarrollo", "tiempo desarrollo"]
    )

    cl_col = _find_cl_column(df)
    if cl_col is None:
        return _warn("No se encontró columna de Chapter Leader en TMD.")

    if metric_col is None:
        return _warn("No se encontró la columna de métrica 'Tiempo Desarrollo'.")

    if not tribu_col or not squad_col:
        return _warn("No se encontraron columnas de 'Tribu' o 'Squad' para TMD.")

    # From here on, use the resolved names:
    df = _filter_by_chapter_leader(df, cl_col)
    if df.empty:
        return _warn("Sin datos de TMD para CL.")

    df[metric_col] = pd.to_numeric(df[metric_col], errors="coerce")

    tribe_avg = (
        df.groupby(tribu_col)[metric_col].mean().dropna().sort_values(ascending=False)
    )
    squad_avg = (
        df.groupby(squad_col)[metric_col].mean().dropna().sort_values(ascending=False)
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
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    global DATA_DIR, FILES_DIR, CACHE_DIR

    a = parse_args(argv)
    if a.root:
        DATA_DIR = a.root
        FILES_DIR = DATA_DIR
        CACHE_DIR = os.path.join(FILES_DIR, CACHE_SUBDIR)
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Check and download files if needed
    try:
        from chapter_sync.file_processor import check_and_download_if_needed
        check_and_download_if_needed(Path(FILES_DIR))
    except Exception as e:
        _warn(f"Error al verificar/descargar archivos: {e}. Continuando con archivos existentes.")

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
