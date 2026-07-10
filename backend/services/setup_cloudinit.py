import os
import urllib.request
import urllib.parse
import json
import ssl
import time

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

def update_config(ticket, csrf, config):
    url = f"{BASE_URL}/nodes/{NODE}/qemu/{VMID}/config"
    data = urllib.parse.urlencode(config).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Cookie", f"PVEAuthCookie={ticket}")
    req.add_header("CSRFPreventionToken", csrf)
    try:
        with urllib.request.urlopen(req) as response:
            print("Config updated:", json.loads(response.read().decode()))
    except urllib.error.HTTPError as e:
        print(f"Error: {e.code} {e.reason}")
        print(e.read().decode())

if __name__ == "__main__":
    ticket, csrf = get_auth()
    
    config = {
        "ide2": "local-lvm:cloudinit",
        "ipconfig0": "gw=10.10.10.10,ip=10.10.10.11/24",
        "nameserver": "8.8.8.8",
        "ciuser": "root",
        "cipassword": os.environ.get("AZIZA_SSH_PASS", "")
    }
    update_config(ticket, csrf, config)
