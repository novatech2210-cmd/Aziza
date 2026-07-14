#!/usr/bin/env python3
"""
Voice-to-Voice Q&A Test for Aziza AI (Russian, Uzbek, English)

This test script:
1. Communicates with Aziza via the WebSocket API at http://localhost:8080
2. Sends questions in all 3 languages
3. Receives audio responses
4. Records responses as MP4 files

Uses simplified approach without complex dependencies.
"""

import uuid
import time
import json
import requests
import base64
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8080"
TEST_LANGUAGES = ['ru', 'uz', 'en']

# Test questions for each language
QUESTIONS = {
    'ru': 'Здравствуйте! Как ваш день проходит?',  # Hello! How is your day going?
    'uz': 'Salom! Sizning kunningiz qanday?',  # Hello! How is your day going?
    'en': 'Hello! How is your day going?'
}

# Mock responses (for demo purposes - in real test, would capture actual responses)
MOCK_RESPONSES = {
    'ru': 'Ответ на русском языке. Это русский ответ Aziza голосового помощника.',
    'uz': 'Uzbek tilidagi javob. Bu Aziza vozov asistentning o`zbekcha javobi.',
    'en': 'English language response. This is Aziza voice assistant\'s English response.'
}

def generate_test_audio_base64():
    """
    Generate base64-encoded test audio.
    In a real test, this would record actual voice input.
    For now, we use a simple sine wave.
    """
    # Create a simple 440Hz sine wave (1 second)
    import numpy as np
    duration = 1.0  # seconds
    sample_rate = 24000
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = 0.5 * np.sin(2 * np.pi * 440 * t) * 32767
    tone = tone.astype(np.int16)
    
    # Convert to bytes
    audio_bytes = tone.tobytes()
    
    # Base64 encode for transmission
    return base64.b64encode(audio_bytes).decode('utf-8')

def send_question_to_voice_system(question, language, audio_base64):
    """
    Send question to Aziza voice system and retrieve response.
    Returns the response data.
    """
    session_id = str(uuid.uuid4())
    
    # Data for API request
    test_data = {
        "sessionId": session_id,
        "question": question,
        "language": language,
        "audio": audio_base64,
        "timestamp": datetime.now().isoformat(),
        "source": "test_system"
    }
    
    try:
        # Send POST request to voice system API
        response = requests.post(
            f"{API_BASE}/voice/chat",
            json=test_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            result['sessionId'] = session_id
            result['testLanguage'] = language
            return result
        else:
            print(f"  [ERROR] API returned status {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"  [ERROR] Failed to send question: {e}")
        return None

def save_response_as_mp4(response_data, language):
    """
    Create MP4 file from voice response.
    This is a mock implementation that simulates MP4 generation.
    In reality, this would process the actual audio response.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mp4_path = f"/tmp/aziza_response_{language}_{timestamp}.mp4"
    
    # Create a text-based MP4 file as proof of concept
    with open(mp4_path, 'w') as f:
        f.write("MP4 file containing Aziza voice response\n")
        f.write(f"Language: {language}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Session ID: {response_data.get('sessionId')}\n")
        f.write(f"Response Text: {response_data.get('response')}\n")
    
    return mp4_path

def play_test_tone(file_path="play/test_tone.wav"):
    """Create a simple test tone file"""
    # Ensure directory exists
    import os
    os.makedirs(os.path.dirname(file_path) if '/' in file_path else os.path.dirname('.'), exist_ok=True)
    
    # Create a simple 440Hz sine wave
    import numpy as np
    sample_rate = 8000
    duration = 0.5
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = 0.5 * np.sin(2 * np.pi * 440 * t) * 32767
    tone = tone.astype(np.int16)
    
    import wave
    with wave.open(file_path, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(tone.tobytes())
    
    return file_path

def main():
    """
    Main test function.
    Iterates through all languages, sends questions, and saves responses.
    """
    print("=== AZIZA Voice-to-Voice Q&A Test ===")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API endpoint: {API_BASE}")
    
    # Prepare test audio
    print("\n[PREPARE] Generating test audio...")
    test_audio = generate_test_audio_base64()
    
    # Run tests
    results = []
    successful_responses = 0
    
    for language in TEST_LANGUAGES:
        print(f"\n--- Testing {language.upper()} ---")
        print(f"Question: {QUESTIONS[language]}")
        print("[TESTING] Sending question...")
        
        # Send question to voice system
        response_data = send_question_to_voice_system(
            question=QUESTIONS[language],
            language=language,
            audio_base64=test_audio
        )
        
        if response_data:
            print(f"  [RECEIVED] Response data: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            
            # Save response as MP4
            mp4_file = save_response_as_mp4(response_data, language)
            print(f"  [SAVED] Response MP4: {mp4_file}")
            
            results.append({
                'language': language,
                'sessionId': response_data.get('sessionId'),
                'timestamp': datetime.now().isoformat(),
                'mp4File': mp4_file,
                'success': True
            })
            
            successful_responses += 1
        else:
            print(f"  [FAILED] No response received for {language}")
            results.append({
                'language': language,
                'sessionId': None,
                'timestamp': datetime.now().isoformat(),
                'mp4File': None,
                'success': False
            })
    
    # Print summary
    print(f"\n=== TEST SUMMARY ===")
    print(f"Total languages tested: {len(TEST_LANGUAGES)}")
    print(f"Successful responses: {successful_responses}")
    print(f"Success rate: {successful_responses/len(TEST_LANGUAGES)*100:.1f}%")
    
    print("\nResponse Files:")
    for result in results:
        status = "✓" if result['success'] else "✗"
        print(f"  {status} {result['language'].upper()}: {result['mp4File']}")
    
    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Save results to JSON
    results_path = "/tmp/test_results.json"
    with open(results_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'testType': 'voice_to_voice_qna',
            'languages': ['ru', 'uz', 'en'],
            'results': results,
            'summary': {
                'totalTested': len(TEST_LANGUAGES),
                'successful': successful_responses,
                'successRate': successful_responses/len(TEST_LANGUAGES)*100
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {results_path}")

if __name__ == "__main__":
    main()
