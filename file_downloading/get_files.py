import os
import re
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
load_dotenv()  # reads .env in working dir (or parent dirs)

TENANT_ID = os.environ["AZ_TENANT_ID"]
CLIENT_ID = os.environ["AZ_CLIENT_ID"]
CLIENT_SECRET = os.environ["AZ_CLIENT_SECRET"]
DOWNLOAD_ROOT = Path(os.getenv("DOWNLOAD_DIR", "downloads")).resolve()
DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)

# Pattern keys
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
        url="https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FDB%20Validacion%20Dashboard%2FOKRs%2FCantidad%20y%20Calidad%20Pases&ga=1",
        prefix="Pases a Producción y Reversiones",
        pattern=DMY_DOTS,
    ),
    # TMD (OneDrive) — "BD Dashboard OKR T.Desarrollo - DD.MM.YYYY.xlsx"
    FolderRule(
        url="https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FDB%20Validacion%20Dashboard%2FOKRs%2FTMD%20%28Desarrollo%29&ga=1",
        prefix="BD Dashboard OKR T.Desarrollo",
        pattern=DMY_DOTS,
    ),
    # SharePoint site — only "Reporte_NM_DD_MM_YY.xlsx"
    FolderRule(
        url="https://credicorponline.sharepoint.com/sites/Equipodata/Documentos%20compartidos/Forms/AllItems.aspx?id=%2Fsites%2FEquipodata%2FDocumentos%20compartidos%2FGeneral%2FNivel%20de%20Madurez%2FReportes%20Resumen&sortField=Modified&isAscending=false&viewid=6dc15532%2D2728%2D4c0b%2Dbff6%2D88c32f50d811&p=true&ga=1",
        prefix="Reporte_NM_",
        pattern=DMY_UNDERSCORE_2Y,
    ),
    # IA COPILOT (OneDrive) — "dashboard-YYYYMMDD.xlsx"
    FolderRule(
        url="https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FIA%20COPILOT&sortField=Modified&isAscending=false&ga=1",
        prefix="dashboard-",
        pattern=YMD_COMPACT,
    ),
]


# ==== Utilities ====
def sanitize_filename(name: str) -> str:
    """Remove characters illegal on Windows/macOS and strip trailing spaces."""
    # Windows forbidden: < > : " / \ | ? * and control chars
    name = "".join(ch for ch in name if 31 < ord(ch) != 127 and ch not in '<>:"/\\|?*')
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
    """Normalize Unicode & drop trailing '(n)' before the extension; unify dashes."""
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
            return datetime(y, mth, d, tzinfo=timezone.utc)
    elif pattern == YMD_COMPACT:
        m = RX_YMD_COMPACT.search(base)
        if m:
            y, mth, d = map(int, m.groups())
            return datetime(y, mth, d, tzinfo=timezone.utc)
    elif pattern == DMY_UNDERSCORE_2Y:
        # Try underscore format first (DD_MM_YY)
        m = RX_DMY_UNDERSCORE_2Y.search(base)
        if m:
            d, mth, yy = map(int, m.groups())
            return datetime(2000 + yy, mth, d, tzinfo=timezone.utc)
        # Try compact format (DDMMYY) as fallback
        m = RX_DMY_COMPACT_2Y.search(base)
        if m:
            d, mth, yy = map(int, m.groups())
            return datetime(2000 + yy, mth, d, tzinfo=timezone.utc)
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
        Accepts OneDrive 'onedrive.aspx?id=...' and SharePoint 'AllItems.aspx?id=...' links.
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
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{enc}:/children"
        else:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
        return list(self._paged(url))

    def download_item(self, drive_id: str, item_id: str, dest_path: Path) -> Path:
        """
        Download a drive item to dest_path (file path, not folder).
        Streams content; returns the saved path.
        """
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content"
        with self.session.get(url, headers=self.h, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return dest_path


# ==== Selection logic ====
def choose_latest(items: List[dict], rule: FolderRule) -> Optional[dict]:
    """Filter by extension & prefix, parse date per rule, tie-break on lastModifiedDateTime."""
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

    cand.sort(key=lambda t: (t[0], t[1]), reverse=True)  # by parsed date, then modified
    return cand[0][2]


def find_latest_month_folder(gc: GraphClient, drive_id: str, parent_folder_rel: str) -> Optional[str]:
    """
    Find the latest month folder (YYYYMM format) in the parent directory.
    Returns the folder name (e.g., "202510") or None if no matching folders found.
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


def run_downloads(gc: GraphClient, rules: List[FolderRule]) -> list[Path]:
    saved_paths: list[Path] = []

    for rule in rules:
        print(
            f"\n=== Processing folder ===\n{rule.url}\nRule: prefix='{rule.prefix}', pattern={rule.pattern}"
        )
        try:
            host, site_path, library, folder_rel, root_kind = gc.split_url(rule.url)
            site_id = gc.site_id(host, site_path)
            drive_id = gc.drive_id(site_id, root_kind, library)
            
            # Special handling for Reportes Resumen: find latest month folder
            if "Reportes Resumen" in folder_rel:
                print("  Detected Reportes Resumen folder, finding latest month subfolder...")
                latest_month = find_latest_month_folder(gc, drive_id, folder_rel)
                if latest_month:
                    folder_rel = f"{folder_rel}/{latest_month}"
                    print(f"  Using month folder: {latest_month}")
                else:
                    print("  Warning: No month folders found in Reportes Resumen, proceeding with parent folder")
            
            items = gc.list_children(drive_id, folder_rel)

            if not items:
                print("  No items found in this folder.")
                continue

            chosen = choose_latest(items, rule)
            if not chosen:
                print("  No matching .xlsx files for this rule.")
                continue

            # Prepare destination path
            subdir_name = sanitize_filename(rule.prefix) or "downloads"
            out_dir = DOWNLOAD_ROOT / subdir_name
            out_dir.mkdir(parents=True, exist_ok=True)

            filename = sanitize_filename(chosen["name"])
            dest = ensure_unique_path(out_dir, filename)

            # Download
            print(f"  Downloading: {chosen['name']} → {dest}")
            saved = gc.download_item(drive_id, chosen["id"], dest)
            print(f"  Saved: {saved}")
            saved_paths.append(saved)

        except requests.HTTPError as e:
            print(f"  HTTP error: {e.response.status_code} {e.response.text}")
        except Exception as ex:
            print(f"  ERROR: {ex}")

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
    else:
        print("\nNo files were saved (nothing matched your rules).")


if __name__ == "__main__":
    main()
