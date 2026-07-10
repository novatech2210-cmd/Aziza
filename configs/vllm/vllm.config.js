module.exports = {
  apps: [
    {
      name: "vllm-english",
      // NOTE: PM2 ecosystem.config.js calls start_vllm_en.sh directly.
      // This file is kept for reference / manual launch only.
      script: "/root/aziza-build/venv312/bin/python3",
      args: "-m vllm.entrypoints.openai.api_server" +
        " --model Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24" +
        " --quantization bitsandbytes --load-format bitsandbytes" +
        " --gpu-memory-utilization 0.20" +
        " --enforce-eager" +
        " --port 8002" +
        " --disable-frontend-multiprocessing" +
        " --max-model-len 2048" +
        " --chat-template /root/aziza-build/en_chatml.jinja",
      cwd: "/root/aziza-build",
      env: {
        HF_TOKEN: process.env.HF_TOKEN,
        HF_ENDPOINT: "https://hf-mirror.com",
        CUDA_VISIBLE_DEVICES: "0"
      }
    },
    {
      name: "vllm-uzbek",
      script: "/root/aziza-build/venv312/bin/python3",
      args: "-m vllm.entrypoints.openai.api_server" +
        " --model uzlm/alloma-3B-Instruct" +
        " --quantization bitsandbytes --load-format bitsandbytes" +
        " --gpu-memory-utilization 0.20" +
        " --enforce-eager" +
        " --port 8003" +
        " --disable-frontend-multiprocessing" +
        " --max-model-len 1024" +
        " --max-num-seqs 32" +
        " --max-num-batched-tokens 1024" +
        " --served-model-name alloma" +
        " --chat-template /root/aziza-build/adapters/aziza-adapter-final-uz/chat_template.jinja" +
        " --enable-lora" +
        " --lora-modules aziza_uzbek=/root/aziza-build/adapters/aziza-adapter-final-uz" +
        " --max-lora-rank 64",
      cwd: "/root/aziza-build",
      env: {
        HF_TOKEN: process.env.HF_TOKEN,
        HF_ENDPOINT: "https://hf-mirror.com",
        CUDA_VISIBLE_DEVICES: "0"
      }
    }
  ]
};
