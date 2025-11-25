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
   Esto instalará todas las dependencias necesarias, incluyendo PySide6 para la interfaz gráfica Qt.
   
   Nota: El proyecto usa `pyproject.toml` para gestionar dependencias. Si encuentras un archivo `requirements.txt`, es legacy y no es necesario usarlo.
3. Coloca los archivos de Excel requeridos en `chapter_sync/files/` (ubicación por defecto) o indica otra carpeta al ejecutar los scripts mediante el parámetro `--root` o la configuración.
4. Opcionalmente define la variable de entorno `CHAPTERSYNC_CONFIG` apuntando a un JSON con tu configuración (rutas y datos del Chapter Leader).
5. (Opcional) Si planeas usar la funcionalidad de descarga automática de archivos desde Azure, crea un archivo `.env` en la raíz del proyecto con las credenciales necesarias:
   ```
   AZ_CLIENT_ID=tu_client_id
   AZ_CLIENT_SECRET=tu_client_secret
   AZ_TENANT_ID=tu_tenant_id
   ```
6. (Opcional) Para ejecutar los tests, instala las dependencias de desarrollo:
   ```bash
   pip install -e .[dev]
   ```

## Versión de Pruebas sin Verificación SSL

**IMPORTANTE: Esta sección describe una versión especial SOLO para pruebas. NO usar en producción.**

Existe una variante de la aplicación que desactiva completamente la verificación de certificados SSL. Esta versión está diseñada para permitir la validación funcional en entornos corporativos donde hay problemas de certificados SSL (por ejemplo, proxies corporativos que interceptan HTTPS).

### Características de la versión sin SSL

- **Desactiva completamente la verificación SSL**: Todas las conexiones HTTPS se realizan sin validar certificados
- **Advertencias visibles**: El título de la ventana y los logs muestran claramente que es una versión de pruebas
- **Nombre diferenciado**: El ejecutable se llama `ChapterSync_NoSSL_Test.exe` para evitar confusión

### Riesgos de seguridad

⚠️ **ADVERTENCIA CRÍTICA**: Esta versión es vulnerable a ataques Man-in-the-Middle (MITM) porque no valida certificados SSL. El tráfico puede ser interceptado y modificado por atacantes.

**Solo debe usarse para:**
- Validación funcional en entornos corporativos controlados
- Pruebas cuando hay problemas de certificados SSL que impiden el funcionamiento normal
- Diagnóstico temporal mientras se resuelve el problema de certificados

**NO debe usarse para:**
- Producción
- Entornos con datos sensibles sin protección adicional
- Cualquier uso donde la seguridad sea crítica

### Cómo construir la versión sin SSL

1. Ejecuta el script de build especial:
   ```bash
   build_no_ssl.bat
   ```

2. El ejecutable se generará en `dist\ChapterSync_NoSSL_Test.exe`

3. Al ejecutarlo, verás:
   - Título de ventana: "ChapterSync (MODO PRUEBAS - SSL NO VERIFICADO, NO USAR EN PRD)"
   - Advertencias en los logs al iniciar descargas
   - Mensaje destacado en el diagnóstico del sistema

### Diferencias con la versión normal

| Característica | Versión Normal | Versión Sin SSL (Pruebas) |
|---------------|----------------|---------------------------|
| Verificación SSL | Activada (por defecto) | Desactivada (forzada) |
| Nombre ejecutable | `ChapterSync PPT Generator.exe` | `ChapterSync_NoSSL_Test.exe` |
| Título ventana | "ChapterSync" | "ChapterSync (MODO PRUEBAS...)" |
| Seguridad | Protegida contra MITM | Vulnerable a MITM |
| Uso recomendado | Producción | Solo pruebas |

## Uso

### Línea de comandos
Usa la herramienta `chaptersync` para generar gráficas o presentaciones.

Ejemplo:
```bash
chaptersync graphs --root ./chapter_sync/files --rev --dr --m --tmd
```

Nota: Si no especificas `--root`, se usará la ubicación por defecto `chapter_sync/files/`.
Argumentos:
- `--rev [ARCHIVO]` – gráficas de calidad.
- `--dr [ARCHIVO]`  – gráfica de dedicación.
- `--m [ARCHIVO]`   – gráfica de madurez.
- `--tmd [ARCHIVO]` – gráficas de tiempo de desarrollo.

Las gráficas se muestran con Matplotlib.

### Crear una presentación
Ejecuta `chaptersync ppt` para capturar todas las gráficas y añadirlas a `chapter_sync/inputs/Template.pptx`. La presentación resultante se guarda en `chapter_sync/outputs/`.

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

El módulo `graphs.py` guarda en `chapter_sync/files/cached_files/` los datos de Excel para acelerar ejecuciones futuras.

## Tests

Los tests se encuentran en el directorio `tests/`. Actualmente, `test_graphs_by_cl.py` verifica que la generación de gráficos para cada Chapter Leader se ejecute sin errores, asegurando que las funciones de graficado (`plot_calidad_pases`, `plot_dedicacion_tm`, `plot_niveles_madurez`, `plot_tiempo_desarrollo`) no fallen al procesar los datos.

Para ejecutar los tests, primero instala las dependencias de desarrollo:

```bash
pip install -e .[dev]
```

Luego ejecuta los tests con `pytest`:

```bash
pytest
```

Los tests se configuraron para ejecutarse en un entorno sin interfaz gráfica (headless) usando `matplotlib.use("Agg")`, lo que los hace adecuados para entornos de integración continua (CI).

## Generar ejecutable

El repositorio incluye `presentation_gui.spec` para crear una versión ejecutable
de la GUI usando PyInstaller. La interfaz por defecto es PySide6 (Qt). Instala primero las dependencias de build:

```bash
pip install -e .[build]
```

Nota: PySide6 ya está incluido en las dependencias principales, por lo que no es necesario instalarlo por separado.

Luego ejecuta:

```bash
pyinstaller presentation_gui.spec
```

El ejecutable se creará dentro de `dist/` junto con todos los archivos necesarios
(directorio `chapter_sync/files` y la plantilla `chapter_sync/inputs/Template.pptx`).

