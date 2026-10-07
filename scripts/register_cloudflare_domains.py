"""Register every Cloudflare zone as a Search Console domain property.

Per zone: fetch a DNS_TXT token from the Site Verification API, publish it as a
TXT record on the zone apex via Cloudflare, wait until public DNS serves it,
verify ownership, then add ``sc-domain:<zone>`` to Search Console.

Idempotent: existing TXT records, verified owners and properties are reused.
Zones whose nameservers are not active at Cloudflare (status != active) are
skipped, since public DNS would never see the record.

Usage (Cloudflare global key from llm.local, see BookStack "Search-Console-MCP"):
    CF_EMAIL=... CF_KEY=... uv run python scripts/register_cloudflare_domains.py [zone ...]

Needs the "Site Verification API" enabled in the Google Cloud project of the
OAuth client and a browser login (scopes webmasters + siteverification). The
token is kept in memory only and never touches the MCP server's token.json.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/siteverification",
]
CLIENT_SECRETS = os.environ.get(
    "GSC_OAUTH_CLIENT_SECRETS_FILE",
    os.path.expanduser("~/Library/Application Support/mcp-gsc/client_secrets.json"),
)
CF_API = "https://api.cloudflare.com/client/v4"
DNS_WAIT_SECONDS = 600


def cloudflare(method: str, path: str, body=None) -> dict:
    request = urllib.request.Request(
        CF_API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "X-Auth-Email": os.environ["CF_EMAIL"],
            "X-Auth-Key": os.environ["CF_KEY"],
            "Content-Type": "application/json",
            "User-Agent": "minicon-gsc-register/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if not data.get("success"):
        raise RuntimeError(f"Cloudflare {method} {path}: {data.get('errors')}")
    return data


def public_txt(domain: str) -> list:
    out = subprocess.run(
        ["dig", "+short", "TXT", domain, "@1.1.1.1"], capture_output=True, text=True
    ).stdout
    return [line.strip().strip('"') for line in out.splitlines()]


def ensure_txt(zone: dict, token: str) -> str:
    records = cloudflare(
        "GET", f"/zones/{zone['id']}/dns_records?type=TXT&name={zone['name']}&per_page=100"
    )["result"]
    if any(r["content"].strip('"') == token for r in records):
        return "TXT vorhanden"
    cloudflare("POST", f"/zones/{zone['id']}/dns_records", {
        "type": "TXT", "name": zone["name"], "content": token, "ttl": 300,
        "comment": "Google Search Console Verifizierung (mcp-gsc)",
    })
    return "TXT angelegt"


def wait_for_dns(domain: str, token: str) -> bool:
    deadline = time.time() + DNS_WAIT_SECONDS
    while time.time() < deadline:
        if token in public_txt(domain):
            return True
        time.sleep(15)
    return False


def main() -> None:
    wanted = set(sys.argv[1:])
    zones = cloudflare("GET", "/zones?per_page=100")["result"]
    if wanted:
        zones = [z for z in zones if z["name"] in wanted]

    creds = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES).run_local_server(port=0)
    verification = build("siteVerification", "v1", credentials=creds, cache_discovery=False)
    console = build("searchconsole", "v1", credentials=creds, cache_discovery=False)

    # Enabling an API takes a few minutes to propagate; wait instead of failing every zone.
    probe = {"site": {"type": "INET_DOMAIN", "identifier": zones[0]["name"]}, "verificationMethod": "DNS_TXT"}
    for attempt in range(40):
        try:
            verification.webResource().getToken(body=probe).execute()
            break
        except HttpError as e:
            if "accessNotConfigured" not in str(e) and "SERVICE_DISABLED" not in str(e):
                raise
            if attempt == 0:
                print("Site Verification API noch nicht aktiv – warte (bis 10 Minuten) ...", flush=True)
            time.sleep(15)
    else:
        sys.exit("Site Verification API nicht aktiv. Im Google-Cloud-Projekt aktivieren und erneut starten.")

    existing = {s["siteUrl"]: s["permissionLevel"]
                for s in console.sites().list().execute().get("siteEntry", [])}

    for zone in sorted(zones, key=lambda z: z["name"]):
        domain = zone["name"]
        property_url = f"sc-domain:{domain}"
        if existing.get(property_url) in ("siteOwner", "siteFullUser"):
            print(f"{domain}: bereits in der Search Console ({existing[property_url]})")
            continue
        if zone["status"] != "active":
            print(f"{domain}: übersprungen – Zone ist bei Cloudflare '{zone['status']}' (Nameserver nicht umgestellt)")
            continue
        try:
            site = {"type": "INET_DOMAIN", "identifier": domain}
            token = verification.webResource().getToken(
                body={"site": site, "verificationMethod": "DNS_TXT"}
            ).execute()["token"]
            txt_state = ensure_txt(zone, token)
            if not wait_for_dns(domain, token):
                print(f"{domain}: {txt_state}, aber nach {DNS_WAIT_SECONDS}s nicht öffentlich sichtbar – später erneut starten")
                continue
            verification.webResource().insert(
                verificationMethod="DNS_TXT", body={"site": site}
            ).execute()
            console.sites().add(siteUrl=property_url).execute()
            print(f"{domain}: {txt_state}, verifiziert, als {property_url} angelegt")
        except HttpError as e:
            print(f"{domain}: Fehler {e.resp.status}: {e.reason}")


if __name__ == "__main__":
    main()
