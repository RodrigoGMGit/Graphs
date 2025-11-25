"""Runtime hook para desactivar verificación SSL en versión de pruebas.

Este archivo se ejecuta al inicio de la aplicación cuando se construye
con presentation_gui_no_ssl.spec. Establece la variable de entorno que
fuerza la desactivación de la verificación SSL.
"""

import os

# Establecer variable de entorno para desactivar SSL en esta versión
os.environ['DISABLE_SSL_VERIFY_FOR_TESTING'] = 'true'

