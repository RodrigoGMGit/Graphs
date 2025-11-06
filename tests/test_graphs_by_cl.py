import matplotlib

matplotlib.use("Agg")  # headless for CI

import matplotlib.pyplot as plt
import pytest

from chapter_sync import graphs
from chapter_sync.chapter_leaders import CL_DATA, find_source_for


@pytest.mark.parametrize("cl_name,cl_email", CL_DATA)
def test_graphs_run_without_errors(cl_name, cl_email):
    """Generates all graphs for each Chapter Leader."""
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
        graphs.plot_calidad_pases: find_source_for("calidad"),
        graphs.plot_dedicacion_tm: find_source_for("dedicacion"),
        graphs.plot_niveles_madurez: find_source_for("madurez"),
        graphs.plot_tiempo_desarrollo: find_source_for("tiempo"),
    }

    for fn in plotting_fns:
        src = file_map[fn]
        if src is None:
            pytest.skip(f"Falta archivo para {fn.__name__}")
        try:
            fn(src)
            plt.close("all")
        except Exception as exc:
            pytest.fail(f"{fn.__name__} falló para '{cl_name}': {exc}")
