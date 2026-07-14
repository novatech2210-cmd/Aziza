/**
 * Shared language detection module for AZIZA.
 *
 * Consolidates detection logic previously scattered across:
 * - chat.gateway.ts (franc-min + heuristic)
 * - persona-plex/main.py (script counting + keywords)
 * - admin-api/services/language.py (langdetect)
 *
 * Primary detection path:
 * 1. Uzbek-specific character signals (okina, Қ, Ғ, Ҳ, Ў, ҷ)
 * 2. Uzbek keyword matching (expanded sets with transliterated forms)
 * 3. franc-min trigram detection
 * 4. Script ratio fallback
 */

// ── Uzbek-specific Unicode characters ──────────────────────────────────────

const UZBEK_CYRILLIC_CHARS = new Set([
  0x049A, 0x049B, // Қ/қ
  0x0492, 0x0493, // Ғ/ғ
  0x04BA, 0x04BB, // Һ/һ
  0x040E, 0x045E, // Ў/ў
  0x04B6, 0x04B7, // Ҷ/ҷ
]);

const OKINA = 0x02BB; // ʻ (modifier letter turned comma, Uzbek Latin orthography)

// ── Uzbek keyword sets ─────────────────────────────────────────────────────
// Common words that distinguish Uzbek from English/Russian.
// Latin set includes transliterated forms users commonly type.

const UZBEK_LATIN_KEYWORDS = new Set([
  // Pronouns & determiners
  'men', 'sen', 'siz', 'biz', 'ular', 'uning', 'mening', 'sening', 'sizning',
  'bizning', 'ularning', 'shu', 'bu', 'o\'sha',
  // Conjunctions & particles
  'va', 'lekin', 'yoki', 'ham', 'garchi', 'shuningdek',
  'balki', 'yoqsa', 'agarda', 'agar',
  // Postpositions & cases
  'da', 'dan', 'ga', 'ni', 'uchtun', 'ustida', 'ostida', 'oldida',
  'keyinida', 'yonida', 'orasida',
  // Case forms
  'menga', 'senga', 'unga', 'bizga', 'ulgarga',
  'meni', 'seni', 'sizni', 'uni', 'bizni', 'ularni',
  'sizga', 'sizinga',
  // Question words
  'qanday', 'nima', 'qachon', 'qaerda', 'nega', 'qanaqa', 'necha', 'qaysi',
  'nimani', 'nima uchun', 'qayerdan',
  // Common verbs
  'yaxshi', 'yomon', 'bor', 'yo\'q', 'qilish', 'bo\'lish', 'lish',
  'kerak', 'mumkin', 'tushundi', 'tushunaman',
  'bermoq', 'berdingiz', 'berding', 'beradi', 'berdingizmi',
  'qildingiz', 'qildim', 'qilyapman', 'qilaman',
  'keldingiz', 'keldim', 'ketdingiz',
  'gapirish', 'gapiraman', 'gapiring',
  'yozish', 'yozaman', 'o\'qish', 'o\'qiyman',
  'tushunish', 'tushunaman', 'bilish', 'bilaman',
  'sevish', 'sevaman', 'ishlash', 'ishlayman',
  'yashash', 'yashayman', 'ketish', 'ketaman',
  'kelish', 'kelaman', 'berish', 'beraman',
  // Greetings & politeness
  'salom', 'assalomu alaykum', 'rahmat', 'kechirasiz', 'iltimos',
  'xush', 'kelibsiz', 'hayr', 'alom',
  // Numbers
  'bir', 'ikki', 'uch', 'to\'rt', 'besh', 'olti', 'yetti', 'sakkiz', 'to\'qqiz', 'o\'n',
  // Common nouns
  'odam', 'joy', 'vaqt', 'kun', 'oy', 'yil', 'soat', 'daqiqa',
  'mamlakat', 'shahar', 'qishloq', 'uy', 'maktab', 'ish',
  // Adjectives
  'katta', 'kichik', 'yangi', 'eski', 'chiroyli', 'tez', 'sekin',
  // Food & daily life
  'ovqat', 'non', 'choy', 'suv', 'go\'sht', 'meva',
  // Affixes that are strong Uzbek signals
  'lish', 'mish', 'dir', 'kan', 'mikan', 'echan', 'uvchi',
  // Transliterated forms users often type
  'qalesiz', 'qalaysiz', 'yaxshimisiz', 'ey',
  // Common transliterated greetings
  'hello', 'hi', 'hey',
  // Uzbek-specific Latin letters as strong signal
  'o\'g', 'o\'z', 'o\'zbekiston',
  // Common word forms
  'berdingizmi', 'qildingizmi', 'kelasizmi', 'ketasizmi',
  'yordingizmi', 'tushundingizmi', 'bilasizmi',
  'gapirasizmi', 'yozasizmi', 'o\'qiyapsizmi',
  'yaxshimisiz', 'yomonmisiz',
]);

const UZBEK_CYRILLIC_KEYWORDS = new Set([
  // Pronouns
  'сиз', 'биз', 'мен', 'сен', 'уния', 'улар', 'менинг', 'сенинг',
  'сизнинг', 'бизнинг', 'уларнинг', 'шу', 'бу', 'ўша',
  // Conjunctions
  'ва', 'лекин', 'ёки', 'ҳам', 'гарчи', 'шунингдек',
  'бalki', 'ёкса', 'агарда', 'агар',
  // Postpositions
  'да', 'дан', 'га', 'ни', 'устида', 'остида', 'олдида',
  'кейинида', 'ёнида', 'орасида',
  // Question words
  'қандай', 'нима', 'қачон', 'қаерда', 'нега', 'қанақа', 'неча', 'қайси',
  'нимани', 'нима учун', 'қаердан',
  // Common verbs & adjectives
  'яхши', 'ёмон', 'бор', 'йўқ', 'қилиш', 'бўлиш',
  'керак', 'мумкин', 'тушунди', 'тушунаман',
  // Greetings
  'салом', 'ассалому алайкум', 'раҳмат', 'кечирингиз', 'илтимос',
  'хуш', 'келибсиз', 'ҳайр',
  // Numbers
  'бир', 'икки', 'уч', 'тўрт', 'беш', 'олти', 'etti', 'саккиз', 'тўққиз', 'ўн',
  // Common nouns
  'одам', 'жой', 'вақт', 'кун', 'ой', 'йил', 'соат', 'дақиқа',
  'мамлакат', 'шаҳар', 'қишлоқ', 'уй', 'мактаб', 'иш',
  // Adjectives
  'кatta', 'кичик', 'янги', 'эски', 'чиройли', 'тез', 'скин',
  // Affixes
  'лиш', 'миш', 'дир', 'кан', 'микан', 'ечан', 'увчи',
]);

// Transliterated Uzbek words that users commonly type in Latin script
// but that overlap with English character patterns
const TRANSLITERATED_UZ_INDICATORS = new Set([
  'assalomu', 'alaykum', 'rahmat', 'kechirasiz', 'iltimos',
  'yaxshimisiz', 'qalaysiz', 'qalesiz', 'nima gap',
  'yaxshi', 'yomon', 'katta', 'kichik', 'yangi', 'eski',
  'qanday', 'qachon', 'qaerda', 'nega', 'qanaqa',
  'salom', 'hayr', 'xush', 'kelibsiz',
  // Common Uzbek phrases users type
  'menga', 'senga', 'unga', 'bizga', 'ulgarga',
  'meni', 'seni', 'sizni', 'uni', 'bizni', 'ularni',
  'shuning', 'uning', 'bizning', 'ularning',
]);

// ── Script analysis ────────────────────────────────────────────────────────

interface ScriptCounts {
  cyrillic: number;
  latin: number;
  other: number;
  hasOkina: boolean;
  hasUzbekCyrillic: boolean;
}

function analyzeScript(text: string): ScriptCounts {
  const counts: ScriptCounts = {
    cyrillic: 0,
    latin: 0,
    other: 0,
    hasOkina: false,
    hasUzbekCyrillic: false,
  };

  for (const ch of text) {
    const cp = ch.charCodeAt(0);
    if (cp === OKINA) {
      counts.hasOkina = true;
      counts.latin++;
    } else if ((cp >= 0x0400 && cp <= 0x04FF) || (cp >= 0x0500 && cp <= 0x052F)) {
      counts.cyrillic++;
      if (UZBEK_CYRILLIC_CHARS.has(cp)) {
        counts.hasUzbekCyrillic = true;
      }
    } else if (cp >= 0x0041 && cp <= 0x007A) {
      counts.latin++;
    } else if (cp >= 0x00C0 && cp <= 0x024F) {
      // Extended Latin (accented chars: é, ö, ü, etc.)
      counts.latin++;
    }
  }

  return counts;
}

// ── Keyword matching ───────────────────────────────────────────────────────

function extractWords(text: string): Set<string> {
  return new Set(
    text
      .toLowerCase()
      .replace(/['']/g, "'")
      .split(/[\s,.\-!?;:()]+/)
      .filter(w => w.length > 1),
  );
}

function countUzbekMatches(words: Set<string>): { latin: number; cyrillic: number; transliterated: number } {
  let latin = 0;
  let cyrillic = 0;
  let transliterated = 0;

  for (const word of words) {
    if (UZBEK_LATIN_KEYWORDS.has(word)) latin++;
    if (UZBEK_CYRILLIC_KEYWORDS.has(word)) cyrillic++;
    if (TRANSLITERATED_UZ_INDICATORS.has(word)) transliterated++;
  }

  return { latin, cyrillic, transliterated };
}

// ── Detection result ───────────────────────────────────────────────────────

export interface LanguageDetectionResult {
  language: string;
  script?: string;
  confidence: number;
}

// ── Main detection function ────────────────────────────────────────────────

export function detectLanguage(text: string): LanguageDetectionResult {
  const trimmed = text.trim();
  if (!trimmed) {
    return { language: 'en', confidence: 0 };
  }

  const script = analyzeScript(trimmed);
  const totalAlpha = script.cyrillic + script.latin + script.other;

  if (totalAlpha === 0) {
    return { language: 'en', confidence: 0 };
  }

  // 1. Definitive Uzbek signals: okina or Uzbek-specific Cyrillic chars
  if (script.hasOkina || script.hasUzbekCyrillic) {
    const isCyrillic = script.cyrillic > script.latin;
    return {
      language: 'uz',
      script: isCyrillic ? 'uz_cyrillic' : 'uz_latin',
      confidence: 0.95,
    };
  }

  // 2. Keyword-based detection (expanded with transliterated forms)
  const words = extractWords(trimmed);
  const matches = countUzbekMatches(words);

  // Strong Uzbek signal: 3+ keyword matches across any script
  if (matches.latin + matches.cyrillic + matches.transliterated >= 3) {
    const isCyrillic = script.cyrillic > script.latin;
    return {
      language: 'uz',
      script: isCyrillic ? 'uz_cyrillic' : 'uz_latin',
      confidence: 0.9,
    };
  }

  // Medium Uzbek signal: 2+ matches
  if (matches.latin + matches.cyrillic + matches.transliterated >= 2) {
    const isCyrillic = script.cyrillic > script.latin;
    return {
      language: 'uz',
      script: isCyrillic ? 'uz_cyrillic' : 'uz_latin',
      confidence: 0.85,
    };
  }

  // Single transliterated match + Latin script → still suspect Uzbek
  if (matches.transliterated >= 1 && script.latin > script.cyrillic * 3) {
    return {
      language: 'uz',
      script: 'uz_latin',
      confidence: 0.7,
    };
  }

  // 3. Try franc-min if available
  try {
    const franc = require('franc-min').franc;
    const code = franc(trimmed, { minLength: 3 });
    const map: Record<string, string> = {
      rus: 'ru', uzb: 'uz', eng: 'en',
    };
    const detected = map[code];
    if (detected === 'uz') {
      const isCyrillic = script.cyrillic > script.latin;
      return {
        language: 'uz',
        script: isCyrillic ? 'uz_cyrillic' : 'uz_latin',
        confidence: 0.85,
      };
    }
    if (detected) {
      return { language: detected, confidence: 0.8 };
    }
  } catch {
    // franc-min not available
  }

  // 4. Script ratio fallback
  const cyrillicRatio = script.cyrillic / totalAlpha;
  const latinRatio = script.latin / totalAlpha;

  if (cyrillicRatio > 0.7) {
    return { language: 'ru', confidence: Math.max(0.7, cyrillicRatio) };
  }
  if (latinRatio > 0.7) {
    return { language: 'en', confidence: Math.max(0.7, latinRatio) };
  }

  // Mixed script → default to dominant
  if (cyrillicRatio > latinRatio) {
    return { language: 'ru', confidence: Math.max(0.6, cyrillicRatio) };
  }

  return { language: 'en', confidence: Math.max(0.6, latinRatio) };
}

/**
 * Detect Uzbek script variant from text.
 */
export function detectUzbekScript(text: string): string {
  let cyrillic = 0;
  let latin = 0;
  for (const ch of text) {
    const cp = ch.charCodeAt(0);
    if (cp === OKINA) { latin++; continue; }
    if ((cp >= 0x0400 && cp <= 0x04FF) || (cp >= 0x0500 && cp <= 0x052F)) {
      cyrillic++;
    } else if (cp >= 0x0041 && cp <= 0x007A) {
      latin++;
    }
  }
  return cyrillic > latin ? 'uz_cyrillic' : 'uz_latin';
}
