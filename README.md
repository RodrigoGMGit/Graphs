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
5. (Opcional) Para probar la nueva interfaz en Qt instala las dependencias extra:

   ```bash
   pip install -e .[qt]
   ```

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

La interfaz gráfica utiliza PySide6 (Qt) como framework principal y permite configurar la información del Chapter Leader y exportar la presentación con un solo clic.

La GUI incluye:
- **Interfaz moderna** con diseño profesional basado en Qt
- **Gestión de perfiles** para guardar múltiples Chapter Leaders
- **Indicadores de carga** con diálogo de progreso durante la generación
- **Sistema de logging** con timestamps y códigos de color
- **Barra de estado** con feedback visual inmediato

#### Interfaz alternativa (DearPyGUI)

Si prefieres usar la interfaz legacy construida con DearPyGUI:

```bash
chaptersync gui --ui dpg
```

## Estructura del repositorio

```
chapter_sync/
  ├── gui.py           # Interfaz gráfica legacy (DearPyGUI v3.7.0)
  ├── gui_qt/          # Interfaz gráfica principal (PySide6)
  │   ├── main.py      # Bootstrap de la aplicación Qt
  │   ├── widgets.py   # Componentes de la interfaz
  │   └── controller.py # Lógica de negocio
  ├── graphs.py        # Generación de gráficas
  ├── presentation.py  # Compilación de PPTX
  ├── files/           # Libros de Excel de ejemplo
  │   └── cached_files/  # Caché Parquet generada automáticamente
  ├── inputs/          # Plantilla de la presentación
  └── outputs/         # Archivos PPTX resultantes (ignorados por git)
```

El módulo `graphs.py` guarda en `cached_files/` los datos de Excel para acelerar ejecuciones futuras.

## Tests

Los tests se encuentran en el directorio `tests/`. Actualmente, `test_graphs_by_cl.py` verifica que la generación de gráficos para cada Chapter Leader se ejecute sin errores, asegurando que las funciones de graficado (`plot_calidad_pases`, `plot_dedicacion_tm`, `plot_niveles_madurez`, `plot_tiempo_desarrollo`) no fallen al procesar los datos.

Para ejecutar los tests, asegúrate de tener las dependencias instaladas y luego usa `pytest`:

```bash
pytest
```

Los tests se configuraron para ejecutarse en un entorno sin interfaz gráfica (headless) usando `matplotlib.use("Agg")`, lo que los hace adecuados para entornos de integración continua (CI).

## Generar ejecutable

El repositorio incluye `presentation_gui.spec` para crear una versión ejecutable
de la GUI usando PyInstaller. La interfaz por defecto es PySide6 (Qt). Instala primero las dependencias:

```bash
pip install -e .[build,qt]
```

Luego ejecuta:

```bash
pyinstaller presentation_gui.spec
```

El ejecutable se creará dentro de `dist/` junto con todos los archivos necesarios
(directorio `chapter_sync/files` y la plantilla `chapter_sync/inputs/Template.pptx`).

