#!/usr/bin/env python3
"""
Russian Language Test Suite for Aziza AI
Tests: greeting, knowledge, task assistance, persona consistency, code-switch detection
"""
import json, time, sys
import urllib.request

API = "http://localhost:11435/chat"
PASS, FAIL = 0, 0

CYAN  = "\033[96m"
GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
BOLD  = "\033[1m"
RESET = "\033[0m"

def ask(message: str, max_tokens: int = 200, temperature: float = 0.7) -> dict:
    body = json.dumps({"message": message, "temperature": temperature, "max_tokens": max_tokens}).encode()
    req  = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def check(label: str, data: dict, min_cyrillic: float = 0.5, must_contain: list[str] = None):
    global PASS, FAIL
    ratio = data.get("cyrillic_ratio", 0)
    resp  = data.get("response", "")
    ms    = data.get("total_ms", 0)
    toks  = data.get("output_tokens", 0)
    ok    = ratio >= min_cyrillic

    if must_contain:
        for kw in must_contain:
            if kw.lower() not in resp.lower():
                ok = False
                break

    status = f"{GREEN}✅ PASS{RESET}" if ok else f"{RED}❌ FAIL{RESET}"
    print(f"\n{BOLD}{CYAN}── {label} ──{RESET}")
    print(f"  Prompt:   {YELLOW}{data.get('_prompt','')[:80]}{RESET}")
    print(f"  Response: {resp[:300]}")
    print(f"  Cyrillic: {ratio:.1%} | Tokens: {toks} | {ms:.0f}ms | {status}")
    if ok:
        PASS += 1
    else:
        FAIL += 1
    return ok

TESTS = [
    {
        "label": "1. Greeting & Identity",
        "prompt": "Привет! Как тебя зовут?",
        "min_cyrillic": 0.5,
    },
    {
        "label": "2. Capabilities Overview",
        "prompt": "Что ты умеешь делать? Расскажи о своих возможностях.",
        "min_cyrillic": 0.5,
    },
    {
        "label": "3. Business Task — Email Draft",
        "prompt": "Напиши короткое деловое письмо клиенту с подтверждением встречи на завтра в 15:00.",
        "min_cyrillic": 0.6,
    },
    {
        "label": "4. General Knowledge — AI",
        "prompt": "Что такое искусственный интеллект? Объясни простыми словами.",
        "min_cyrillic": 0.5,
    },
    {
        "label": "5. Code-Switch Resistance (English input)",
        "prompt": "Hello, what is your name and what can you do?",
        "min_cyrillic": 0.0,  # may respond in English — just check it doesn't crash
    },
    {
        "label": "6. Instruction Following — List Format",
        "prompt": "Назови 5 самых больших городов России. Ответь списком.",
        "min_cyrillic": 0.5,
    },
    {
        "label": "7. Persona — Aziza Broker Role",
        "prompt": "Ты Азиза — AI-ассистент брокера недвижимости. Помоги клиенту выбрать квартиру в Ташкенте.",
        "min_cyrillic": 0.5,
    },
    {
        "label": "8. Uzbek Cyrillic Script (cross-lingual)",
        "prompt": "Саломалайкум! Сиз ким сиз ва нима қила оласиз?",
        "min_cyrillic": 0.3,  # model may respond in either Russian or Uzbek
    },
    {
        "label": "9. Latency — Short Query",
        "prompt": "Как дела?",
        "min_cyrillic": 0.5,
        "max_tokens": 50,
    },
    {
        "label": "10. Long-Form — Story Generation",
        "prompt": "Напиши короткий рассказ о роботе, который учится говорить по-русски.",
        "min_cyrillic": 0.6,
        "max_tokens": 300,
    },
]

print(f"\n{BOLD}{'═'*60}")
print(f"  AZIZA Russian Language Test Suite")
print(f"  Model: Vikhr-Llama-3.1-8B-Instruct  |  API: {API}")
print(f"{'═'*60}{RESET}\n")

for t in TESTS:
    try:
        data = ask(t["prompt"], max_tokens=t.get("max_tokens", 200))
        data["_prompt"] = t["prompt"]
        check(t["label"], data, min_cyrillic=t.get("min_cyrillic", 0.5),
              must_contain=t.get("must_contain"))
    except Exception as e:
        print(f"\n{RED}❌ ERROR in {t['label']}: {e}{RESET}")
        FAIL += 1
    time.sleep(0.5)

print(f"\n{BOLD}{'═'*60}")
print(f"  RESULTS: {GREEN}{PASS} PASSED{RESET}  {RED}{FAIL} FAILED{RESET}  ({PASS+FAIL} total)")
print(f"{'═'*60}{RESET}\n")
sys.exit(0 if FAIL == 0 else 1)
