"""Utilities to discover Chapter Leaders from existing Excel files."""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Iterable, List, Optional, Tuple

import pandas as pd

from . import graphs

EMAIL_RE = re.compile(r"\(([^)]+@[^)]+)\)$")


def _normalize(txt: str) -> str:
    if not isinstance(txt, str):
        txt = str(txt)
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return re.sub(r"\s+", "", txt).upper()


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


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------

def _list_excels(root: str) -> List[str]:
    """List all Excel files recursively, returning relative paths."""
    try:
        files = []
        for current_root, dirs, filenames in os.walk(root):
            for filename in filenames:
                if filename.lower().endswith(".xlsx"):
                    # Get relative path from root
                    rel_path = os.path.relpath(
                        os.path.join(current_root, filename), root
                    )
                    files.append(rel_path)
        return files
    except FileNotFoundError:
        return []


def _find_by_tokens(tokens: List[str]) -> Optional[str]:
    """Find Excel files matching tokens, searching recursively."""
    files = _list_excels(graphs.FILES_DIR)
    if not files:
        return None
    toks = [_normalize(t) for t in tokens]
    # Match tokens against filename (not full path)
    matches = [
        f for f in files
        if any(t in _normalize(os.path.basename(f)) for t in toks)
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda f: os.path.getmtime(
            os.path.join(graphs.FILES_DIR, f)
        ),
        reverse=True,
    )
    return os.path.join(graphs.FILES_DIR, matches[0])


def find_source_for(task: str) -> Optional[str]:
    """Locate the spreadsheet path for the given task name."""
    try:
        p = graphs._find_file_by_keyword(graphs.FILE_KEYWORDS[task])
        if p:
            return p
    except Exception:
        pass
    if task == "calidad":
        p = _find_by_tokens([
            "Pases a Producción y Reversiones",
            "Pases a Produccion y Reversiones",
        ])
        if p:
            return p
        for f in sorted(
            _list_excels(graphs.FILES_DIR),
            key=lambda x: os.path.getmtime(os.path.join(graphs.FILES_DIR, x)),
            reverse=True,
        ):
            # Match against filename, not full path
            n = _normalize(os.path.basename(f))
            if "PASES" in n and ("REVERSION" in n or "REVERSIONES" in n):
                return os.path.join(graphs.FILES_DIR, f)
        return None
    if task == "dedicacion":
        return _find_by_tokens(["DR", "dashboard"])
    if task == "madurez":
        return _find_by_tokens(["NivelesMadurez", "Reporte_NM", "Reporte NM", "ReporteNM"])
    if task == "tiempo":
        return _find_by_tokens(["TMD", "T.Desarrollo", "Desarrollo"])
    return None


# ---------------------------------------------------------------------------
# CL extraction
# ---------------------------------------------------------------------------

def _extract_cls_from_df(df: pd.DataFrame, preferred_cols: List[str]) -> List[Tuple[str, str]]:
    def find_col(cands: List[str]) -> Optional[str]:
        lut = {_normalize(c): c for c in df.columns}
        for c in cands:
            k = _normalize(c)
            if k in lut:
                return lut[k]
        for c in df.columns:
            if "chapter" in str(c).lower():
                return c
        return None

    cl_col = find_col(preferred_cols)
    if cl_col is None:
        return []

    vals = pd.Series(df[cl_col]).dropna().astype(str).unique().tolist()
    return [_parse_name_email(v) for v in vals]


def load_chapter_leaders() -> List[Tuple[str, str]]:
    """Return unique pairs of chapter leader name and email from all sources."""

    pairs: List[Tuple[str, str]] = []

    cal_path = find_source_for("calidad")
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

    dr_path = find_source_for("dedicacion")
    if dr_path:
        try:
            xl = pd.ExcelFile(dr_path)
            sh = "DR" if "DR" in xl.sheet_names else xl.sheet_names[0]
            df = graphs.read_any(dr_path, sheet_name=sh)
            pairs += _extract_cls_from_df(df, ["CL", "Nombre CL", "Chapter leader"])
        except Exception:
            pass

    tmd_path = find_source_for("tiempo")
    if tmd_path:
        try:
            df = graphs.read_any(tmd_path)
            cl_col = graphs._find_cl_column(df)
            if cl_col:
                pairs += _extract_cls_from_df(df, [cl_col])
        except Exception:
            pass

    mad_path = find_source_for("madurez")
    if mad_path:
        try:
            df = graphs.read_any(mad_path)
            pairs += _extract_cls_from_df(df, ["Chapter Leader", "Chapter leader", "Nombre CL", "CL"])
        except Exception:
            pass

    pairs = _dedupe_pairs(pairs)
    return pairs


# Convenience constant for easy import
CL_DATA = load_chapter_leaders()

__all__ = ["find_source_for", "load_chapter_leaders", "CL_DATA"]
