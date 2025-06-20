# Graphs Packaging

Este proyecto utiliza PyInstaller para crear un ejecutable único de la aplicación basada en `presentation_gui.py`.

## Requisitos
- Python 3 instalado.
- PyInstaller disponible (`pip install pyinstaller`).
- Las dependencias listadas en `requirements.txt` se instalarán automáticamente.

## Archivos incluidos
- Carpeta `files/` con sus subdirectorios.
- Archivo `inputs/Template.pptx`.
- Script `generate_presentation.py` que se ejecuta dinámicamente desde la GUI.

## Construcción
Ejecute el script `build.sh` en la raíz del repositorio:

```bash
./build.sh
```

El script instalará las dependencias y generará el ejecutable utilizando la especificación `presentation_gui.spec`.


El ejecutable se ubicará en la carpeta `dist/`.

