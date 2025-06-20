# Utilidades de Gráficos

Este repositorio contiene varios scripts de Python que generan gráficas a partir de archivos de Excel y crean presentaciones en PowerPoint.

## Funcionalidades

- **graphs.py** – interfaz de línea de comandos que construye gráficas de:
  - Calidad (pases vs. reversiones)
  - Dedicación del equipo
  - Niveles de madurez LEP
  - Tiempo de desarrollo (TMD)
- **generate_presentation.py** – compila las gráficas anteriores en un PPTX usando una plantilla.
- **presentation_gui.py** – interfaz basada en Dear PyGUI que automatiza todo el proceso.
- **ind_graphs/** – ejemplos independientes con rutas fijas.

## Instalación

1. Instala Python 3.9 o superior.
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Coloca los archivos de Excel requeridos en `files/` o indica otra carpeta al ejecutar los scripts.

## Uso

### Línea de comandos
Ejecuta `graphs.py` para generar gráficas específicas. Si no se indica un archivo, se busca en la ruta dada uno que contenga la palabra clave correspondiente.

Ejemplo:
```bash
python graphs.py --root ./files --rev --dr --m --tmd
```
Argumentos:
- `--rev [ARCHIVO]` – gráficas de calidad.
- `--dr [ARCHIVO]`  – gráfica de dedicación.
- `--m [ARCHIVO]`   – gráfica de madurez.
- `--tmd [ARCHIVO]` – gráficas de tiempo de desarrollo.

Las gráficas se muestran con Matplotlib.

### Crear una presentación
Ejecuta `generate_presentation.py` para capturar todas las gráficas y añadirlas a `inputs/Template.pptx`. La presentación resultante se guarda en `outputs/`.

```bash
python generate_presentation.py
```

### GUI
Si prefieres una interfaz gráfica ejecuta:
```bash
python presentation_gui.py
```
Permite configurar la información del Chapter Leader y exportar la presentación con un solo clic.

## Estructura del repositorio

```
files/          # Libros de Excel de ejemplo
cached_files/   # Caché Parquet generada automáticamente
inputs/         # Plantilla de la presentación
outputs/        # Archivos PPTX resultantes (ignorados por git)
ind_graphs/     # Scripts de graficado independientes
```

El módulo `graphs.py` guarda en `cached_files/` los datos de Excel para acelerar ejecuciones futuras.

## Licencia

Licencia MIT.
