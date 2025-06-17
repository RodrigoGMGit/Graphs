import os

import matplotlib.pyplot as plt
import pandas as pd

# ---------------- CONFIG ----------------
WORK_DIR = os.path.dirname(__file__)  # directorio donde está este script
FILE_PATH = os.path.join(WORK_DIR, "files", "DR__Reporte_detallado_general.xlsx")

CL_NAME = "ANTHONY JAESSON ROJAS MUNARES"
TM_COL = "Nombres"  # columna de Team Member
# ----------------------------------------

# 1. Cargar datos
df = pd.read_excel(FILE_PATH)

# 2. Filtrar por Chapter Leader
mask = df["Nombre CL"].str.upper().str.contains(CL_NAME)
df_cl = df.loc[mask]

# 3. Agrupar por Team Member y calcular promedio de dedicación
grouped = df_cl.groupby(TM_COL)["Dedicación"].mean().sort_values(ascending=False)

tms = grouped.index.tolist()
ded = grouped.values.tolist()

# 4. Gráfico de barras horizontales con gridlines
plt.figure(figsize=(10, 6))
# Dibujamos la rejilla primero para que quede detrás
plt.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)

# Barras
bars = plt.barh(tms, ded, color="seagreen", zorder=3)

# Etiquetas de valor sobre cada barra
for bar in bars:
    width = bar.get_width()
    plt.annotate(
        f"{width:.2f}",
        xy=(width, bar.get_y() + bar.get_height() / 2),
        xytext=(3, 0),
        textcoords="offset points",
        ha="left",
        va="center",
    )

plt.xlabel("Promedio de dedicación")
plt.title("Team Members vs Promedio de dedicación (Horizontal)")
plt.tight_layout()

# 5. Guardar y mostrar
img_path = os.path.join(WORK_DIR, "tm_dedicacion_horizontal.png")
# plt.savefig(img_path, dpi=300)
plt.show()

print(f"Gráfico guardado en: {img_path}")
