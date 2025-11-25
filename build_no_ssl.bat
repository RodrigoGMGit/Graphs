@echo off
REM Script de build para crear versión SIN VERIFICACIÓN SSL (SOLO PRUEBAS)
REM NO USAR EN PRODUCCIÓN

echo ========================================
echo Building ChapterSync - No SSL Version
echo SOLO PARA PRUEBAS - NO USAR EN PRD
echo ========================================
echo.

REM Establecer variable de entorno para desactivar SSL
set DISABLE_SSL_VERIFY_FOR_TESTING=true

REM Ejecutar PyInstaller con el spec file especial
pyinstaller presentation_gui_no_ssl.spec

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Build completado exitosamente
    echo ========================================
    echo.
    echo El ejecutable se encuentra en: dist\ChapterSync_NoSSL_Test.exe
    echo.
    echo ADVERTENCIA: Esta versión NO verifica certificados SSL
    echo Solo debe usarse para pruebas en entornos controlados
    echo NO usar en producción
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERROR: El build fallo
    echo ========================================
    exit /b 1
)

