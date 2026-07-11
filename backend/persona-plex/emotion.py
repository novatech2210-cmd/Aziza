"""
Emotion Detection for PersonaPlex.

Provides lightweight rule-based emotion detection from text input.
Uses keyword matching, punctuation patterns, and emoji detection.
No ML dependencies required.
"""

import re
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("EmotionDetector")


@dataclass
class EmotionResult:
    emotion: str
    confidence: float
    arousal: float  # 0.0 (calm) to 1.0 (excited)
    valence: float  # 0.0 (negative) to 1.0 (positive)


# Emotion keywords per language
_EMOTION_KEYWORDS = {
    "ru": {
        "happy": ["радость", "счастье", "весело", "отлично", "прекрасно", "класс", "супер", "круто", "ура", "обожаю", "рад", "счастлив", "восторг"],
        "sad": ["грустно", "печально", "тоска", "одиноко", "жаль", "увы", "горе", "слёзы", "плачу"],
        "angry": ["злость", "бесит", "ужасно", "отвратительно", "ненавижу", "идиот", "дурак", "тупо", "кошмар"],
        "surprised": ["ого", "вау", "невероятно", "серьёзно", "правда", "неужели", "wow"],
        "fear": ["боюсь", "страшно", "паника", "тревога", "волнуюсь", "опасно"],
        "grateful": ["спасибо", "благодарю", "благодарность", "ценно", "помощь"],
    },
    "uz": {
        "happy": ["baxt", "baxtli", "quvonch", "ajoyib", "a'lo", "zo'r", "katta", "xursand", "sevinch", "yorqin"],
        "sad": ["qayg'u", "g'am", "hafsala", "yalg'iz", "afsus", "huzun", "qoshi"],
        "angry": ["g'azab", "jahl", "yomon", "nafrat", "asabi", "qattiq"],
        "surprised": ["vau", "hayrat", "chindan", "haqiqatan", "ajab"],
        "fear": ["qo'rqaman", "qo'rqinchli", "xavotir", "tashvish", "dahshat"],
        "grateful": ["rahmat", "minnatdor", "sakram", "yuqori"],
    },
    "en": {
        "happy": ["happy", "great", "awesome", "love", "wonderful", "amazing", "excellent", "fantastic", "yay", "haha"],
        "sad": ["sad", "sorry", "unfortunately", "miss", "lonely", "depressed", "cry", "tears"],
        "angry": ["angry", "hate", "terrible", "awful", "stupid", "furious", "annoying", "ridiculous"],
        "surprised": ["wow", "really", "seriously", "unbelievable", "incredible", "omg"],
        "fear": ["scared", "afraid", "worried", "anxious", "panic", "terrifying"],
        "grateful": ["thank", "thanks", "grateful", "appreciate", "helpful"],
    },
}

# Emoji emotion mapping
_EMOJI_EMOTIONS = {
    "happy": ["😊", "😄", "😃", "😁", "🥰", "😍", "🥳", "😆"],
    "sad": ["😢", "😭", "😞", "😔", "🥺", "😿"],
    "angry": ["😡", "🤬", "😤", "💢", "😠"],
    "surprised": ["😲", "😮", "🤯", "😳", "😱"],
    "love": ["❤️", "💕", "💗", "💖", "💘", "💝"],
}

# Emotion to valence/arousal mapping
_EMOTION_DIMENSIONS = {
    "neutral": {"valence": 0.5, "arousal": 0.3},
    "happy": {"valence": 0.9, "arousal": 0.7},
    "sad": {"valence": 0.2, "arousal": 0.3},
    "angry": {"valence": 0.1, "arousal": 0.9},
    "surprised": {"valence": 0.6, "arousal": 0.8},
    "fear": {"valence": 0.2, "arousal": 0.8},
    "grateful": {"valence": 0.8, "arousal": 0.4},
    "love": {"valence": 0.9, "arousal": 0.6},
}

# Adaptation prompts per emotion
_EMOTION_ADAPTATIONS = {
    "neutral": "",
    "happy": "The user seems happy and positive. Match their energy with warm, enthusiastic responses.",
    "sad": "The user seems sad or down. Be empathetic, gentle, and supportive. Offer comfort without being dismissive.",
    "angry": "The user seems frustrated or angry. Stay calm, acknowledge their frustration, and try to help resolve the issue.",
    "surprised": "The user seems surprised. Share in their excitement or help them process the information.",
    "fear": "The user seems worried or anxious. Reassure them and provide clear, helpful information.",
    "grateful": "The user is expressing gratitude. Acknowledge it warmly and continue being helpful.",
    "love": "The user is expressing affection. Respond warmly and naturally.",
}


def detect_emotion(text: str, language: str = "en") -> EmotionResult:
    """
    Detect emotion from text input using keyword matching and patterns.
    
    Args:
        text: Input text to analyze
        language: Language code (en, ru, uz)
    
    Returns:
        EmotionResult with detected emotion, confidence, and dimensions
    """
    text_lower = text.lower().strip()
    if not text_lower:
        return EmotionResult("neutral", 0.5, 0.3, 0.5)
    
    scores = {}
    
    # Check keywords for detected language and English (common across all)
    # Use word-boundary matching to avoid substring false positives
    # (e.g., "hate" inside "zamechatelno")
    for lang in [language, "en"]:
        keywords = _EMOTION_KEYWORDS.get(lang, {})
        for emotion, words in keywords.items():
            count = sum(1 for w in words
                        if re.search(r'(?<!\w)' + re.escape(w) + r'(?!\w)', text_lower))
            if count > 0:
                scores[emotion] = scores.get(emotion, 0) + count
    
    # Check emojis
    for emotion, emojis in _EMOJI_EMOTIONS.items():
        count = sum(1 for e in emojis if e in text)
        if count > 0:
            key = "love" if emotion == "love" else emotion
            scores[key] = scores.get(key, 0) + count * 2  # Emoji weighted higher
    
    # Exclamation marks indicate arousal
    exclamation_count = text.count("!")
    question_count = text.count("?")
    
    # ALL CAPS indicates strong emotion
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    
    # Determine winning emotion
    if not scores:
        # Check punctuation-based arousal
        if exclamation_count >= 2 or caps_ratio > 0.5:
            return EmotionResult("surprised", 0.4, 0.7, 0.5)
        return EmotionResult("neutral", 0.6, 0.3, 0.5)
    
    best_emotion = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = min(scores[best_emotion] / max(total, 1), 1.0)
    
    # Boost confidence for strong signals
    if exclamation_count >= 2:
        confidence = min(confidence + 0.1, 1.0)
    if caps_ratio > 0.5:
        confidence = min(confidence + 0.1, 1.0)
    
    dims = _EMOTION_DIMENSIONS.get(best_emotion, _EMOTION_DIMENSIONS["neutral"])
    
    return EmotionResult(
        emotion=best_emotion,
        confidence=round(confidence, 2),
        arousal=dims["arousal"],
        valence=dims["valence"],
    )


def get_emotion_adaptation(emotion: str) -> str:
    """Get the system prompt adaptation for a detected emotion."""
    return _EMOTION_ADAPTATIONS.get(emotion, "")


def get_emotion_state(session_emotions: list[str]) -> str:
    """
    Compute dominant emotion from recent emotion history.
    
    Args:
        session_emotions: List of recent emotion labels
    
    Returns:
        Dominant emotion label
    """
    if not session_emotions:
        return "neutral"
    
    # Count occurrences
    counts = {}
    for e in session_emotions:
        counts[e] = counts.get(e, 0) + 1
    
    return max(counts, key=counts.get)
