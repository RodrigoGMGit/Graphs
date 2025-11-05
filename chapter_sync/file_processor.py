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

logger = logging.getLogger(__name__)

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
        logger.info("No files to process in downloads directory")
        return processed_files
    
    for file_path in files_to_process:
        try:
            filename = file_path.name
            
            # Identify file type
            file_info = _identify_file_type(filename)
            if not file_info:
                logger.warning(
                    f"Could not identify file type for {filename}. "
                    "Skipping. Expected prefixes: {list(PREFIX_MAPPING.keys())}"
                )
                continue
            
            standardized_name, pattern = file_info
            
            # Extract date from filename
            date_obj = parse_date_from_filename(filename, pattern)
            if not date_obj:
                logger.warning(
                    f"Could not extract date from filename: {filename}. "
                    "This should not happen. Skipping file."
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
                    logger.error(f"Too many duplicate files for {new_filename}")
                    break
            
            # Move file (this removes original)
            shutil.move(str(file_path), str(dest_path))
            logger.info(f"Moved: {file_path} → {dest_path}")
            processed_files.append((file_path, dest_path))
            
        except OSError as e:
            logger.error(f"Failed to process {file_path}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing {file_path}: {e}", exc_info=True)
            continue
    
    return processed_files

