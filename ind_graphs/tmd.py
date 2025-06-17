import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import cm, colors

# ---------------- CONFIG ----------------
WORKSPACE_DIR = os.path.dirname(__file__)  # directorio de este script
FILE_PATH = os.path.join(
    WORKSPACE_DIR, "files", "TMD__BD Dashboard OKR T.Desarrollo-02.05.25.xlsx"
)
SHEET_NAME = "Reporte Tiempo Desarrollo"
CL_KEY = "ANTHONY JAESSON"  # substring en cl_dev
THRESHOLD = 13  # días
sns.set_theme(style="whitegrid", context="talk")
# ----------------------------------------

# 1) Cargar datos
df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME)

# 2) Filtrar por Chapter Leader
mask = df["cl_dev"].fillna("").str.upper().str.contains(CL_KEY)
df_cl = df.loc[mask].copy()
df_cl["Tiempo Desarrollo"] = pd.to_numeric(df_cl["Tiempo Desarrollo"], errors="coerce")

# 3) Promedios por tribu y squad
tribu_avg = (
    df_cl.groupby("Descripción tribu")["Tiempo Desarrollo"]
    .mean()
    .dropna()
    .sort_values(ascending=False)
)
squad_avg = (
    df_cl.groupby("Descripción squad")["Tiempo Desarrollo"]
    .mean()
    .dropna()
    .sort_values(ascending=False)
)


def plot_horizontal_bars(series, title, filename):
    """Crea y guarda un gráfico de barras horizontales con gradiente de color."""
    vals = series.values
    labels = series.index.tolist()
    max_val = np.nanmax(vals)

    # Colores: verde (≤ umbral) → rojo (≥ máx)
    cmap = cm.get_cmap("RdYlGn_r")
    norm = colors.Normalize(vmin=THRESHOLD, vmax=max_val)
    bar_colors = [cmap(norm(v)) for v in vals]

    plt.figure(figsize=(14, 6))
    ax = sns.barplot(y=labels, x=vals, palette=bar_colors)

    ax.set_title(title)
    ax.set_xlabel("Promedio de días")
    ax.set_ylabel("")

    # Ticks enteros
    ax.set_xticks(np.arange(0, int(np.ceil(max_val)) + 1, 1))
    ax.set_xlim(0, np.ceil(max_val) + 1)

    # Etiquetas numéricas sobre las barras
    for p, v in zip(ax.patches, vals):
        ax.annotate(
            f"{v:.1f}",
            (v, p.get_y() + p.get_height() / 2),
            ha="left",
            va="center",
            xytext=(3, 0),
            textcoords="offset points",
            fontsize=9,
        )

    # Línea de umbral
    ax.axvline(THRESHOLD, color="black", linestyle="--", linewidth=1)

    # Barra de color (gradiente)
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    plt.colorbar(sm, ax=ax, orientation="vertical", label="Días (rojo = peor)")

    plt.tight_layout()
    # plt.savefig(filename, dpi=300)
    plt.show()


# 4) Graficar y guardar
plot_horizontal_bars(
    tribu_avg,
    f"Tiempo de Desarrollo Promedio por Tribu (umbral {THRESHOLD} días)",
    os.path.join(WORKSPACE_DIR, "tribu_threshold_gradient.png"),
)

plot_horizontal_bars(
    squad_avg,
    f"Tiempo de Desarrollo Promedio por Squad (umbral {THRESHOLD} días)",
    os.path.join(WORKSPACE_DIR, "squad_threshold_gradient.png"),
)

print("PNG generados:")
print(os.path.join(WORKSPACE_DIR, "tribu_threshold_gradient.png"))
print(os.path.join(WORKSPACE_DIR, "squad_threshold_gradient.png"))
