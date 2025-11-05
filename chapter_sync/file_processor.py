"""File processing module for renaming and moving downloaded files.

This module handles automatic processing of downloaded Excel files:
- Extracts dates from filenames
- Renames files with standardized names and YYYY-MM-DD date format
- Moves files to appropriate subdirectories in chapter_sync/files
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path for imports
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)

# Days threshold for automatic download
DAYS_THRESHOLD = 6

# Pattern keys matching file_downloading/get_files.py
DMY_DOTS = "DMY_DOTS"  # 09.06.2025  or 09-06-2025
YMD_COMPACT = "YMD_COMPACT"  # 20250616
DMY_UNDERSCORE_2Y = "DMY_UNDERSCORE_2Y"  # 31_05_25  -> 2025-05-31 (assume 20YY)

# Compile regexes once
RX_DMY_DOTS = re.compile(r"(?<!\d)(\d{2})[.\-](\d{2})[.\-](\d{4})(?!\d)")
RX_YMD_COMPACT = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")
RX_DMY_UNDERSCORE_2Y = re.compile(r"(?<!\d)(\d{2})_(\d{2})_(\d{2})(?!\d)")
RX_DMY_COMPACT_2Y = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)")  # DDMMYY format (no separators)

# Unicode dashes → ASCII hyphen
DASH_MAP = str.maketrans({"\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"})

# Mapping from source prefixes to standardized names
PREFIX_MAPPING = {
    "Pases a Producción y Reversiones": "Calidad",
    "BD Dashboard OKR T.Desarrollo": "TMD",
    "Reporte_NM_": "NivelesMadurez",
    "dashboard-": "DR",
}

# Pattern mapping for each prefix
PREFIX_PATTERNS = {
    "Pases a Producción y Reversiones": DMY_DOTS,
    "BD Dashboard OKR T.Desarrollo": DMY_DOTS,
    "Reporte_NM_": DMY_UNDERSCORE_2Y,
    "dashboard-": YMD_COMPACT,
}


def _norm_name(name: str) -> str:
    """Normalize Unicode & drop trailing '(n)' before the extension; unify dashes."""
    base, ext = os.path.splitext(name)
    base = re.sub(r"\(\d+\)$", "", base).translate(DASH_MAP)
    return unicodedata.normalize("NFKC", base) + ext


def _starts_with_prefix(name: str, prefix: str) -> bool:
    """Check if normalized filename starts with prefix (case-insensitive)."""
    return _norm_name(name).lower().startswith(prefix.lower())


def parse_date_from_filename(filename: str, pattern: str) -> Optional[datetime]:
    """Extract date from filename using the specified pattern.
    
    Args:
        filename: The filename to parse
        pattern: One of DMY_DOTS, YMD_COMPACT, or DMY_UNDERSCORE_2Y
        
    Returns:
        datetime object if date found, None otherwise
    """
    base = os.path.splitext(_norm_name(filename))[0]
    
    if pattern == DMY_DOTS:
        m = RX_DMY_DOTS.search(base)
        if m:
            d, mth, y = map(int, m.groups())
            return datetime(y, mth, d)
    elif pattern == YMD_COMPACT:
        m = RX_YMD_COMPACT.search(base)
        if m:
            y, mth, d = map(int, m.groups())
            return datetime(y, mth, d)
    elif pattern == DMY_UNDERSCORE_2Y:
        # Try underscore format first (DD_MM_YY)
        m = RX_DMY_UNDERSCORE_2Y.search(base)
        if m:
            d, mth, yy = map(int, m.groups())
            return datetime(2000 + yy, mth, d)
        # Try compact format (DDMMYY) as fallback
        m = RX_DMY_COMPACT_2Y.search(base)
        if m:
            d, mth, yy = map(int, m.groups())
            return datetime(2000 + yy, mth, d)
    
    return None


def extract_date_from_standardized_filename(filename: str) -> Optional[datetime]:
    """Extract date from a standardized filename in YYYY-MM-DD format.
    
    Args:
        filename: Filename expected to contain YYYY-MM-DD date
        
    Returns:
        datetime object if date found, None otherwise
    """
    # Pattern for YYYY-MM-DD in filename
    pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
    match = pattern.search(filename)
    if match:
        y, m, d = map(int, match.groups())
        try:
            return datetime(y, m, d)
        except ValueError:
            return None
    return None


def _get_downloads_dir() -> Path:
    """Get the downloads directory path, handling executable mode."""
    if getattr(sys, "frozen", False):
        # Running as executable
        exec_dir = Path(sys.executable).resolve().parent
        return exec_dir / "downloads"
    else:
        # Running as script
        workspace_root = Path(__file__).resolve().parent.parent
        return workspace_root / "downloads"


def _get_files_dir() -> Path:
    """Get the chapter_sync/files directory path, handling executable mode."""
    if getattr(sys, "frozen", False):
        # Running as executable
        exec_dir = Path(sys.executable).resolve().parent
        return exec_dir / "chapter_sync" / "files"
    else:
        # Running as script
        workspace_root = Path(__file__).resolve().parent.parent
        return workspace_root / "chapter_sync" / "files"


def _identify_file_type(filename: str) -> Optional[tuple[str, str]]:
    """Identify the file type and pattern based on filename prefix.
    
    Args:
        filename: The filename to identify
        
    Returns:
        Tuple of (standardized_name, pattern) if matched, None otherwise
    """
    for prefix, standardized_name in PREFIX_MAPPING.items():
        if _starts_with_prefix(filename, prefix):
            pattern = PREFIX_PATTERNS[prefix]
            return standardized_name, pattern
    return None


def process_downloaded_files(downloaded_paths: Optional[list[Path]] = None) -> list[tuple[Path, Path]]:
    """Process downloaded files: rename, extract date, and move to chapter_sync/files.
    
    This function:
    1. Scans downloads directory for .xlsx files (or uses provided paths)
    2. Identifies file type based on prefix
    3. Extracts date from filename
    4. Renames to standardized format: {Name}-{YYYY-MM-DD}.xlsx
    5. Moves to chapter_sync/files/{Name}/ subdirectory
    6. Removes original file from downloads (move operation)
    
    Args:
        downloaded_paths: Optional list of specific file paths to process.
                         If None, scans entire downloads directory.
        
    Returns:
        List of tuples (source_path, destination_path) for successfully processed files
        
    Raises:
        OSError: If file operations fail (permissions, etc.)
    """
    downloads_dir = _get_downloads_dir()
    files_dir = _get_files_dir()
    
    # Ensure target directory exists
    files_dir.mkdir(parents=True, exist_ok=True)
    
    processed_files: list[tuple[Path, Path]] = []
    
    # Get files to process
    if downloaded_paths:
        files_to_process = [Path(p) for p in downloaded_paths if Path(p).suffix.lower() == ".xlsx"]
    else:
        # Scan downloads directory recursively
        files_to_process = []
        if downloads_dir.exists():
            for file_path in downloads_dir.rglob("*.xlsx"):
                files_to_process.append(file_path)
    
    if not files_to_process:
        logger.info("No hay archivos para procesar en el directorio de descargas")
        return processed_files
    
    for file_path in files_to_process:
        try:
            filename = file_path.name
            
            # Identify file type
            file_info = _identify_file_type(filename)
            if not file_info:
                logger.warning(
                    f"No se pudo identificar el tipo de archivo para {filename}. "
                    f"Omitiendo. Prefijos esperados: {list(PREFIX_MAPPING.keys())}"
                )
                continue
            
            standardized_name, pattern = file_info
            
            # Extract date from filename
            date_obj = parse_date_from_filename(filename, pattern)
            if not date_obj:
                logger.warning(
                    f"No se pudo extraer la fecha del nombre de archivo: {filename}. "
                    "Esto no debería ocurrir. Omitiendo archivo."
                )
                continue
            
            # Format date as YYYY-MM-DD
            date_str = date_obj.strftime("%Y-%m-%d")
            
            # Create new filename
            new_filename = f"{standardized_name}-{date_str}.xlsx"
            
            # Determine destination directory
            dest_dir = files_dir / standardized_name
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Destination path
            dest_path = dest_dir / new_filename
            
            # Handle duplicate files (add counter if needed)
            counter = 1
            original_dest = dest_path
            while dest_path.exists():
                base_name = f"{standardized_name}-{date_str}"
                dest_path = dest_dir / f"{base_name} ({counter}).xlsx"
                counter += 1
                if counter > 1000:  # Safety limit
                    logger.error(f"Demasiados archivos duplicados para {new_filename}")
                    break
            
            # Move file (this removes original)
            shutil.move(str(file_path), str(dest_path))
            logger.info(f"Movido: {file_path} → {dest_path}")
            processed_files.append((file_path, dest_path))
            
        except OSError as e:
            logger.error(f"Error al procesar {file_path}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error inesperado al procesar {file_path}: {e}", exc_info=True)
            continue
    
    return processed_files


def get_types_needing_download(files_dir: Path) -> dict[str, dict]:
    """Check which file types need to be downloaded based on date thresholds.
    
    For each file type (Calidad, DR, NivelesMadurez, TMD), checks if:
    - No files exist for that type, OR
    - The latest file is older than DAYS_THRESHOLD days
    
    Args:
        files_dir: Directory containing subdirectories for each file type
        
    Returns:
        Dictionary mapping file type to dict with:
        - 'needs_download': bool indicating if download is needed
        - 'latest_date': Optional[datetime] with the latest local file date (None if no files)
    """
    result: dict[str, dict] = {}
    file_types = ["Calidad", "DR", "NivelesMadurez", "TMD"]
    today = datetime.now().date()
    
    for file_type in file_types:
        type_dir = files_dir / file_type
        latest_date: Optional[datetime] = None
        needs_download = False
        
        if not type_dir.exists():
            # No directory means no files, need download
            logger.info(f"No se encontró directorio de archivos para {file_type}, se descargará")
            needs_download = True
        else:
            # Find all .xlsx files in the type directory
            xlsx_files = list(type_dir.glob("*.xlsx"))
            
            if not xlsx_files:
                # No files found, need download
                logger.info(f"No se encontraron archivos para {file_type}, se descargará")
                needs_download = True
            else:
                # Extract dates from all files and find the latest
                for file_path in xlsx_files:
                    date_obj = extract_date_from_standardized_filename(file_path.name)
                    if date_obj:
                        if latest_date is None or date_obj > latest_date:
                            latest_date = date_obj
                
                if latest_date is None:
                    # Could not extract dates from any file, need download
                    logger.warning(
                        f"No se pudieron extraer fechas de ningún archivo para {file_type}, "
                        "se descargará para asegurar que tengamos archivos válidos"
                    )
                    needs_download = True
                else:
                    # Calculate days since latest file
                    days_old = (today - latest_date.date()).days
                    
                    if days_old > DAYS_THRESHOLD:
                        logger.info(
                            f"{file_type}: el archivo más reciente tiene {days_old} días "
                            f"(umbral: {DAYS_THRESHOLD}), se descargará"
                        )
                        needs_download = True
                    else:
                        logger.debug(
                            f"{file_type}: el archivo más reciente tiene {days_old} días, "
                            f"dentro del umbral ({DAYS_THRESHOLD} días)"
                        )
        
        result[file_type] = {
            "needs_download": needs_download,
            "latest_date": latest_date
        }
    
    return result


def check_and_download_if_needed(files_dir: Path) -> None:
    """Check file dates and download if needed.
    
    This function:
    1. Checks which file types need download (based on date thresholds)
    2. For each type needing download, discovers the latest remote file date
    3. Compares remote date with local date to avoid unnecessary downloads
    4. Downloads only the types that actually need it (remote date is newer)
    5. Processes downloaded files automatically
    6. Logs all operations and errors
    
    Args:
        files_dir: Directory containing subdirectories for each file type
    """
    # Check which types need download and get their local dates
    types_info = get_types_needing_download(files_dir)
    
    # Filter to only types that need download
    types_needing_download = [
        file_type for file_type, info in types_info.items()
        if info["needs_download"]
    ]
    
    if not types_needing_download:
        logger.debug("Todos los tipos de archivo están actualizados, no se necesita descarga")
        return
    
    logger.info(
        f"Tipos de archivo que necesitan descarga ({len(types_needing_download)}): "
        f"{', '.join(types_needing_download)}"
    )
    
    # Import here to avoid circular dependency
    from file_downloading.get_files import download_specific_types, discover_latest_file_date
    
    # Download each type individually, after checking remote dates
    types_to_actually_download = []
    
    for file_type in types_needing_download:
        local_date = types_info[file_type]["latest_date"]
        
        # Discover remote file date
        logger.info(f"Verificando fecha de archivo remoto para {file_type}")
        remote_date = discover_latest_file_date(file_type, logger=logger)
        
        if remote_date is None:
            # Discovery failed - cannot download anyway, skip
            logger.warning(
                f"No se pudo obtener fecha del archivo remoto para {file_type}. "
                "Omitiendo descarga (no se puede descargar de todas formas)."
            )
            continue
        
        # Compare dates (only date part, ignore time/timezone)
        remote_date_only = remote_date.date()
        
        if local_date is None:
            # No local file, proceed with download
            logger.info(
                f"{file_type}: No hay archivo local, procediendo con descarga "
                f"(archivo remoto: {remote_date_only})"
            )
            types_to_actually_download.append(file_type)
        else:
            local_date_only = local_date.date()
            
            if remote_date_only == local_date_only:
                # Same date, skip download
                logger.info(
                    f"{file_type}: Archivo remoto tiene misma fecha que local "
                    f"({local_date_only}), omitiendo descarga"
                )
            elif remote_date_only < local_date_only:
                # Remote is older, skip download
                logger.info(
                    f"{file_type}: Archivo remoto es más antiguo que local "
                    f"(remoto: {remote_date_only}, local: {local_date_only}), omitiendo descarga"
                )
            else:
                # Remote is newer, proceed with download
                logger.info(
                    f"{file_type}: Archivo remoto es más reciente que local "
                    f"(remoto: {remote_date_only}, local: {local_date_only}), procediendo con descarga"
                )
                types_to_actually_download.append(file_type)
    
    if not types_to_actually_download:
        logger.info("No hay archivos para descargar después de comparar fechas")
        return
    
    logger.info(
        f"Archivos a descargar después de comparar fechas ({len(types_to_actually_download)}): "
        f"{', '.join(types_to_actually_download)}"
    )
    
    # Download each type
    for file_type in types_to_actually_download:
        try:
            logger.info(f"Buscando archivos más recientes para {file_type}")
            
            # Download this specific type
            downloaded_paths = download_specific_types([file_type], logger=logger)
            
            if downloaded_paths:
                logger.info(f"Descarga completada para {file_type}: {len(downloaded_paths)} archivo(s)")
                
                # Process downloaded files (rename, move to files_dir)
                processed = process_downloaded_files(downloaded_paths)
                if processed:
                    logger.info(
                        f"Archivos procesados para {file_type}: "
                        f"{len(processed)} archivo(s) movidos a {files_dir}"
                    )
                else:
                    logger.warning(f"No se pudieron procesar archivos descargados para {file_type}")
            else:
                logger.warning(
                    f"No se descargaron archivos para {file_type}. "
                    "Continuando con archivos existentes."
                )
                
        except Exception as e:
            error_msg = f"Error al descargar {file_type}: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)
            logger.info(f"Continuando con archivos existentes para {file_type}")
            # Continue with next type, don't block execution

