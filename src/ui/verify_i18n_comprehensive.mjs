import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { en, ru } from './src/i18n/translations.ts';
import { getNestedValue, interpolate } from './src/i18n/utils.ts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let totalChecks = 0;
let passedChecks = 0;
let failures = [];

function assert(condition, message) {
  totalChecks++;
  if (condition) {
    passedChecks++;
    console.log(`  [PASS] ${message}`);
  } else {
    failures.push(message);
    console.error(`  [FAIL] ${message}`);
  }
}

console.log('====================================================');
console.log('=== EMPIRICAL CHALLENGE 2: i18n & String Parity ===');
console.log('====================================================\n');

// ----------------------------------------------------
// 1. DICTIONARY SYMMETRY & LEAF NODE ANALYSIS
// ----------------------------------------------------
console.log('--- TEST SUITE 1: Dictionary Symmetry & Parity ---');

function extractAllPaths(obj, prefix = '') {
  let paths = {};
  for (const [k, v] of Object.entries(obj)) {
    const currentPath = prefix ? `${prefix}.${k}` : k;
    if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
      Object.assign(paths, extractAllPaths(v, currentPath));
    } else {
      paths[currentPath] = v;
    }
  }
  return paths;
}

const enPaths = extractAllPaths(en);
const ruPaths = extractAllPaths(ru);

console.log(`Total EN leaf paths: ${Object.keys(enPaths).length}`);
console.log(`Total RU leaf paths: ${Object.keys(ruPaths).length}`);

assert(Object.keys(enPaths).length > 0, 'EN dictionary is non-empty');
assert(Object.keys(ruPaths).length > 0, 'RU dictionary is non-empty');
assert(Object.keys(enPaths).length === Object.keys(ruPaths).length, `EN and RU key count parity: ${Object.keys(enPaths).length} vs ${Object.keys(ruPaths).length}`);

// Check all EN keys exist in RU
for (const key of Object.keys(enPaths)) {
  assert(key in ruPaths, `Key '${key}' in EN exists in RU`);
}

// Check all RU keys exist in EN
for (const key of Object.keys(ruPaths)) {
  assert(key in enPaths, `Key '${key}' in RU exists in EN`);
}

// Check non-empty strings
for (const [key, val] of Object.entries(enPaths)) {
  assert(typeof val === 'string' && val.trim().length > 0, `EN key '${key}' has valid non-empty string`);
}
for (const [key, val] of Object.entries(ruPaths)) {
  assert(typeof val === 'string' && val.trim().length > 0, `RU key '${key}' has valid non-empty string`);
}

// ----------------------------------------------------
// 2. PLACEHOLDER TOKEN PARITY
// ----------------------------------------------------
console.log('\n--- TEST SUITE 2: Placeholder Token Symmetry ---');

function getTokens(str) {
  const matches = str.match(/\{(\w+)\}/g) || [];
  return matches.map(m => m.replace(/[{}]/g, '')).sort();
}

for (const key of Object.keys(enPaths)) {
  const enVal = enPaths[key];
  const ruVal = ruPaths[key];
  if (typeof enVal === 'string' && typeof ruVal === 'string') {
    const enTokens = getTokens(enVal);
    const ruTokens = getTokens(ruVal);
    assert(
      JSON.stringify(enTokens) === JSON.stringify(ruTokens),
      `Token symmetry for '${key}': EN=${JSON.stringify(enTokens)}, RU=${JSON.stringify(ruTokens)}`
    );
  }
}

// ----------------------------------------------------
// 3. CODEBASE AST & t(...) EXTRACTION SCAN
// ----------------------------------------------------
console.log('\n--- TEST SUITE 3: Codebase t(...) Key Resolution ---');

const srcDir = path.join(__dirname, 'src');

function getFilesRecursively(dir, filterExt = ['.tsx', '.ts']) {
  let results = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      results = results.concat(getFilesRecursively(fullPath, filterExt));
    } else if (filterExt.includes(path.extname(fullPath))) {
      results.push(fullPath);
    }
  }
  return results;
}

const tsxFiles = getFilesRecursively(srcDir, ['.tsx']);
console.log(`Found ${tsxFiles.length} TSX component files to scan:`);
tsxFiles.forEach(f => console.log(`  - ${path.relative(__dirname, f)}`));

// Match literal string calls: t('foo.bar') or t("foo.bar")
const tStaticKeyRegex = /\bt\(\s*['"]([a-zA-Z0-9_.]+)['"]/g;
let foundStaticKeys = new Set();

for (const file of tsxFiles) {
  const content = fs.readFileSync(file, 'utf-8');
  let match;
  while ((match = tStaticKeyRegex.exec(content)) !== null) {
    const key = match[1];
    foundStaticKeys.add(key);
  }
}

console.log(`\nFound ${foundStaticKeys.size} distinct static t('...') keys used in TSX files.`);

for (const key of foundStaticKeys) {
  const enVal = getNestedValue(en, key);
  const ruVal = getNestedValue(ru, key);
  assert(enVal !== undefined, `TSX static key '${key}' resolves in EN dictionary (got: "${enVal}")`);
  assert(ruVal !== undefined, `TSX static key '${key}' resolves in RU dictionary (got: "${ruVal}")`);
}

// Dynamic keys check:
// In SettingsModal.tsx: `settings.tab_title` with `{ tab: t(\`settings.tab_${activeTab}\`) }`
console.log('\n--- Checking dynamic key resolutions ---');
const tabs = ['appearance', 'agent', 'security', 'app'];
for (const tab of tabs) {
  const tabKey = `settings.tab_${tab}`;
  assert(getNestedValue(en, tabKey) !== undefined, `Dynamic tab key '${tabKey}' resolves in EN`);
  assert(getNestedValue(ru, tabKey) !== undefined, `Dynamic tab key '${tabKey}' resolves in RU`);
  
  const enTabTitle = interpolate(getNestedValue(en, 'settings.tab_title'), { tab: getNestedValue(en, tabKey) });
  const ruTabTitle = interpolate(getNestedValue(ru, 'settings.tab_title'), { tab: getNestedValue(ru, tabKey) });
  
  assert(enTabTitle.includes(getNestedValue(en, tabKey)), `EN tab title formatted correctly: "${enTabTitle}"`);
  assert(ruTabTitle.includes(getNestedValue(ru, tabKey)), `RU tab title formatted correctly: "${ruTabTitle}"`);
}

// ----------------------------------------------------
// 4. HARDCODED STRING & CYRILLIC AUDIT
// ----------------------------------------------------
console.log('\n--- TEST SUITE 4: Hardcoded Text and Cyrillic Audit ---');

const cyrillicRegex = /[\u0400-\u04FF]/;

for (const file of tsxFiles) {
  const relPath = path.relative(__dirname, file);
  const lines = fs.readFileSync(file, 'utf-8').split('\n');
  
  lines.forEach((line, idx) => {
    // Skip comments
    const trimmed = line.trim();
    if (trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*')) return;
    
    // Check Cyrillic in code (excluding the language selector label itself if intentional)
    if (cyrillicRegex.test(line)) {
      const isLanguageDropdownOption = line.includes('Русский') || line.includes('ru-RU');
      if (isLanguageDropdownOption) {
        console.log(`  [INFO] Expected Cyrillic option label at ${relPath}:${idx + 1}: ${trimmed}`);
      } else {
        assert(false, `Unexpected raw Cyrillic string in ${relPath}:${idx + 1}: ${trimmed}`);
      }
    }
  });
}

// ----------------------------------------------------
// 5. ENGINE BEHAVIORAL & STRESS TESTS
// ----------------------------------------------------
console.log('\n--- TEST SUITE 5: i18n Engine Behavioral Stress Tests ---');

// Interpolation tests
assert(interpolate('Hello {name}!', { name: 'Friday' }) === 'Hello Friday!', 'Simple interpolation');
assert(interpolate('Queue ({count})', { count: 5 }) === 'Queue (5)', 'Numeric interpolation');
assert(interpolate('Queue ({count})', { count: 0 }) === 'Queue (0)', 'Zero numeric interpolation');
assert(interpolate('No params here') === 'No params here', 'No params handling');
assert(interpolate('Missing {var}', {}) === 'Missing {var}', 'Missing param preserves placeholder');
assert(interpolate('{a} and {b}', { a: '1', b: '2' }) === '1 and 2', 'Multiple tokens');

// Nested lookup tests
assert(getNestedValue(en, 'settings.tabs.appearance') === 'Appearance', 'Deep nested lookup');
assert(getNestedValue(en, 'settings.tab_appearance') === 'Appearance', 'Flat nested lookup');
assert(getNestedValue(en, 'non.existent.key') === undefined, 'Non-existent key returns undefined');
assert(getNestedValue(null, 'any.key') === undefined, 'Null object returns undefined');
assert(getNestedValue(undefined, 'any.key') === undefined, 'Undefined object returns undefined');
assert(getNestedValue(en, '') === undefined, 'Empty key returns undefined');
assert(getNestedValue({ a: { b: 123 } }, 'a.b') === undefined, 'Non-string leaf returns undefined');

// Multi-language switching simulation
function simulateT(dict, key, params) {
  const raw = getNestedValue(dict, key) || getNestedValue(en, key) || key;
  return interpolate(raw, params);
}

assert(simulateT(en, 'chat.empty_connected') === 'How can I help you today?', 'Simulate T: EN chat.empty_connected');
assert(simulateT(ru, 'chat.empty_connected') === 'Чем я могу помочь вам сегодня?', 'Simulate T: RU chat.empty_connected');
assert(simulateT(ru, 'chat.queue_header', { count: 3 }) === 'В очереди (3)', 'Simulate T: RU chat.queue_header with count 3');
assert(simulateT(en, 'chat.queue_header', { count: 3 }) === 'In Queue (3)', 'Simulate T: EN chat.queue_header with count 3');
assert(simulateT(ru, 'nonexistent.key') === 'nonexistent.key', 'Simulate T: Missing key fallback to literal');

console.log('\n====================================================');
console.log(`TOTAL CHECKS: ${totalChecks}`);
console.log(`PASSED: ${passedChecks}`);
console.log(`FAILED: ${failures.length}`);
console.log('====================================================');

if (failures.length > 0) {
  console.error('\nFAILURE SUMMARY:');
  failures.forEach((f, i) => console.error(`${i + 1}. ${f}`));
  process.exit(1);
} else {
  console.log('\nALL EMPIRICAL TESTS PASSED PERFECTLY!');
  process.exit(0);
}
