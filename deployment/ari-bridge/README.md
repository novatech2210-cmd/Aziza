# ari-bridge deploy notes (Phase 5 Stage 2)

Source: [`services/ari-bridge/`](../../services/ari-bridge/).

Install on VM-B (`sida-pbx`) once Slice 2.1 + 2.2 are merged:

```bash
sudo useradd --system --home-dir /opt/ari-bridge --shell /usr/sbin/nologin ari-bridge
sudo mkdir -p /opt/ari-bridge /etc/ari-bridge /var/log/ari-bridge
sudo chown -R ari-bridge:ari-bridge /opt/ari-bridge /var/log/ari-bridge

# Copy build output (npm run build in services/ari-bridge produces dist/ + node_modules).
sudo rsync -a services/ari-bridge/{dist,node_modules,package.json} /opt/ari-bridge/

# Config (edit secrets locally first).
sudo cp services/ari-bridge/config/ari-bridge.example.json /etc/ari-bridge/ari-bridge.json
sudo chown ari-bridge:ari-bridge /etc/ari-bridge/ari-bridge.json
sudo chmod 0640 /etc/ari-bridge/ari-bridge.json

# Service unit.
sudo cp deploy/ari-bridge/ari-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ari-bridge
sudo journalctl -u ari-bridge -f
```

Verify against the existing `[from-amd-test]` dialplan: dialing extension 7777
should emit `started`, `answered`, and `hangup` POSTs visible in
`journalctl -u ari-bridge -f` and arriving at `Qube_Web`.

The same `app` value (`amd-stasis`) is shared with the adapter — ARI multiplexes
the event stream between subscribers per app name, so the bridge does not
interfere with the AMD path.
