# tests/test_graphs_by_cl.py
import os
import re
from typing import Iterable, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")  # headless for CI

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from chapter_sync import graphs

# ──────────────────────────────────────────────────────────────────────────────
# Normalization & parsing helpers
# ──────────────────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"\(([^)]+@[^)]+)\)$")


def _normalize(txt: str) -> str:
    import re as _re
    import unicodedata

    if not isinstance(txt, str):
        txt = str(txt)
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return _re.sub(r"\s+", "", txt).upper()


def _parse_name_email(raw: str) -> Tuple[str, str]:
    if not isinstance(raw, str):
        return ("", "")
    s = raw.strip()
    m = EMAIL_RE.search(s)
    if m:
        return (s[: m.start()].rstrip(), m.group(1).strip())
    return (s, "")


def _dedupe_pairs(pairs: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    seen = set()
    out: List[Tuple[str, str]] = []
    for name, mail in pairs:
        if not name:
            continue
        key = (_normalize(name), (mail or "").lower())
        if key not in seen:
            seen.add(key)
            out.append((name.strip(), (mail or "").strip()))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# File discovery (legacy tokens first, then fallbacks for new names)
# ──────────────────────────────────────────────────────────────────────────────


def _list_excels(root: str) -> List[str]:
    try:
        return [f for f in os.listdir(root) if f.lower().endswith(".xlsx")]
    except FileNotFoundError:
        return []


def _find_by_tokens(tokens: List[str]) -> Optional[str]:
    files = _list_excels(graphs.FILES_DIR)
    if not files:
        return None
    toks = [_normalize(t) for t in tokens]
    matches = [f for f in files if any(t in _normalize(f) for t in toks)]
    if not matches:
        return None
    # If multiple, pick most recent
    matches.sort(
        key=lambda f: os.path.getmtime(os.path.join(graphs.FILES_DIR, f)), reverse=True
    )
    return os.path.join(graphs.FILES_DIR, matches[0])


def _find_src_for(task: str) -> Optional[str]:
    # Try project’s finder first
    try:
        p = graphs._find_file_by_keyword(graphs.FILE_KEYWORDS[task])
        if p:
            return p
    except Exception:
        pass
    # Fallbacks per task for new names
    if task == "calidad":
        p = _find_by_tokens(
            [
                "Pases a Producción y Reversiones",
                "Pases a Produccion y Reversiones",
            ]
        )
        if p:
            return p
        # looser fallback: any file that mentions PASES + REVERSION(ES)
        for f in sorted(
            _list_excels(graphs.FILES_DIR),
            key=lambda x: os.path.getmtime(os.path.join(graphs.FILES_DIR, x)),
            reverse=True,
        ):
            n = _normalize(f)
            if "PASES" in n and ("REVERSION" in n or "REVERSIONES" in n):
                return os.path.join(graphs.FILES_DIR, f)
        return None
    if task == "dedicacion":
        return _find_by_tokens(["DR", "dashboard"])
    if task == "madurez":
        return _find_by_tokens(
            ["NivelesMadurez", "Reporte_NM", "Reporte NM", "ReporteNM"]
        )
    if task == "tiempo":
        return _find_by_tokens(["TMD", "T.Desarrollo", "Desarrollo"])
    return None


# ──────────────────────────────────────────────────────────────────────────────
# CL extraction from multiple possible sources (Calidad, DR, TMD, Madurez)
# ──────────────────────────────────────────────────────────────────────────────


def _extract_cls_from_df(
    df: pd.DataFrame, preferred_cols: List[str]
) -> List[Tuple[str, str]]:
    # Try exact preferred order by normalized name
    def find_col(cands: List[str]) -> Optional[str]:
        lut = {_normalize(c): c for c in df.columns}
        for c in cands:
            k = _normalize(c)
            if k in lut:
                return lut[k]
        # softer search by substring “chapter”
        for c in df.columns:
            if "chapter" in str(c).lower():
                return c
        return None

    cl_col = find_col(preferred_cols)
    if cl_col is None:
        return []

    vals = pd.Series(df[cl_col]).dropna().astype(str).unique().tolist()
    return [_parse_name_email(v) for v in vals]


def _load_chapter_leaders() -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []

    # 1) Calidad (prefer: old, then new)
    cal_path = _find_src_for("calidad")
    if cal_path:
        try:
            xl = pd.ExcelFile(cal_path)
            if "Consolidado Pases" in xl.sheet_names:
                df = graphs.read_any(cal_path, sheet_name="Consolidado Pases")
                pairs += _extract_cls_from_df(df, ["Chapter leader"])
            else:
                df = graphs.read_any(cal_path, sheet_name=xl.sheet_names[0])
                pairs += _extract_cls_from_df(df, ["CL", "Chapter leader", "Nombre CL"])
        except Exception:
            pass

    # 2) DR dashboards (sheet “DR” usually has 'CL')
    dr_path = _find_src_for("dedicacion")
    if dr_path:
        try:
            xl = pd.ExcelFile(dr_path)
            # try 'DR' sheet, else first sheet
            sh = "DR" if "DR" in xl.sheet_names else xl.sheet_names[0]
            df = graphs.read_any(dr_path, sheet_name=sh)
            pairs += _extract_cls_from_df(df, ["CL", "Nombre CL", "Chapter leader"])
        except Exception:
            pass

    # 3) TMD
    tmd_path = _find_src_for("tiempo")
    if tmd_path:
        try:
            df = graphs.read_any(tmd_path)
            # leverage graphs helper to locate CL column
            cl_col = graphs._find_cl_column(df)
            if cl_col:
                pairs += _extract_cls_from_df(df, [cl_col])
        except Exception:
            pass

    # 4) Madurez
    mad_path = _find_src_for("madurez")
    if mad_path:
        try:
            df = graphs.read_any(mad_path)
            pairs += _extract_cls_from_df(
                df, ["Chapter Leader", "Chapter leader", "Nombre CL", "CL"]
            )
        except Exception:
            pass

    pairs = _dedupe_pairs(pairs)

    # If still empty, skip module with a clear message
    if not pairs:
        pytest.skip(
            "No se pudieron extraer Chapter Leaders de los archivos disponibles "
            f"en {graphs.FILES_DIR}. Verifica que al menos uno de Calidad/DR/TMD/Madurez esté presente.",
            allow_module_level=True,
        )

    return pairs


CL_DATA = _load_chapter_leaders()

# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cl_name,cl_email", CL_DATA)
def test_graphs_run_without_errors(cl_name, cl_email):
    """
    Genera todos los gráficos para cada Chapter Leader.
    Falla si alguna función lanza excepción. Si un archivo no existe,
    se hace skip de ese gráfico (coherente con el test original).
    """
    # Configurar líder activo para los filtros
    graphs.config.chapter_leader = cl_name
    graphs.config.chapter_leader_email = cl_email
    graphs.CHAPTER_LEADER = cl_name
    graphs.CHAPTER_LEADER_EMAIL = cl_email
    graphs.CL_NORM = graphs.normalize_name(cl_name)

    plotting_fns = [
        graphs.plot_calidad_pases,
        graphs.plot_dedicacion_tm,
        graphs.plot_niveles_madurez,
        graphs.plot_tiempo_desarrollo,
    ]
    file_map = {
        graphs.plot_calidad_pases: _find_src_for("calidad"),
        graphs.plot_dedicacion_tm: _find_src_for("dedicacion"),
        graphs.plot_niveles_madurez: _find_src_for("madurez"),
        graphs.plot_tiempo_desarrollo: _find_src_for("tiempo"),
    }

    for fn in plotting_fns:
        src = file_map[fn]
        if src is None:
            pytest.skip(f"Falta archivo para {fn.__name__}")
        try:
            fn(src)  # si falta el .parquet, read_any() lo creará en cached_files/
            plt.close("all")  # liberar memoria de las figuras generadas
        except Exception as exc:
            pytest.fail(f"{fn.__name__} falló para '{cl_name}': {exc}")
