module.exports = {
  apps: [
    {
      name: "api-gateway",
      script: "dist/main.js",
      cwd: "/root/aziza-build/backend/services/api-gateway",
      env: {
        PORT: 3000,
        REDIS_URL: "redis://localhost:6379",
        JWT_SECRET: process.env.JWT_SECRET,
        ORCHESTRATOR_URL: "http://localhost:8001"
      }
    },
    {
      name: "orchestrator",
      script: "/root/aziza-build/venv312/bin/python3",
      args: "main.py",
      cwd: "/root/aziza-build/backend/services/orchestrator",
      env: {
        REDIS_URL: "redis://localhost:6379",
        PYTHONPATH: "/root/aziza-build/backend:/root/aziza-build/backend/services"
      }
    },
    {
      name: "moshi-worker",
      script: "/root/aziza-build/venv312/bin/python3",
      args: "moshi_service.py",
      cwd: "/root/aziza-build/backend/services/moshi-worker",
      env: {
        WORKER_ID: "worker-01",
        REDIS_URL: "redis://localhost:6379",
        TEXT_API_URL: "http://localhost:8002/v1/chat/completions",
        AZIZA_ADAPTER_PATH: "/root/aziza-build/aziza-multilingual-adapter/final,/root/aziza-build/adapters/moshi_ru_v1/final"
      }
    },
    {
      name: 'personaplex',
      script: '/root/aziza-build/start_personaplex.sh',
      cwd: '/root/aziza-build',
      env: {
        REDIS_URL: 'redis://localhost:6379',
        MONGO_URL: process.env.MONGO_URL
      }
    },
    {
      name: "vllm-english",
      script: "/root/aziza-build/start_vllm_en.sh",
      cwd: "/root/aziza-build",
      env: {
        CUDA_VISIBLE_DEVICES: "0"
      }
    },
    {
      name: "vllm-uzbek",
      script: "/root/aziza-build/start_vllm_uz.sh",
      cwd: "/root/aziza-build",
      env: {
        CUDA_VISIBLE_DEVICES: "0"
      }
    },
    {
      name: "aziza-russian-test",
      script: "/root/aziza-build/venv312/bin/python3",
      args: "-m uvicorn serve_russian_test:app --host 0.0.0.0 --port 8020 --workers 1",
      cwd: "/root/aziza-build",
      env: {
        PORT: 8020,
        HF_TOKEN: process.env.HF_TOKEN
      }
    }
  ]
};
