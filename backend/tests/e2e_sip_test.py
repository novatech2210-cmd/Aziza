import asyncio
import aiohttp
import logging
import os
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("e2e_sip_test")

ARI_URL = os.getenv("ARI_URL", "http://localhost:8088/ari")
ARI_USER = os.getenv("ARI_USER", "asterisk")
ARI_PASS = os.getenv("ARI_PASS", "asterisk")
VLLM_URL = os.getenv("VLLM_URL", "http://localhost:8003/v1/chat/completions")

async def test_ari_connection():
    logger.info("Testing connection to Asterisk ARI...")
    try:
        async with aiohttp.ClientSession() as session:
            auth_header = aiohttp.BasicAuth(ARI_USER, ARI_PASS).encode()
            headers = {'Authorization': auth_header}
            async with session.get(f"{ARI_URL}/asterisk/info", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Connected to Asterisk {data.get('systemInfo', {}).get('version')}")
                    return True
                else:
                    logger.error(f"Failed to connect to ARI: HTTP {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False

async def test_vllm_adapter():
    logger.info("Testing connection to vLLM adapter...")
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "alloma",
                "messages": [{"role": "user", "content": "Salom!"}]
            }
            async with session.post(VLLM_URL, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"vLLM Adapter responded: {data['choices'][0]['message']['content']}")
                    return True
                else:
                    logger.error(f"Failed to connect to vLLM: HTTP {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"vLLM Connection error: {e}")
        return False

async def main():
    ari_success = await test_ari_connection()
    if ari_success:
        logger.info("SIP E2E Test: ARI integration is ready.")
    else:
        logger.warning("SIP E2E Test: ARI is not reachable. Check Asterisk configuration.")
        
    vllm_success = await test_vllm_adapter()
    if vllm_success:
        logger.info("SIP E2E Test: vLLM adapter is ready.")
    else:
        logger.warning("SIP E2E Test: vLLM is not reachable. Check vLLM configuration.")

if __name__ == "__main__":
    asyncio.run(main())
