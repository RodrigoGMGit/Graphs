"""Módulo para manejar configuración SSL."""

import os
import json
import sys
from pathlib import Path
from typing import Optional


def get_ssl_config_path() -> Path:
    """Obtiene la ruta donde guardar la configuración SSL."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "ssl_config.json"
    else:
        return Path(__file__).resolve().parent.parent / "ssl_config.json"


def load_ssl_config() -> dict:
    """Carga la configuración SSL."""
    config_path = get_ssl_config_path()
    if config_path.exists():
        try:
            return json.loads(config_path.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_ssl_config(config: dict) -> None:
    """Guarda la configuración SSL."""
    config_path = get_ssl_config_path()
    config_path.write_text(json.dumps(config, indent=2), "utf-8")


def get_ssl_verify_setting() -> bool:
    """Obtiene si la verificación SSL está habilitada.
    
    Prioridad:
    1. Variable de entorno SSL_VERIFY
    2. Configuración guardada en archivo
    3. True (por defecto, más seguro)
    """
    env_setting = os.getenv('SSL_VERIFY')
    if env_setting is not None:
        return env_setting.lower() != 'false'
    
    config = load_ssl_config()
    return config.get('ssl_verify', True)


def set_ssl_verify(verify: bool) -> None:
    """Establece la configuración de verificación SSL."""
    config = load_ssl_config()
    config['ssl_verify'] = verify
    save_ssl_config(config)


def get_ssl_cert_path() -> Optional[str]:
    """Obtiene la ruta al certificado SSL personalizado.
    
    Prioridad:
    1. Variable de entorno SSL_CERT_FILE
    2. Configuración guardada en archivo
    3. Buscar certificado en directorio de la aplicación
    """
    # Prioridad 1: Variable de entorno
    env_cert = os.getenv('SSL_CERT_FILE')
    if env_cert and Path(env_cert).exists():
        return env_cert
    
    # Prioridad 2: Configuración guardada
    config = load_ssl_config()
    cert_path = config.get('ssl_cert_file')
    if cert_path and Path(cert_path).exists():
        return cert_path
    
    # Prioridad 3: Buscar en directorio de la aplicación
    if getattr(sys, "frozen", False):
        exec_dir = Path(sys.executable).resolve().parent
    else:
        exec_dir = Path(__file__).resolve().parent.parent
    
    for cert_name in ['corporate_ca.crt', 'corporate_ca.pem', 'corporate_ca.cer']:
        cert_path = exec_dir / cert_name
        if cert_path.exists():
            return str(cert_path)
    
    return None


def set_ssl_cert_path(cert_path: Optional[str]) -> None:
    """Establece la ruta al certificado SSL personalizado."""
    config = load_ssl_config()
    if cert_path:
        config['ssl_cert_file'] = cert_path
    else:
        config.pop('ssl_cert_file', None)
    save_ssl_config(config)

