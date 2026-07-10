const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageNumber, PageBreak, Header, Footer, TabStopType,
  TabStopPosition, ExternalHyperlink
} = require('docx');
const fs = require('fs');

// ── Color palette ──────────────────────────────────────────────────────────────
const C = {
  black:       '1A1A2E',
  navy:        '16213E',
  blue:        '0F3460',
  accent:      '1D9E75',
  accentDark:  '085041',
  amber:       'BA7517',
  red:         'A32D2D',
  lightGray:   'F5F5F5',
  midGray:     'E0E0E0',
  darkGray:    '555555',
  white:       'FFFFFF',
  done:        'D4EDDA',
  doneBorder:  '28A745',
  pending:     'FFF3CD',
  pendingBorder:'856404',
  critical:    'F8D7DA',
  criticalBorder:'721C24',
};

// ── Border helpers ─────────────────────────────────────────────────────────────
const border = (color = C.midGray, size = 4) => ({ style: BorderStyle.SINGLE, size, color });
const allBorders = (color, size) => ({ top: border(color, size), bottom: border(color, size), left: border(color, size), right: border(color, size) });
const noBorder = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

// ── Text helpers ───────────────────────────────────────────────────────────────
const run = (text, opts = {}) => new TextRun({ text, font: 'Arial', size: opts.size || 22, bold: opts.bold || false, color: opts.color || C.black, italics: opts.italic || false, ...opts });
const mono = (text, opts = {}) => new TextRun({ text, font: 'Courier New', size: opts.size || 18, color: opts.color || '1D5C3A', bold: opts.bold || false });

const para = (children, opts = {}) => new Paragraph({
  children: Array.isArray(children) ? children : [children],
  spacing: { before: opts.before || 0, after: opts.after || 120 },
  alignment: opts.align || AlignmentType.LEFT,
  indent: opts.indent ? { left: opts.indent } : undefined,
  ...opts,
});

const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  children: [new TextRun({ text, font: 'Arial', size: 36, bold: true, color: C.white })],
  shading: { fill: C.navy, type: ShadingType.CLEAR },
  spacing: { before: 400, after: 200 },
  indent: { left: 200, right: 200 },
});

const h2 = (text, color = C.navy) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  children: [new TextRun({ text, font: 'Arial', size: 28, bold: true, color })],
  border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: C.accent } },
  spacing: { before: 360, after: 160 },
});

const h3 = (text, color = C.blue) => new Paragraph({
  heading: HeadingLevel.HEADING_3,
  children: [new TextRun({ text, font: 'Arial', size: 24, bold: true, color })],
  spacing: { before: 240, after: 120 },
});

const h4 = (text, color = C.darkGray) => new Paragraph({
  children: [new TextRun({ text, font: 'Arial', size: 22, bold: true, color })],
  spacing: { before: 160, after: 80 },
});

const body = (text, opts = {}) => para([run(text, { color: C.darkGray, ...opts })], { after: 100, ...opts });

const bullet = (text, level = 0) => new Paragraph({
  numbering: { reference: 'bullets', level },
  children: [run(text, { size: 20, color: C.darkGray })],
  spacing: { before: 40, after: 40 },
});

const numbered = (text, level = 0) => new Paragraph({
  numbering: { reference: 'numbers', level },
  children: [run(text, { size: 20, color: C.darkGray })],
  spacing: { before: 60, after: 60 },
});

const codeBlock = (lines) => {
  const codeLines = Array.isArray(lines) ? lines : [lines];
  return codeLines.map(line => new Paragraph({
    children: [mono(line)],
    shading: { fill: 'F0F4F0', type: ShadingType.CLEAR },
    spacing: { before: 0, after: 0 },
    indent: { left: 360 },
    border: { left: { style: BorderStyle.SINGLE, size: 16, color: C.accent } },
  }));
};

const spacer = (n = 1) => Array(n).fill(null).map(() => new Paragraph({ children: [new TextRun('')], spacing: { before: 0, after: 80 } }));

// ── Status badge cell ──────────────────────────────────────────────────────────
const statusCell = (text, fill, textColor, width = 1800) => new TableCell({
  borders: noBorders,
  shading: { fill, type: ShadingType.CLEAR },
  width: { size: width, type: WidthType.DXA },
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [run(text, { size: 16, bold: true, color: textColor })],
  })],
});

// ── Standard table row ─────────────────────────────────────────────────────────
const tableRow = (cells, isHeader = false) => new TableRow({
  children: cells.map(({ text, width, fill, textColor, align, size, bold }) =>
    new TableCell({
      borders: allBorders(C.midGray, 4),
      shading: { fill: fill || (isHeader ? C.navy : C.white), type: ShadingType.CLEAR },
      width: { size: width || 2340, type: WidthType.DXA },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({
        alignment: align || AlignmentType.LEFT,
        children: [run(text, { size: size || 20, bold: bold || isHeader, color: textColor || (isHeader ? C.white : C.darkGray) })],
      })],
    })
  ),
});

// ── Alert box ─────────────────────────────────────────────────────────────────
const alertBox = (label, text, fill, borderColor) => new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [9360],
  rows: [new TableRow({
    children: [new TableCell({
      borders: { top: border(borderColor, 8), bottom: border(borderColor, 4), left: border(borderColor, 24), right: border(borderColor, 4) },
      shading: { fill, type: ShadingType.CLEAR },
      width: { size: 9360, type: WidthType.DXA },
      margins: { top: 100, bottom: 100, left: 160, right: 160 },
      children: [new Paragraph({
        children: [
          run(`${label}  `, { size: 20, bold: true, color: borderColor }),
          run(text, { size: 20, color: C.black }),
        ],
        spacing: { before: 0, after: 0 },
      })],
    })],
  })],
});

// ── Phase header banner ────────────────────────────────────────────────────────
const phaseBanner = (phase, title, status, fill) => new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [7000, 2360],
  rows: [new TableRow({
    children: [
      new TableCell({
        borders: noBorders,
        shading: { fill, type: ShadingType.CLEAR },
        width: { size: 7000, type: WidthType.DXA },
        margins: { top: 120, bottom: 120, left: 200, right: 200 },
        children: [new Paragraph({
          children: [
            run(phase + '  ', { size: 22, bold: true, color: C.white }),
            run(title, { size: 26, bold: true, color: C.white }),
          ],
        })],
      }),
      new TableCell({
        borders: noBorders,
        shading: { fill: C.accentDark, type: ShadingType.CLEAR },
        width: { size: 2360, type: WidthType.DXA },
        margins: { top: 120, bottom: 120, left: 100, right: 100 },
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [run(status, { size: 20, bold: true, color: C.white })],
        })],
      }),
    ],
  })],
});

// ── Task card ─────────────────────────────────────────────────────────────────
const taskCard = (id, title, status, statusFill, statusText, owner, deps, description, steps, acceptance) => {
  const rows = [];

  // Header row
  rows.push(new TableRow({
    children: [
      new TableCell({
        borders: { top: border(C.accent, 12), bottom: border(C.midGray, 4), left: border(C.accent, 12), right: border(C.midGray, 4) },
        shading: { fill: 'F8FFFE', type: ShadingType.CLEAR },
        width: { size: 6000, type: WidthType.DXA },
        margins: { top: 100, bottom: 80, left: 160, right: 160 },
        children: [new Paragraph({
          children: [
            run(id + '  ', { size: 18, bold: true, color: C.accent }),
            run(title, { size: 22, bold: true, color: C.navy }),
          ],
        })],
      }),
      new TableCell({
        borders: { top: border(C.accent, 12), bottom: border(C.midGray, 4), left: border(C.midGray, 4), right: border(C.accent, 12) },
        shading: { fill: statusFill, type: ShadingType.CLEAR },
        width: { size: 3360, type: WidthType.DXA },
        margins: { top: 100, bottom: 80, left: 100, right: 160 },
        children: [
          new Paragraph({ alignment: AlignmentType.CENTER, children: [run(status, { size: 18, bold: true, color: statusText })] }),
          new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Owner: ' + owner, { size: 16, color: C.darkGray })] }),
        ],
      }),
    ],
  }));

  // Deps row if present
  if (deps && deps.length > 0) {
    rows.push(new TableRow({
      children: [new TableCell({
        columnSpan: 2,
        borders: { top: border(C.midGray, 4), bottom: border(C.midGray, 4), left: border(C.accent, 12), right: border(C.accent, 12) },
        shading: { fill: C.lightGray, type: ShadingType.CLEAR },
        width: { size: 9360, type: WidthType.DXA },
        margins: { top: 60, bottom: 60, left: 160, right: 160 },
        children: [new Paragraph({
          children: [
            run('Depends on: ', { size: 18, bold: true, color: C.darkGray }),
            run(deps.join(' → '), { size: 18, color: C.blue }),
          ],
        })],
      })],
    }));
  }

  // Description
  rows.push(new TableRow({
    children: [new TableCell({
      columnSpan: 2,
      borders: { top: border(C.midGray, 4), bottom: border(C.midGray, 4), left: border(C.accent, 12), right: border(C.accent, 12) },
      shading: { fill: C.white, type: ShadingType.CLEAR },
      width: { size: 9360, type: WidthType.DXA },
      margins: { top: 80, bottom: 80, left: 160, right: 160 },
      children: [
        new Paragraph({ children: [run('Objective: ', { size: 20, bold: true, color: C.navy }), run(description, { size: 20, color: C.darkGray })], spacing: { before: 0, after: 60 } }),
        ...steps.map(s => new Paragraph({
          children: [run('• ', { size: 20, bold: true, color: C.accent }), run(s, { size: 19, color: C.darkGray })],
          spacing: { before: 30, after: 30 },
          indent: { left: 200 },
        })),
      ],
    })],
  }));

  // Acceptance criteria
  rows.push(new TableRow({
    children: [new TableCell({
      columnSpan: 2,
      borders: { top: border(C.midGray, 4), bottom: border(C.accent, 12), left: border(C.accent, 12), right: border(C.accent, 12) },
      shading: { fill: 'F0FFF8', type: ShadingType.CLEAR },
      width: { size: 9360, type: WidthType.DXA },
      margins: { top: 80, bottom: 100, left: 160, right: 160 },
      children: [
        new Paragraph({ children: [run('ACCEPTANCE CRITERIA', { size: 18, bold: true, color: C.accentDark })], spacing: { before: 0, after: 60 } }),
        ...acceptance.map(a => new Paragraph({
          children: [run('✓  ', { size: 18, bold: true, color: C.accentDark }), run(a, { size: 18, color: C.darkGray })],
          spacing: { before: 20, after: 20 },
          indent: { left: 160 },
        })),
      ],
    })],
  }));

  return new Table({ width: { size: 9360, type: WidthType.DXA }, columnWidths: [6000, 3360], rows });
};

// ══════════════════════════════════════════════════════════════════════════════
// DOCUMENT ASSEMBLY
// ══════════════════════════════════════════════════════════════════════════════

const children = [

  // ── COVER ──────────────────────────────────────────────────────────────────
  new Paragraph({
    children: [run('AZIZA AI PLATFORM', { size: 72, bold: true, color: C.white })],
    shading: { fill: C.navy, type: ShadingType.CLEAR },
    alignment: AlignmentType.CENTER,
    spacing: { before: 800, after: 200 },
  }),
  new Paragraph({
    children: [run('MASTER PRODUCTION BUILD PROMPT', { size: 36, bold: true, color: C.accent })],
    shading: { fill: C.navy, type: ShadingType.CLEAR },
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 },
  }),
  new Paragraph({
    children: [run('Novatech  ·  Client: Ivan  ·  Confidential', { size: 24, color: '8899AA' })],
    shading: { fill: C.navy, type: ShadingType.CLEAR },
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 600 },
  }),

  // Cover summary table
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3120, 3120, 3120],
    rows: [
      new TableRow({
        children: [
          new TableCell({ borders: allBorders(C.accent, 8), shading: { fill: C.accentDark, type: ShadingType.CLEAR }, width: { size: 3120, type: WidthType.DXA }, margins: { top: 120, bottom: 120, left: 160, right: 160 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('TARGET LANGUAGES', { size: 18, bold: true, color: C.white })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Russian (RU) + Uzbek (UZ)', { size: 20, bold: true, color: C.accent })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Latin & Cyrillic scripts', { size: 16, color: 'AADDCC' })] }),
            ],
          }),
          new TableCell({ borders: allBorders(C.accent, 8), shading: { fill: C.accentDark, type: ShadingType.CLEAR }, width: { size: 3120, type: WidthType.DXA }, margins: { top: 120, bottom: 120, left: 160, right: 160 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('INTERACTION MODES', { size: 18, bold: true, color: C.white })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Text → Text', { size: 18, bold: true, color: C.accent })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Voice → Text', { size: 18, bold: true, color: C.accent })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Voice ↔ Voice (Full Duplex)', { size: 18, bold: true, color: C.accent })] }),
            ],
          }),
          new TableCell({ borders: allBorders(C.accent, 8), shading: { fill: C.accentDark, type: ShadingType.CLEAR }, width: { size: 3120, type: WidthType.DXA }, margins: { top: 120, bottom: 120, left: 160, right: 160 },
            children: [
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('INFRASTRUCTURE', { size: 18, bold: true, color: C.white })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Vast.ai H100 SXM 80GB', { size: 18, bold: true, color: C.accent })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('PM2 + systemd (no Docker)', { size: 16, color: 'AADDCC' })] }),
              new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Asterisk ARI + Moshi', { size: 16, color: 'AADDCC' })] }),
            ],
          }),
        ],
      }),
    ],
  }),

  ...spacer(2),

  // ── SECTION 1: STACK OVERVIEW ──────────────────────────────────────────────
  h1('1. COMPLETE STACK OVERVIEW'),

  h2('1.1 Architecture Decision Record'),
  alertBox('LOCKED:', 'All architecture decisions below are final and approved. Do not introduce Docker, do not change inference engine, do not change model family without team sign-off.', 'FFF8E1', C.amber),
  ...spacer(1),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2200, 3080, 4080],
    rows: [
      tableRow([
        { text: 'Layer', width: 2200 },
        { text: 'Technology', width: 3080 },
        { text: 'Decision Rationale', width: 4080 },
      ], true),
      tableRow([{ text: 'Base Model', width: 2200 }, { text: 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24', width: 3080 }, { text: 'Strong multilingual Cyrillic + Latin coverage. 8B fits H100 with NF4 quant leaving room for LoRA.', width: 4080 }]),
      tableRow([{ text: 'Fine-Tuning', width: 2200 }, { text: 'QLoRA r=16 alpha=32 NF4', width: 3080 }, { text: 'LOCKED CONFIG — do not change. Proven on Russian. Uzbek uses identical pipeline.', width: 4080 }]),
      tableRow([{ text: 'Voice Inference', width: 2200 }, { text: 'Moshi (full-duplex)', width: 3080 }, { text: 'Only production-ready full-duplex voice model. No VAD latency. Native streaming.', width: 4080 }]),
      tableRow([{ text: 'Text Inference', width: 2200 }, { text: 'vLLM (text-only path)', width: 3080 }, { text: 'Used for text→text mode only. Moshi handles voice paths.', width: 4080 }]),
      tableRow([{ text: 'API Gateway', width: 2200 }, { text: 'NestJS (port 3000)', width: 3080 }, { text: 'WebSocket session management, auth, Redis pub/sub, language routing.', width: 4080 }]),
      tableRow([{ text: 'Middleware', width: 2200 }, { text: 'FastAPI (port 8020)', width: 3080 }, { text: 'Inference bridge: text-in/text-out and PCM audio frames to Moshi.', width: 4080 }]),
      tableRow([{ text: 'Persona Engine', width: 2200 }, { text: 'PersonaPlex (microservice)', width: 3080 }, { text: 'Dynamic system prompt injection. Personality NOT baked into weights.', width: 4080 }]),
      tableRow([{ text: 'Telephony', width: 2200 }, { text: 'Asterisk ARI + FFmpeg', width: 3080 }, { text: 'SIP trunk → RTP → PCM → WebSocket → Moshi. FFmpeg for codec transcoding.', width: 4080 }]),
      tableRow([{ text: 'Session Store', width: 2200 }, { text: 'Redis (pub/sub + state)', width: 3080 }, { text: 'Worker registration, session state, max_sessions=1 per GPU worker enforced.', width: 4080 }]),
      tableRow([{ text: 'Process Mgmt', width: 2200 }, { text: 'PM2 + systemd', width: 3080 }, { text: 'No Docker. All processes native on H100 instance. PM2 ecosystem.config.js.', width: 4080 }]),
      tableRow([{ text: 'Frontend', width: 2200 }, { text: 'Vue 3 + Pinia', width: 3080 }, { text: 'Text chat UI + voice UI. Cloudflare tunnel on port 8010 for Ivan demo access.', width: 4080 }]),
      tableRow([{ text: 'Telephony DB', width: 2200 }, { text: 'PostgreSQL', width: 3080 }, { text: 'User auth, session history, usage tracking, tier management.', width: 4080 }]),
    ],
  }),

  ...spacer(1),

  h2('1.2 Three Interaction Modes — How They Work'),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2000, 7360],
    rows: [
      tableRow([{ text: 'Mode', width: 2000 }, { text: 'Data Flow', width: 7360 }], true),
      tableRow([{ text: 'Text → Text', width: 2000 }, { text: 'Browser POST /chat → NestJS Gateway → FastAPI (serve_test.py) → Vikhr-Llama-3.1+QLoRA adapter → JSON response → Browser', width: 7360 }]),
      tableRow([{ text: 'Voice → Text', width: 2000 }, { text: 'Browser mic (WebAudio API) → 16kHz PCM → WebSocket → Moshi ASR → text transcript → NestJS → LLM → text response → Browser', width: 7360 }]),
      tableRow([{ text: 'Voice ↔ Voice', width: 2000 }, { text: 'Browser mic → PCM frames → WebSocket → Moshi full-duplex inference → PCM audio frames → Browser speaker (AudioWorklet) — simultaneously bidirectional. Phone: SIP → Asterisk → ARI → FFmpeg → PCM → same Moshi path.', width: 7360 }]),
    ],
  }),

  ...spacer(1),

  h2('1.3 Language Routing'),
  body('Every session carries a language tag: ru | uz-latin | uz-cyrillic. The NestJS Gateway uses this tag to: (1) select the correct QLoRA adapter, (2) inject the correct PersonaPlex system prompt, (3) apply the language drift guard (retry if >10% ASCII in response). The Moshi worker loads the adapter at session init. Language switching mid-session is not supported — a new session must be created.'),

  ...spacer(2),

  // ── SECTION 2: CURRENT STATUS ──────────────────────────────────────────────
  h1('2. CURRENT STATUS — WHAT IS DONE VS PENDING'),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3800, 1600, 1600, 2360],
    rows: [
      tableRow([
        { text: 'Component', width: 3800 },
        { text: 'Russian', width: 1600 },
        { text: 'Uzbek', width: 1600 },
        { text: 'Notes', width: 2360 },
      ], true),
      tableRow([{ text: 'Tokenizer audit script', width: 3800 }, { text: '✅ N/A', width: 1600, textColor: '28A745' }, { text: '⚡ NEXT', width: 1600, textColor: C.amber, bold: true }, { text: 'audit_tokenizer.py ready to run', width: 2360 }]),
      tableRow([{ text: 'Dataset (JSONL, ChatML format)', width: 3800 }, { text: '✅ Done', width: 1600, textColor: '28A745' }, { text: '❌ Pending', width: 1600, textColor: C.red }, { text: 'HuggingFace sources identified', width: 2360 }]),
      tableRow([{ text: 'train_*.py script', width: 3800 }, { text: '✅ Done', width: 1600, textColor: '28A745' }, { text: '❌ Not written', width: 1600, textColor: C.red }, { text: 'Clone of train_russian.py', width: 2360 }]),
      tableRow([{ text: 'QLoRA training run (3-stage)', width: 3800 }, { text: '✅ Done', width: 1600, textColor: '28A745' }, { text: '❌ Not started', width: 1600, textColor: C.red }, { text: '~12-18hrs on H100', width: 2360 }]),
      tableRow([{ text: 'Adapter eval (>80% accuracy)', width: 3800 }, { text: '✅ Passed', width: 1600, textColor: '28A745' }, { text: '❌ Not run', width: 1600, textColor: C.red }, { text: 'eval_uzbek.py not written', width: 2360 }]),
      tableRow([{ text: 'Adapter archived (.tar.gz)', width: 3800 }, { text: '✅ Done', width: 1600, textColor: '28A745' }, { text: '❌ Not done', width: 1600, textColor: C.red }, { text: '', width: 2360 }]),
      tableRow([{ text: 'serve_*_test.py (port 8020)', width: 3800 }, { text: '✅ Running', width: 1600, textColor: '28A745' }, { text: '❌ Not built', width: 1600, textColor: C.red }, { text: 'Extend existing serve script', width: 2360 }]),
      tableRow([{ text: 'PersonaPlex system prompts', width: 3800 }, { text: '✅ Done', width: 1600, textColor: '28A745' }, { text: '❌ Not added', width: 1600, textColor: C.red }, { text: 'uz-latin + uz-cyrillic contexts', width: 2360 }]),
      tableRow([{ text: 'API Gateway language routing', width: 3800 }, { text: '✅ Done', width: 1600, textColor: '28A745' }, { text: '❌ Not added', width: 1600, textColor: C.red }, { text: 'Add uz-latin / uz-cyrillic modes', width: 2360 }]),
      tableRow([{ text: 'TTFT benchmark (<100ms p95)', width: 3800 }, { text: '✅ Passing', width: 1600, textColor: '28A745' }, { text: '❌ Not benchmarked', width: 1600, textColor: C.red }, { text: 'bench_ttft.py not written', width: 2360 }]),
      tableRow([{ text: 'Voice→Text (Moshi ASR path)', width: 3800 }, { text: '⚠️ Partial', width: 1600, textColor: C.amber }, { text: '⚠️ Partial', width: 1600, textColor: C.amber }, { text: 'Moshi worker runs, no ASR endpoint wired to frontend', width: 2360 }]),
      tableRow([{ text: 'Full-duplex Voice↔Voice (Moshi)', width: 3800 }, { text: '⚠️ Partial', width: 1600, textColor: C.amber }, { text: '⚠️ Partial', width: 1600, textColor: C.amber }, { text: 'Moshi tested standalone; not wired into NestJS', width: 2360 }]),
      tableRow([{ text: 'Vue 3 frontend (text chat)', width: 3800 }, { text: '✅ Built', width: 1600, textColor: '28A745' }, { text: '✅ Built', width: 1600, textColor: '28A745' }, { text: 'Based on aziza-web/frontend', width: 2360 }]),
      tableRow([{ text: 'Vue 3 frontend (voice UI)', width: 3800 }, { text: '❌ Not built', width: 1600, textColor: C.red }, { text: '❌ Not built', width: 1600, textColor: C.red }, { text: 'AudioWorklet + mic input needed', width: 2360 }]),
      tableRow([{ text: 'Orchestrator GPU pool routing', width: 3800 }, { text: '❌ Not done', width: 1600, textColor: C.red }, { text: '❌ Not done', width: 1600, textColor: C.red }, { text: 'TASK-3.1 in Phase 3', width: 2360 }]),
      tableRow([{ text: 'Asterisk ARI bridge', width: 3800 }, { text: '❌ Not built', width: 1600, textColor: C.red }, { text: '❌ Not built', width: 1600, textColor: C.red }, { text: 'TASK-3.2 — critical path', width: 2360 }]),
      tableRow([{ text: 'PM2 ecosystem.config.js', width: 3800 }, { text: '❌ Not written', width: 1600, textColor: C.red }, { text: '❌ Not written', width: 1600, textColor: C.red }, { text: 'TASK-3.3', width: 2360 }]),
      tableRow([{ text: 'Git repository + branch strategy', width: 3800 }, { text: '❌ Not created', width: 1600, textColor: C.red }, { text: '❌ Not created', width: 1600, textColor: C.red }, { text: 'TASK-3.4', width: 2360 }]),
      tableRow([{ text: 'End-to-end SIP call test', width: 3800 }, { text: '❌ Not done', width: 1600, textColor: C.red }, { text: '❌ Not done', width: 1600, textColor: C.red }, { text: 'TASK-3.5 — final gate', width: 2360 }]),
    ],
  }),

  ...spacer(2),

  // ── SECTION 3: PHASE 2 — UZBEK COMPLETION ─────────────────────────────────
  h1('3. PHASE 2 — UZBEK LANGUAGE COMPLETION'),
  phaseBanner('PHASE 2', 'Multilingual Fine-Tuning', 'Russian ✅  |  Uzbek ⏳', C.blue),
  ...spacer(1),

  h2('3.1 Dataset Strategy — No Waiting for Ivan'),
  body('Uzbek datasets are available NOW on HuggingFace. Do not wait. Pull, process, and train immediately. Ivan\'s custom dataset (if delivered) can be merged as a second fine-tuning pass later.'),
  ...spacer(1),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2800, 1400, 1600, 3560],
    rows: [
      tableRow([{ text: 'Dataset', width: 2800 }, { text: 'Size', width: 1400 }, { text: 'Script', width: 1600 }, { text: 'Use', width: 3560 }], true),
      tableRow([{ text: 'behbudiy/alpaca-cleaned-uz', width: 2800 }, { text: '52,000 pairs', width: 1400 }, { text: 'Uzbek Latin', width: 1600 }, { text: 'PRIMARY — instruction/response, Alpaca format, Google Translate quality', width: 3560 }]),
      tableRow([{ text: 'saillab/alpaca-uzbek-cleaned', width: 2800 }, { text: '52,000 pairs', width: 1400 }, { text: 'Uzbek Latin', width: 1600 }, { text: 'SECONDARY — second independent translation, adds variation', width: 3560 }]),
      tableRow([{ text: 'behbudiy/translation-instruction', width: 2800 }, { text: '20,000 pairs', width: 1400 }, { text: 'Latin', width: 1600 }, { text: 'Professional/formal register. EN↔UZ bilingual. Higher quality filter.', width: 3560 }]),
      tableRow([{ text: 'tahrirchi/uz-books', width: 2800 }, { text: '~40,000 books', width: 1400 }, { text: 'Latin+Cyrillic', width: 1600 }, { text: 'CYRILLIC SOURCE — prose corpus. Convert to dialogue pairs for Cyrillic training.', width: 3560 }]),
      tableRow([{ text: 'Den4ikAI/russian_dialogues', width: 2800 }, { text: '2.47M rows', width: 1400 }, { text: 'Cyrillic', width: 1600 }, { text: 'Russian supplement if aziza-bilingual.jsonl needs augmentation.', width: 3560 }]),
    ],
  }),

  ...spacer(1),

  // TASK 2.1
  taskCard(
    'TASK-2.1', 'Tokenizer Audit — Uzbek Character Coverage',
    '⚡ START HERE', 'FFF3CD', C.amber,
    'Chris / H100',
    [],
    'Run audit_tokenizer.py against Vikhr-Llama-3.1-8B-Instruct tokenizer. Verify ≥90% single-token coverage for all Uzbek Latin special graphemes and Uzbek Cyrillic characters. Decide whether tokenizer extension is needed before any training begins.',
    [
      'Characters to audit — Uzbek Latin: Oʻ oʻ Gʻ gʻ Sh sh Ch ch Ng ng',
      'Characters to audit — Uzbek Cyrillic: Ҳ ҳ Ҷ ҷ Қ қ Ғ ғ Ў ў',
      'For each char: print token IDs, decoded tokens, fragment count. Flag any >2 tokens.',
      'If any Latin char fragments to >3 tokens: add via tokenizer.add_tokens() and resize embeddings.',
      'Save extended tokenizer to /adapters/tokenizer-uz-extended/ if extension applied.',
      'Run 50-sentence Uzbek Latin corpus through tokenizer. Compute coverage ratio.',
    ],
    [
      'Script produces coverage report to stdout with PASS/FAIL verdict',
      'Coverage ≥90% on Uzbek Latin confirmed',
      'Cyrillic chars verified (Vikhr-Llama has existing Cyrillic coverage)',
      'If extension applied: adapter_config.json reflects new vocab_size',
    ]
  ),

  ...spacer(1),

  // TASK 2.2
  taskCard(
    'TASK-2.2', 'Dataset Preparation — Uzbek Latin + Cyrillic',
    'PENDING', C.pending, C.amber,
    'Chris / H100',
    ['TASK-2.1 (tokenizer coverage confirmed first)'],
    'Download, sample, and format Uzbek datasets into aziza-uzbek.jsonl. Target: ≥3,000 validated dialogue pairs (1,500 Latin + 1,500 Cyrillic). Must match exact ChatML messages format used by train_russian.py.',
    [
      'Run: from datasets import load_dataset; ds = load_dataset("behbudiy/alpaca-cleaned-uz")',
      'Sample 1,200 pairs for academic+professional register (Latin). Sample 300 colloquial pairs from saillab source.',
      'For Cyrillic: use tahrirchi/uz-books — extract paragraph pairs and reformat as dialogue turns.',
      'Normalise ALL records to: {"messages": [{"role":"system","content":"<Aziza persona in Uzbek>"},{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}',
      'System turn must contain Uzbek Aziza persona: "Siz — Aziza, ovozli AI-assistentsiz..." (formal uz-latin) or Cyrillic equivalent.',
      'Write validate_uzbek_dataset.py: check valid JSON, required keys, no English drift (>10% ASCII = fail), script purity per line.',
      'CRITICAL: No Latin/Cyrillic mixing within a single dialogue. Each dialogue is mono-script.',
    ],
    [
      '≥3,000 validated lines in aziza-uzbek.jsonl',
      'validate_uzbek_dataset.py exits 0 with: total lines, Latin count, Cyrillic count, failed=0',
      'Dataset backed up to aziza-uzbek.jsonl.tar.gz',
    ]
  ),

  ...spacer(1),

  // TASK 2.3
  taskCard(
    'TASK-2.3', 'Write train_uzbek.py',
    'PENDING', C.pending, C.amber,
    'Chris',
    ['TASK-2.1', 'TASK-2.2'],
    'Clone train_russian.py into train_uzbek.py. Change only dataset path, language arg default, and adapter output name. If tokenizer was extended in TASK-2.1, load from /adapters/tokenizer-uz-extended/ instead of HuggingFace.',
    [
      'Copy train_russian.py → train_uzbek.py',
      'Change BASE_MODEL_ID default language to uz_latin',
      'Change default ADAPTER output to /root/aziza/adapters/uz_colloquial',
      'If tokenizer extended: add --tokenizer_path arg, load AutoTokenizer.from_pretrained(args.tokenizer_path)',
      'LOCKED CONFIG unchanged: r=16, alpha=32, NF4, lr=2e-4, batch=4, grad_accum=4, max_seq=512, epochs=3',
      'Add checkpoint saves after Stage 1 → uz-stage1/ and Stage 2 → uz-stage2/',
      'Dry run first: python3 train_uzbek.py --dry_run to validate dataset format before GPU time',
    ],
    [
      'train_uzbek.py --dry_run exits 0 with dataset validation passing',
      'Effective batch size logged as 16 (4 × 4)',
      'Output path resolves to /root/aziza/adapters/uz_colloquial/',
    ]
  ),

  ...spacer(1),

  // TASK 2.4
  taskCard(
    'TASK-2.4', 'Execute QLoRA Training Run — Uzbek',
    'PENDING', C.pending, C.amber,
    'Chris / H100 (GPU time)',
    ['TASK-2.3'],
    'Run the 3-stage curriculum QLoRA training on the H100. Estimated 12–18 hours. Monitor for OOM, NaN loss, and checkpoint saves. Produce aziza-adapter-final-uz.',
    [
      'Check VRAM clear: nvidia-smi (need ≥30GB free before starting)',
      'Start screen session: screen -S aziza-train-uz',
      'Export HF_TOKEN, then run: python3 train_uzbek.py --register colloquial --dataset_path ./aziza-uzbek.jsonl --output_base /root/aziza/adapters',
      'Monitor: watch -n 10 nvidia-smi AND tail -f runs/uz_colloquial_*/trainer_log.jsonl',
      'OOM fallback: add --batch_size 2 --grad_accum 8 (maintains effective batch of 16)',
      'On completion: verify /root/aziza/adapters/uz_colloquial/adapter_model.safetensors exists',
      'Archive: tar -czf aziza-adapter-final-uz.tar.gz /root/aziza/adapters/uz_colloquial/',
    ],
    [
      'Training completes all 3 stages with no CUDA OOM or NaN loss',
      'adapter_model.safetensors and adapter_config.json present in output dir',
      'aziza-adapter-final-uz.tar.gz created and stored off-GPU',
    ]
  ),

  ...spacer(1),

  // TASK 2.5
  taskCard(
    'TASK-2.5', 'Write eval_uzbek.py and Run Acceptance Gates',
    'PENDING', C.pending, C.amber,
    'Chris',
    ['TASK-2.4'],
    'Clone eval_russian.py into eval_uzbek.py. Replace Cyrillic-ratio metric with Uzbek script coverage metric. Run all 5 acceptance gates. Must achieve ≥80% Uzbek script fidelity.',
    [
      'Copy eval_russian.py → eval_uzbek.py',
      'Replace has_cyrillic() with has_uzbek_script(): for Latin check for ʻ (U+02BB) presence; for Cyrillic check for Ҳ Ҷ Қ Ғ Ў range',
      'Replace RU_TEST_PROMPTS with 10 Uzbek prompts covering: greeting, persona, academic, professional, cultural, business writing, translation, AI explanation, everyday task, capability description — in target script',
      'Gate thresholds unchanged: adapter_loads=1.0, pass_rate≥0.8, script_pct≥0.8, ttft_proxy, no_english_regression≥0.5',
      'Add language_switching gate: Latin input → Latin output, Cyrillic input → Cyrillic output. Target ≥95%.',
      'Run: python3 eval_uzbek.py --adapter /root/aziza/adapters/uz_colloquial --language uz_latin',
      'If pass_rate < 0.8: rerun train_uzbek.py with --register all to use full dataset',
    ],
    [
      'Script fidelity ≥80% on held-out Uzbek test set',
      'Language switching accuracy ≥95% (Latin→Latin, Cyrillic→Cyrillic)',
      'eval_uzbek_report.txt saved to adapter directory',
      'All 5 gates pass. Exit code 0.',
    ]
  ),

  ...spacer(1),

  // TASK 2.6
  taskCard(
    'TASK-2.6', 'TTFT Benchmark — Combined Adapters, Voice-First Validation',
    'PENDING', C.pending, C.amber,
    'Chris',
    ['TASK-2.5'],
    'Write bench_ttft.py using StoppingCriteria hook to measure real Time-To-First-Token (not batch proxy). Target: p95 TTFT <100ms across all three language modes simultaneously.',
    [
      'Write TTFTTimer(StoppingCriteria) class: record wall-clock time on first new token generated',
      'Open WebSocket to serve_russian_test.py extended to accept --adapter_path arg',
      'Send 50 prompts alternating: Russian / Uzbek Latin / Uzbek Cyrillic',
      'Record: per-prompt TTFT_ms. Report: p50, p95, p99 for each language + combined',
      'If p95 > 100ms: investigate tokenizer extension overhead, NF4 cache miss on new tokens, Moshi buffer config',
      'Save bench_ttft_report.txt to /root/aziza/adapters/',
    ],
    [
      'p95 TTFT <100ms across all three language modes',
      'No regression vs Russian-only baseline (p95 delta <15ms)',
      'bench_ttft_report.txt saved with full percentile breakdown',
    ]
  ),

  ...spacer(1),

  // TASK 2.7
  taskCard(
    'TASK-2.7', 'Extend API Gateway — Uzbek Language Modes',
    'PENDING', C.pending, C.amber,
    'Chris',
    ['TASK-2.5'],
    'Update NestJS API Gateway session init to support uz-latin and uz-cyrillic as first-class language modes. Update PersonaPlex with Uzbek system prompts. Add Uzbek drift guard.',
    [
      'Add language field to session init payload: "ru" | "uz-latin" | "uz-cyrillic"',
      'Map uz-latin → PersonaPlex Uzbek Latin context (formal "Siz" + "sen" register rules)',
      'Map uz-cyrillic → PersonaPlex Uzbek Cyrillic context',
      'Uzbek drift guard: if response contains >10% ASCII printable chars (excl. digits/punct) in Uzbek mode → flag and retry once',
      'Load correct adapter at session start based on language tag',
      'Extend serve_russian_test.py to serve_multilingual.py: accepts --language arg, loads correct adapter',
    ],
    [
      'POST /session with language: "uz-latin" returns Uzbek Latin responses end-to-end',
      'Language drift guard triggers retry on English-drifted responses',
      'PersonaPlex has separate context entries for uz-latin and uz-cyrillic',
      '/health endpoint reports all three adapter statuses',
    ]
  ),

  ...spacer(2),

  // ── SECTION 4: PHASE 3 — PRODUCTION INTEGRATION ───────────────────────────
  h1('4. PHASE 3 — PRODUCTION & ORCHESTRATOR INTEGRATION'),
  phaseBanner('PHASE 3', 'Production Infrastructure', 'Foundation Ready  |  Integration Pending', C.navy),
  ...spacer(1),

  // TASK 3.1
  taskCard(
    'TASK-3.1', 'Orchestrator — Dynamic GPU Worker Pool Routing',
    'PENDING', C.pending, C.amber,
    'Chris',
    [],
    'Revise NestJS Orchestrator so session requests route directly to an idle GPU worker WebSocket URL. No session ever proxied through the Orchestrator. Redis-backed worker registry with atomic status transitions.',
    [
      'On worker startup: SET worker:{id}:status "idle" AND SET worker:{id}:ws_url "ws://<host>:<port>" in Redis',
      'On POST /session: scan Redis for worker:*:status = "idle", pick one atomically with GETSET worker:{id}:status "busy"',
      'Return {ws_url: "ws://..."} directly to client. Client connects to worker directly.',
      'On session end: worker sets own status back to "idle" via DELETE + SET',
      'If no idle workers: return 503 {error: "all_workers_busy", retry_after: 5}',
      'Worker ID = PM2 app instance name (e.g., aziza-worker-0)',
      'Add /workers/status admin endpoint showing all workers and their current state',
    ],
    [
      'POST /session returns {ws_url} pointing directly to idle worker',
      'Worker status transitions verified via Redis CLI: idle → busy → idle',
      'N simultaneous session requests satisfied with 0 queuing (N = running PM2 worker count)',
      '503 returned cleanly when all workers busy',
    ]
  ),

  ...spacer(1),

  // TASK 3.2
  taskCard(
    'TASK-3.2', 'Voice Frontend — AudioWorklet + WebSocket Browser Client',
    'PENDING', C.pending, C.amber,
    'Chris',
    ['TASK-3.1'],
    'Build the browser-side voice client in Vue 3. AudioWorkletProcessor captures mic at 16kHz, streams PCM frames over WebSocket to Moshi worker. Receives PCM audio frames back and plays them via AudioBufferSourceNode queue. This enables both Voice→Text and Voice↔Voice modes in the browser.',
    [
      'AudioWorkletProcessor: 40ms PCM frames at 16kHz mono. Post to main thread via port.postMessage().',
      'Main thread: WebSocket to worker ws_url from Orchestrator. Send binary PCM frames.',
      'Receive binary frames from Moshi: feed into AudioPlaybackQueue using scheduled AudioBufferSourceNode.',
      'AudioContext sample rate: detect browser native rate (usually 48kHz), resample to 16kHz for send, resample Moshi 24kHz output to native for playback using linear interpolation.',
      'Vue component: <VoiceChat> with states: idle / connecting / listening / speaking / error',
      'Show real-time transcript overlay while Moshi generates text alongside audio.',
      'Language selector dropdown: Russian / Uzbek Latin / Uzbek Cyrillic — sets session language on connect.',
      'Full-duplex indicator: show when both mic active AND audio playing (true duplex mode).',
    ],
    [
      'Browser mic input → Moshi → audio playback working end-to-end with <300ms perceived latency',
      'No audio glitches or gaps during 5-minute continuous voice session',
      'Language switching works by ending session and starting new one with correct language tag',
      'Voice→Text mode: response displayed as text + optionally spoken',
    ]
  ),

  ...spacer(1),

  // TASK 3.3
  taskCard(
    'TASK-3.3', 'Asterisk ARI Bridge — RTP → WebSocket Audio Pipeline',
    'PENDING', C.pending, C.amber,
    'Chris',
    ['TASK-3.1'],
    'Build Python + asyncio service (asterisk_ari_bridge.py) connecting Asterisk ARI to Moshi inference. Enables real phone calls through the full Aziza AI stack.',
    [
      'Connect to Asterisk ARI: aiohttp WebSocket to http://localhost:8088/ari. Subscribe to StasisStart on app "aziza".',
      'On incoming call: answer channel, initiate ExternalMedia RTP stream on local UDP port.',
      'FFmpeg subprocess: asyncio.subprocess, receive RTP on UDP port, transcode to 16kHz mono PCM, pipe to stdout.',
      'Read PCM chunks from FFmpeg stdout → asyncio queue → WebSocket binary frames to Moshi worker URL.',
      'Receive Moshi response PCM → reverse FFmpeg transcode to G.711 ulaw → RTP back to Asterisk channel.',
      'Full duplex: continue reading mic RTP while Moshi audio is playing (no half-duplex blocking).',
      'Error handling: Moshi WS disconnect → hold tone + reconnect once. ARI channel drop → cancel all tasks cleanly.',
      'No sync requests anywhere — entire service is asyncio/aiohttp/websockets.',
    ],
    [
      'Incoming SIP call → StasisStart → bridge connects → Moshi responds in correct language',
      'Audio round-trip latency ≤300ms LAN (phone mic → Moshi → phone speaker)',
      'Service survives 10 consecutive calls with no memory leak or zombie FFmpeg processes',
      'Language detection: ARI channel variable AZIZA_LANGUAGE used to set session language',
    ]
  ),

  ...spacer(1),

  // TASK 3.4
  taskCard(
    'TASK-3.4', 'PM2 Ecosystem Config — All Production Processes',
    'PENDING', C.pending, C.amber,
    'Chris',
    ['TASK-3.1', 'TASK-3.3'],
    'Write ecosystem.config.js defining every production process. Single pm2 start ecosystem.config.js brings up the complete stack. Must survive server reboot via pm2 save + pm2 startup.',
    [
      'aziza-gateway: NestJS API Gateway, port 3000, env: REDIS_URL, JWT_SECRET',
      'aziza-orchestrator: session routing service',
      'aziza-worker-0 through aziza-worker-N: Moshi inference workers. Each with WORKER_ID and WS_PORT env vars. Startup hook registers ws_url in Redis.',
      'aziza-ari-bridge: Asterisk bridge service (asterisk_ari_bridge.py)',
      'aziza-personaplex: PersonaPlex microservice',
      'aziza-frontend: static file serving (serve dist/ on port 8010)',
      'Each worker startup script: register in Redis before PM2 marks online',
      'pm2 save + pm2 startup generates systemd unit. Test with server reboot.',
      'Adding new worker: increment N in config, pm2 reload — zero downtime.',
    ],
    [
      'pm2 start ecosystem.config.js: all services online, 0 restarts in first 60s',
      'pm2 save + pm2 startup survives reboot',
      'pm2 status shows all 6+ processes as online',
      'Redis shows all workers registered with idle status after startup',
    ]
  ),

  ...spacer(1),

  // TASK 3.5
  taskCard(
    'TASK-3.5', 'Git Repository — Production Config + Branch Strategy',
    'PENDING', C.pending, C.amber,
    'Chris',
    [],
    'Create the permanent Git repository. Commit all existing assets to dev branch. Establish branch protections and PR workflow for team collaboration.',
    [
      'Create repo aziza-platform (private)',
      'Directories: /gateway /orchestrator /inference /telephony /training /personaplex /frontend',
      '/training: train_russian.py, train_uzbek.py, eval_*.py, bench_ttft.py, audit_tokenizer.py, validate_uzbek_dataset.py',
      'Root files: ecosystem.config.js, .env.example (all env vars documented, no secrets), README.md',
      '.gitignore: *.safetensors, *.tar.gz, *.jsonl, .env, node_modules/, __pycache__/, runs/, rag_index/',
      'Branch strategy: main=production (protected, no direct push), dev=integration, feature/task-{id}-{slug}',
      'PR rules: feature/* → dev requires 1 review. dev → main requires passing E2E test result attached.',
      'CONTRIBUTING.md: branch naming, PR checklist, env setup instructions',
    ],
    [
      'Repo created with all existing assets committed to dev',
      'main branch protection enabled',
      '.gitignore excludes all model weights and datasets',
      'CONTRIBUTING.md documents full workflow',
    ]
  ),

  ...spacer(1),

  // TASK 3.6
  taskCard(
    'TASK-3.6', 'End-to-End Integration Test — All Three Modes',
    'PENDING', C.pending, C.amber,
    'Chris + Ivan',
    ['TASK-2.7', 'TASK-3.1', 'TASK-3.2', 'TASK-3.3', 'TASK-3.4'],
    'Final acceptance test covering all three interaction modes in both Russian and Uzbek. This is the milestone completion gate for Ivan.',
    [
      'TEXT→TEXT: POST /chat with Russian + Uzbek Latin + Uzbek Cyrillic prompts. Assert: correct script response, <3000ms, coherent.',
      'VOICE→TEXT: Browser mic → speak Russian sentence → assert Cyrillic transcript appears within 2s of end-of-speech.',
      'VOICE↔VOICE BROWSER: Open voice session, speak greeting in Russian → hear Aziza respond in Russian audio. Repeat in Uzbek.',
      'VOICE↔VOICE PHONE: Dial SIP trunk DID, speak Russian → Aziza responds. Speak Uzbek → Aziza responds in Uzbek. Record both sides.',
      'Monitor during test: pm2 logs tailing all workers, Redis worker status transitions, no uncaught exceptions.',
      'Assert phone round-trip latency <300ms (Asterisk MixMonitor timestamp vs first audio byte).',
      'Run all 3 modes for 10 minutes continuous without crash or memory leak.',
    ],
    [
      'All 3 modes working in both Russian and Uzbek without intervention',
      'Text→Text: <3s response, correct script, coherent language',
      'Voice→Text: transcript appears <2s after end-of-speech',
      'Voice↔Voice: audio round-trip <300ms, no glitches in 10-min session',
      'Phone call: SIP→Asterisk→Moshi→SIP working end-to-end',
      'Test results documented in /tests/e2e/results/ with timestamps',
    ]
  ),

  ...spacer(2),

  // ── SECTION 5: EXECUTION SEQUENCE ─────────────────────────────────────────
  h1('5. EXECUTION SEQUENCE & CRITICAL PATH'),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [720, 2400, 2640, 3600],
    rows: [
      tableRow([{ text: '#', width: 720 }, { text: 'Tasks', width: 2400 }, { text: 'Parallel With', width: 2640 }, { text: 'Notes', width: 3600 }], true),
      tableRow([{ text: '1', width: 720, bold: true }, { text: 'TASK-2.1 (tokenizer audit)', width: 2400 }, { text: 'TASK-3.5 (git setup)', width: 2640 }, { text: 'UNBLOCKS everything in Phase 2. Run tonight.', width: 3600 }]),
      tableRow([{ text: '2', width: 720, bold: true }, { text: 'TASK-2.2 (dataset prep)', width: 2400 }, { text: 'TASK-3.4 (PM2 config)', width: 2640 }, { text: 'Download HuggingFace datasets, format, validate.', width: 3600 }]),
      tableRow([{ text: '3', width: 720, bold: true }, { text: 'TASK-2.3 (write train_uzbek.py)', width: 2400 }, { text: '—', width: 2640 }, { text: '30-minute task. Clone + minimal edits.', width: 3600 }]),
      tableRow([{ text: '4', width: 720, bold: true }, { text: 'TASK-2.4 (Uzbek training run)', width: 2400 }, { text: 'TASK-3.1 + TASK-3.2 + TASK-3.3', width: 2640 }, { text: '12-18hrs GPU time. Run overnight. Work on Phase 3 in parallel.', width: 3600 }]),
      tableRow([{ text: '5', width: 720, bold: true }, { text: 'TASK-2.5 (eval_uzbek.py)', width: 2400 }, { text: 'TASK-3.3 (ARI bridge)', width: 2640 }, { text: 'Run morning after training. ~15 min.', width: 3600 }]),
      tableRow([{ text: '6', width: 720, bold: true }, { text: 'TASK-2.6 (TTFT benchmark)', width: 2400 }, { text: 'TASK-3.4 (PM2 config)', width: 2640 }, { text: 'Run after eval passes.', width: 3600 }]),
      tableRow([{ text: '7', width: 720, bold: true }, { text: 'TASK-2.7 (API Gateway Uzbek)', width: 2400 }, { text: '—', width: 2640 }, { text: 'NestJS language routing + PersonaPlex Uzbek prompts.', width: 3600 }]),
      tableRow([{ text: '8', width: 720, bold: true }, { text: 'TASK-3.1 (Orchestrator routing)', width: 2400 }, { text: 'TASK-2.4 training run', width: 2640 }, { text: 'Can build while GPU is training.', width: 3600 }]),
      tableRow([{ text: '9', width: 720, bold: true }, { text: 'TASK-3.2 (Voice frontend)', width: 2400 }, { text: 'TASK-2.4 training run', width: 2640 }, { text: 'Vue 3 AudioWorklet component. Can build while GPU trains.', width: 3600 }]),
      tableRow([{ text: '10', width: 720, bold: true }, { text: 'TASK-3.3 (ARI bridge)', width: 2400 }, { text: 'TASK-2.4 training run', width: 2640 }, { text: 'Critical path for phone mode. Build in parallel.', width: 3600 }]),
      tableRow([{ text: '11', width: 720, bold: true }, { text: 'TASK-3.4 (PM2 ecosystem)', width: 2400 }, { text: 'TASK-2.4 training run', width: 2640 }, { text: 'Write ecosystem.config.js while GPU trains.', width: 3600 }]),
      tableRow([{ text: '12', width: 720, bold: true }, { text: 'TASK-3.6 (E2E test — FINAL)', width: 2400 }, { text: '—', width: 2640 }, { text: 'All tasks above must be complete. Ivan milestone gate.', width: 3600 }]),
    ],
  }),

  ...spacer(1),
  alertBox('CRITICAL PATH:', 'TASK-2.1 → TASK-2.2 → TASK-2.3 → TASK-2.4 → TASK-2.5 → TASK-2.7 → TASK-3.6. Everything on the critical path is sequential and GPU-bound. Phase 3 tasks (3.1, 3.2, 3.3, 3.4) should be built IN PARALLEL during the 12-18hr Uzbek training window.', 'FFF3CD', C.amber),
  ...spacer(2),

  // ── SECTION 6: ENVIRONMENT & CONFIG REFERENCE ─────────────────────────────
  h1('6. ENVIRONMENT & CONFIGURATION REFERENCE'),

  h2('6.1 Required Environment Variables'),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [3200, 2560, 3600],
    rows: [
      tableRow([{ text: 'Variable', width: 3200 }, { text: 'Example Value', width: 2560 }, { text: 'Used By', width: 3600 }], true),
      tableRow([{ text: 'HF_TOKEN', width: 3200 }, { text: 'hf_xxxxxxxxxxxx', width: 2560 }, { text: 'All training + serving scripts', width: 3600 }]),
      tableRow([{ text: 'MODEL_ID', width: 3200 }, { text: 'Vikhrmodels/Vikhr-Llama3.1-8B-Instruct-R-21-09-24', width: 2560 }, { text: 'serve_multilingual.py, eval scripts', width: 3600 }]),
      tableRow([{ text: 'ADAPTER_PATH_RU', width: 3200 }, { text: '/root/aziza/adapters/ru_colloquial', width: 2560 }, { text: 'serve_multilingual.py', width: 3600 }]),
      tableRow([{ text: 'ADAPTER_PATH_UZ_LATIN', width: 3200 }, { text: '/root/aziza/adapters/uz_colloquial', width: 2560 }, { text: 'serve_multilingual.py', width: 3600 }]),
      tableRow([{ text: 'ADAPTER_PATH_UZ_CYRILLIC', width: 3200 }, { text: '/root/aziza/adapters/uz_cyrillic', width: 2560 }, { text: 'serve_multilingual.py', width: 3600 }]),
      tableRow([{ text: 'REDIS_URL', width: 3200 }, { text: 'redis://localhost:6379', width: 2560 }, { text: 'NestJS Gateway, Orchestrator', width: 3600 }]),
      tableRow([{ text: 'JWT_SECRET', width: 3200 }, { text: '<random 64-char hex>', width: 2560 }, { text: 'NestJS Gateway auth', width: 3600 }]),
      tableRow([{ text: 'DATABASE_URL', width: 3200 }, { text: 'postgresql://aziza:pw@localhost/aziza_db', width: 2560 }, { text: 'Backend server.py', width: 3600 }]),
      tableRow([{ text: 'WORKER_ID', width: 3200 }, { text: 'aziza-worker-0', width: 2560 }, { text: 'Each Moshi worker process', width: 3600 }]),
      tableRow([{ text: 'WS_PORT', width: 3200 }, { text: '8021 (8021, 8022, 8023...)', width: 2560 }, { text: 'Each Moshi worker (increment per instance)', width: 3600 }]),
      tableRow([{ text: 'ASTERISK_URL', width: 3200 }, { text: 'http://localhost:8088', width: 2560 }, { text: 'asterisk_ari_bridge.py', width: 3600 }]),
      tableRow([{ text: 'ASTERISK_USER', width: 3200 }, { text: 'aziza', width: 2560 }, { text: 'ARI auth', width: 3600 }]),
      tableRow([{ text: 'ASTERISK_PASS', width: 3200 }, { text: '<ari password>', width: 2560 }, { text: 'ARI auth', width: 3600 }]),
    ],
  }),

  ...spacer(1),

  h2('6.2 Locked Training Config — Do Not Change'),
  ...codeBlock([
    'LOCKED_CONFIG = {',
    '    "lora_r": 16,',
    '    "lora_alpha": 32,',
    '    "lora_dropout": 0.05,',
    '    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],',
    '    "max_seq_length": 512,',
    '    "batch_size": 4,',
    '    "grad_accum_steps": 4,      # effective batch = 16',
    '    "learning_rate": 2e-4,',
    '    "num_epochs": 3,',
    '    "lr_scheduler_type": "cosine",',
    '    "quantization": "nf4",       # 4-bit NF4',
    '    "double_quant": True,',
    '    "compute_dtype": "float16",',
    '}',
  ]),

  ...spacer(1),

  h2('6.3 HuggingFace Dataset Load Commands'),
  ...codeBlock([
    'from datasets import load_dataset',
    '',
    '# Uzbek Latin — Primary (52K instruction pairs)',
    'uz_primary = load_dataset("behbudiy/alpaca-cleaned-uz")',
    '',
    '# Uzbek Latin — Secondary (52K, independent translation)',
    'uz_secondary = load_dataset("saillab/alpaca-uzbek-cleaned")',
    '',
    '# Uzbek Bilingual — Professional register (20K, higher quality)',
    'uz_bilingual = load_dataset("behbudiy/translation-instruction")',
    '',
    '# Uzbek Cyrillic — Book corpus (Latin+Cyrillic, 40K books)',
    'uz_books = load_dataset("tahrirchi/uz-books")',
    '',
    '# Russian supplement if needed',
    'ru_dialogues = load_dataset("Den4ikAI/russian_dialogues")',
  ]),

  ...spacer(2),

  // ── SECTION 7: ACCEPTANCE CHECKLIST ───────────────────────────────────────
  h1('7. FINAL PRODUCTION ACCEPTANCE CHECKLIST'),
  body('Every item below must be checked before declaring the system production-ready and presenting to Ivan.'),
  ...spacer(1),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [600, 5760, 1500, 1500],
    rows: [
      tableRow([{ text: '', width: 600 }, { text: 'Acceptance Item', width: 5760 }, { text: 'Status', width: 1500 }, { text: 'Evidence', width: 1500 }], true),
      tableRow([{ text: '□', width: 600 }, { text: 'Russian QLoRA adapter eval passed (≥80% Cyrillic accuracy)', width: 5760 }, { text: '✅ Done', width: 1500, textColor: '28A745' }, { text: 'eval_results.json', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Uzbek Latin QLoRA adapter eval passed (≥80% accuracy)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Uzbek Cyrillic QLoRA adapter eval passed (≥80% accuracy)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'TTFT p95 <100ms — Russian', width: 5760 }, { text: '✅ Done', width: 1500, textColor: '28A745' }, { text: 'bench_ttft_report.txt', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'TTFT p95 <100ms — Uzbek Latin', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'TTFT p95 <100ms — Uzbek Cyrillic', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Text→Text: Russian coherent response in <3s', width: 5760 }, { text: '✅ Done', width: 1500, textColor: '28A745' }, { text: 'smoke test /chat', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Text→Text: Uzbek Latin coherent response in <3s', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Text→Text: Uzbek Cyrillic coherent response in <3s', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Voice→Text: transcript <2s after end-of-speech (Russian)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Voice→Text: transcript <2s after end-of-speech (Uzbek)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Voice↔Voice browser: audio round-trip <300ms (Russian)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Voice↔Voice browser: audio round-trip <300ms (Uzbek)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Voice↔Voice phone (SIP): end-to-end call working (Russian)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Voice↔Voice phone (SIP): end-to-end call working (Uzbek)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'PersonaPlex: Aziza stays in character 5+ turns (Russian)', width: 5760 }, { text: '✅ Done', width: 1500, textColor: '28A745' }, { text: 'eval gate 5', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'PersonaPlex: Aziza stays in character 5+ turns (Uzbek)', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: '10-minute continuous session — no crash, no memory leak', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'PM2 ecosystem starts all services from cold boot', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'Git repo created, all assets committed, branch protection on', width: 5760 }, { text: '❌ Pending', width: 1500, textColor: C.red }, { text: '', width: 1500 }]),
      tableRow([{ text: '□', width: 600 }, { text: 'All adapter .tar.gz backups stored off-GPU', width: 5760 }, { text: 'RU ✅ / UZ ❌', width: 1500, textColor: C.amber }, { text: '', width: 1500 }]),
    ],
  }),

  ...spacer(2),

  // ── FOOTER ─────────────────────────────────────────────────────────────────
  new Paragraph({
    children: [run('AZIZA AI PLATFORM — MASTER BUILD PROMPT  ·  Novatech  ·  Confidential  ·  June 2026', { size: 18, color: '888888' })],
    alignment: AlignmentType.CENTER,
    border: { top: { style: BorderStyle.SINGLE, size: 4, color: C.accent } },
    spacing: { before: 200, after: 0 },
  }),
];

// ── Assemble document ──────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 480, hanging: 240 } } },
        }, {
          level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 240 } } },
        }],
      },
      {
        reference: 'numbers',
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 480, hanging: 240 } } },
        }],
      },
    ],
  },
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Arial', color: C.white },
        paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: C.navy },
        paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: C.blue },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            run('AZIZA AI PLATFORM  ·  MASTER BUILD PROMPT', { size: 16, color: '888888', bold: true }),
            new TextRun({ text: '\t', font: 'Arial', size: 16 }),
            run('Novatech  ·  Confidential', { size: 16, color: 'AAAAAA' }),
          ],
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.accent } },
          spacing: { before: 0, after: 120 },
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('/mnt/user-data/outputs/AZIZA_MASTER_BUILD_PROMPT.docx', buffer);
  console.log('Done: AZIZA_MASTER_BUILD_PROMPT.docx');
});
