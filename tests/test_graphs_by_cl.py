# tests/test_graphs_by_cl.py
import re

import matplotlib

matplotlib.use("Agg")  # backend headless

import matplotlib.pyplot as plt
import pytest

from chapter_sync import graphs

EMAIL_RE = re.compile(r"\(([^)]+@[^)]+)\)$")


def _parse_name_email(raw: str) -> tuple[str, str]:
    if not isinstance(raw, str):
        return ("", "")
    m = EMAIL_RE.search(raw.strip())
    if m:
        return raw[: m.start()].rstrip(), m.group(1).strip()
    return raw.strip(), ""


def _load_chapter_leaders():
    path = graphs._find_file_by_keyword(graphs.FILE_KEYWORDS["calidad"])
    if path is None:
        pytest.skip("Archivo de Calidad no encontrado")
    df = graphs.read_any(path, sheet_name="Consolidado Pases")
    col = next((c for c in df.columns if "chapter" in c.lower()), None)
    if col is None:
        pytest.skip("Columna 'Chapter leader' ausente")
    pairs = [_parse_name_email(v) for v in df[col].dropna().unique()]
    # deduplicar conservando orden
    seen, unique = set(), []
    for p in pairs:
        if p[0] and p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


CL_DATA = _load_chapter_leaders()


@pytest.mark.parametrize("cl_name,cl_email", CL_DATA)
def test_graphs_run_without_errors(cl_name, cl_email):
    """
    Genera todos los gráficos para cada Chapter Leader.
    Falla si alguna función lanza excepción.
    """
    # Configurar líder activo para los filtros de graphs.py
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
        graphs.plot_calidad_pases: graphs._find_file_by_keyword(
            graphs.FILE_KEYWORDS["calidad"]
        ),
        graphs.plot_dedicacion_tm: graphs._find_file_by_keyword(
            graphs.FILE_KEYWORDS["dedicacion"]
        ),
        graphs.plot_niveles_madurez: graphs._find_file_by_keyword(
            graphs.FILE_KEYWORDS["madurez"]
        ),
        graphs.plot_tiempo_desarrollo: graphs._find_file_by_keyword(
            graphs.FILE_KEYWORDS["tiempo"]
        ),
    }

    for fn in plotting_fns:
        src = file_map[fn]
        if src is None:
            pytest.skip(f"Falta archivo para {fn.__name__}")
        try:
            fn(src)  # si falta el .parquet, read_any() lo creará en cached_files/
            plt.close("all")  # liberar memoria de la figura
        except Exception as exc:
            pytest.fail(f"{fn.__name__} falló para '{cl_name}': {exc}")
