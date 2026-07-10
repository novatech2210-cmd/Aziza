module.exports = {
  apps: [
    {
      name: "api-gateway",
      script: "dist/main.js",
      cwd: "/root/aziza-build/backend/services/api-gateway",
      env: {
        PORT: 8080,
        REDIS_URL: "redis://localhost:6379",
        JWT_SECRET: process.env.JWT_SECRET,
        ORCHESTRATOR_URL: "http://localhost:8001"
      }
    },
    {
      name: "orchestrator",
      script: "/root/aziza-build/venv/bin/python3",
      args: "main.py",
      cwd: "/root/aziza-build/backend/services/orchestrator",
      env: {
        REDIS_URL: "redis://localhost:6379",
        PYTHONPATH: "/root/aziza-build/backend:/root/aziza-build/backend/services"
      }
    },
    {
      name: "moshi-worker",
      script: "/root/aziza-build/venv/bin/python3",
      args: "moshi_service.py",
      cwd: "/root/aziza-build/backend/services/moshi-worker",
      env: {
        WORKER_ID: "worker-01",
        REDIS_URL: "redis://localhost:6379",
        TEXT_API_URL: "http://localhost:8020/chat",
        AZIZA_ADAPTER_PATH: "/root/aziza-build/aziza-multilingual-adapter/final"
      }
    },
    {
      name: 'personaplex',
      script: '/root/aziza-build/venv/bin/python3',
      args: '-m uvicorn main:app --port 8000',
      cwd: '/root/aziza-build/backend/persona-plex',
      env: {
        REDIS_URL: 'redis://localhost:6379',
        MONGO_URL: 'mongodb://localhost:27017/aziza'
      }
    }
  ]
};
