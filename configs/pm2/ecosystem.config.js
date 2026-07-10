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
        TEXT_API_URL_UZ: "http://localhost:8003/v1/chat/completions",
        HF_HOME: "/root/aziza-build/model_cache",
        HF_TOKEN: process.env.HF_TOKEN
      }
    },
    {
      name: 'personaplex',
      script: '/root/aziza-build/venv312/bin/python3',
      args: '-m uvicorn main:app --port 8000',
      cwd: '/root/aziza-build/backend/persona-plex',
      env: {
        REDIS_URL: 'redis://localhost:6379',
        MONGO_URL: 'mongodb://localhost:27017/aziza'
      }
    },
    {
      name: "vllm-english",
      script: "/root/aziza-build/venv312/bin/python3",
      args: "-m vllm.entrypoints.openai.api_server --model Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24 --quantization bitsandbytes --load-format bitsandbytes --gpu-memory-utilization 0.35 --port 8002 --max-model-len 1024 --max-num-seqs 4 --disable-frontend-multiprocessing --chat-template /root/aziza-build/training/scripts/en_chatml.jinja --enable-lora --lora-modules aziza_russian=/root/aziza-build/training/lora/adapters/ru_all --max-lora-rank 64 --enforce-eager",
      cwd: "/root/aziza-build",
      env: {
        CUDA_VISIBLE_DEVICES: "0"
      }
    },
    {
      name: "vllm-uzbek",
      script: "/root/aziza-build/venv312/bin/python3",
      args: "-m vllm.entrypoints.openai.api_server --model uzlm/alloma-3B-Instruct --trust-remote-code --quantization bitsandbytes --load-format bitsandbytes --gpu-memory-utilization 0.32 --port 8003 --max-model-len 1024 --max-num-seqs 2 --disable-frontend-multiprocessing --served-model-name alloma --chat-template /root/aziza-build/training/lora/adapters/aziza-adapter-final-uz/chat_template.jinja --enable-lora --lora-modules aziza_uzbek=/root/aziza-build/training/lora/adapters/aziza-adapter-final-uz --max-lora-rank 64 --enforce-eager",
      cwd: "/root/aziza-build",
      env: {
        CUDA_VISIBLE_DEVICES: "0"
      }
    },
    {
      name: "aziza-russian-test",
      script: "/root/aziza-build/venv312/bin/python3",
      args: "-m uvicorn serve_russian_test:app --host 0.0.0.0 --port 8020 --workers 1",
      cwd: "/root/aziza-build/backend/gateway",
      env: {
        PYTHONPATH: "/root/aziza-build",
        PORT: 8020,
        HF_TOKEN: process.env.HF_TOKEN
      }
    }
  ]
};
