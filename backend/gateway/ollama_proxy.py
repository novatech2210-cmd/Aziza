#!/usr/bin/env python3
"""
Ollama-to-vLLM Proxy
Translates Ollama API calls to vLLM OpenAI API calls
"""

import http.server
import json
import urllib.request
import urllib.error
import sys

# vLLM endpoints
VLLM_ENGLISH_URL = "http://localhost:8002/v1/chat/completions"
VLLM_UZBEK_URL = "http://localhost:8003/v1/chat/completions"
LLM_MODEL_EN = "Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24"
LLM_MODEL_UZ = "uzlm/alloma-3B-Instruct"

class OllamaProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/api/tags':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "models": [
                    {"name": "llama3", "model": "llama3"},
                    {"name": "qwen:latest", "model": "qwen:latest"}
                ]
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body)
        except:
            self.send_response(400)
            self.end_headers()
            return
        
        if self.path == '/api/chat':
            self._handle_chat(data)
        elif self.path == '/api/generate':
            self._handle_generate(data)
        else:
            self.send_response(404)
            self.end_headers()
    
    def _detect_language(self, text):
        # Check for Russian Cyrillic
        if any(c in text for c in 'аеёийоуъыьэюяАЕЁИЙОУЪЫЬЭЮЯ'):
            return 'ru'
        # Check for Uzbek Latin characters (ўғҳқ)
        elif any(c in text for c in 'ўғҳқЎҒҲҚ'):
            return 'uz'
        # Check for common Uzbek words
        elif any(word in text.lower() for word in ['salom', 'qalaysiz', 'rahmat', 'ha', 'yoq', 'nima', 'kim', 'qayerda']):
            return 'uz'
        else:
            return 'en'
    
    def _handle_chat(self, data):
        messages = data.get('messages', [])
        user_message = ""
        for msg in messages:
            if msg.get('role') == 'user':
                user_message = msg.get('content', '')
                break
        
        lang = self._detect_language(user_message)
        
        if lang == 'uz':
            vllm_url = VLLM_UZBEK_URL
            model = LLM_MODEL_UZ
        else:
            vllm_url = VLLM_ENGLISH_URL
            model = LLM_MODEL_EN
        
        vllm_data = {
            "model": model,
            "messages": messages,
            "stream": data.get('stream', False),
            "temperature": data.get('options', {}).get('temperature', 0.7),
            "max_tokens": 2048
        }
        
        try:
            req = urllib.request.Request(
                vllm_url,
                data=json.dumps(vllm_data).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                ollama_response = {
                    "model": data.get('model', 'llama3'),
                    "message": {"role": "assistant", "content": content},
                    "done": True
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(ollama_response).encode())
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
    
    def _handle_generate(self, data):
        prompt = data.get('prompt', '')
        lang = self._detect_language(prompt)
        
        if lang == 'uz':
            vllm_url = VLLM_UZBEK_URL
            model = LLM_MODEL_UZ
        else:
            vllm_url = VLLM_ENGLISH_URL
            model = LLM_MODEL_EN
        
        vllm_data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": data.get('stream', False),
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
        try:
            req = urllib.request.Request(
                vllm_url,
                data=json.dumps(vllm_data).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                ollama_response = {
                    "model": data.get('model', 'llama3'),
                    "response": content,
                    "done": True
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(ollama_response).encode())
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

def run_proxy(port=11434):
    server = http.server.HTTPServer(('127.0.0.1', port), OllamaProxyHandler)
    print(f"Ollama proxy running on port {port}")
    server.serve_forever()

if __name__ == '__main__':
    run_proxy()
