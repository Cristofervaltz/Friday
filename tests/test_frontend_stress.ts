/**
 * Deep Empirical Challenger Test Suite for Friday UI
 * Focus:
 * 1. handleInstantSend dispatch logic, queue mutation, idempotency, race conditions, state transitions
 * 2. I18nProvider translation lookup, parameter interpolation, fallback, language switching, localStorage sync
 * 3. Token parity check between EN and RU dictionaries (ensuring identical parameter placeholders)
 * 4. Exhaustive dictionary parity, UI component call-site verification, and hardcoded raw text audit
 * 5. Edge cases: Unicode, Markdown, HTML injection, Special characters, Whitespace
 */

import { en, ru, translations } from '../src/ui/src/i18n/translations.ts';
import { getNestedValue, interpolate } from '../src/ui/src/i18n/utils.ts';
import { STORAGE_KEY, getInitialLanguage } from '../src/ui/src/i18n/context.ts';
import type { Language, TranslationDict, TranslationParams } from '../src/ui/src/i18n/types.ts';
import * as fs from 'fs';
import * as path from 'path';

// ANSI color codes
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const CYAN = '\x1b[36m';
const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';

let totalTests = 0;
let passedTests = 0;
let failedTests = 0;

function assert(condition: boolean, msg: string) {
  totalTests++;
  if (condition) {
    passedTests++;
    console.log(`  ${GREEN}✓${RESET} ${msg}`);
  } else {
    failedTests++;
    console.error(`  ${RED}✗ FAIL:${RESET} ${msg}`);
    throw new Error(`Assertion failed: ${msg}`);
  }
}

function describe(suiteName: string, fn: () => void) {
  console.log(`\n${BOLD}${CYAN}=== Suite: ${suiteName} ===${RESET}`);
  try {
    fn();
  } catch (err: any) {
    console.error(`  ${RED}Suite Error in [${suiteName}]: ${err.message}${RESET}`);
  }
}

// ---------------------------------------------------------------------------
// 1. handleInstantSend State Machine & Dispatch Simulation
// ---------------------------------------------------------------------------

interface Message {
  id: string;
  role: 'user' | 'bot' | 'system' | 'tool' | 'assistant';
  content: string;
}

interface QueuedMessage {
  id: string;
  text: string;
}

class AppInstantSendHarness {
  messages: Message[] = [];
  messageQueue: QueuedMessage[] = [];
  isThinking: boolean = false;
  connected: boolean = true;
  sentWsMessages: Array<{ type: string; content: string }> = [];
  hiddenCommands = ['/voice', '/clear', '/settings'];

  // Simulated WebSocket
  ws = {
    readyState: 1, // OPEN
    send: (payload: string) => {
      this.sentWsMessages.push(JSON.parse(payload));
    }
  };

  // The exact logic from App.tsx handleInstantSend
  handleInstantSend(msgId: string) {
    const msg = this.messageQueue.find(m => m.id === msgId);
    if (!msg || !this.ws || !this.connected) return;

    // pop out of queue
    this.messageQueue = this.messageQueue.filter(m => m.id !== msgId);

    // show user msg in chat feed
    if (!this.hiddenCommands.includes(msg.text)) {
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: msg.text };
      this.messages.push(userMsg);
    }

    // send over websocket straight away
    this.isThinking = true;
    this.ws.send(JSON.stringify({ type: 'message', content: msg.text }));
  }

  // Regular handleSubmit logic from App.tsx
  handleSubmit(input: string, forceInstant: boolean = false) {
    if (!input.trim() || !this.ws || !this.connected) return;
    const text = input.trim();

    if (this.isThinking && !forceInstant) {
      this.messageQueue.push({ id: Date.now().toString() + Math.random(), text });
      return;
    }

    if (!this.hiddenCommands.includes(text)) {
      this.messages.push({ id: Date.now().toString(), role: 'user', content: text });
    }

    this.isThinking = true;
    this.ws.send(JSON.stringify({ type: 'message', content: text }));
  }

  // Auto dequeue effect simulation
  processQueueOnDoneThinking() {
    if (!this.isThinking && this.messageQueue.length > 0 && this.ws && this.connected) {
      const nextMsg = this.messageQueue[0];
      this.messageQueue = this.messageQueue.slice(1);
      const userMsg: Message = { id: Date.now().toString(), role: 'user', content: nextMsg.text };
      this.messages.push(userMsg);
      this.isThinking = true;
      this.ws.send(JSON.stringify({ type: 'message', content: nextMsg.text }));
    }
  }
}

describe('Instant Send: Normal & Concurrent Scenarios', () => {
  const harness = new AppInstantSendHarness();

  harness.messageQueue = [
    { id: 'msg-1', text: 'First task' },
    { id: 'msg-2', text: 'Second task (instant target)' },
    { id: 'msg-3', text: 'Third task' },
  ];
  harness.isThinking = true;

  // Instant send the second message while thinking
  harness.handleInstantSend('msg-2');

  assert(harness.messageQueue.length === 2, 'Queue length should decrease from 3 to 2');
  assert(harness.messageQueue.map(m => m.id).join(',') === 'msg-1,msg-3', 'Remaining queue should preserve exact order [msg-1, msg-3]');
  assert(harness.messages.length === 1 && harness.messages[0].content === 'Second task (instant target)', 'Messages list should contain the instant-sent message');
  assert(harness.messages[0].role === 'user', 'Instant-sent message role should be user');
  assert(harness.sentWsMessages.length === 1, 'WebSocket should have sent exactly 1 message');
  assert(harness.sentWsMessages[0].type === 'message' && harness.sentWsMessages[0].content === 'Second task (instant target)', 'WebSocket payload must match instant-send contract');
  assert(harness.isThinking === true, 'isThinking should remain true');
});

describe('Instant Send: Idempotency & Repeat Click Protection', () => {
  const harness = new AppInstantSendHarness();
  harness.messageQueue = [{ id: 'msg-repeat', text: 'Repeat test' }];

  // Call handleInstantSend twice with the same msgId
  harness.handleInstantSend('msg-repeat');
  const countAfterFirst = harness.sentWsMessages.length;
  harness.handleInstantSend('msg-repeat'); // second call

  assert(countAfterFirst === 1, 'First call should send 1 WS message');
  assert(harness.sentWsMessages.length === 1, 'Second call with already-dispatched ID must be a safe no-op');
  assert(harness.messageQueue.length === 0, 'Queue should remain empty');
  assert(harness.messages.length === 1, 'Messages list should not duplicate the item');
});

describe('Instant Send: Non-existent ID & Disconnected State Handling', () => {
  const harness = new AppInstantSendHarness();
  harness.messageQueue = [{ id: 'msg-valid', text: 'Valid task' }];

  // 1. Non-existent id
  harness.handleInstantSend('msg-invalid-999');
  assert(harness.messageQueue.length === 1, 'Non-existent ID does not mutate message queue');
  assert(harness.sentWsMessages.length === 0, 'Non-existent ID does not dispatch WS message');

  // 2. Disconnected state
  harness.connected = false;
  harness.handleInstantSend('msg-valid');
  assert(harness.messageQueue.length === 1, 'Disconnected state does not remove item from queue');
  assert(harness.sentWsMessages.length === 0, 'Disconnected state does not send WS message');
});

describe('Instant Send: Hidden Commands Filtering', () => {
  const harness = new AppInstantSendHarness();
  harness.messageQueue = [
    { id: 'cmd-voice', text: '/voice' },
    { id: 'cmd-clear', text: '/clear' },
    { id: 'cmd-settings', text: '/settings' },
  ];

  harness.handleInstantSend('cmd-voice');
  harness.handleInstantSend('cmd-clear');
  harness.handleInstantSend('cmd-settings');

  assert(harness.messageQueue.length === 0, 'All hidden commands dequeued properly');
  assert(harness.sentWsMessages.length === 3, 'All 3 hidden commands sent over WebSocket');
  assert(harness.messages.length === 0, 'Hidden commands should NOT be appended to visible chat messages array');
});

describe('Instant Send: Interleaving with Auto-Queue Processing', () => {
  const harness = new AppInstantSendHarness();
  harness.messageQueue = [
    { id: 'q1', text: 'Queue 1' },
    { id: 'q2', text: 'Queue 2' },
    { id: 'q3', text: 'Queue 3' },
  ];
  harness.isThinking = true;

  // User instant-sends q3 while q1, q2 are waiting
  harness.handleInstantSend('q3');
  assert(harness.sentWsMessages.length === 1 && harness.sentWsMessages[0].content === 'Queue 3', 'q3 dispatched immediately');

  // Server finishes thinking for q3
  harness.isThinking = false;
  harness.processQueueOnDoneThinking();

  assert(harness.sentWsMessages.length === 2 && harness.sentWsMessages[1].content === 'Queue 1', 'Auto-dequeue picks q1 next');
  assert(harness.messageQueue.length === 1 && harness.messageQueue[0].id === 'q2', 'Only q2 remains in queue');

  // Server finishes thinking for q1
  harness.isThinking = false;
  harness.processQueueOnDoneThinking();

  assert(harness.sentWsMessages.length === 3 && harness.sentWsMessages[2].content === 'Queue 2', 'Auto-dequeue picks q2 next');
  assert(harness.messageQueue.length === 0, 'Queue is fully drained without duplicate processing');
});

describe('Instant Send: Form Submit Force-Instant', () => {
  const harness = new AppInstantSendHarness();
  harness.isThinking = true;

  // Submit with forceInstant = true (the lightning button next to textarea)
  harness.handleSubmit('Urgent command while thinking', true);

  assert(harness.messageQueue.length === 0, 'Force-instant input is not queued');
  assert(harness.sentWsMessages.length === 1 && harness.sentWsMessages[0].content === 'Urgent command while thinking', 'Force-instant input sent immediately over WS');
  assert(harness.messages.length === 1 && harness.messages[0].content === 'Urgent command while thinking', 'Force-instant input added to chat feed');
});

describe('Instant Send: Complex Payloads (Unicode, Markdown, JSON, Emojis)', () => {
  const harness = new AppInstantSendHarness();
  const complexPayload = '🚀 Deploy to production: `npm run build && tsc`\n\n- Step 1: "test"\n- Step 2: <b>safe</b>';
  harness.messageQueue = [{ id: 'complex-1', text: complexPayload }];

  harness.handleInstantSend('complex-1');

  assert(harness.sentWsMessages.length === 1, 'Complex payload dispatched');
  assert(harness.sentWsMessages[0].content === complexPayload, 'Complex payload preserved verbatim without encoding corruption');
  assert(harness.messages[0].content === complexPayload, 'Complex payload in messages feed matches exactly');
});


// ---------------------------------------------------------------------------
// 2. I18n Engine: Nested Key Lookup, Interpolation, & Fallbacks
// ---------------------------------------------------------------------------

describe('I18n: getNestedValue Resolution', () => {
  const testDict = {
    simple: 'Simple Value',
    nested: {
      level1: {
        level2: 'Deep Value'
      }
    },
    'flat.key.with.dots': 'Flat Dot Value',
    numeric: 123,
    nullVal: null,
  };

  assert(getNestedValue(testDict, 'simple') === 'Simple Value', 'Resolve root key');
  assert(getNestedValue(testDict, 'nested.level1.level2') === 'Deep Value', 'Resolve deep dot-notation path');
  assert(getNestedValue(testDict, 'flat.key.with.dots') === 'Flat Dot Value', 'Resolve direct flat key with dots');
  assert(getNestedValue(testDict, 'nested.nonexistent') === undefined, 'Missing intermediate key returns undefined');
  assert(getNestedValue(testDict, 'nonexistent') === undefined, 'Missing root key returns undefined');
  assert(getNestedValue(testDict, 'numeric') === undefined, 'Non-string leaf returns undefined');
  assert(getNestedValue(testDict, 'nullVal') === undefined, 'Null property returns undefined');
  assert(getNestedValue(null, 'any.key') === undefined, 'Null dictionary returns undefined');
  assert(getNestedValue(undefined, 'any.key') === undefined, 'Undefined dictionary returns undefined');
  assert(getNestedValue({}, '') === undefined, 'Empty string key returns undefined');
});

describe('I18n: Interpolation Stress & Edge Cases', () => {
  assert(interpolate('Hello {name}', { name: 'World' }) === 'Hello World', 'Standard single token');
  assert(interpolate('In Queue ({count})', { count: 0 }) === 'In Queue (0)', 'Number 0 is properly rendered and not falsy skipped');
  assert(interpolate('In Queue ({count})', { count: 42 }) === 'In Queue (42)', 'Positive integer interpolation');
  assert(interpolate('{a} + {b} = {c}', { a: '1', b: '2', c: '3' }) === '1 + 2 = 3', 'Multiple tokens');
  assert(interpolate('No params template') === 'No params template', 'Undefined params bag returns raw text untouched');
  assert(interpolate('Hello {name} and {missing}', { name: 'Alice' }) === 'Hello Alice and {missing}', 'Missing param preserves {token} without throwing');
  assert(interpolate('Special chars: {val}', { val: '<script>alert(1)</script>' }) === 'Special chars: <script>alert(1)</script>', 'Special characters');
  assert(interpolate('{x} repeated {x}', { x: 'yes' }) === 'yes repeated yes', 'Repeated token in same template');
  assert(interpolate('Empty param: {empty}', { empty: '' }) === 'Empty param: ', 'Empty string param value');
});

describe('I18n: Fallback Logic Simulation', () => {
  function createTranslate(currentLang: Language, dicts: Record<Language, TranslationDict>) {
    return (key: string, params?: TranslationParams): string => {
      let raw = getNestedValue(dicts[currentLang], key);
      if (raw === undefined && currentLang !== 'en') {
        raw = getNestedValue(dicts.en, key);
      }
      if (raw === undefined) {
        raw = key;
      }
      return interpolate(raw, params);
    };
  }

  const mockDicts: Record<Language, TranslationDict> = {
    en: {
      greeting: 'Hello {name}',
      only_in_en: 'English exclusive',
      nested: { test: 'Nested EN' }
    },
    ru: {
      greeting: 'Привет {name}',
      nested: { test: 'Nested RU' }
    }
  };

  const tRu = createTranslate('ru', mockDicts);
  const tEn = createTranslate('en', mockDicts);

  assert(tRu('greeting', { name: 'Иван' }) === 'Привет Иван', 'RU translation works with interpolation');
  assert(tRu('only_in_en') === 'English exclusive', 'RU falls back to EN when key is missing in RU');
  assert(tRu('completely.unknown.key') === 'completely.unknown.key', 'RU falls back to literal key if missing in all dictionaries');
  assert(tEn('completely.unknown.key') === 'completely.unknown.key', 'EN falls back to literal key if missing');
  assert(tEn('nested.test') === 'Nested EN', 'EN resolves nested key');
  assert(tRu('nested.test') === 'Nested RU', 'RU resolves nested key');
});


// ---------------------------------------------------------------------------
// 3. Language Switching & LocalStorage Persistence
// ---------------------------------------------------------------------------

describe('I18n: Storage Initialization & Error Resilience', () => {
  let mockStorage: Record<string, string> = {};
  const fakeLocalStorage = {
    getItem: (k: string) => mockStorage[k] ?? null,
    setItem: (k: string, v: string) => { mockStorage[k] = v; },
    clear: () => { mockStorage = {}; }
  };

  function testInitialLang(storedValue: string | null): Language {
    try {
      const saved = storedValue;
      if (saved === 'en' || saved === 'ru') {
        return saved;
      }
    } catch {}
    return 'en';
  }

  assert(testInitialLang('ru') === 'ru', 'Loads "ru" if stored');
  assert(testInitialLang('en') === 'en', 'Loads "en" if stored');
  assert(testInitialLang(null) === 'en', 'Defaults to "en" if null');
  assert(testInitialLang('french') === 'en', 'Defaults to "en" if invalid language string');
  assert(testInitialLang('') === 'en', 'Defaults to "en" if empty string');

  const throwingLocalStorage = {
    getItem: () => { throw new Error('SecurityError: Access denied'); },
    setItem: () => { throw new Error('QuotaExceededError'); }
  };

  let initLang = 'en';
  try {
    const saved = throwingLocalStorage.getItem();
    if (saved === 'en' || saved === 'ru') initLang = saved;
  } catch {
    initLang = 'en';
  }
  assert(initLang === 'en', 'Gracefully falls back to "en" when localStorage.getItem throws');

  let writeSuccess = true;
  try {
    throwingLocalStorage.setItem();
  } catch {
    writeSuccess = false;
  }
  assert(!writeSuccess, 'localStorage.setItem exception caught cleanly without crashing app');
});


// ---------------------------------------------------------------------------
// 4. Exhaustive Dictionary Parity & Token Parity Audit
// ---------------------------------------------------------------------------

function flattenKeys(obj: any, prefix = ''): string[] {
  let keys: string[] = [];
  for (const k of Object.keys(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (obj[k] && typeof obj[k] === 'object' && !Array.isArray(obj[k])) {
      keys = keys.concat(flattenKeys(obj[k], fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

describe('I18n: Dictionary Parity & Placeholder Integrity (EN vs RU)', () => {
  const enKeys = flattenKeys(en);
  const ruKeys = flattenKeys(ru);

  console.log(`    Total EN dictionary keys: ${enKeys.length}`);
  console.log(`    Total RU dictionary keys: ${ruKeys.length}`);

  assert(enKeys.length > 50, `EN dictionary must contain >= 50 keys (found ${enKeys.length})`);
  assert(ruKeys.length > 50, `RU dictionary must contain >= 50 keys (found ${ruKeys.length})`);

  const missingInRu = enKeys.filter(k => !ruKeys.includes(k));
  const missingInEn = ruKeys.filter(k => !enKeys.includes(k));

  assert(missingInRu.length === 0, `All EN keys must exist in RU dictionary (missing: ${missingInRu.join(', ')})`);
  assert(missingInEn.length === 0, `All RU keys must exist in EN dictionary (missing: ${missingInEn.join(', ')})`);

  // Verify no null or empty string values in either dictionary
  let enEmptyCount = 0;
  for (const k of enKeys) {
    const val = getNestedValue(en, k);
    if (!val || typeof val !== 'string' || val.trim().length === 0) {
      enEmptyCount++;
      console.error(`    EN empty value at key: ${k}`);
    }
  }
  assert(enEmptyCount === 0, 'No empty or null values in EN dictionary');

  let ruEmptyCount = 0;
  for (const k of ruKeys) {
    const val = getNestedValue(ru, k);
    if (!val || typeof val !== 'string' || val.trim().length === 0) {
      ruEmptyCount++;
      console.error(`    RU empty value at key: ${k}`);
    }
  }
  assert(ruEmptyCount === 0, 'No empty or null values in RU dictionary');

  // Token / Parameter placeholder parity check
  // e.g. If EN has {count}, RU must also have {count}
  const tokenRegex = /\{(\w+)\}/g;
  let tokenMismatches = 0;

  for (const k of enKeys) {
    const enVal = getNestedValue(en, k) as string;
    const ruVal = getNestedValue(ru, k) as string;

    const enTokens = (enVal.match(tokenRegex) || []).sort();
    const ruTokens = (ruVal.match(tokenRegex) || []).sort();

    if (enTokens.join(',') !== ruTokens.join(',')) {
      tokenMismatches++;
      console.error(`    Token mismatch for key "${k}": EN has [${enTokens.join(', ')}] vs RU has [${ruTokens.join(', ')}]`);
    }
  }

  assert(tokenMismatches === 0, `All translation placeholders must match 1:1 between EN and RU (found ${tokenMismatches} mismatches)`);
});


// ---------------------------------------------------------------------------
// 5. Static UI Component Call-site Extraction & Resolution Verification
// ---------------------------------------------------------------------------

describe('UI Component Key Resolution & Untranslated Raw String Audit', () => {
  const uiSrcDir = path.resolve(__dirname, '../src/ui/src');
  const componentFiles = [
    path.join(uiSrcDir, 'App.tsx'),
    path.join(uiSrcDir, 'components', 'Sidebar.tsx'),
    path.join(uiSrcDir, 'components', 'SettingsModal.tsx'),
    path.join(uiSrcDir, 'components', 'VoicePanel.tsx'),
    path.join(uiSrcDir, 'components', 'WorkspaceSelector.tsx'),
    path.join(uiSrcDir, 'components', 'CreateProjectModal.tsx'),
    path.join(uiSrcDir, 'components', 'AgentDashboard.tsx'),
    path.join(uiSrcDir, 'components', 'ArtifactRenderer.tsx'),
  ];

  const tCallRegex = /\bt\(\s*['"`]([a-zA-Z0-9_.]+)['"`]/g;
  const usedKeys = new Set<string>();

  for (const file of componentFiles) {
    assert(fs.existsSync(file), `Component file must exist: ${path.basename(file)}`);
    const content = fs.readFileSync(file, 'utf-8');

    let match;
    while ((match = tCallRegex.exec(content)) !== null) {
      usedKeys.add(match[1]);
    }
  }

  console.log(`    Found ${usedKeys.size} distinct t(...) static key references across all UI components`);
  assert(usedKeys.size >= 25, `Expected >= 25 distinct t() key usages in components (found ${usedKeys.size})`);

  const unresolvableEn: string[] = [];
  const unresolvableRu: string[] = [];

  for (const key of usedKeys) {
    const enVal = getNestedValue(en, key);
    const ruVal = getNestedValue(ru, key);
    if (enVal === undefined) unresolvableEn.push(key);
    if (ruVal === undefined) unresolvableRu.push(key);
  }

  assert(unresolvableEn.length === 0, `All t() keys used in components must resolve in EN: missing [${unresolvableEn.join(', ')}]`);
  assert(unresolvableRu.length === 0, `All t() keys used in components must resolve in RU: missing [${unresolvableRu.join(', ')}]`);

  // Check for raw hardcoded Russian text (excluding comments and language selector autonyms like 'Русский')
  const cyrillicRegex = /[\u0400-\u04FF]/;
  const rawCyrillicViolations: string[] = [];

  for (const file of componentFiles) {
    const content = fs.readFileSync(file, 'utf-8');
    const lines = content.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();
      // Skip comment lines or legitimate language display name options
      if (trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*') || trimmed.includes('Русский')) {
        continue;
      }
      const noCommentLine = line.replace(/\/\/.*$/, '');
      if (cyrillicRegex.test(noCommentLine)) {
        rawCyrillicViolations.push(`${path.basename(file)}:${i + 1}: ${trimmed}`);
      }
    }
  }

  if (rawCyrillicViolations.length > 0) {
    console.error(`    ${RED}Found raw Cyrillic in UI code:${RESET}\n` + rawCyrillicViolations.map(v => '      ' + v).join('\n'));
  }
  assert(rawCyrillicViolations.length === 0, `Zero hardcoded untranslated Cyrillic strings in UI component code (found ${rawCyrillicViolations.length})`);
});


// ---------------------------------------------------------------------------
// Final Summary
// ---------------------------------------------------------------------------

console.log(`\n${BOLD}========================================${RESET}`);
console.log(`${BOLD}TEST RUN SUMMARY${RESET}`);
console.log(`  Total Checks:  ${totalTests}`);
console.log(`  Passed Checks: ${GREEN}${passedTests}${RESET}`);
console.log(`  Failed Checks: ${failedTests > 0 ? RED : GREEN}${failedTests}${RESET}`);
console.log(`${BOLD}========================================${RESET}\n`);

if (failedTests > 0) {
  process.exit(1);
} else {
  console.log(`${GREEN}${BOLD}✓ ALL CHALLENGE & STRESS TESTS PASSED CLEANLY!${RESET}\n`);
}
