import re

with open("eval_uzbek.py", "r") as f:
    code = f.read()

# 1. Prompts
code = re.sub(r'RU_TEST_PROMPTS = \[.*?\]', '''UZ_TEST_PROMPTS = [
    ("Salom! Isming nima va nimalar qila olasan?", "Greeting + persona identity"),
    ("O\\'zing haqingda gapirib ber. Kimsan?", "Self-description — persona awareness"),
    ("Mashinali o\\'rganish va neyron tarmoqlarning tamoyillarini tushuntirib ber.", "Academic register — ML concepts"),
    ("Mijoz bilan restoranda uchrashuvni qanday qilib eng yaxshi tarzda tashkil qilish mumkin?", "Professional register — hospitality domain"),
    ("O\\'zbek madaniyati va an\\'analari haqida nimalarni bilasan?", "Cultural knowledge + context"),
    ("Hamkorga rasmiy biznes xati yozishda menga yordam ber.", "Professional — business writing"),
    ("Ingliz tilidan o\\'zbek tiliga tarjima qil: \\'The weather is beautiful today.\\'", "Translation task"),
    ("Sun\\'iy intellekt nima ekanligini oddiy so\\'zlar bilan tushuntirib ber.", "Colloquial explanation of AI"),
    ("Choyni qanday qilib to\\'g\\'ri damlash kerak?", "Everyday colloquial task"),
    ("O\\'zbek tilida o\\'z maqsading va imkoniyatlaringni ta\\'riflab ber.", "Capability description in Uzbek"),
]''', code, flags=re.DOTALL)

code = code.replace("RU_TEST_PROMPTS", "UZ_TEST_PROMPTS")
code = code.replace("EN_PROMPTS_THAT_SHOULD_STAY_RUSSIAN", "EN_PROMPTS_THAT_SHOULD_STAY_UZBEK")
code = code.replace("Russian for me", "Uzbek for me")
code = code.replace("Russian prompts", "Uzbek prompts")
code = code.replace("Russian responses", "Uzbek responses")
code = code.replace("serve_russian_test.py", "serve_multilingual.py")

# 2. Cyrillic helpers -> Uzbek script helpers
uzbek_helpers = '''def has_uzbek_script(text: str) -> bool:
    uz_cyrillic = set("ҲҶҚҒЎҳҷқғў")
    if any(c in text for c in ["ʻ", "‘", "’", "'"]):
        return True
    if any(c in uz_cyrillic for c in text):
        return True
    # Fallback: just check if it contains common uzbek latin characters if there are no apostrophes
    if " va " in text or " bilan " in text or " uchun " in text:
        return True
    return False

def uzbek_script_ratio(text: str) -> float:
    if not text: return 0.0
    words = text.split()
    uzbek_words = sum(1 for w in words if has_uzbek_script(w) or w.endswith(("ni", "ning", "da", "dan", "ga", "lar")))
    return uzbek_words / len(words) if words else 0.0'''

code = re.sub(r'def has_cyrillic.*?def cyrillic_ratio.*?return cyrillic_chars / alpha_chars if alpha_chars > 0 else 0\.0', uzbek_helpers, code, flags=re.DOTALL)

code = code.replace("has_cyrillic", "has_uzbek_script")
code = code.replace("cyrillic_ratio", "uzbek_script_ratio")
code = code.replace("cyrillic_present", "uzbek_present")
code = code.replace("cyr_ratio", "uzbek_ratio")
code = code.replace("Cyrillic character ratio", "Uzbek word ratio")
code = code.replace("Cyrillic-containing", "Uzbek-containing")
code = code.replace("Cyrillic", "Uzbek")
code = code.replace("cyrillic", "uzbek")
code = code.replace("gate_cyrillic_pct", "gate_uzbek_pct")
code = code.replace("ru_prompts_uzbek_pct", "uz_prompts_uzbek_pct")

with open("eval_uzbek.py", "w") as f:
    f.write(code)
