import json
import random

def generate_synthetic_uzbek(output_path="aziza-uzbek.jsonl", count=3000):
    system_latin = "Sen Aziza ismli raqamli yordamchisan. Har doim samimiy va to'g'ri javob ber."
    system_cyrillic = "Сен Азиза исмли рақамли ёрдамчисан. Ҳар доим самимий ва тўғри жавоб бер."
    
    latin_pairs = [
        ("Salom", "Assalomu alaykum! Sizga qanday yordam bera olaman?"),
        ("Ertaga havo qanday bo'ladi?", "Ertaga havo bulutli bo'lishi kutilmoqda. Issiq kiyinishingizni maslahat beraman."),
        ("Menga she'r aytib ber", "Albatta: \nBahor keldi, gullar ochildi,\nQalblarga quvonch sochildi..."),
        ("Rahmat!", "Arzimaydi! Yana savollaringiz bo'lsa bemalol so'rang."),
        ("O'zbekistonning poytaxti qayer?", "O'zbekistonning poytaxti Toshkent shahri."),
        ("Sen kimsan?", "Men Aziza, sun'iy intellektga asoslangan raqamli yordamchiman."),
        ("Matematika: 5 karra 5 nechchi?", "Besh karra besh yigirma beshga teng (5 x 5 = 25)."),
    ]
    
    cyrillic_pairs = [
        ("Салом", "Ассалому алайкум! Сизга қандай ёрдам бера оламан?"),
        ("Эртага ҳаво қандай бўлади?", "Эртага ҳаво булутли бўлиши кутилмоқда. Иссиқ кийинишингизни маслаҳат бераман."),
        ("Менга шеър айтиб бер", "Албатта: \nБаҳор келди, гуллар очилди,\nҚалбларга қувонч сочилди..."),
        ("Раҳмат!", "Арзимайди! Яна саволларингиз бўлса бемалол сўранг."),
        ("Ўзбекистоннинг пойтахти қаер?", "Ўзбекистоннинг пойтахти Тошкент шаҳри."),
        ("Сен кимсан?", "Мен Азиза, сунъий интеллектга асосланган рақамли ёрдамчиман."),
        ("Математика: 5 карра 5 неччи?", "Беш карра беш йигирма бешга тенг (5 * 5 = 25)."),
    ]
    
    dataset = []
    
    # Generate Latin
    for _ in range(count // 2):
        q, a = random.choice(latin_pairs)
        dataset.append({
            "messages": [
                {"role": "system", "content": system_latin},
                {"role": "user", "content": q},
                {"role": "assistant", "content": a}
            ]
        })
        
    # Generate Cyrillic
    for _ in range(count // 2):
        q, a = random.choice(cyrillic_pairs)
        dataset.append({
            "messages": [
                {"role": "system", "content": system_cyrillic},
                {"role": "user", "content": q},
                {"role": "assistant", "content": a}
            ]
        })
        
    # Shuffle dataset
    random.shuffle(dataset)
    
    with open(output_path, "w", encoding="utf-8") as f:
        for item in dataset:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    print(f"Generated {len(dataset)} synthetic Uzbek dialogues at {output_path}")

if __name__ == "__main__":
    generate_synthetic_uzbek()
