# Chapter Sync PPT Generator

Este sistema automatiza la generación de presentaciones (PPTX) con métricas de Chapter Sync a partir de archivos Excel mensuales y ofrece una GUI en Dear PyGUI para que el usuario (el Chapter Leader o su equipo) lance el proceso sin tocar código

## Funcionalidades

- **chapter_sync.graphs** – módulo de línea de comandos que construye gráficas de:
  - Calidad (pases vs. reversiones)
  - Dedicación del equipo
  - Niveles de madurez LEP
  - Tiempo de desarrollo (TMD)
- **chapter_sync.presentation** – compila las gráficas anteriores en un PPTX usando una plantilla.
- **chapter_sync.gui** – interfaz basada en Dear PyGUI que automatiza todo el proceso.

## Instalación

1. Instala Python 3.9 o superior.
2. Instala las dependencias:
   ```bash
   pip install -e .
   ```
3. Coloca los archivos de Excel requeridos en `files/` o indica otra carpeta al ejecutar los scripts.
4. Opcionalmente define la variable `CHAPTERSYNC_CONFIG` apuntando a un JSON con tu configuración (rutas y datos del Chapter Leader).

## Uso

### Línea de comandos
Usa la herramienta `chaptersync` para generar gráficas o presentaciones.

Ejemplo:
```bash
chaptersync graphs --root ./files --rev --dr --m --tmd
```
Argumentos:
- `--rev [ARCHIVO]` – gráficas de calidad.
- `--dr [ARCHIVO]`  – gráfica de dedicación.
- `--m [ARCHIVO]`   – gráfica de madurez.
- `--tmd [ARCHIVO]` – gráficas de tiempo de desarrollo.

Las gráficas se muestran con Matplotlib.

### Crear una presentación
Ejecuta `chaptersync ppt` para capturar todas las gráficas y añadirlas a `inputs/Template.pptx`. La presentación resultante se guarda en `outputs/`.

```bash
chaptersync ppt
```

### GUI
Si prefieres una interfaz gráfica ejecuta:
```bash
chaptersync gui
```
Permite configurar la información del Chapter Leader y exportar la presentación con un solo clic.

## Estructura del repositorio

```
files/          # Libros de Excel de ejemplo
files/cached_files/   # Caché Parquet generada automáticamente
inputs/         # Plantilla de la presentación
outputs/        # Archivos PPTX resultantes (ignorados por git)
```

El módulo `graphs.py` guarda en `cached_files/` los datos de Excel para acelerar ejecuciones futuras.

