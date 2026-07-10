import os
import urllib.request
import urllib.parse
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

NODE = "node53"
VMID = "101"
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

def qemu_monitor(ticket, csrf, cmd):
    url = f"{BASE_URL}/nodes/{NODE}/qemu/{VMID}/monitor"
    data = urllib.parse.urlencode({"command": cmd}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Cookie", f"PVEAuthCookie={ticket}")
    req.add_header("CSRFPreventionToken", csrf)
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print(res)
    except Exception as e:
        print(f"Error sending monitor command: {e}")

if __name__ == "__main__":
    ticket, csrf = get_auth()
    qemu_monitor(ticket, csrf, "info network")
    qemu_monitor(ticket, csrf, "info status")
