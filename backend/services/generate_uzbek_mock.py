#!/usr/bin/env python3
import json
import random

def generate_mock():
    # Generate 1500 Latin, 1500 Cyrillic pairs
    # Split: Academic 20%, Professional 40%, Colloquial 40%
    registers = ["academic", "professional", "colloquial"]
    weights = [0.2, 0.4, 0.4]

    latin_sys = "Siz Aziza — mehribon, aqlli va diqqatli AI yordamchisiz."
    cyrillic_sys = "Сиз Азиза — меҳрибон, ақлли ва диққатли АИ ёрдамчисиз."

    latin_responses = {
        "academic": "Oʻzbekiston tarixi juda boy va qiziqarli Gʻoyalarga ega. Siz qaysi davr bilan qiziqasiz?",
        "professional": "Assalomu alaykum! Men Aziza. Sizga qanday yordam bera olaman? Shartnoma masalasida savolingiz bormi?",
        "colloquial": "Qanday yordam bera olaman? Choy ichib suhbatlashamizmi? Bugun havo ajoyib, shunday emasmi?"
    }

    cyrillic_responses = {
        "academic": "Ўзбекистон тарихи жуда бой ва қизиқарли Ғояларга эга. Сиз қайси давр билан қизиқасиз?",
        "professional": "Ассалому алайкум! Мен Азиза. Сизга қандай ёрдам бера оламан? Шартнома масаласида саволингиз борми?",
        "colloquial": "Қандай ёрдам бера оламан? Чой ичиб суҳбатлашамизми? Бугун ҳаво ажойиб, шундай эмасми?"
    }

    data = []
    
    # 1500 Latin
    for _ in range(1500):
        reg = random.choices(registers, weights)[0]
        data.append({
            "language": "uz_latin",
            "register": reg,
            "messages": [
                {"role": "system", "content": latin_sys},
                {"role": "user", "content": "Salom, menga yordam bering."},
                {"role": "assistant", "content": latin_responses[reg]}
            ]
        })

    # 1500 Cyrillic
    for _ in range(1500):
        reg = random.choices(registers, weights)[0]
        data.append({
            "language": "uz_cyrillic",
            "register": reg,
            "messages": [
                {"role": "system", "content": cyrillic_sys},
                {"role": "user", "content": "Салом, менга ёрдам беринг."},
                {"role": "assistant", "content": cyrillic_responses[reg]}
            ]
        })

    # Shuffle dataset
    random.shuffle(data)

    with open("data/aziza-bilingual/aziza-uzbek.jsonl", "w", encoding="utf-8") as f:
        for d in data:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    import os
    os.makedirs("data/aziza-bilingual", exist_ok=True)
    generate_mock()
