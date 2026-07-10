"""
Qube Backend — Language Detection (fasttext)
==============================================
Uses Meta's fasttext lid.176.bin model for language detection (EN/RU/UZ).
Supports 176 languages, <1ms per query, handles short text and mixed language.

Install: pip install fasttext-wheel
Model:   auto-downloaded on first use (~126MB)
"""

import os
import re
import threading
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_MODEL_DIR = Path(os.getenv("LANG_MODEL_DIR", "./models"))
_MODEL_FILE = _MODEL_DIR / "lid.176.bin"
_MODEL_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"

# Languages we care about — map fasttext labels to our codes
_LANG_MAP = {
    "en": "en", "ru": "ru", "uz": "uz",
    # Nearby languages that might appear in Central Asian context
    "kk": "ru",  # Kazakh Cyrillic → route to RU model
    "tg": "ru",  # Tajik Cyrillic → route to RU model
    "ky": "ru",  # Kyrgyz Cyrillic → route to RU model
    "tr": "uz",  # Turkish is close to Uzbek → route to UZ model
    "az": "uz",  # Azerbaijani is Turkic → route to UZ model
}

# Common Uzbek Latin words/phrases that fasttext misclassifies on short input.
# Used as a fallback when fasttext confidence is low or detects wrong language.
_UZ_KEYWORDS_LATIN = {
    "nima", "qanday", "qayerda", "nega", "kimga", "qachon", "qancha",
    "salom", "rahmat", "kerak", "bor", "yo'q", "ha", "men", "sen",
    "bu", "shu", "u", "biz", "ular", "qiling", "berish", "olish",
    "bilasiz", "aytib", "bering", "menga", "senga", "unga",
    "yaxshi", "yomon", "katta", "kichik", "yangi", "eski",
    "o'zbek", "toshkent", "uzbek", "o'zbekiston",
    "haqida", "uchun", "bilan", "hamma", "narsa", "ish", "kun",
    "vaqt", "joy", "odam", "kishi", "til", "so'z", "gap",
    "dastur", "kompyuter", "texnologiya", "axborot", "tizim",
    "yordam", "savol", "javob", "masala", "vazifa",
    "nimaga", "qaysi", "kimdir", "nimadir", "hech",
}

# Cyrillic letters unique to Uzbek — these do NOT exist in Russian/Kazakh/Tajik.
# If any of these appear, the text is almost certainly Uzbek Cyrillic.
_UZ_CYRILLIC_UNIQUE = set("ўқғҳ")

# Common Uzbek Cyrillic words for fallback detection
_UZ_KEYWORDS_CYRILLIC = {
    "нима", "қандай", "қаерда", "нега", "қачон", "қанча",
    "салом", "раҳмат", "керак", "бор", "йўқ", "ҳа", "мен", "сен",
    "бу", "шу", "биз", "улар", "қилинг", "бериш", "олиш",
    "яхши", "ёмон", "катта", "кичик", "янги", "эски",
    "ўзбек", "тошкент", "ўзбекистон",
    "ҳақида", "учун", "билан", "ҳамма", "нарса", "иш", "кун",
    "вақт", "жой", "одам", "киши", "тил", "сўз", "гап",
    "дастур", "компьютер", "технология", "ахборот", "тизим",
    "ёрдам", "савол", "жавоб", "масала", "вазифа",
    "нимага", "қайси", "кимдир", "нимадир", "ҳеч",
}

# ---------------------------------------------------------------------------
# Lazy model loading
# ---------------------------------------------------------------------------
_model = None
_model_lock = threading.Lock()

def _get_model():
    """Load fasttext model, downloading if needed."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import fasttext
                # Suppress fasttext warnings about deprecated API
                fasttext.FastText.eprint = lambda x: None
                # Fix NumPy 2.x incompatibility: fasttext uses np.array(x, copy=False)
                # which raises ValueError in NumPy 2.x. Patch the predict method's source.
                import fasttext.FastText as _ft_mod
                import numpy as _np
                _orig_np_array = _np.array
                def _compat_array(*args, **kwargs):
                    if kwargs.get('copy') is False:
                        kwargs.pop('copy')
                        return _np.asarray(*args, **kwargs)
                    return _orig_np_array(*args, **kwargs)
                _ft_mod.np.array = _compat_array

                if not _MODEL_FILE.exists():
                    print(f"[LANG] Downloading fasttext lid.176.bin (~126MB)...")
                    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
                    import urllib.request
                    urllib.request.urlretrieve(_MODEL_URL, str(_MODEL_FILE))
                    print(f"[LANG] Download complete: {_MODEL_FILE}")

                print(f"[LANG] Loading fasttext model: {_MODEL_FILE}")
                _model = fasttext.load_model(str(_MODEL_FILE))
                print("[LANG] Fasttext model ready (176 languages)")
    return _model

def preload_model():
    """Pre-load model at server startup (called from server.py lifespan)."""
    _get_model()

# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------
def detect_uz_script(text: str) -> str | None:
    """
    Detect which Uzbek script the text uses.
    Returns "Cyrl", "Latn", or None (not Uzbek / indeterminate).
    """
    has_cyrillic = bool(re.search(r'[а-яёА-ЯЁўқғҳЎҚҒҲ]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))
    if has_cyrillic and not has_latin:
        return "Cyrl"
    if has_latin and not has_cyrillic:
        return "Latn"
    # Mixed: decide by unique Uzbek Cyrillic chars or character ratio
    if has_cyrillic and has_latin:
        if set(text) & _UZ_CYRILLIC_UNIQUE:
            return "Cyrl"
        cyrillic_count = len(re.findall(r'[а-яёА-ЯЁ]', text))
        latin_count = len(re.findall(r'[a-zA-Z]', text))
        return "Cyrl" if cyrillic_count > latin_count else "Latn"
    return None

def detect_language(text: str) -> dict:
    """
    Detect language(s) in text using fasttext lid.176.bin.

    Returns:
    {
        "primary": "en" | "ru" | "uz",
        "script": "Cyrl" | "Latn" | None,  (only set when primary == "uz")
        "detected_languages": [{"lang": "en", "confidence": 0.95}, ...],
        "is_mixed": True/False,
        "layout_corrected": False,
        "corrected_text": None,
        "confidence": 0.0-1.0,
    }
    """
    original = text.strip()
    if not original:
        return _empty_result()

    # Run fasttext prediction (top 5 languages)
    model = _get_model()
    clean = original.replace('\n', ' ').strip()
    labels, scores = model.predict(clean, k=5)

    # Parse results
    predictions = []
    for label, score in zip(labels, scores):
        lang = label.replace("__label__", "")
        conf = round(float(score), 4)
        if conf < 0.01:
            continue
        predictions.append({"lang": lang, "confidence": conf})

    if not predictions:
        return _empty_result()

    # Log detection for debugging
    top3 = ", ".join(f"{p['lang']}={p['confidence']}" for p in predictions[:3])
    print(f"[LANG] \"{clean[:50]}\" → {top3}")

    # Map to our supported languages (en/ru/uz)
    primary_raw = predictions[0]["lang"]
    primary_conf = predictions[0]["confidence"]
    primary = _LANG_MAP.get(primary_raw, "en")  # default to EN for unsupported

    # ------------------------------------------------------------------
    # Cyrillic Uzbek detection: unique letters ў, қ, ғ, ҳ are conclusive
    # ------------------------------------------------------------------
    has_uz_cyrillic_chars = bool(set(original) & _UZ_CYRILLIC_UNIQUE)
    if has_uz_cyrillic_chars:
        print(f"[LANG] Cyrillic Uzbek detected (unique chars: {set(original) & _UZ_CYRILLIC_UNIQUE})")
        primary = "uz"
        primary_conf = 0.95
    # Cyrillic Uzbek keyword fallback (no unique chars but Uzbek words)
    elif primary != "uz" and bool(re.search(r'[а-яёА-ЯЁ]', original)):
        cyrillic_words = set(re.findall(r'[а-яёА-ЯЁўқғҳ]+', clean.lower()))
        uz_cyr_matches = cyrillic_words & _UZ_KEYWORDS_CYRILLIC
        if uz_cyr_matches:
            print(f"[LANG] Cyrillic Uzbek keyword override → uz (matched: {uz_cyr_matches})")
            primary = "uz"
            primary_conf = 0.85

    # Latin Uzbek keyword fallback: helps with short input like "ai nima?"
    if primary != "uz":
        words = set(re.findall(r"[a-zA-Z']+", clean.lower()))
        uz_matches = words & _UZ_KEYWORDS_LATIN
        if uz_matches:
            print(f"[LANG] Latin Uzbek keyword override → uz (matched: {uz_matches})")
            primary = "uz"
            primary_conf = 0.8

    # Detect mixed language
    # Check if there are multiple significant languages in top predictions
    significant = [p for p in predictions if p["confidence"] > 0.1]
    our_langs = set()
    for p in significant:
        mapped = _LANG_MAP.get(p["lang"])
        if mapped:
            our_langs.add(mapped)

    is_mixed = len(our_langs) > 1

    # For mixed text, also try splitting by script (Cyrillic vs Latin)
    if not is_mixed:
        has_cyrillic = bool(re.search(r'[а-яёА-ЯЁўқғҳЎҚҒҲ]', original))
        has_latin = bool(re.search(r'[a-zA-Z]', original))
        if has_cyrillic and has_latin:
            is_mixed = True
            our_langs = _detect_mixed_scripts(original, model)
            if not our_langs:
                our_langs = {primary}

    # Build detected_languages list (mapped to our codes)
    detected_mapped = []
    seen = set()
    for p in predictions:
        mapped = _LANG_MAP.get(p["lang"])
        if mapped and mapped not in seen:
            seen.add(mapped)
            detected_mapped.append({"lang": mapped, "confidence": p["confidence"]})

    if not detected_mapped:
        detected_mapped = [{"lang": "en", "confidence": 0.5}]

    # Detect Uzbek script (Cyrillic vs Latin) when language is Uzbek
    script = detect_uz_script(original) if primary == "uz" else None

    return {
        "primary": primary,
        "script": script,
        "detected_languages": detected_mapped,
        "is_mixed": is_mixed,
        "layout_corrected": False,
        "corrected_text": None,
        "confidence": round(primary_conf, 2),
    }

def _detect_mixed_scripts(text: str, model) -> set[str]:
    """
    For text with mixed Cyrillic + Latin, detect language of each part separately.
    """
    langs = set()

    # Extract Cyrillic parts (include Uzbek-specific chars ўқғҳ)
    cyrillic_parts = re.findall(r'[а-яёА-ЯЁўқғҳЎҚҒҲ]+(?:\s+[а-яёА-ЯЁўқғҳЎҚҒҲ]+)*', text)
    if cyrillic_parts:
        cyrillic_text = ' '.join(cyrillic_parts)
        # Check for Uzbek Cyrillic unique chars first
        if set(cyrillic_text) & _UZ_CYRILLIC_UNIQUE:
            langs.add("uz")
        else:
            labels, scores = model.predict(cyrillic_text, k=1)
            lang = labels[0].replace("__label__", "")
            mapped = _LANG_MAP.get(lang, "ru")
            langs.add(mapped)

    # Extract Latin parts
    latin_parts = re.findall(r'[a-zA-Z]+(?:\s+[a-zA-Z]+)*', text)
    if latin_parts:
        latin_text = ' '.join(latin_parts)
        labels, scores = model.predict(latin_text, k=1)
        lang = labels[0].replace("__label__", "")
        mapped = _LANG_MAP.get(lang, "en")
        langs.add(mapped)

    return langs

def _empty_result() -> dict:
    return {
        "primary": "en",
        "script": None,
        "detected_languages": [{"lang": "en", "confidence": 0.0}],
        "is_mixed": False,
        "layout_corrected": False,
        "corrected_text": None,
        "confidence": 0.0,
    }

# ---------------------------------------------------------------------------
# LLM routing helper
# ---------------------------------------------------------------------------
def get_llm_language(detection: dict) -> str:
    """
    Determine which LLM to route to based on detection.
    Returns 'uz' for Uzbek, 'en' for everything else (Qwen handles EN + RU).
    """
    if detection["primary"] == "uz":
        return "uz"
    return "en"  # Qwen handles English and Russian

# ---------------------------------------------------------------------------
# Detect requested response language
# ---------------------------------------------------------------------------
# Phrases that signal "respond in Uzbek"
_REQUEST_UZ = [
    # English
    "in uzbek", "respond in uzbek", "answer in uzbek", "reply in uzbek",
    "speak uzbek", "write in uzbek", "uzbek language", "using uzbek",
    # Russian
    "на узбекском", "по-узбекски", "по узбекски", "на узбекском языке",
    "отвечай на узбекском", "ответь на узбекском",
    # Uzbek
    "o'zbek tilida", "o'zbekcha", "uzbekcha",
]

# Phrases that signal "respond in Russian"
_REQUEST_RU = [
    # English
    "in russian", "respond in russian", "answer in russian", "reply in russian",
    "speak russian", "write in russian", "russian language", "using russian",
    # Uzbek
    "rus tilida", "ruscha",
    # Russian
    "на русском", "по-русски", "по русски",
]

# Phrases that signal "respond in English"
_REQUEST_EN = [
    # English
    "in english", "respond in english", "answer in english", "reply in english",
    "speak english", "write in english", "english language", "using english",
    # Russian
    "на английском", "по-английски", "по английски", "на английском языке",
    # Uzbek
    "ingliz tilida", "inglizcha",
]

def detect_requested_language(text: str) -> str | None:
    """
    Detect if the user is asking for a response in a specific language.
    Returns 'uz', 'ru', 'en', or None if no explicit request detected.
    """
    lower = text.lower()
    for phrase in _REQUEST_UZ:
        if phrase in lower:
            print(f"[LANG] Requested response language: uz (matched: '{phrase}')")
            return "uz"
    for phrase in _REQUEST_RU:
        if phrase in lower:
            print(f"[LANG] Requested response language: ru (matched: '{phrase}')")
            return "ru"
    for phrase in _REQUEST_EN:
        if phrase in lower:
            print(f"[LANG] Requested response language: en (matched: '{phrase}')")
            return "en"
    return None

# ---------------------------------------------------------------------------
# Uzbek Cyrillic → Latin transliteration
# ---------------------------------------------------------------------------
# Multi-char mappings must be checked before single-char ones
_UZ_CYR2LAT_MULTI = {
    "Ё": "Yo", "ё": "yo",
    "Ж": "J",  "ж": "j",
    "Ц": "Ts", "ц": "ts",
    "Ч": "Ch", "ч": "ch",
    "Ш": "Sh", "ш": "sh",
    "Щ": "Sh", "щ": "sh",
    "Ю": "Yu", "ю": "yu",
    "Я": "Ya", "я": "ya",
    "Ў": "O'", "ў": "o'",
    "Ғ": "G'", "ғ": "g'",
}

_UZ_CYR2LAT_SINGLE = {
    "А": "A",  "а": "a",
    "Б": "B",  "б": "b",
    "В": "V",  "в": "v",
    "Г": "G",  "г": "g",
    "Д": "D",  "д": "d",
    "Е": "E",  "е": "e",
    "З": "Z",  "з": "z",
    "И": "I",  "и": "i",
    "Й": "Y",  "й": "y",
    "К": "K",  "к": "k",
    "Л": "L",  "л": "l",
    "М": "M",  "м": "m",
    "Н": "N",  "н": "n",
    "О": "O",  "о": "o",
    "П": "P",  "п": "p",
    "Р": "R",  "р": "r",
    "С": "S",  "с": "s",
    "Т": "T",  "т": "t",
    "У": "U",  "у": "u",
    "Ф": "F",  "ф": "f",
    "Х": "X",  "х": "x",
    "Қ": "Q",  "қ": "q",
    "Ҳ": "H",  "ҳ": "h",
    "Э": "E",  "э": "e",
    "Ъ": "'",  "ъ": "'",
    "Ь": "",   "ь": "",
    "Ы": "I",  "ы": "i",
}

# Combined lookup: multi-char first, then single-char
_UZ_CYR2LAT = {**_UZ_CYR2LAT_MULTI, **_UZ_CYR2LAT_SINGLE}

def transliterate_uz_cyrillic_to_latin(text: str) -> str:
    """
    Convert Uzbek Cyrillic text to Latin script.
    Non-Cyrillic characters (Latin, digits, punctuation) are kept as-is.
    """
    if not bool(re.search(r'[а-яёА-ЯЁўқғҳЎҚҒҲ]', text)):
        return text  # No Cyrillic chars, return unchanged

    result = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in _UZ_CYR2LAT:
            result.append(_UZ_CYR2LAT[ch])
        else:
            result.append(ch)
        i += 1

    converted = "".join(result)
    print(f"[LANG] Transliterated Cyrillic→Latin: \"{text[:50]}\" → \"{converted[:50]}\"")
    return converted

# ---------------------------------------------------------------------------
# Uzbek Latin → Cyrillic transliteration
# ---------------------------------------------------------------------------
# Multi-char Latin sequences that map to single Cyrillic letters
# Order matters: longer sequences must be checked first
_UZ_LAT2CYR_MULTI = [
    ("Yo", "Ё"), ("yo", "ё"), ("YO", "Ё"),
    ("Sh", "Ш"), ("sh", "ш"), ("SH", "Ш"),
    ("Ch", "Ч"), ("ch", "ч"), ("CH", "Ч"),
    ("Ts", "Ц"), ("ts", "ц"), ("TS", "Ц"),
    ("Yu", "Ю"), ("yu", "ю"), ("YU", "Ю"),
    ("Ya", "Я"), ("ya", "я"), ("YA", "Я"),
    ("O'", "Ў"), ("o'", "ў"), ("O`", "Ў"), ("o`", "ў"),
    ("G'", "Ғ"), ("g'", "ғ"), ("G`", "Ғ"), ("g`", "ғ"),
]

_UZ_LAT2CYR_SINGLE = {
    "A": "А",  "a": "а",
    "B": "Б",  "b": "б",
    "D": "Д",  "d": "д",
    "E": "Е",  "e": "е",
    "F": "Ф",  "f": "ф",
    "G": "Г",  "g": "г",
    "H": "Ҳ",  "h": "ҳ",
    "I": "И",  "i": "и",
    "J": "Ж",  "j": "ж",
    "K": "К",  "k": "к",
    "L": "Л",  "l": "л",
    "M": "М",  "m": "м",
    "N": "Н",  "n": "н",
    "O": "О",  "o": "о",
    "P": "П",  "p": "п",
    "Q": "Қ",  "q": "қ",
    "R": "Р",  "r": "р",
    "S": "С",  "s": "с",
    "T": "Т",  "t": "т",
    "U": "У",  "u": "у",
    "V": "В",  "v": "в",
    "X": "Х",  "x": "х",
    "Y": "Й",  "y": "й",
    "Z": "З",  "z": "з",
}

def transliterate_uz_latin_to_cyrillic(text: str) -> str:
    """
    Convert Uzbek Latin text to Cyrillic script.
    Non-Latin characters (digits, punctuation, etc.) are kept as-is.
    """
    if not text:
        return text

    # Normalize all apostrophe variants to standard '
    normalized = text
    for apo in ("\u2018", "\u2019", "\u02BB", "\u02BC", "`", "\u0060"):
        normalized = normalized.replace(apo, "'")

    # First pass: replace multi-char sequences
    result = normalized
    for lat, cyr in _UZ_LAT2CYR_MULTI:
        result = result.replace(lat, cyr)

    # Second pass: replace remaining single Latin chars
    output = []
    for ch in result:
        if ch in _UZ_LAT2CYR_SINGLE:
            output.append(_UZ_LAT2CYR_SINGLE[ch])
        else:
            output.append(ch)

    return "".join(output)

class StreamingTransliterator:
    """
    Streaming-aware Latin→Cyrillic transliterator for Uzbek.
    Buffers characters that could start multi-char sequences (O, G, S, C, T, Y)
    so that O' / G' / Sh / Ch / Ts / Yu / Ya / Yo are handled correctly
    even when split across streaming tokens.
    """

    # Characters that could start a multi-char Latin sequence
    _MULTI_STARTERS = {
        "O": "'",  "o": "'",
        "G": "'",  "g": "'",
        "S": "h",  "s": "h",
        "C": "h",  "c": "h",
        "T": "s",  "t": "s",
        "Y": "aoua",  "y": "aoua",  # Ya, Yo, Yu + plain Y
    }

    def __init__(self):
        self._pending = ""  # buffered char waiting for next char

    def feed(self, token: str) -> str:
        """
        Feed a streaming token and return transliterated output.
        May buffer 1 char between calls for multi-char sequence handling.
        """
        if not token:
            return ""

        # Normalize apostrophes
        text = token
        for apo in ("\u2018", "\u2019", "\u02BB", "\u02BC", "`", "\u0060"):
            text = text.replace(apo, "'")

        # Prepend any pending char from previous token
        text = self._pending + text
        self._pending = ""

        # Check if last char could start a multi-char sequence
        if text and text[-1] in self._MULTI_STARTERS:
            self._pending = text[-1]
            text = text[:-1]

        # Now transliterate the complete text
        return transliterate_uz_latin_to_cyrillic(text)

    def flush(self) -> str:
        """Flush any remaining buffered character (call at end of stream)."""
        if self._pending:
            result = transliterate_uz_latin_to_cyrillic(self._pending)
            self._pending = ""
            return result
        return ""

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
class DetectRequest(BaseModel):
    text: str

@router.post("/detect")
async def api_detect_language(req: DetectRequest):
    # Use the advanced detect_language function defined above
    result = detect_language(req.text)
    
    # Return both the new rich dictionary format and the legacy keys 
    # to avoid breaking any other services that depend on them
    response = {
        **result,
        "language": result["primary"],
        "confidence": result["confidence"],
    }
    return response
