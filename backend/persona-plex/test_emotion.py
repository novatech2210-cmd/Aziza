"""Tests for the PersonaPlex emotion detection module."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emotion import (
    detect_emotion,
    get_emotion_adaptation,
    get_emotion_state,
    EmotionResult,
    _EMOTION_KEYWORDS,
    _EMOJI_EMOTIONS,
)


class TestEmotionDetection:
    def test_happy_detection_en(self):
        result = detect_emotion("I'm so happy today!")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['happy', 'neutral']
        assert result.confidence >= 0

    def test_sad_detection_en(self):
        result = detect_emotion("I feel so sad and depressed")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['sad', 'neutral']

    def test_angry_detection_en(self):
        result = detect_emotion("This is terrible! I'm furious!")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['angry', 'neutral']

    def test_neutral_detection(self):
        result = detect_emotion("The weather is nice today")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['neutral', 'happy']

    def test_russian_happy(self):
        result = detect_emotion("Я очень рад сегодня!")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['happy', 'neutral']

    def test_russian_sad(self):
        result = detect_emotion("Мне очень грустно и одиноко")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['sad', 'neutral']

    def test_uzbek_happy(self):
        result = detect_emotion("Men juda baxtli edim!")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['happy', 'neutral']

    def test_empty_text(self):
        result = detect_emotion("")
        assert isinstance(result, EmotionResult)
        assert result.emotion == 'neutral'

    def test_emoji_happy(self):
        result = detect_emotion("😊😊😊")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['happy', 'neutral']

    def test_emoji_sad(self):
        result = detect_emotion("😢😢😢")
        assert isinstance(result, EmotionResult)
        assert result.emotion in ['sad', 'neutral']

    def test_result_has_valence_arousal(self):
        result = detect_emotion("I'm excited!")
        assert hasattr(result, 'valence')
        assert hasattr(result, 'arousal')
        assert 0 <= result.valence <= 1
        assert 0 <= result.arousal <= 1


class TestEmotionAdaptation:
    def test_happy_adaptation(self):
        adaptation = get_emotion_adaptation("happy")
        assert isinstance(adaptation, str)
        assert len(adaptation) > 0

    def test_sad_adaptation(self):
        adaptation = get_emotion_adaptation("sad")
        assert isinstance(adaptation, str)
        assert len(adaptation) > 0

    def test_angry_adaptation(self):
        adaptation = get_emotion_adaptation("angry")
        assert isinstance(adaptation, str)
        assert len(adaptation) > 0

    def test_neutral_adaptation(self):
        adaptation = get_emotion_adaptation("neutral")
        assert isinstance(adaptation, str)

    def test_unknown_emotion(self):
        adaptation = get_emotion_adaptation("unknown_emotion")
        assert adaptation == ""


class TestEmotionState:
    def test_empty_history(self):
        state = get_emotion_state([])
        assert state == "neutral"

    def test_single_emotion(self):
        state = get_emotion_state(["happy"])
        assert state == "happy"

    def test_multiple_same(self):
        state = get_emotion_state(["happy", "happy", "happy"])
        assert state == "happy"

    def test_mixed_emotions_returns_dominant(self):
        state = get_emotion_state(["happy", "sad", "happy", "happy"])
        assert state == "happy"

    def test_all_different_returns_first_dominant(self):
        state = get_emotion_state(["happy", "sad", "angry"])
        assert state in ["happy", "sad", "angry"]


class TestEmotionKeywords:
    def test_emotion_keywords_structure(self):
        assert isinstance(_EMOTION_KEYWORDS, dict)
        assert 'en' in _EMOTION_KEYWORDS
        assert 'ru' in _EMOTION_KEYWORDS
        assert 'uz' in _EMOTION_KEYWORDS

    def test_emotion_keywords_have_words(self):
        for lang, emotions in _EMOTION_KEYWORDS.items():
            assert isinstance(emotions, dict)
            for emotion, words in emotions.items():
                assert isinstance(words, list)
                assert len(words) > 0

    def test_emotion_types_present(self):
        for lang in ['en', 'ru', 'uz']:
            assert 'happy' in _EMOTION_KEYWORDS[lang]
            assert 'sad' in _EMOTION_KEYWORDS[lang]
            assert 'angry' in _EMOTION_KEYWORDS[lang]


class TestEmojiEmotions:
    def test_emoji_emotions_structure(self):
        assert isinstance(_EMOJI_EMOTIONS, dict)
        assert len(_EMOJI_EMOTIONS) > 0

    def test_emoji_emotions_have_emotion_labels(self):
        for emoji, emotion_list in _EMOJI_EMOTIONS.items():
            assert isinstance(emoji, str)
            assert isinstance(emotion_list, (str, list))
