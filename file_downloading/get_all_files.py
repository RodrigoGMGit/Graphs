import os
import time
import urllib.parse

import requests
from dotenv import load_dotenv

# Load environment variables from .env in the project root (or parent dirs)
load_dotenv()

# ---------- YOUR CREDENTIALS ----------
TENANT_ID = os.getenv("AZ_TENANT_ID", "")
CLIENT_ID = os.getenv("AZ_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZ_CLIENT_SECRET", "")

if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    raise RuntimeError(
        "Missing AZ_TENANT_ID / AZ_CLIENT_ID / AZ_CLIENT_SECRET in environment (.env)."
    )

# ---------- YOUR FOLDER URLS ----------
FOLDER_URLS = [
    "https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FDB%20Validacion%20Dashboard%2FOKRs%2FCantidad%20y%20Calidad%20Pases&ga=1",
    "https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FDB%20Validacion%20Dashboard%2FOKRs%2FTMD%20%28Desarrollo%29&ga=1",
    "https://credicorponline.sharepoint.com/sites/Equipodata/Documentos%20compartidos/Forms/AllItems.aspx?id=%2Fsites%2FEquipodata%2FDocumentos%20compartidos%2FGeneral%2FNivel%20de%20Madurez%2FReportes%20Resumen%2F202505&sortField=Modified&isAscending=false&viewid=6dc15532%2D2728%2D4c0b%2Dbff6%2D88c32f50d811&p=true&ga=1",
    "https://credicorponline-my.sharepoint.com/personal/rmejiac_bcp_com_pe/_layouts/15/onedrive.aspx?id=%2Fpersonal%2Frmejiac%5Fbcp%5Fcom%5Fpe%2FDocuments%2FCOE%20INGENIER%C3%8DA%20Y%20COE%20QUALITY%20ENGINEER%2FIA%20COPILOT&sortField=Modified&isAscending=false&ga=1",
]


# ---------- TOKEN ----------
def get_graph_token(tenant_id, client_id, client_secret):
    r = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
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


# ---------- URL → (host, site_path, library, folder_rel) ----------
def extract_effective_path(url: str):
    u = urllib.parse.urlparse(url)
    host = u.netloc
    qs = urllib.parse.parse_qs(u.query)

    # Prefer the server-relative path carried in ?id=...
    if "id" in qs and qs["id"]:
        server_rel = urllib.parse.unquote(qs["id"][0])
    else:
        # Strip /Forms/AllItems.aspx if present; otherwise use the path as-is
        server_rel = urllib.parse.unquote(u.path.split("/Forms/AllItems.aspx")[0])

    parts = [p for p in server_rel.strip("/").split("/") if p]
    if len(parts) < 3:
        raise ValueError(f"URL path too short to contain site + library: {url}")

    root_kind = parts[0]  # 'sites' | 'teams' | 'personal'
    site_or_user = parts[1]
    site_path = f"/{root_kind}/{site_or_user}"  # e.g., /personal/rmejiac_bcp_com_pe

    library = parts[2]  # e.g., 'Documents' or 'Documentos compartidos'
    folder_rel = "/".join(parts[3:]) if len(parts) > 3 else ""  # path under the library

    return host, site_path, library, folder_rel, root_kind


# ---------- GRAPH HELPERS ----------
def get_site_id(token: str, host: str, site_path: str) -> str:
    url = f"https://graph.microsoft.com/v1.0/sites/{host}:{site_path}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def get_drive_id(token: str, site_id: str, root_kind: str, library_name: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    # OneDrive personal sites: default 'Documents' drive via /sites/{id}/drive
    if root_kind == "personal":
        r = requests.get(
            f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive",
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["id"]

    # Team/site collections: default library names vary by language
    default_names = {"Shared Documents", "Documentos compartidos"}
    if library_name in default_names:
        r = requests.get(
            f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive",
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["id"]

    # Non-default library → search in /drives by name
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    for d in r.json().get("value", []):
        if d.get("name") == library_name:
            return d["id"]
    raise RuntimeError(f"Library '{library_name}' not found on site {site_id}")


def list_children(token: str, drive_id: str, folder_rel: str):
    headers = {"Authorization": f"Bearer {token}"}
    if folder_rel:
        enc = urllib.parse.quote(folder_rel.strip("/"))
        url = (
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{enc}:/children"
        )
    else:
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"

    items = []
    while url:
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", "3")))
            continue
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
    return items


# ---------- MAIN ----------
def main():
    token = get_graph_token(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    print("Token acquired. Proceeding with Sites.Read.All-only flow.\n")

    for url in FOLDER_URLS:
        print(f"=== Folder URL ===\n{url}\n")
        try:
            host, site_path, library, folder_rel, root_kind = extract_effective_path(
                url
            )
            site_id = get_site_id(token, host, site_path)
            drive_id = get_drive_id(token, site_id, root_kind, library)
            items = list_children(token, drive_id, folder_rel)

            if not items:
                print("No items in this folder.\n")
                continue

            print(
                "Type  | Name                                   | Size (bytes) | Last Modified (UTC)                     | Item ID"
            )
            print("-" * 120)
            for it in items:
                is_dir = "folder" in it
                kind = "DIR " if is_dir else "FILE"
                size = it.get("size", 0)
                mod = it.get("lastModifiedDateTime", "")
                name = it["name"]
                iid = it["id"]
                print(f"{kind:4}| {name:40} | {size:12} | {mod:35} | {iid}")
            print()

        except requests.HTTPError as e:
            print(f"HTTP error: {e.response.status_code} {e.response.text}\n")
        except Exception as ex:
            print(f"ERROR: {ex}\n")


if __name__ == "__main__":
    main()
