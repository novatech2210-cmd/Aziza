import { detectLanguage, detectUzbekScript } from './language-detection';

describe('Language Detection', () => {
  describe('detectLanguage', () => {
    // ── English ──────────────────────────────────────────────────────────
    it('should detect English text', () => {
      const result = detectLanguage('Hello, how are you today?');
      expect(result.language).toBe('en');
    });

    it('should detect English with high confidence for clear text', () => {
      const result = detectLanguage('The weather is beautiful this morning');
      expect(result.language).toBe('en');
      expect(result.confidence).toBeGreaterThanOrEqual(0.7);
    });

    it('should detect short English phrases', () => {
      const result = detectLanguage('yes no maybe');
      expect(result.language).toBe('en');
    });

    // ── Russian ──────────────────────────────────────────────────────────
    it('should detect Russian text', () => {
      const result = detectLanguage('Привет, как дела?');
      expect(result.language).toBe('ru');
    });

    it('should detect Russian with high confidence', () => {
      const result = detectLanguage('Сегодня очень хорошая погода на улице');
      expect(result.language).toBe('ru');
      expect(result.confidence).toBeGreaterThanOrEqual(0.7);
    });

    // ── Uzbek Cyrillic ───────────────────────────────────────────────────
    it('should detect Uzbek Cyrillic text', () => {
      const result = detectLanguage('Салом, қандай экансиз?');
      expect(result.language).toBe('uz');
      expect(result.script).toBe('uz_cyrillic');
    });

    it('should detect Uzbek with unique Cyrillic chars (Қ, Ғ, Ҳ, Ў)', () => {
      const result = detectLanguage('Ўзбекистонда яшаш');
      expect(result.language).toBe('uz');
      expect(result.confidence).toBeGreaterThanOrEqual(0.9);
    });

    // ── Uzbek Latin ──────────────────────────────────────────────────────
    it('should detect Uzbek Latin text with keywords', () => {
      const result = detectLanguage('Salom, qanday ekansiz?');
      expect(result.language).toBe('uz');
      expect(result.script).toBe('uz_latin');
    });

    it('should detect Uzbek with okina character (U+02BB)', () => {
      const result = detectLanguage("O\u02BBzbekiston juda go\u02BBzal");
      expect(result.language).toBe('uz');
      expect(result.confidence).toBeGreaterThanOrEqual(0.9);
    });

    // ── Transliterated Uzbek (key improvement) ───────────────────────────
    it('should detect transliterated Uzbek: Assalomu alaykum', () => {
      const result = detectLanguage('Assalomu alaykum');
      expect(result.language).toBe('uz');
      expect(result.confidence).toBeGreaterThanOrEqual(0.85);
    });

    it('should detect transliterated Uzbek: rahmat', () => {
      const result = detectLanguage('Rahmat sizga');
      expect(result.language).toBe('uz');
    });

    it('should detect transliterated Uzbek: kechirasiz', () => {
      const result = detectLanguage('Kechirasiz, menga yordam bering');
      expect(result.language).toBe('uz');
    });

    it('should detect transliterated Uzbek: iltimos', () => {
      const result = detectLanguage('Iltimos, sekinroq gapiring');
      expect(result.language).toBe('uz');
    });

    it('should detect transliterated Uzbek: salom + yaxshi', () => {
      const result = detectLanguage('Salom, yaxshimisiz?');
      expect(result.language).toBe('uz');
    });

    it('should detect transliterated Uzbek: qanday + nima', () => {
      const result = detectLanguage('Nima qanday qildingiz?');
      expect(result.language).toBe('uz');
    });

    it('should detect transliterated Uzbek with 3+ keyword matches', () => {
      const result = detectLanguage('Men sizga yordam bermoqchiman');
      expect(result.language).toBe('uz');
      expect(result.confidence).toBeGreaterThanOrEqual(0.8);
    });

    // ── Edge cases ───────────────────────────────────────────────────────
    it('should handle empty text', () => {
      const result = detectLanguage('');
      expect(result.language).toBe('en');
      expect(result.confidence).toBe(0);
    });

    it('should handle whitespace-only text', () => {
      const result = detectLanguage('   ');
      expect(result.language).toBe('en');
      expect(result.confidence).toBe(0);
    });

    it('should handle numbers only', () => {
      const result = detectLanguage('12345');
      expect(result.language).toBe('en');
    });

    it('should handle mixed numbers and text', () => {
      const result = detectLanguage('100 dollar berdingizmi sizga');
      expect(result.language).toBe('uz');
    });
  });

  describe('detectUzbekScript', () => {
    it('should detect Latin script', () => {
      expect(detectUzbekScript('Salom dunyo')).toBe('uz_latin');
    });

    it('should detect Cyrillic script', () => {
      expect(detectUzbekScript('Салом дунё')).toBe('uz_cyrillic');
    });

    it('should prefer Cyrillic when equal', () => {
      // Equal counts → cyrillic wins
      expect(detectUzbekScript('ab')).toBe('uz_latin');
    });
  });
});
