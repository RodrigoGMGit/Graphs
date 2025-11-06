import os
import re
import sys
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# ==== ENV / CONFIG ====


def _load_env_with_logging(logger=None, silent=False):
    """Load .env file with detailed logging about search paths.

    Args:
        logger: Optional logger instance (if None, uses print)
        silent: If True, suppress all logging messages
    """
    if silent:

        def log_func(msg):
            pass  # no-op function
    else:
        log_func = logger.info if logger else print

    if getattr(sys, "frozen", False):
        # Running as executable - look for .env in sys._MEIPASS (bundled files)
        # This is where PyInstaller extracts bundled data files
        meipass = Path(getattr(sys, "_MEIPASS", Path.cwd()))
        env_path = meipass / ".env"
        log_func(f"Buscando .env en bundle (sys._MEIPASS): {env_path}")
        if env_path.exists():
            log_func(f"✓ Archivo .env encontrado en bundle: {env_path}")
            load_dotenv(env_path, override=True)
        else:
            log_func(f"✗ Archivo .env no encontrado en bundle: {env_path}")
            # Fallback to executable directory (for external .env file)
            exec_dir = Path(sys.executable).resolve().parent
            exec_env = exec_dir / ".env"
            log_func(f"Buscando .env en directorio del ejecutable: {exec_env}")
            if exec_env.exists():
                log_func(f"✓ Archivo .env encontrado en: {exec_env}")
                load_dotenv(exec_env, override=True)
            else:
                log_func(f"✗ Archivo .env no encontrado en: {exec_env}")
                log_func("Intentando buscar .env en directorios padres...")
                load_dotenv()
    else:
        # Running as script - look in project root and parent dirs
        log_func("Buscando .env en directorio de trabajo y padres...")
        load_dotenv()


# Load environment variables
_load_env_with_logging()

TENANT_ID = os.getenv("AZ_TENANT_ID", "")
CLIENT_ID = os.getenv("AZ_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZ_CLIENT_SECRET", "")


def _check_credentials(logger=None) -> tuple[str, str, str]:
    """Check and return credentials, raising descriptive error if missing."""
    log_func = logger.warning if logger else print

    if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
        if getattr(sys, "frozen", False):
            meipass = Path(getattr(sys, "_MEIPASS", Path.cwd()))
            bundle_env = meipass / ".env"
            exec_dir = Path(sys.executable).resolve().parent
            exec_env = exec_dir / ".env"
            error_msg = (
                "Missing AZ_TENANT_ID / AZ_CLIENT_ID / "
                "AZ_CLIENT_SECRET in environment (.env).\n"
                "El archivo .env debe estar incluido en el build "
                "del ejecutable o en:\n"
                f"  - Bundle: {bundle_env}\n"
                f"  - Directorio del ejecutable: {exec_env}\n"
                "con las siguientes variables:\n"
                "  AZ_TENANT_ID=tu_tenant_id\n"
                "  AZ_CLIENT_ID=tu_client_id\n"
                "  AZ_CLIENT_SECRET=tu_client_secret"
            )
        else:
            error_msg = (
                "Missing AZ_TENANT_ID / AZ_CLIENT_ID / "
                "AZ_CLIENT_SECRET in environment (.env).\n"
                "Por favor, crea un archivo .env en la raíz del "
                "proyecto con las credenciales."
            )
        log_func(error_msg)
        raise RuntimeError(error_msg)
    return TENANT_ID, CLIENT_ID, CLIENT_SECRET


DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_DIR", "downloads")).resolve()
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# Pattern keys
DMY_DOTS = "DMY_DOTS"  # 09.06.2025  or 09-06-2025
YMD_COMPACT = "YMD_COMPACT"  # 20250616
# 31_05_25  -> 2025-05-31 (assume 20YY)
DMY_UNDERSCORE_2Y = "DMY_UNDERSCORE_2Y"

# Compile regexes once
RX_DMY_DOTS = re.compile(r"(?<!\d)(\d{2})[.\-](\d{2})[.\-](\d{4})(?!\d)")
RX_YMD_COMPACT = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")
RX_DMY_UNDERSCORE_2Y = re.compile(r"(?<!\d)(\d{2})_(\d{2})_(\d{2})(?!\d)")
# DDMMYY format (no separators)
RX_DMY_COMPACT_2Y = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)")

# Unicode dashes → ASCII hyphen
DASH_MAP = str.maketrans({"\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"})


@dataclass(frozen=True)
class FolderRule:
    url: str
    prefix: str  # filename must start with this (case-insensitive)
    pattern: str  # one of the constants above
    exts: Tuple[str, ...] = (".xlsx",)  # .xlsx only per your requirement


# --- Your four folders with their date rules ---
FOLDERS: List[FolderRule] = [
    # Cantidad y Calidad de Pases (OneDrive) — "Pases a Producción y Reversiones – DD.MM.YYYY.xlsx"
    FolderRule(
        url=(
            "https://credicorponline-my.sharepoint.com/personal/"
            "rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?"
            "id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2F"
            "COE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2F"
            "DB%20Validacion%20Dashboard%2FOKRs%2F"
            "Cantidad%20y%20Calidad%20Pases&ga=1"
        ),
        prefix="Pases a Producción y Reversiones",
        pattern=DMY_DOTS,
    ),
    # TMD (OneDrive) — "BD Dashboard OKR T.Desarrollo - DD.MM.YYYY.xlsx"
    FolderRule(
        url=(
            "https://credicorponline-my.sharepoint.com/personal/"
            "rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?"
            "id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2F"
            "COE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2F"
            "DB%20Validacion%20Dashboard%2FOKRs%2F"
            "TMD%20%28Desarrollo%29&ga=1"
        ),
        prefix="BD Dashboard OKR T.Desarrollo",
        pattern=DMY_DOTS,
    ),
    # SharePoint site — only "Reporte_NM_DD_MM_YY.xlsx"
    FolderRule(
        url=(
            "https://credicorponline.sharepoint.com/sites/Equipodata/"
            "Documentos%20compartidos/Forms/AllItems.aspx?"
            "id=%2Fsites%2FEquipodata%2FDocumentos%20compartidos%2F"
            "General%2FNivel%20de%20Madurez%2FReportes%20Resumen&"
            "sortField=Modified&isAscending=false&"
            "viewid=6dc15532%2D2728%2D4c0b%2Dbff6%2D88c32f50d811&"
            "p=true&ga=1"
        ),
        prefix="Reporte_NM_",
        pattern=DMY_UNDERSCORE_2Y,
    ),
    # IA COPILOT (OneDrive) — "dashboard-YYYYMMDD.xlsx"
    FolderRule(
        url=(
            "https://credicorponline-my.sharepoint.com/personal/"
            "rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?"
            "id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2F"
            "COE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2F"
            "IA%20COPILOT&sortField=Modified&isAscending=false&ga=1"
        ),
        prefix="dashboard-",
        pattern=YMD_COMPACT,
    ),
]

# Mapping from standardized type names to prefixes
TYPE_TO_PREFIX = {
    "Calidad": "Pases a Producción y Reversiones",
    "TMD": "BD Dashboard OKR T.Desarrollo",
    "NivelesMadurez": "Reporte_NM_",
    "DR": "dashboard-",
}


# ==== Utilities ====
def sanitize_filename(name: str) -> str:
    """Remove characters illegal on Windows/macOS and strip trailing spaces."""
    # Windows forbidden: < > : " / \ | ? * and control chars
    forbidden = '<>:"/\\|?*'
    name = "".join(ch for ch in name if 31 < ord(ch) != 127 and ch not in forbidden)
    return name.rstrip(" .")


def ensure_unique_path(dirpath: Path, filename: str) -> Path:
    """Return a non-clobbering path (adds (1), (2) … if needed)."""
    base, ext = os.path.splitext(filename)
    candidate = dirpath / filename
    i = 1
    while candidate.exists():
        candidate = dirpath / f"{base} ({i}){ext}"
        i += 1
    return candidate


def norm_name(name: str) -> str:
    """Normalize Unicode & drop trailing '(n)' before the extension;
    unify dashes."""
    base, ext = os.path.splitext(name)
    base = re.sub(r"\(\d+\)$", "", base).translate(DASH_MAP)
    return unicodedata.normalize("NFKC", base) + ext


def starts_with_prefix(name: str, prefix: str) -> bool:
    return norm_name(name).lower().startswith(prefix.lower())


def parse_date_from_name(name: str, pattern: str) -> Optional[datetime]:
    """Return a UTC datetime parsed from filename per rule, else None."""
    base = os.path.splitext(norm_name(name))[0]
    if pattern == DMY_DOTS:
        m = RX_DMY_DOTS.search(base)
        if m:
            d, mth, y = map(int, m.groups())
            try:
                return datetime(y, mth, d, tzinfo=timezone.utc)
            except ValueError:
                return None
    elif pattern == YMD_COMPACT:
        m = RX_YMD_COMPACT.search(base)
        if m:
            y, mth, d = map(int, m.groups())
            try:
                return datetime(y, mth, d, tzinfo=timezone.utc)
            except ValueError:
                return None
    elif pattern == DMY_UNDERSCORE_2Y:
        # Try underscore format first (DD_MM_YY)
        m = RX_DMY_UNDERSCORE_2Y.search(base)
        if m:
            d, mth, yy = map(int, m.groups())
            try:
                return datetime(2000 + yy, mth, d, tzinfo=timezone.utc)
            except ValueError:
                pass  # Try fallback format below
        # Try compact format (DDMMYY) as fallback
        m = RX_DMY_COMPACT_2Y.search(base)
        if m:
            d, mth, yy = map(int, m.groups())
            try:
                return datetime(2000 + yy, mth, d, tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


# ==== Microsoft Graph client (Sites.Read.All route) ====
class GraphClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.session = requests.Session()
        tok = self._token(tenant_id, client_id, client_secret)
        self.h = {"Authorization": f"Bearer {tok}"}

    def _token(self, tenant: str, cid: str, secret: str) -> str:
        r = self.session.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": cid,
                "client_secret": secret,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
            timeout=30,
        )
        r.raise_for_status()
        js = r.json()
        if "access_token" not in js:
            raise RuntimeError(f"Token error: {js}")
        return js["access_token"]

    def _get(self, url: str) -> requests.Response:
        while True:
            r = self.session.get(url, headers=self.h, timeout=60)
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "3")))
                continue
            r.raise_for_status()
            return r

    def _paged(self, url: str) -> Iterable[dict]:
        while url:
            data = self._get(url).json()
            yield from data.get("value", [])
            url = data.get("@odata.nextLink")

    @staticmethod
    def split_url(url: str) -> Tuple[str, str, str, str, str]:
        """
        Returns (host, site_path, library, folder_rel, root_kind)
        Accepts OneDrive 'onedrive.aspx?id=...' and SharePoint
        'AllItems.aspx?id=...' links.
        """
        u = urllib.parse.urlparse(url)
        host = u.netloc
        qs = urllib.parse.parse_qs(u.query)
        if "id" in qs and qs["id"]:
            server_rel = urllib.parse.unquote(qs["id"][0])
        else:
            server_rel = urllib.parse.unquote(u.path.split("/Forms/AllItems.aspx")[0])

        parts = [p for p in server_rel.strip("/").split("/") if p]
        if len(parts) < 3:
            raise ValueError(f"URL path too short: {url}")

        root_kind, site_or_user, library = parts[0], parts[1], parts[2]
        site_path = f"/{root_kind}/{site_or_user}"
        folder_rel = "/".join(parts[3:]) if len(parts) > 3 else ""
        return host, site_path, library, folder_rel, root_kind

    def site_id(self, host: str, site_path: str) -> str:
        return self._get(
            f"https://graph.microsoft.com/v1.0/sites/{host}:{site_path}"
        ).json()["id"]

    def drive_id(self, site_id: str, root_kind: str, library: str) -> str:
        # Default drive for personal sites or default library names
        if root_kind == "personal" or library in {
            "Shared Documents",
            "Documentos compartidos",
        }:
            return self._get(
                f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"
            ).json()["id"]
        # Non-default library → match by name
        for d in (
            self._get(f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives")
            .json()
            .get("value", [])
        ):
            if d.get("name") == library:
                return d["id"]
        raise RuntimeError(f"Library '{library}' not found on site {site_id}")

    def list_children(self, drive_id: str, folder_rel: str) -> List[dict]:
        if folder_rel:
            enc = urllib.parse.quote(folder_rel.strip("/"))
            url = (
                f"https://graph.microsoft.com/v1.0/drives/{drive_id}/"
                f"root:/{enc}:/children"
            )
        else:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
        return list(self._paged(url))

    def download_item(self, drive_id: str, item_id: str, dest_path: Path) -> Path:
        """
        Download a drive item to dest_path (file path, not folder).
        Streams content; returns the saved path.
        """
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        url = (
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/"
            f"items/{item_id}/content"
        )
        with self.session.get(url, headers=self.h, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return dest_path


# ==== Selection logic ====
def choose_latest(items: List[dict], rule: FolderRule) -> Optional[dict]:
    """Filter by extension & prefix, parse date per rule, tie-break on
    lastModifiedDateTime."""
    cand = []
    exts = set(x.lower() for x in rule.exts)

    for it in items:
        if "folder" in it:
            continue
        name = it["name"]
        if os.path.splitext(name)[1].lower() not in exts:
            continue
        if not starts_with_prefix(name, rule.prefix):
            continue

        dt = parse_date_from_name(name, rule.pattern)
        if dt is None:
            continue

        mod = datetime.fromisoformat(
            it["lastModifiedDateTime"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        cand.append((dt, mod, it))

    if not cand:
        return None

    # by parsed date, then modified
    cand.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return cand[0][2]


def find_latest_month_folder(
    gc: GraphClient, drive_id: str, parent_folder_rel: str
) -> Optional[str]:
    """
    Find the latest month folder (YYYYMM format) in the parent directory.
    Returns the folder name (e.g., "202510") or None if no matching
    folders found.
    """
    items = gc.list_children(drive_id, parent_folder_rel)

    # Filter for folders matching YYYYMM pattern (6 digits)
    month_folders = []
    for it in items:
        if "folder" not in it:
            continue
        name = it["name"]
        # Check if name matches YYYYMM pattern (exactly 6 digits)
        if re.match(r"^\d{6}$", name):
            month_folders.append(name)

    if not month_folders:
        return None

    # Sort by name descending (YYYYMM format naturally sorts correctly)
    month_folders.sort(reverse=True)
    return month_folders[0]


def run_downloads(
    gc: GraphClient, rules: List[FolderRule], quiet: bool = False, log_func=None
) -> list[Path]:
    saved_paths: list[Path] = []

    for rule in rules:
        if not quiet:
            print(
                f"\n=== Processing folder ===\n{rule.url}\nRule: prefix='{rule.prefix}', pattern={rule.pattern}"
            )
        try:
            host, site_path, library, folder_rel, root_kind = gc.split_url(rule.url)
            site_id = gc.site_id(host, site_path)
            drive_id = gc.drive_id(site_id, root_kind, library)

            # Special handling for Reportes Resumen: find latest month folder
            if "Reportes Resumen" in folder_rel:
                if not quiet:
                    print(
                        "  Detected Reportes Resumen folder, finding latest month subfolder..."
                    )
                latest_month = find_latest_month_folder(gc, drive_id, folder_rel)
                if latest_month:
                    folder_rel = f"{folder_rel}/{latest_month}"
                    if not quiet:
                        print(f"  Using month folder: {latest_month}")
                else:
                    if not quiet:
                        print(
                            "  Warning: No month folders found in Reportes Resumen, proceeding with parent folder"
                        )

            items = gc.list_children(drive_id, folder_rel)

            if not items:
                if not quiet:
                    print("  No items found in this folder.")
                continue

            chosen = choose_latest(items, rule)
            if not chosen:
                if not quiet:
                    print("  No matching .xlsx files for this rule.")
                continue

            # Prepare destination path
            subdir_name = sanitize_filename(rule.prefix) or "downloads"
            out_dir = DOWNLOAD_ROOT / subdir_name
            out_dir.mkdir(parents=True, exist_ok=True)

            filename = sanitize_filename(chosen["name"])
            dest = ensure_unique_path(out_dir, filename)

            # Download - only show essential message
            if quiet:
                if log_func:
                    log_func(f"Descargando: {chosen['name']}")
                else:
                    print(f"Descargando: {chosen['name']}")
            else:
                print(f"  Downloading: {chosen['name']} → {dest}")
            saved = gc.download_item(drive_id, chosen["id"], dest)
            if not quiet:
                print(f"  Saved: {saved}")
            saved_paths.append(saved)

        except requests.HTTPError as e:
            print(f"  HTTP error: {e.response.status_code} {e.response.text}")
        except Exception as ex:
            print(f"  ERROR: {ex}")

    return saved_paths


def discover_latest_file_date(file_type: str, logger=None) -> Optional[datetime]:
    """Discover the date of the latest file on the server for a given type without downloading.

    This function reuses the logic from run_downloads and choose_latest to find
    the most recent file on the server, but only returns its date without downloading.

    Args:
        file_type: Standardized type name (Calidad, DR, NivelesMadurez, TMD)
        logger: Optional logger instance (if None, uses print)

    Returns:
        datetime object with the date of the latest file, or None if:
        - File type not found
        - No matching files found
        - Connection/API error occurred
    """
    if logger is None:

        def log_func(msg):
            pass  # Silent in discovery mode
    else:

        def log_func(msg):
            logger.debug(msg)

    # Get prefix for requested type
    if file_type not in TYPE_TO_PREFIX:
        if logger:
            logger.warning(f"Tipo de archivo desconocido '{file_type}' para discovery")
        return None

    prefix = TYPE_TO_PREFIX[file_type]

    # Find the rule for this prefix
    rule = None
    for r in FOLDERS:
        if r.prefix == prefix:
            rule = r
            break

    if not rule:
        if logger:
            logger.warning(f"No se encontró regla de descarga para {file_type}")
        return None

    try:
        # Check credentials before initializing client
        try:
            tenant_id, client_id, client_secret = _check_credentials(logger)
        except RuntimeError as e:
            if logger:
                logger.debug(f"Credenciales no disponibles para {file_type}: {e}")
            return None

        # Initialize Graph client
        gc = GraphClient(tenant_id, client_id, client_secret)

        # Get folder info
        host, site_path, library, folder_rel, root_kind = gc.split_url(rule.url)
        site_id = gc.site_id(host, site_path)
        drive_id = gc.drive_id(site_id, root_kind, library)

        # Special handling for Reportes Resumen: find latest month folder
        if "Reportes Resumen" in folder_rel:
            latest_month = find_latest_month_folder(gc, drive_id, folder_rel)
            if latest_month:
                folder_rel = f"{folder_rel}/{latest_month}"

        # List files
        items = gc.list_children(drive_id, folder_rel)

        if not items:
            return None

        # Find latest file using existing logic
        chosen = choose_latest(items, rule)
        if not chosen:
            return None

        # Extract date from filename
        filename = chosen["name"]
        date_obj = parse_date_from_name(filename, rule.pattern)

        return date_obj

    except Exception as e:
        if logger:
            logger.debug(f"Error durante discovery para {file_type}: {e}")
        return None


def download_specific_types(types_to_download: list[str], logger=None) -> list[Path]:
    """Download files for specific types only.

    Args:
        types_to_download: List of standardized type names (Calidad, DR, NivelesMadurez, TMD)
        logger: Optional logger instance (if None, uses print)

    Returns:
        List of paths to downloaded files
    """
    if logger is None:

        def log_func(msg):
            print(msg)
    else:

        def log_func(msg):
            logger.info(msg)

    if not types_to_download:
        return []

    # Get prefixes for requested types
    prefixes_to_download = set()
    for file_type in types_to_download:
        if file_type in TYPE_TO_PREFIX:
            prefixes_to_download.add(TYPE_TO_PREFIX[file_type])
        else:
            log_func(
                f"Advertencia: Tipo de archivo desconocido '{file_type}', omitiendo"
            )

    if not prefixes_to_download:
        log_func("No hay tipos válidos para descargar")
        return []

    # Filter FOLDERS to only include rules for requested types
    filtered_rules = [rule for rule in FOLDERS if rule.prefix in prefixes_to_download]

    if not filtered_rules:
        log_func("No se encontraron reglas de descarga para los tipos solicitados")
        return []

    saved_paths: list[Path] = []

    try:
        # Check credentials before initializing client
        try:
            tenant_id, client_id, client_secret = _check_credentials(logger)
        except RuntimeError as e:
            error_msg = f"No se pueden descargar archivos: {e}"
            log_func(error_msg)
            if logger:
                logger.error(error_msg, exc_info=True)
            return []

        # Initialize Graph client (silently)
        gc = GraphClient(tenant_id, client_id, client_secret)

        # Run downloads with filtered rules (quiet mode for less verbose output)
        saved_paths = run_downloads(gc, filtered_rules, quiet=True, log_func=log_func)

        if saved_paths:
            log_func(f"Descarga completada: {len(saved_paths)} archivo(s)")
        else:
            log_func("No se encontraron archivos nuevos para descargar.")

    except requests.HTTPError as e:
        error_msg = f"Error HTTP al descargar archivos: {e.response.status_code} {e.response.text}"
        log_func(error_msg)
        if logger:
            logger.error(error_msg, exc_info=True)
    except requests.ConnectionError as e:
        error_msg = f"Error de conexión al descargar archivos: {e}"
        log_func(error_msg)
        if logger:
            logger.error(error_msg, exc_info=True)
    except Exception as e:
        error_msg = f"Error inesperado al descargar archivos: {e}"
        log_func(error_msg)
        if logger:
            logger.error(error_msg, exc_info=True)

    return saved_paths


def main():
    print("Token: acquiring (Sites.Read.All-only flow)…")
    gc = GraphClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    print(f"OK. Download root: {DOWNLOAD_ROOT}")

    saved = run_downloads(gc, FOLDERS)
    if saved:
        print("\n=== Done. Files saved ===")
        for p in saved:
            print(f" - {p}")

        # Process downloaded files: rename, date, and move to chapter_sync/files
        print("\n=== Processing downloaded files ===")
        try:
            from chapter_sync.file_processor import process_downloaded_files

            processed = process_downloaded_files(saved)
            if processed:
                print(f"Successfully processed {len(processed)} file(s):")
                for source, dest in processed:
                    print(f"  {source.name} → {dest}")
            else:
                print("No files were processed.")
        except Exception as e:
            print(f"Warning: File processing failed: {e}")
            print("Files remain in downloads directory. You can process them manually.")
    else:
        print("\nNo files were saved (nothing matched your rules).")


if __name__ == "__main__":
    main()
