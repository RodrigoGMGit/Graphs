import os
import re

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# ------------- CONFIG -----------------
WORKSPACE_DIR = os.path.dirname(__file__)  # directorio de este script
FILE_PATH = os.path.join(
    WORKSPACE_DIR,
    "files",
    "Calidad__Pases a Producción y Reversiones – BCP TI 2025.xlsx",
)

CL_KEY = "ANTHONY JAESSON"
MONTHS = [
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
month_cat = pd.CategoricalDtype(categories=MONTHS, ordered=True)

sns.set_theme(style="whitegrid", context="notebook")
# --------------------------------------

# 1) Cargar datos
pases_df = pd.read_excel(FILE_PATH, sheet_name="Consolidado Pases")
revs_df = pd.read_excel(FILE_PATH, sheet_name="Consolidado Reversiones")

# 2) Filtrar por Chapter Leader
pases_a = pases_df[
    pases_df["Chapter leader"].str.contains(CL_KEY, case=False, na=False)
].copy()
revs_a = revs_df[
    revs_df["Chapter leader"].str.contains(CL_KEY, case=False, na=False)
].copy()

# 3) Convertir "Mes" en categórico ordenado
pases_a["Mes"] = pases_a["Mes"].astype(month_cat)
revs_a["Mes"] = revs_a["Mes"].astype(month_cat)

# 4) Conteo por Squad y Mes
pass_cnt = pases_a.groupby(["Squad", "Mes"]).size().reset_index(name="passes")
rev_cnt = revs_a.groupby(["Squad", "Mes"]).size().reset_index(name="revs")

# 5) Combinar y rellenar solo columnas numéricas
full = pd.merge(pass_cnt, rev_cnt, on=["Squad", "Mes"], how="outer")
full[["passes", "revs"]] = full[["passes", "revs"]].fillna(0).astype(int)

# 6) Mantener solo filas con datos (>0) y recalcular las categorías de Mes
full = full[(full["passes"] + full["revs"]) > 0].copy()
full["Mes"] = full["Mes"].cat.remove_unused_categories()


# 7) Crear un gráfico independiente por Squad
def safe_slug(text):
    """Convierte el nombre del Squad en un slug seguro para usar como nombre de archivo."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())


for sq in sorted(full["Squad"].unique()):
    df_s = full[full["Squad"] == sq].sort_values("Mes")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df_s["Mes"].astype(str), df_s["passes"], marker="o", label="Pases")
    ax.plot(
        df_s["Mes"].astype(str),
        df_s["revs"],
        marker="x",
        linestyle="--",
        label="Reversiones",
    )
    ax.set_title(sq, fontsize=11)
    ax.set_ylabel("Número de Pases / Reversiones")
    ax.set_xticklabels(df_s["Mes"].astype(str), rotation=45, ha="right")
    ax.legend(fontsize=8)
    fig.tight_layout()

    # Guardar figura con nombre único por Squad
    img_name = f"line_{safe_slug(sq)}.png"
    img_path = os.path.join(WORKSPACE_DIR, img_name)
    # fig.savefig(img_path, dpi=300)
    plt.show()

    print(f"Gráfico para '{sq}' guardado en {img_path}")
