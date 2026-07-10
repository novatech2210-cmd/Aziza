import os
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROXMOX_URL = os.environ.get("PROXMOX_API_URL", "")
USERNAME = os.environ.get("PROXMOX_API_USER", "")
PASSWORD = os.environ.get("PROXMOX_API_PASS", "")
NODE = "node53"
VMID = "101"

session = requests.Session()
response = session.post(f"{PROXMOX_URL}/access/ticket", data={"username": USERNAME, "password": PASSWORD}, verify=False)
if response.status_code == 200:
    data = response.json()["data"]
    session.headers.update({"CSRFPreventionToken": data["CSRFPreventionToken"]})
    session.cookies.update({"PVEAuthCookie": data["ticket"]})

    # Try agent ping
    ping = session.post(f"{PROXMOX_URL}/nodes/{NODE}/qemu/{VMID}/agent/ping", verify=False)
    print("Agent Ping:", ping.json() if ping.status_code == 200 else ping.text)
    
    # Try getting interfaces
    if ping.status_code == 200:
        ifaces = session.get(f"{PROXMOX_URL}/nodes/{NODE}/qemu/{VMID}/agent/network-get-interfaces", verify=False)
        print("Interfaces:", json.dumps(ifaces.json(), indent=2) if ifaces.status_code == 200 else ifaces.text)
else:
    print("Login failed:", response.text)

