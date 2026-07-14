#!/usr/bin/env python3
"""Environment validation for AZIZA services.

Validates that all required environment variables are set and
services are reachable before starting PM2 processes.

Usage:
    python3 validate_env.py              # Check all services
    python3 validate_env.py --gateway    # Check API gateway only
    python3 validate_env.py --services   # Check all services
"""

import argparse
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import List, Tuple

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"

REQUIRED_ENV = {
    "api-gateway": ["JWT_SECRET", "PORT"],
    "orchestrator": ["REDIS_URL"],
    "moshi-worker": ["REDIS_URL", "WORKER_ID", "HF_TOKEN"],
    "personaplex": ["REDIS_URL", "MONGO_URL"],
}

OPTIONAL_ENV = {
    "api-gateway": ["MONGODB_URI", "REDIS_URL", "ORCHESTRATOR_URL"],
    "moshi-worker": ["TEXT_API_URL", "TEXT_API_URL_UZ", "HF_HOME"],
}


def check_env_vars(service: str) -> List[Tuple[str, bool, str]]:
    results = []
    required = REQUIRED_ENV.get(service, [])
    optional = OPTIONAL_ENV.get(service, [])

    for var in required:
        val = os.environ.get(var)
        if not val:
            results.append((var, False, "REQUIRED - not set"))
        elif var in ("JWT_SECRET", "HF_TOKEN") and len(val) < 8:
            results.append((var, False, "too short (min 8 chars)"))
        else:
            masked = val[:4] + "***" if len(val) > 4 else "***"
            results.append((var, True, masked))

    for var in optional:
        val = os.environ.get(var)
        if val:
            masked = val[:20] + "..." if len(val) > 20 else val
            results.append((var, True, masked))
        else:
            results.append((var, True, "(not set, using default)"))

    return results


def check_port(port: int, name: str) -> Tuple[str, bool, str]:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return (f"Port {port} ({name})", True, "reachable")
    except (ConnectionRefusedError, OSError):
        return (f"Port {port} ({name})", False, "not reachable")
    except Exception as e:
        return (f"Port {port} ({name})", False, str(e))


def check_mongodb() -> Tuple[str, bool, str]:
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/aziza")
    try:
        import pymongo
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        return ("MongoDB", True, f"connected ({uri})")
    except ImportError:
        return ("MongoDB", True, f"uri={uri} (pymongo not installed, skip check)")
    except Exception as e:
        return ("MongoDB", False, str(e)[:100])


def check_redis() -> Tuple[str, bool, str]:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    try:
        import redis
        r = redis.from_url(url, socket_timeout=3)
        r.ping()
        return ("Redis", True, f"connected ({url})")
    except ImportError:
        return ("Redis", True, f"url={url} (redis not installed, skip check)")
    except Exception as e:
        return ("Redis", False, str(e)[:100])


def check_pm2() -> Tuple[str, bool, str]:
    try:
        result = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            apps = json.loads(result.stdout)
            running = [a for a in apps if a.get("pm2_env", {}).get("status") == "online"]
            return ("PM2", True, f"{len(running)} apps running")
        return ("PM2", False, f"exit code {result.returncode}")
    except FileNotFoundError:
        return ("PM2", False, "pm2 not found")
    except Exception as e:
        return ("PM2", False, str(e)[:100])


def main():
    parser = argparse.ArgumentParser(description="AZIZA Environment Validator")
    parser.add_argument("--gateway", action="store_true", help="Check API gateway only")
    parser.add_argument("--services", action="store_true", help="Check all services")
    parser.add_argument("--env-only", action="store_true", help="Only check env vars")
    args = parser.parse_args()

    print(f"\n{YELLOW}AZIZA Environment Validation{NC}")
    print("=" * 50)

    all_ok = True

    # ── Env vars ──
    services = ["api-gateway", "orchestrator", "moshi-worker", "personaplex"]
    if args.gateway:
        services = ["api-gateway"]

    for service in services:
        print(f"\n{YELLOW}[{service}]{NC}")
        results = check_env_vars(service)
        for var, ok, val in results:
            status = f"{GREEN}OK{NC}" if ok else f"{RED}FAIL{NC}"
            print(f"  {status}  {var} = {val}")
            if not ok:
                all_ok = False

    if not args.env_only:
        # ── Infrastructure ──
        print(f"\n{YELLOW}[Infrastructure]{NC}")
        for check_fn in [check_mongodb, check_redis, check_pm2]:
            name, ok, detail = check_fn()
            status = f"{GREEN}OK{NC}" if ok else f"{RED}FAIL{NC}"
            print(f"  {status}  {name}: {detail}")
            if not ok:
                all_ok = False

        # ── Ports ──
        print(f"\n{YELLOW}[Ports]{NC}")
        ports = [
            (8080, "API Gateway"),
            (8001, "Orchestrator"),
            (8000, "PersonaPlex"),
            (8002, "vLLM English"),
            (8003, "vLLM Uzbek"),
            (8020, "Russian Test"),
            (6379, "Redis"),
            (27017, "MongoDB"),
        ]
        for port, name in ports:
            _, ok, detail = check_port(port, name)
            status = f"{GREEN}UP{NC}" if ok else f"{YELLOW}DOWN{NC}"
            print(f"  {status}  {name} (:{port}): {detail}")

    # ── Summary ──
    print("\n" + "=" * 50)
    if all_ok:
        print(f"{GREEN}VALIDATION PASSED{NC}")
    else:
        print(f"{RED}VALIDATION FAILED{NC} — fix issues above before starting services")

    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
