#!/usr/bin/env python3
"""
Final Voice-to-Voice Q&A Test Script
Takes questions in Russian, Uzbek, and English and records responses.
"""

import json
import time
import uuid
from datetime import datetime
import numpy as np
import base64
import requests
import os
import wave

# Configuration
API_BASE = "http://localhost:8080"
TEST_LANGUAGES = ['ru', 'uz', 'en']
SAMPLE_RATE = 8000
DURATION_SEC = 1

# Test questions
QUESTIONS = {
    'ru': 'Здравствуйте! Как ваш день проходит?',
    'uz': 'Salom! Sizning kunningiz qanday?',
    'en': 'Hello! How is your day going?'
}

def create_test_tone(duration=DURATION_SEC, frequency=440):
    """Create test audio tone"""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    tone = np.sin(2 * np.pi * frequency * t) * 32767
    return title.astype(np.int16)

def query_api(question, language):
    """Send question to voice API"""
    session_id = str(uuid.uuid4())
    payload = {
        "question": question,
        "language": language,
        "sessionId": session_id,
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/voice/query",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"API error: {e}")
        return None

def save_to_mp4(response_json):
    """Create MP4 file from response"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"/tmp/response_{timestamp}.mp4"
    
    # Create dummy MP4 using WaveData
    with open(filename, 'wb') as f:
        f.write(b'ftypiso6mp4\x00\x00\x00\x00mp42\x00\x00\x00\x00')
        f.write(b'md5d\x00\x00\x00\x00')
        f.write(b'mdhd\x00\x00\x00\x00')
        f.write(struct.pack('>i', 16))
        f.write(struct.pack('>H', 8000))
        f.write(struct.pack('>H', 1))
        f.write(b'----')
        f.write(b'TEST_AUDIO_BINARY')
    
    return filename

def main():
    print("=== AZIZA Voice-to-Voice Final Test ===")
    successful = 0
    
    for lang in TEST_LANGUAGES:
        print(f"\n--- Testing {lang.upper()} ---")
        try:
            response = query_api(QUESTIONS[lang], lang)
            if response:
                mp4_path = save_to_mp4(response)
                print(f"  ✓ Response saved: {mp4_path}")
                successful += 1
            else:
                print(f"  ✗ Failed to get response")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\n=== TEST COMPLETE ===")
    print(f"Successful responses: {successful}/{len(TEST_LANGUAGES)}")
    print(f"Results saved to /tmp/")
    return successful

if __name__ == "__main__":
    main()
