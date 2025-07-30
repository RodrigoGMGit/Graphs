import os
import re
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

import requests
from dotenv import load_dotenv

# ==== ENV / CONFIG ====
load_dotenv()  # reads .env in the working directory

TENANT_ID = os.environ["AZ_TENANT_ID"]
CLIENT_ID = os.environ["AZ_CLIENT_ID"]
CLIENT_SECRET = os.environ["AZ_CLIENT_SECRET"]

# Pattern keys
DMY_DOTS = "DMY_DOTS"  # 09.06.2025  or 09-06-2025
YMD_COMPACT = "YMD_COMPACT"  # 20250616
DMY_UNDERSCORE_2Y = "DMY_UNDERSCORE_2Y"  # 31_05_25  -> 2025-05-31 (assume 20YY)

# Compile regexes once
RX_DMY_DOTS = re.compile(r"(?<!\d)(\d{2})[.\-](\d{2})[.\-](\d{4})(?!\d)")
RX_YMD_COMPACT = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")
RX_DMY_UNDERSCORE_2Y = re.compile(r"(?<!\d)(\d{2})_(\d{2})_(\d{2})(?!\d)")

# Unicode dashes → ASCII hyphen
DASH_MAP = str.maketrans({"\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"})


@dataclass(frozen=True)
class FolderRule:
    url: str
    prefix: str  # filename must start with this (case-insensitive)
    pattern: str  # one of the constants above
    exts: Tuple[str, ...] = (".xlsx",)  # restrict to .xlsx as requested


# Your four folders with their rules
FOLDERS: List[FolderRule] = [
    FolderRule(
        url="https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FDB%20Validacion%20Dashboard%2FOKRs%2FCantidad%20y%20Calidad%20Pases&ga=1",
        prefix="Pases a Producción y Reversiones",
        pattern=DMY_DOTS,
    ),
    FolderRule(
        url="https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FDB%20Validacion%20Dashboard%2FOKRs%2FTMD%20%28Desarrollo%29&ga=1",
        prefix="BD Dashboard OKR T.Desarrollo",
        pattern=DMY_DOTS,
    ),
    FolderRule(
        url="https://credicorponline.sharepoint.com/sites/Equipodata/Documentos%20compartidos/Forms/AllItems.aspx?id=%2Fsites%2FEquipodata%2FDocumentos%20compartidos%2FGeneral%2FNivel%20de%20Madurez%2FReportes%20Resumen%2F202505&sortField=Modified&isAscending=false&viewid=6dc15532%2D2728%2D4c0b%2Dbff6%2D88c32f50d811&p=true&ga=1",
        prefix="Reporte_NM_",
        pattern=DMY_UNDERSCORE_2Y,
    ),
    FolderRule(
        url="https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FIA%20COPILOT&sortField=Modified&isAscending=false&ga=1",
        prefix="dashboard-",
        pattern=YMD_COMPACT,
    ),
]


# ==== Utilities ====
def norm_name(name: str) -> str:
    """Normalize Unicode dashes and drop trailing '(n)' before the extension."""
    base, ext = os.path.splitext(name)
    base = re.sub(r"\(\d+\)$", "", base).translate(DASH_MAP)
    return unicodedata.normalize("NFKC", base) + ext


def starts_with_prefix(name: str, prefix: str) -> bool:
    return norm_name(name).lower().startswith(prefix.lower())


def parse_date(name: str, pattern: str) -> Optional[datetime]:
    """Return a timezone-aware UTC datetime parsed from filename, or None."""
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
        m = RX_DMY_UNDERSCORE_2Y.search(base)
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
            for item in data.get("value", []):
                yield item
            url = data.get("@odata.nextLink")

    @staticmethod
    def _split_url(url: str) -> Tuple[str, str, str, str, str]:
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


# ==== Selection logic (dry run) ====
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

        dt = parse_date(name, rule.pattern)
        if dt is None:
            continue
        mod = datetime.fromisoformat(
            it["lastModifiedDateTime"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        cand.append((dt, mod, it))

    if not cand:
        return None

    cand.sort(key=lambda t: (t[0], t[1]), reverse=True)  # date ↓ then modified ↓
    return cand[0][2]


def dry_run_for_folder(gc: GraphClient, rule: FolderRule) -> None:
    host, site_path, library, folder_rel, root_kind = gc._split_url(rule.url)
    site_id = gc.site_id(host, site_path)
    drive_id = gc.drive_id(site_id, root_kind, library)
    items = gc.list_children(drive_id, folder_rel)

    chosen = choose_latest(items, rule)
    print(
        f"\n=== Folder ===\n{rule.url}\nRule: prefix='{rule.prefix}', pattern={rule.pattern}"
    )
    if not items:
        print("  No items found.")
        return
    if not chosen:
        print("  No matching .xlsx files for this rule.")
        return

    parsed = parse_date(chosen["name"], rule.pattern)
    mod = datetime.fromisoformat(
        chosen["lastModifiedDateTime"].replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    print("  Would select:")
    print(f"    Name        : {chosen['name']}")
    print(f"    Parsed date : {parsed.date() if parsed else '—'}")
    print(f"    Modified    : {mod.isoformat()}")
    print(f"    Drive ID    : {drive_id}")
    print(f"    Item ID     : {chosen['id']}")
    print(
        f"    Content URL : /v1.0/drives/{drive_id}/items/{chosen['id']}/content  (not called)"
    )


def main():
    print("Token: acquiring (Sites.Read.All-only flow)…")
    gc = GraphClient(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    print("OK. Dry run (no downloads).")
    for rule in FOLDERS:
        try:
            dry_run_for_folder(gc, rule)
        except requests.HTTPError as e:
            print(f"  HTTP error: {e.response.status_code} {e.response.text}")
        except Exception as ex:
            print(f"  ERROR: {ex}")


if __name__ == "__main__":
    main()
