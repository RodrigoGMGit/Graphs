"""Módulo de diagnóstico del sistema para detectar problemas."""

import os
import ssl
import socket
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple
import requests
from requests.exceptions import SSLError, RequestException


@dataclass
class WritePermissionResult:
    """Resultado de verificación de permisos de escritura."""
    directory: str
    can_write: bool
    error_message: Optional[str] = None


@dataclass
class NetworkConnectivityResult:
    """Resultado de verificación de conectividad de red."""
    endpoint: str
    accessible: bool
    error_message: Optional[str] = None
    response_time_ms: Optional[float] = None


@dataclass
class SystemDiagnosticResult:
    """Resultado del diagnóstico completo del sistema."""
    # Permisos de escritura
    write_permissions: List[WritePermissionResult]
    
    # Conectividad SSL/Red
    has_ssl_error: bool
    ssl_error_message: Optional[str]
    ssl_error_traceback: Optional[str]
    has_proxy: bool
    proxy_details: dict
    connection_works_without_verify: bool
    certificate_chain_info: Optional[str]
    
    # Conectividad a endpoints de Microsoft (si hay credenciales)
    microsoft_endpoints: List[NetworkConnectivityResult]
    has_credentials: bool
    
    # Recomendaciones (sin valores por defecto, deben ir antes de campos con defaults)
    recommendation: str
    severity: str  # "none", "warning", "error"
    
    # Campos con valores por defecto (deben ir al final)
    credentials_valid: Optional[bool] = None
    credentials_error: Optional[str] = None


def check_proxy_environment() -> dict:
    """Verifica variables de entorno de proxy."""
    proxy_vars = {
        'HTTP_PROXY': os.getenv('HTTP_PROXY'),
        'HTTPS_PROXY': os.getenv('HTTPS_PROXY'),
        'http_proxy': os.getenv('http_proxy'),
        'https_proxy': os.getenv('https_proxy'),
        'NO_PROXY': os.getenv('NO_PROXY'),
        'no_proxy': os.getenv('no_proxy'),
    }
    return {k: v for k, v in proxy_vars.items() if v}


def check_system_proxy_windows() -> Optional[str]:
    """Verifica configuración de proxy del sistema en Windows."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
        if proxy_enable:
            proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
            return proxy_server
    except Exception:
        pass
    return None


def test_ssl_connection() -> tuple[bool, Optional[str], Optional[str]]:
    """Prueba conexión SSL a Microsoft.

    Returns:
        Tuple de (éxito, mensaje_error, traceback_error)
    """
    test_url = "https://login.microsoftonline.com"
    try:
        requests.get(test_url, timeout=10, verify=True)
        return True, None, None
    except SSLError as e:
        error_msg = str(e)
        error_tb = traceback.format_exc()
        return False, error_msg, error_tb
    except RequestException as e:
        error_msg = f"Error de conexión: {e}"
        error_tb = traceback.format_exc()
        return False, error_msg, error_tb


def test_ssl_without_verification() -> bool:
    """Prueba conexión sin verificación SSL."""
    test_url = "https://login.microsoftonline.com"
    try:
        requests.get(test_url, timeout=10, verify=False)
        return True
    except Exception:
        return False


def get_certificate_info() -> Optional[str]:
    """Obtiene información de la cadena de certificados."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection(('login.microsoftonline.com', 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname='login.microsoftonline.com') as ssock:
                cert_chain = ssock.getpeercert(chain=True)
                if isinstance(cert_chain, tuple) and len(cert_chain) > 1:
                    info = f"Se recibieron {len(cert_chain)} certificados en la cadena.\n"
                    for i, cert in enumerate(cert_chain):
                        if isinstance(cert, dict):
                            subject = str(cert.get('subject', 'N/A'))
                            issuer = str(cert.get('issuer', 'N/A'))
                            info += f"\nCertificado {i+1}:\n"
                            info += f"  Sujeto: {subject}\n"
                            info += f"  Emisor: {issuer}\n"
                            if 'microsoft' not in subject.lower() and 'microsoft' not in issuer.lower():
                                info += "  ⚠ ADVERTENCIA: Este certificado NO es de Microsoft\n"
                    return info
    except Exception as e:
        return f"Error al obtener certificados: {e}"
    return None


def check_write_permission(directory: Path) -> WritePermissionResult:
    """Verifica permisos de escritura en un directorio.
    
    Realiza una prueba real: crea, escribe, lee y elimina un archivo de prueba.
    """
    try:
        # Asegurar que el directorio existe
        directory.mkdir(parents=True, exist_ok=True)
        
        # Crear archivo de prueba
        test_file = directory / ".diagnostic_test.tmp"
        
        # Intentar escribir
        test_content = "diagnostic_test"
        test_file.write_text(test_content, encoding='utf-8')
        
        # Intentar leer
        read_content = test_file.read_text(encoding='utf-8')
        if read_content != test_content:
            test_file.unlink(missing_ok=True)
            return WritePermissionResult(
                directory=str(directory),
                can_write=False,
                error_message="No se pudo leer el contenido escrito correctamente"
            )
        
        # Intentar eliminar
        test_file.unlink()
        
        return WritePermissionResult(
            directory=str(directory),
            can_write=True
        )
    except PermissionError as e:
        return WritePermissionResult(
            directory=str(directory),
            can_write=False,
            error_message=f"Permiso denegado: {e}"
        )
    except OSError as e:
        return WritePermissionResult(
            directory=str(directory),
            can_write=False,
            error_message=f"Error del sistema: {e}"
        )
    except Exception as e:
        return WritePermissionResult(
            directory=str(directory),
            can_write=False,
            error_message=f"Error inesperado: {e}"
        )


def check_all_write_permissions() -> List[WritePermissionResult]:
    """Verifica permisos de escritura en todos los directorios críticos."""
    results = []
    
    # Determinar rutas según si es ejecutable o script
    if getattr(sys, "frozen", False):
        exec_dir = Path(sys.executable).resolve().parent
        files_dir = exec_dir / "files"
        outputs_dir = exec_dir / "outputs"
        downloads_dir = exec_dir / "downloads"
        base_dir = exec_dir
    else:
        workspace_root = Path(__file__).resolve().parent.parent
        files_dir = workspace_root / "chapter_sync" / "files"
        outputs_dir = workspace_root / "chapter_sync" / "outputs"
        downloads_dir = workspace_root / "downloads"
        base_dir = workspace_root
    
    # Verificar directorios críticos
    directories_to_check = [
        ("Archivos principales", files_dir),
        ("Caché de archivos", files_dir / "cached_files"),
        ("Salidas PPTX", outputs_dir),
        ("Descargas temporales", downloads_dir),
        ("Directorio de ejecución", base_dir),
    ]
    
    for name, directory in directories_to_check:
        result = check_write_permission(directory)
        results.append(result)
    
    return results


def check_microsoft_endpoints() -> Tuple[List[NetworkConnectivityResult], bool, Optional[bool], Optional[str]]:
    """Verifica conectividad a endpoints de Microsoft si hay credenciales.
    
    Returns:
        Tuple de (resultados_endpoints, tiene_credenciales, credenciales_válidas, error_credenciales)
    """
    results = []
    
    # Verificar si hay credenciales
    tenant_id = os.getenv("AZ_TENANT_ID")
    client_id = os.getenv("AZ_CLIENT_ID")
    client_secret = os.getenv("AZ_CLIENT_SECRET")
    
    has_credentials = bool(tenant_id and client_id and client_secret)
    
    if not has_credentials:
        return results, False, None, None
    
    # Obtener configuración SSL
    try:
        from chapter_sync.ssl_config import get_ssl_verify_setting, get_ssl_cert_path
        ssl_verify = get_ssl_verify_setting()
        ssl_cert = get_ssl_cert_path()
        verify_setting = ssl_cert if ssl_cert else ssl_verify
    except ImportError:
        verify_setting = True
    
    # Verificar endpoint de autenticación
    import time
    auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    try:
        start_time = time.time()
        response = requests.post(
            auth_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=10,
            verify=verify_setting,
        )
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            token_data = response.json()
            if "access_token" in token_data:
                results.append(NetworkConnectivityResult(
                    endpoint="Microsoft OAuth2 Token",
                    accessible=True,
                    response_time_ms=response_time
                ))
                
                # Verificar endpoint de Graph API
                token = token_data["access_token"]
                graph_url = "https://graph.microsoft.com/v1.0/me"
                
                try:
                    start_time = time.time()
                    graph_response = requests.get(
                        graph_url,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                        verify=verify_setting,
                    )
                    graph_time = (time.time() - start_time) * 1000
                    
                    if graph_response.status_code in [200, 403]:  # 403 puede ser normal si no tiene permisos de usuario
                        results.append(NetworkConnectivityResult(
                            endpoint="Microsoft Graph API",
                            accessible=True,
                            response_time_ms=graph_time
                        ))
                        return results, True, True, None
                    else:
                        results.append(NetworkConnectivityResult(
                            endpoint="Microsoft Graph API",
                            accessible=False,
                            error_message=f"Código de estado: {graph_response.status_code}",
                            response_time_ms=graph_time
                        ))
                        return results, True, False, f"Graph API retornó código {graph_response.status_code}"
                except Exception as e:
                    results.append(NetworkConnectivityResult(
                        endpoint="Microsoft Graph API",
                        accessible=False,
                        error_message=str(e)
                    ))
                    return results, True, False, f"Error al acceder a Graph API: {e}"
            else:
                return results, True, False, "No se recibió access_token en la respuesta"
        else:
            return results, True, False, f"Error de autenticación: código {response.status_code}"
    except SSLError as e:
        results.append(NetworkConnectivityResult(
            endpoint="Microsoft OAuth2 Token",
            accessible=False,
            error_message=f"Error SSL: {str(e)}"
        ))
        return results, True, None, f"Error SSL: {str(e)}"
    except Exception as e:
        results.append(NetworkConnectivityResult(
            endpoint="Microsoft OAuth2 Token",
            accessible=False,
            error_message=str(e)
        ))
        return results, True, False, f"Error de conexión: {str(e)}"


def run_diagnostic() -> SystemDiagnosticResult:
    """Ejecuta diagnóstico completo del sistema."""
    # 1. Verificar permisos de escritura
    write_permissions = check_all_write_permissions()
    
    # 2. Verificar proxy
    proxy_env = check_proxy_environment()
    proxy_system = check_system_proxy_windows()
    has_proxy = bool(proxy_env or proxy_system)
    
    proxy_details = {
        'environment': proxy_env,
        'system': proxy_system
    }
    
    # 3. Probar conexión SSL
    ssl_works, ssl_error, ssl_traceback = test_ssl_connection()
    
    # Si falla, probar sin verificación
    works_without_verify = False
    if not ssl_works:
        works_without_verify = test_ssl_without_verification()
    
    # Obtener información de certificados
    cert_info = None
    if not ssl_works:
        cert_info = get_certificate_info()
    
    # 4. Verificar endpoints de Microsoft (si hay credenciales)
    microsoft_endpoints, has_credentials, credentials_valid, credentials_error = check_microsoft_endpoints()
    
    # 5. Generar recomendaciones
    issues = []
    severity = "none"
    
    # Verificar problemas de permisos
    write_issues = [r for r in write_permissions if not r.can_write]
    if write_issues:
        issues.append("Problemas de permisos de escritura detectados")
        severity = "error"
    
    # Verificar problemas SSL
    if not ssl_works:
        if has_proxy and works_without_verify:
            issues.append("Proxy/firewall interceptando SSL")
            if severity != "error":
                severity = "error"
        else:
            issues.append("Problema de certificados SSL")
            if severity == "none":
                severity = "warning"
    
    # Verificar problemas de credenciales
    if has_credentials:
        if credentials_valid is False:
            issues.append("Credenciales de Microsoft inválidas")
            if severity != "error":
                severity = "error"
        elif credentials_valid is None and credentials_error and "SSL" in credentials_error:
            # Error SSL ya contado arriba
            pass
    
    # Construir recomendación
    if not issues:
        recommendation = "No se detectaron problemas. El sistema está listo para funcionar."
    else:
        recommendation_parts = ["Problemas detectados:\n"]
        for issue in issues:
            recommendation_parts.append(f"  • {issue}\n")
        recommendation_parts.append("\nRecomendaciones:\n")
        
        if write_issues:
            recommendation_parts.append(
                "  • Verifique los permisos de escritura en los directorios indicados\n"
                "  • Ejecute la aplicación como administrador si es necesario\n"
            )
        
        if not ssl_works and has_proxy:
            recommendation_parts.append(
                "  • Obtenga el certificado raíz de la CA corporativa del equipo de TI\n"
                "  • Colóquelo en el directorio de la aplicación\n"
                "  • O use la opción de desactivar verificación SSL (menos seguro)\n"
            )
        
        if has_credentials and credentials_valid is False:
            recommendation_parts.append(
                "  • Verifique las credenciales en el archivo .env\n"
                "  • Asegúrese de que AZ_TENANT_ID, AZ_CLIENT_ID y AZ_CLIENT_SECRET sean correctos\n"
            )
        
        recommendation = "".join(recommendation_parts)
    
    return SystemDiagnosticResult(
        write_permissions=write_permissions,
        has_ssl_error=not ssl_works,
        ssl_error_message=ssl_error,
        ssl_error_traceback=ssl_traceback,
        has_proxy=has_proxy,
        proxy_details=proxy_details,
        connection_works_without_verify=works_without_verify,
        certificate_chain_info=cert_info,
        microsoft_endpoints=microsoft_endpoints,
        has_credentials=has_credentials,
        recommendation=recommendation,
        severity=severity,
        credentials_valid=credentials_valid,
        credentials_error=credentials_error,
    )


def generate_report(result: SystemDiagnosticResult) -> str:
    """Genera un reporte de texto del diagnóstico completo."""
    report = []
    report.append("="*70)
    report.append("  REPORTE DE DIAGNÓSTICO DEL SISTEMA")
    report.append("="*70)
    report.append("")
    
    report.append(f"Python: {sys.version}")
    report.append(f"Plataforma: {sys.platform}")
    report.append(f"Directorio: {os.getcwd()}")
    report.append("")
    
    # Permisos de escritura
    report.append("-"*70)
    report.append("  PERMISOS DE ESCRITURA")
    report.append("-"*70)
    report.append("")
    
    all_write_ok = True
    for perm_result in result.write_permissions:
        if perm_result.can_write:
            report.append(f"✅ {perm_result.directory}")
        else:
            report.append(f"❌ {perm_result.directory}")
            if perm_result.error_message:
                report.append(f"   Error: {perm_result.error_message}")
            all_write_ok = False
    
    if all_write_ok:
        report.append("\n✓ Todos los directorios tienen permisos de escritura correctos")
    report.append("")
    
    # Conectividad SSL/Red
    report.append("-"*70)
    report.append("  CONECTIVIDAD SSL/RED")
    report.append("-"*70)
    report.append("")
    
    if result.has_ssl_error:
        report.append("❌ ERROR SSL DETECTADO")
        report.append(f"   Mensaje: {result.ssl_error_message}")
        if result.ssl_error_traceback:
            report.append("")
            report.append("   Traceback completo:")
            report.append("-"*70)
            report.append(result.ssl_error_traceback)
            report.append("-"*70)
    else:
        report.append("✅ Conexión SSL funciona correctamente")
    
    report.append("")
    
    report.append("-"*70)
    report.append("  CONFIGURACIÓN DE PROXY")
    report.append("-"*70)
    report.append("")
    
    if result.has_proxy:
        report.append("✓ Proxy detectado:")
        if result.proxy_details.get('environment'):
            report.append("  Variables de entorno:")
            for key, value in result.proxy_details['environment'].items():
                report.append(f"    {key} = {value}")
        if result.proxy_details.get('system'):
            report.append(f"  Proxy del sistema: {result.proxy_details['system']}")
    else:
        report.append("✗ No se detectó proxy")
    
    report.append("")
    
    if result.certificate_chain_info:
        report.append("-"*70)
        report.append("  INFORMACIÓN DE CERTIFICADOS")
        report.append("-"*70)
        report.append("")
        report.append(result.certificate_chain_info)
        report.append("")
    
    # Endpoints de Microsoft
    if result.has_credentials:
        report.append("-"*70)
        report.append("  ENDPOINTS DE MICROSOFT")
        report.append("-"*70)
        report.append("")
        
        if result.credentials_valid is True:
            report.append("✅ Credenciales válidas")
        elif result.credentials_valid is False:
            report.append("❌ Credenciales inválidas")
            if result.credentials_error:
                report.append(f"   Error: {result.credentials_error}")
        else:
            report.append("⚠️ No se pudo verificar credenciales (posible error SSL)")
            if result.credentials_error:
                report.append(f"   Error: {result.credentials_error}")
        
        report.append("")
        
        for endpoint_result in result.microsoft_endpoints:
            if endpoint_result.accessible:
                time_str = f" ({endpoint_result.response_time_ms:.0f}ms)" if endpoint_result.response_time_ms else ""
                report.append(f"✅ {endpoint_result.endpoint}{time_str}")
            else:
                report.append(f"❌ {endpoint_result.endpoint}")
                if endpoint_result.error_message:
                    report.append(f"   Error: {endpoint_result.error_message}")
        report.append("")
    else:
        report.append("-"*70)
        report.append("  ENDPOINTS DE MICROSOFT")
        report.append("-"*70)
        report.append("")
        report.append("ℹ️ No se encontraron credenciales (.env). La verificación de endpoints se omite.")
        report.append("")
    
    # Recomendaciones
    report.append("-"*70)
    report.append("  RECOMENDACIONES")
    report.append("-"*70)
    report.append("")
    report.append(result.recommendation)
    report.append("")
    
    report.append("="*70)
    report.append("  Fin del reporte")
    report.append("="*70)
    
    return "\n".join(report)

