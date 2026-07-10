import os
import urllib.request
import urllib.parse
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

BASE_URL = os.environ.get("PROXMOX_API_URL", "")

def get_auth():
    url = f"{BASE_URL}/access/ticket"
    data = urllib.parse.urlencode({
        "username": os.environ.get("PROXMOX_API_USER", ""),
        "password": os.environ.get("PROXMOX_API_PASS", "")
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode())
        return res["data"]["ticket"], res["data"]["CSRFPreventionToken"]

def get_storage(ticket, csrf):
    url = f"{BASE_URL}/storage"
    req = urllib.request.Request(url)
    req.add_header("Cookie", f"PVEAuthCookie={ticket}")
    req.add_header("CSRFPreventionToken", csrf)
    try:
        with urllib.request.urlopen(req) as response:
            print(json.dumps(json.loads(response.read().decode())["data"], indent=2))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    ticket, csrf = get_auth()
    get_storage(ticket, csrf)
