import asyncio
import redis.asyncio as redis
import time
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmokeTest")

async def test_stream():
    redis_client = redis.from_url("redis://localhost:6379")
    pubsub = redis_client.pubsub()
    
    session_id = "smoke_test_123"
    
    # We will subscribe to what streaming-runtime outputs
    # Streaming runtime listens to session:{session_id}:audio_in
    # When VAD sees speech, it publishes to session:{session_id}:audio
    # When VAD sees silence, it waits for session:{session_id}:playback
    
    await pubsub.psubscribe(f"session:{session_id}:audio", f"session:{session_id}:playback", f"session:{session_id}:control")
    
    logger.info("Starting smoke test...")
    
    # Generate 1 second of "speech" tone (16kHz, 16-bit PCM)
    # webrtcvad needs something that looks like speech. Let's just generate a loud 440Hz sine wave.
    import math
    import struct
    
    import random
    
    sample_rate = 16000
    duration_sec = 1.0 # longer duration
    num_samples = int(sample_rate * duration_sec)
    
    # White noise
    audio_data = bytearray()
    for i in range(num_samples):
        val = random.randint(-32768, 32767)
        audio_data.extend(struct.pack('<h', val))
        
    # Send frames of 960 bytes (30ms)
    frames = [audio_data[i:i+960] for i in range(0, len(audio_data), 960) if len(audio_data[i:i+960]) == 960]
    
    logger.info(f"Sending {len(frames)} speech frames...")
    
    start_time = time.time()
    
    # Send speech
    for frame in frames:
        await redis_client.publish(f"session:{session_id}:audio_in", bytes(frame))
        await asyncio.sleep(0.01) # Simulate real-time slightly faster
        
    # Read output
    received_audio = False
    
    try:
        # Wait for Moshi input channel
        async for msg in pubsub.listen():
            if msg["type"] == "pmessage":
                channel = msg["channel"].decode()
                if channel == f"session:{session_id}:audio":
                    logger.info(f"SUCCESS: Received VAD-filtered audio chunk back! Latency: {time.time() - start_time:.4f}s")
                    received_audio = True
                    break
    except asyncio.TimeoutError:
        logger.error("FAILED: Did not receive audio chunk back from streaming-runtime.")

    # Now send silence to trigger Thinking state
    logger.info("Sending silence to trigger Thinking state...")
    silence = bytearray([0] * 960)
    for _ in range(15): # 450ms of silence
        await redis_client.publish(f"session:{session_id}:audio_in", bytes(silence))
        await asyncio.sleep(0.01)
        
    logger.info("Test complete.")
    
if __name__ == "__main__":
    asyncio.run(test_stream())
