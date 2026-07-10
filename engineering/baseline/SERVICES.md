# Service Inventory

## PM2 Processes
```
┌────┬───────────────────────┬─────────────┬─────────┬─────────┬──────────┬────────┬──────┬───────────┬──────────┬──────────┬──────────┬──────────┐
│ id │ name                  │ namespace   │ version │ mode    │ pid      │ uptime │ ↺    │ status    │ cpu      │ mem      │ user     │ watching │
├────┼───────────────────────┼─────────────┼─────────┼─────────┼──────────┼────────┼──────┼───────────┼──────────┼──────────┼──────────┼──────────┤
│ 7  │ admin-api             │ default     │ N/A     │ fork    │ 1115     │ 6h     │ 0    │ online    │ 0%       │ 83.2mb   │ root     │ disabled │
│ 0  │ api-gateway           │ default     │ 0.0.1   │ fork    │ 5819     │ 86m    │ 3    │ online    │ 0%       │ 80.6mb   │ root     │ disabled │
│ 8  │ aziza-russian-test    │ default     │ N/A     │ fork    │ 7438     │ 82m    │ 15   │ online    │ 0%       │ 53.2mb   │ root     │ disabled │
│ 2  │ moshi-worker          │ default     │ N/A     │ fork    │ 5838     │ 86m    │ 3    │ online    │ 0%       │ 636.7mb  │ root     │ disabled │
│ 1  │ orchestrator          │ default     │ N/A     │ fork    │ 5820     │ 86m    │ 3    │ online    │ 0%       │ 46.1mb   │ root     │ disabled │
│ 3  │ personaplex           │ default     │ N/A     │ fork    │ 5835     │ 86m    │ 3    │ online    │ 0%       │ 72.9mb   │ root     │ disabled │
│ 4  │ vllm-english          │ default     │ N/A     │ fork    │ 6120     │ 86m    │ 6    │ online    │ 0%       │ 5.6gb    │ root     │ disabled │
│ 5  │ vllm-uzbek            │ default     │ N/A     │ fork    │ 5872     │ 86m    │ 3    │ online    │ 0%       │ 8.5gb    │ root     │ disabled │
└────┴───────────────────────┴─────────────┴─────────┴─────────┴──────────┴────────┴──────┴───────────┴──────────┴──────────┴──────────┴──────────┘
```

## Docker Containers
```
CONTAINER ID   IMAGE          COMMAND                  CREATED      STATUS       PORTS     NAMES
b30705e415c5   mongo:latest   "docker-entrypoint.s…"   9 days ago   Up 7 hours             mongodb
```

## Network Ports (Listening)
```

```
