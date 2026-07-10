# Known Issues

| Severity | Description | Affected Subsystem | Recommended Fix |
|---|---|---|---|
| Medium | Occasional Port Collisions on restart | PM2 / Gateway | Implement grace-period teardown in FastAPI shutdown events. |
| Low | Large log files | PM2 | Configure `pm2-logrotate`. |
