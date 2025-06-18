import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# ---------------- CONFIG ----------------
WORKSPACE_DIR = os.path.dirname(__file__)  # directorio de este script
FILE_PATH = os.path.join(
    WORKSPACE_DIR, "files", "NivelesMadurez__Reporte_NM_25_04_25.xlsx"
)
CHAPTER_STR = "ANTHONY JAESSON ROJAS MUNARES"  # Chapter Leader a filtrar
sns.set_theme(style="whitegrid")
# ----------------------------------------

# 1) Cargar datos
df = pd.read_excel(FILE_PATH)

# 2) Filtrar por Chapter Leader
mask = df["Chapter Leader"].fillna("").str.upper().str.contains(CHAPTER_STR)
df_cl = df.loc[mask]

# 3) Detectar columnas LEP (empiezan con "LEP")
lep_cols = [c for c in df_cl.columns if str(c).startswith("LEP")]
if not lep_cols:
    raise ValueError("No se encontraron columnas que comiencen con 'LEP'.")

# 4) Detectar columna de Squad (SQ / SQUAD / SQUAD NAME / NOMBRE SQUAD)
sq_candidates = [
    c
    for c in df_cl.columns
    if c.upper() in {"SQ", "SQUAD", "SQUAD NAME", "NOMBRE SQUAD"}
]
if not sq_candidates:
    raise ValueError("No se encontró una columna para el nombre del Squad.")
SQ_COL = sq_candidates[0]

# 5) Promedios por Squad
group_sq = df_cl.groupby(SQ_COL)[lep_cols].mean()

# Ordenar squads por promedio global descendente
group_sq["overall_avg"] = group_sq.mean(axis=1)
group_sq = group_sq.sort_values("overall_avg", ascending=False).drop(
    columns="overall_avg"
)

# Preparar datos derretidos (melt) para seaborn
melted_sq = group_sq.reset_index().melt(
    id_vars=SQ_COL, value_vars=lep_cols, var_name="Métrica LEP", value_name="Puntuación"
)

# 6) Gráfico: Barras agrupadas horizontales
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

# Etiquetas de valor sobre cada barra
# for p in ax.patches:
#     w = p.get_width()
#     ax.annotate(
#         f"{w:.2f}",
#         (w, p.get_y() + p.get_height() / 2),
#         ha="left",
#         va="center",
#         xytext=(3, 0),
#         textcoords="offset points",
#         fontsize=8,
#     )

plt.legend(title="Métrica LEP", bbox_to_anchor=(1.05, 1), loc="upper left")
plt.tight_layout()

# 7) Guardar y mostrar
output_img = os.path.join(WORKSPACE_DIR, "niveles_madurez_sq_horizontal.png")
# plt.savefig(output_img, dpi=300)
plt.show()

print(f"Gráfico guardado en: {output_img}")
