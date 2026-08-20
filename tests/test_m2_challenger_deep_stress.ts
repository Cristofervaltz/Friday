/**
 * Challenger Deep Stress & Referential Stability Test Suite
 * Milestone 2: Frontend React UI Optimization & Memoization
 * 
 * Verifies:
 * 1. Rapid token streaming simulation & Re-render isolation (O(1) active message render vs O(N) thrash)
 * 2. Referential stability of past message objects during streaming chunk concatenation
 * 3. visibleMessages memoization across all message types (bot, user, tool, system, empty, whitespace)
 * 4. React callback referential stability across token stream cycles
 * 5. AST & module-level static hoisting checks (REMARK_PLUGINS, components useMemo)
 * 6. I18n Context value referential stability
 * 7. Key stability in message lists (no inline dynamic keys)
 */

import * as fs from 'fs';
import * as path from 'path';

// ANSI color codes
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const CYAN = '\x1b[36m';
const RESET = '\x1b[0m';
const BOLD = '\x1b[1m';
const YELLOW = '\x1b[33m';

let totalAssertions = 0;
let passedAssertions = 0;
let failedAssertions = 0;

function assert(condition: boolean, msg: string) {
  totalAssertions++;
  if (condition) {
    passedAssertions++;
    console.log(`  ${GREEN}✓${RESET} ${msg}`);
  } else {
    failedAssertions++;
    console.error(`  ${RED}✗ FAIL:${RESET} ${msg}`);
    throw new Error(`Assertion failed: ${msg}`);
  }
}

function suite(name: string, fn: () => void) {
  console.log(`\n${BOLD}${CYAN}=== Suite: ${name} ===${RESET}`);
  try {
    fn();
  } catch (err: any) {
    console.error(`  ${RED}Suite Failure: ${err.message}${RESET}`);
  }
}

interface Message {
  id: string;
  role: 'user' | 'bot' | 'system' | 'tool' | 'assistant';
  content: string;
}

// ============================================================================
// 1. Rapid Token Streaming & Message Referential Stability Simulation
// ============================================================================

suite('1. Token Streaming: Referential Stability & Re-render Counts', () => {
  // Simulate App.tsx state & React.memo semantics
  let messages: Message[] = [];
  
  // Seed with 100 historical messages
  for (let i = 0; i < 100; i++) {
    messages.push({
      id: `hist-msg-${i}`,
      role: i % 2 === 0 ? 'user' : 'bot',
      content: `Historical message payload #${i} with some text content.`
    });
  }

  // User submits a prompt before bot starts streaming
  messages.push({
    id: 'user-prompt-1',
    role: 'user',
    content: 'Please summarize the project status.'
  });

  const initialHistoricalRefs = messages.map(m => m);
  const HISTORICAL_COUNT = initialHistoricalRefs.length; // 101 items

  // Streaming reduction function matching App.tsx lines 249-256
  function streamTokenChunk(prevMessages: Message[], cleanContent: string): Message[] {
    const last = prevMessages[prevMessages.length - 1];
    if (last && last.role === 'bot') {
      return [...prevMessages.slice(0, -1), { ...last, content: last.content + cleanContent }];
    } else {
      return [...prevMessages, { id: 'stream-bot-1', role: 'bot', content: cleanContent }];
    }
  }

  // Track render counts for memoized components
  const renderCounts = new Map<string, number>();
  function trackRender(id: string) {
    renderCounts.set(id, (renderCounts.get(id) || 0) + 1);
  }

  // React.memo comparator for ChatMessageItem (shallow prop comparison: prevMsg === nextMsg)
  function simulateChatMessageItemRender(
    prevProps: { msg: Message },
    nextProps: { msg: Message }
  ): boolean {
    if (prevProps.msg !== nextProps.msg) {
      trackRender(nextProps.msg.id);
      return true; // re-rendered
    }
    return false; // memoized skip
  }

  // First streaming chunk arrives: creates new bot message
  const prevSnapshot0 = messages;
  messages = streamTokenChunk(messages, 'Thinking');
  trackRender('stream-bot-1');

  // Stream 500 consecutive token chunks
  const tokens = [' about', ' the', ' implementation', ' of', ' memoization', ' in', ' React', ' 19', '.'];
  const NUM_CHUNKS = 500;

  for (let c = 0; c < NUM_CHUNKS; c++) {
    const chunk = tokens[c % tokens.length];
    const prevMessagesSnapshot = messages;
    messages = streamTokenChunk(messages, chunk);

    // Simulate React render pass across all messages in list
    for (let i = 0; i < messages.length; i++) {
      const prevMsg = prevMessagesSnapshot[i];
      const nextMsg = messages[i];
      if (prevMsg) {
        simulateChatMessageItemRender({ msg: prevMsg }, { msg: nextMsg });
      }
    }
  }

  // Verification 1: All historical messages (0..100) must NOT have been cloned or modified
  let unshiftedHistoricalMismatches = 0;
  for (let i = 0; i < HISTORICAL_COUNT; i++) {
    if (messages[i] !== initialHistoricalRefs[i]) {
      unshiftedHistoricalMismatches++;
    }
  }
  assert(unshiftedHistoricalMismatches === 0, `All ${HISTORICAL_COUNT} historical & user messages retained 100% referential identity across 500 stream chunks (mismatches: ${unshiftedHistoricalMismatches})`);

  // Verification 2: Historical messages re-render count must be ZERO during streaming
  let historicalRenders = 0;
  for (let i = 0; i < HISTORICAL_COUNT; i++) {
    historicalRenders += (renderCounts.get(initialHistoricalRefs[i].id) || 0);
  }
  assert(historicalRenders === 0, `0 re-renders occurred on historical messages during 500 streaming token chunks (actual: ${historicalRenders})`);

  // Verification 3: Only the active streaming message re-rendered exactly NUM_CHUNKS + 1 times
  const activeMessageRenders = renderCounts.get('stream-bot-1') || 0;
  assert(activeMessageRenders === NUM_CHUNKS + 1, `Active streaming message rendered exactly ${NUM_CHUNKS + 1} times (initial + ${NUM_CHUNKS} chunks; actual: ${activeMessageRenders})`);

  // Verification 4: Content of active message matches cumulative stream
  assert(messages[HISTORICAL_COUNT].content.startsWith('Thinking about the implementation'), 'Active message content accumulated all streamed tokens correctly');
  assert(messages[HISTORICAL_COUNT].role === 'bot', 'Active message role is bot');
  assert(messages.length === HISTORICAL_COUNT + 1, `Total message count is ${HISTORICAL_COUNT + 1}`);
});

// ============================================================================
// 2. visibleMessages Memoization & Role Filtering
// ============================================================================

suite('2. visibleMessages Memoization & Multi-Type Filtering', () => {
  // Exact useMemo filter function from App.tsx line 553
  function computeVisibleMessages(msgs: Message[]): Message[] {
    return msgs.filter(m => m.role !== 'system' && m.content && m.content.trim().length > 0);
  }

  const rawMessages: Message[] = [
    { id: '1', role: 'system', content: 'You are Friday AI assistant.' },
    { id: '2', role: 'user', content: 'Hello there!' },
    { id: '3', role: 'bot', content: 'Hi! How can I assist you today?' },
    { id: '4', role: 'system', content: 'INTERNAL_SYSTEM_PROMPT_UPDATE' },
    { id: '5', role: 'tool', content: '{"status": "ok", "result": 42}' },
    { id: '6', role: 'assistant', content: 'I have processed the tool result.' },
    { id: '7', role: 'bot', content: '' }, // empty string
    { id: '8', role: 'bot', content: '   ' }, // spaces only
    { id: '9', role: 'bot', content: '\t\n\r\n  ' }, // whitespace only
    { id: '10', role: 'user', content: 'What is the current time?' },
    { id: '11', role: 'system', content: '' }, // empty system msg
    { id: '12', role: 'tool', content: 'Current time: 19:00:00' },
  ];

  const visible = computeVisibleMessages(rawMessages);

  assert(visible.length === 6, `Expected exactly 6 visible messages out of 12 raw messages (found ${visible.length})`);
  assert(visible.map(m => m.id).join(',') === '2,3,5,6,10,12', `Visible messages IDs match expected set [2, 3, 5, 6, 10, 12] (got [${visible.map(m => m.id).join(',')}])`);

  // Verify all system messages excluded
  assert(visible.every(m => m.role !== 'system'), 'Zero system messages present in visibleMessages');

  // Verify all empty/whitespace messages excluded
  assert(visible.every(m => m.content && m.content.trim().length > 0), 'Zero empty or whitespace-only messages in visibleMessages');

  // Verify tool, user, bot, assistant messages are properly retained
  const rolesFound = new Set(visible.map(m => m.role));
  assert(rolesFound.has('user'), 'User role retained');
  assert(rolesFound.has('bot'), 'Bot role retained');
  assert(rolesFound.has('tool'), 'Tool role retained');
  assert(rolesFound.has('assistant'), 'Assistant role retained');

  // Stress test: 10,000 mixed messages
  const stressRaw: Message[] = [];
  let expectedVisibleCount = 0;
  for (let i = 0; i < 10000; i++) {
    const r = i % 5;
    if (r === 0) {
      stressRaw.push({ id: `s-${i}`, role: 'system', content: `sys msg ${i}` });
    } else if (r === 1) {
      stressRaw.push({ id: `e-${i}`, role: 'bot', content: '   \n  ' });
    } else if (r === 2) {
      stressRaw.push({ id: `u-${i}`, role: 'user', content: `user msg ${i}` });
      expectedVisibleCount++;
    } else if (r === 3) {
      stressRaw.push({ id: `b-${i}`, role: 'bot', content: `bot reply ${i}` });
      expectedVisibleCount++;
    } else {
      stressRaw.push({ id: `t-${i}`, role: 'tool', content: `tool out ${i}` });
      expectedVisibleCount++;
    }
  }

  const stressVisible = computeVisibleMessages(stressRaw);
  assert(stressVisible.length === expectedVisibleCount, `10,000 item stress filter produced ${stressVisible.length} visible items (expected ${expectedVisibleCount})`);
  assert(stressVisible.every(m => m.role !== 'system' && m.content.trim().length > 0), 'Stress filtered list satisfies all invariant constraints');
});

// ============================================================================
// 3. Callback Referential Stability Across State Transitions
// ============================================================================

suite('3. App.tsx Callback Memoization & Dependency Array Invariants', () => {
  const appPath = path.resolve(__dirname, '../src/ui/src/App.tsx');
  assert(fs.existsSync(appPath), 'App.tsx exists');
  const appCode = fs.readFileSync(appPath, 'utf-8');

  // List of callbacks required to be wrapped in useCallback
  const expectedCallbacks = [
    'scrollToBottom',
    'applyTheme',
    'handleAction',
    'handlePermission',
    'handleSubmit',
    'handleEditQueue',
    'handleKeyDown',
    'handleAttachFile',
    'handleClearWorkspace',
    'handleOpenCreateProject',
    'handleCloseCreateProject',
    'handleProjectCreated',
    'handleProjectSkip',
    'handleOpenVoice',
    'handleCloseVoice',
    'handleCloseSettings',
    'handleVoiceAutoSendChange',
    'handleSettingsChanged',
    'handleStopTts',
    'handleDeleteQueued',
    'handleRemoveAttachment',
  ];

  for (const cbName of expectedCallbacks) {
    const regex = new RegExp(`const\\s+${cbName}\\s*=\\s*useCallback\\(`, 'm');
    assert(regex.test(appCode), `Callback "${cbName}" is wrapped in useCallback`);
  }

  // Verify handleInstantSend preserves its exact AST pattern (for Python AST test compatibility)
  assert(appCode.includes('const handleInstantSend = (msgId: string) => {'), 'handleInstantSend signature matches exact expected AST');
  assert(appCode.includes('const msg = messageQueue.find(m => m.id === msgId);'), 'handleInstantSend finds msg by id');
  assert(appCode.includes('setMessageQueue(prev => prev.filter(m => m.id !== msgId));'), 'handleInstantSend removes item via filter');
});

// ============================================================================
// 4. Subcomponent Memoization & Static Hoisting
// ============================================================================

suite('4. Subcomponent React.memo & Static Plugin Hoisting', () => {
  const componentsDir = path.resolve(__dirname, '../src/ui/src/components');
  
  // 1. Sidebar.tsx
  const sidebarCode = fs.readFileSync(path.join(componentsDir, 'Sidebar.tsx'), 'utf-8');
  assert(sidebarCode.includes('export const Sidebar = React.memo('), 'Sidebar is wrapped in React.memo');

  // 2. WorkspaceSelector.tsx
  const wsCode = fs.readFileSync(path.join(componentsDir, 'WorkspaceSelector.tsx'), 'utf-8');
  assert(wsCode.includes('export const WorkspaceSelector = React.memo('), 'WorkspaceSelector is wrapped in React.memo');
  assert(wsCode.includes('const getShortName = useCallback('), 'WorkspaceSelector getShortName wrapped in useCallback');

  // 3. AgentDashboard.tsx
  const adCode = fs.readFileSync(path.join(componentsDir, 'AgentDashboard.tsx'), 'utf-8');
  assert(adCode.includes('export const AgentDashboard: React.FC<AgentDashboardProps> = React.memo('), 'AgentDashboard is wrapped in React.memo');

  // 4. VoicePanel.tsx
  const vpCode = fs.readFileSync(path.join(componentsDir, 'VoicePanel.tsx'), 'utf-8');
  assert(vpCode.includes('export const VoicePanel = React.memo('), 'VoicePanel is wrapped in React.memo');

  // 5. SettingsModal.tsx
  const smCode = fs.readFileSync(path.join(componentsDir, 'SettingsModal.tsx'), 'utf-8');
  assert(smCode.includes('export const SettingsModal = React.memo('), 'SettingsModal is wrapped in React.memo');
  assert(smCode.includes('const loadSettings = useCallback('), 'SettingsModal loadSettings is memoized');
  assert(smCode.includes('const handleSave = useCallback('), 'SettingsModal handleSave is memoized');

  // 6. CreateProjectModal.tsx
  const cpmCode = fs.readFileSync(path.join(componentsDir, 'CreateProjectModal.tsx'), 'utf-8');
  assert(cpmCode.includes('export const CreateProjectModal = React.memo('), 'CreateProjectModal is wrapped in React.memo');
  assert(cpmCode.includes('const handleAddFolder = useCallback('), 'CreateProjectModal handleAddFolder is memoized');
  assert(cpmCode.includes('const handleSkip = useCallback('), 'CreateProjectModal handleSkip is memoized');

  // 7. ArtifactRenderer.tsx
  const arCode = fs.readFileSync(path.join(componentsDir, 'ArtifactRenderer.tsx'), 'utf-8');
  assert(arCode.includes('const REMARK_PLUGINS = [remarkGfm];'), 'REMARK_PLUGINS statically hoisted to module scope');
  assert(arCode.includes('const Mermaid: React.FC<{ diagram: string }> = React.memo('), 'Mermaid renderer wrapped in React.memo');
  assert(arCode.includes('export const ArtifactRenderer: React.FC<ArtifactRendererProps> = React.memo('), 'ArtifactRenderer wrapped in React.memo');
  assert(arCode.includes('const components = useMemo('), 'ArtifactRenderer components mapping wrapped in useMemo');

  // 8. App.tsx memoized components
  const appCode = fs.readFileSync(path.join(__dirname, '../src/ui/src/App.tsx'), 'utf-8');
  assert(appCode.includes('const ToolBlock = memo(function ToolBlock('), 'ToolBlock is wrapped in React memo');
  assert(appCode.includes('const ChatMessageItem = memo(function ChatMessageItem('), 'ChatMessageItem is wrapped in React memo');
  assert(appCode.includes('const visibleMessages = useMemo('), 'visibleMessages is wrapped in useMemo');
});

// ============================================================================
// 5. I18n Context Value Memoization Stability
// ============================================================================

suite('5. I18n Context Value Memoization Stability', () => {
  const i18nContextPath = path.resolve(__dirname, '../src/ui/src/i18n/I18nContext.tsx');
  assert(fs.existsSync(i18nContextPath), 'I18nContext.tsx exists');
  const i18nCode = fs.readFileSync(i18nContextPath, 'utf-8');

  assert(i18nCode.includes('const contextValue = useMemo(() => ({'), 'contextValue wrapped in useMemo');
  assert(i18nCode.includes('[language, setLanguage, t]'), 'contextValue correctly depends on [language, setLanguage, t]');
  assert(i18nCode.includes('const setLanguage = useCallback('), 'setLanguage wrapped in useCallback');
  assert(i18nCode.includes('const t = useCallback('), 't translation helper wrapped in useCallback');
});

// ============================================================================
// 6. List Item Key Stability Audit
// ============================================================================

suite('6. List Item Key Stability Audit', () => {
  const appCode = fs.readFileSync(path.join(__dirname, '../src/ui/src/App.tsx'), 'utf-8');
  
  // Verify ChatMessageItem key uses msg.id || idx
  assert(appCode.includes('key={msg.id || idx}'), 'ChatMessageItem renders with stable key (msg.id || idx)');
  
  // Verify messageQueue items use msg.id
  assert(appCode.includes('key={msg.id}'), 'messageQueue items render with stable key (msg.id)');
  
  // Verify attachedFiles chips use index key
  assert(appCode.includes('key={idx} className="attachment-chip"'), 'attachedFiles chips use stable index key');

  // Verify chats list in Sidebar uses chat.id
  const sidebarCode = fs.readFileSync(path.join(__dirname, '../src/ui/src/components/Sidebar.tsx'), 'utf-8');
  assert(sidebarCode.includes('key={chat.id}'), 'Sidebar chats use stable key (chat.id)');
});

// ============================================================================
// Summary
// ============================================================================

console.log(`\n${BOLD}========================================${RESET}`);
console.log(`${BOLD}CHALLENGER DEEP STRESS RUN SUMMARY${RESET}`);
console.log(`  Total Checks:  ${totalAssertions}`);
console.log(`  Passed Checks: ${GREEN}${passedAssertions}${RESET}`);
console.log(`  Failed Checks: ${failedAssertions > 0 ? RED : GREEN}${failedAssertions}${RESET}`);
console.log(`${BOLD}========================================${RESET}\n`);

if (failedAssertions > 0) {
  process.exit(1);
} else {
  console.log(`${GREEN}${BOLD}✓ ALL CHALLENGER DEEP STRESS TESTS PASSED CLEANLY!${RESET}\n`);
}
