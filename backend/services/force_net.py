import os
import urllib.request
import urllib.parse
import json
import time
import ssl
import sys

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

def send_key(ticket, csrf, key):
    url = f"{BASE_URL}/nodes/{NODE}/qemu/{VMID}/sendkey"
    data = urllib.parse.urlencode({"key": key}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Cookie", f"PVEAuthCookie={ticket}")
    req.add_header("CSRFPreventionToken", csrf)
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"Error sending {key}: {e}")
        return False

def type_string(ticket, csrf, string):
    char_map = {
        ' ': 'spc', '-': 'minus', '.': 'dot', '/': 'slash', '=': 'equal',
        ':': 'shift-semicolon', '_': 'shift-minus', '"': 'shift-apostrophe',
        "'": 'apostrophe', '>': 'shift-dot', '<': 'shift-comma',
        '|': 'shift-backslash', '&': 'shift-7', '!': 'shift-1',
        '@': 'shift-2', '#': 'shift-3', '$': 'shift-4', '%': 'shift-5',
        '^': 'shift-6', '*': 'shift-8', '(': 'shift-9', ')': 'shift-0',
        '+': 'shift-equal', '{': 'shift-bracket_left', '}': 'shift-bracket_right',
        '[': 'bracket_left', ']': 'bracket_right', '\\': 'backslash',
        ';': 'semicolon', ',': 'comma', '`': 'grave_accent', '~': 'shift-grave_accent',
        '?': 'shift-slash'
    }
    
    for char in string:
        if char == '\n':
            send_key(ticket, csrf, "ret")
            time.sleep(1)
            continue

        if char.isupper():
            key = f"shift-{char.lower()}"
        elif char in char_map:
            key = char_map[char]
        else:
            key = char
            
        success = False
        retries = 3
        while not success and retries > 0:
            success = send_key(ticket, csrf, key)
            if not success:
                time.sleep(1)
                retries -= 1
        time.sleep(0.05)

if __name__ == "__main__":
    ticket, csrf = get_auth()
    
    cmds = [
        "root",
        os.environ.get("AZIZA_SSH_PASS", ""),
        "ip link set enp6s18 up",
        "ip addr flush dev enp6s18",
        "ip addr add 10.10.10.11/24 dev enp6s18",
        "ip route add default via 10.10.10.10",
        "systemctl restart ssh"
    ]
    
    send_key(ticket, csrf, "ret")
    time.sleep(2)
    send_key(ticket, csrf, "ret")
    time.sleep(2)

    for cmd in cmds:
        print(f"Typing: {cmd}")
        type_string(ticket, csrf, cmd + "\n")
        time.sleep(2)

    print("Done")
