"""
Qube Admin API — Configuration
All settings pulled from environment variables.
"""

import os

# JWT
JWT_SECRET: str = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM: str = "HS256"

# Gateway (NestJS api-gateway, includes /api prefix)
GATEWAY_URL: str = os.getenv("GATEWAY_URL", "http://localhost:8080/api")

# Database (asyncpg DSN — optional; features gracefully degrade without it)
DB_DSN: str | None = os.getenv("DB_DSN", None)

# Server
PORT: int = int(os.getenv("PORT", "8012"))

# Feature flags
PHASE9_ENABLED: bool = os.getenv("PHASE9_ENABLED", "false").lower() in ("1", "true", "yes")
